from __future__ import annotations

from itertools import combinations

from .base import *  # noqa: F403

@router.post("/api/fpl/team/{entry_id}/import")
def import_user_team(entry_id: int, gameweek: Optional[int] = Query(default=None, ge=1, le=38)):
    db = SessionLocal()
    try:
        gw = _resolve_gameweek(db, gameweek)
        current_gw = _int(_get_meta(db, "current_gw"), 0)
        # If next GW picks aren't published yet, gracefully fall back.
        payload, resolved_gw = _fetch_entry_picks_with_fallback(entry_id, gw, [current_gw, gw - 1])
        gw = resolved_gw
        picks = payload.get("picks", [])
        hist = payload.get("entry_history", {})

        db.query(UserSquadPick).filter(UserSquadPick.entry_id == entry_id, UserSquadPick.event == gw).delete()

        for p in picks:
            row = UserSquadPick(
                entry_id=entry_id,
                event=gw,
                player_id=_int(p.get("element")),
                list_position=_int(p.get("position")),
                multiplier=_int(p.get("multiplier"), 1),
                is_captain=bool(p.get("is_captain", False)),
                is_vice_captain=bool(p.get("is_vice_captain", False)),
                purchase_price=_int(p.get("purchase_price"), 0),
                selling_price=_int(p.get("selling_price"), 0),
            )
            db.add(row)

        _set_meta(db, f"entry:{entry_id}:last_import", datetime.now(timezone.utc).isoformat())
        db.commit()

        # Persist optional team snapshot metadata for rival context.
        _set_meta(db, f"entry:{entry_id}:player_name", str(payload.get("player_name") or ""))
        _set_meta(db, f"entry:{entry_id}:entry_name", str(payload.get("name") or ""))

        return {
            "ok": True,
            "entry_id": entry_id,
            "gameweek": gw,
            "picks_imported": len(picks),
            "bank": _float(hist.get("bank"), 0.0) / 10.0,
            "value": _float(hist.get("value"), 0.0) / 10.0,
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error while importing team: {e}")
    finally:
        db.close()

@router.get("/api/fpl/team/{entry_id}/recommendation", response_model=TeamRecommendation)
def team_recommendation(
    entry_id: int,
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No player data found. Run POST /api/fpl/ingest/bootstrap first.")

        gw = _resolve_gameweek(db, gameweek)
        current_gw = _int(_get_meta(db, "current_gw"), 0)
        payload, resolved_gw = _fetch_entry_picks_with_fallback(entry_id, gw, [current_gw, gw - 1])
        gw = resolved_gw
        picks = payload.get("picks", [])
        hist = payload.get("entry_history", {})

        horizon_weights, transfer_threshold = _strategy_config(mode)

        squad_ids = [_int(p.get("element")) for p in picks]
        if len(squad_ids) < 11:
            raise HTTPException(status_code=400, detail="FPL returned incomplete squad data")

        player_by_id = {p.id: p for p in players}
        fixtures = db.query(Fixture).all()

        squad_scored: List[Tuple[float, Player]] = []
        for pid in squad_ids:
            player = player_by_id.get(pid)
            if player is None:
                continue
            xpts = _expected_points(player, fixtures, gw)
            squad_scored.append((xpts, player))

        if len(squad_scored) < 11:
            raise HTTPException(status_code=400, detail="Your squad has players missing from local DB. Re-run bootstrap ingest.")

        starting_pairs, bench_pairs, formation = _build_lineup_from_squad(squad_scored)

        ordered_starting_pairs = sorted(starting_pairs, key=lambda x: x[0], reverse=True)
        starting_xi = []
        for xpts, p in ordered_starting_pairs:
            fc, fb = _fixture_badge_for_gw(p, fixtures, gw)
            starting_xi.append(_pick_to_response(p, xpts, fixture_count=fc, fixture_badge=fb))

        bench = []
        for xpts, p in bench_pairs:
            fc, fb = _fixture_badge_for_gw(p, fixtures, gw)
            bench.append(_pick_to_response(p, xpts, fixture_count=fc, fixture_badge=fb))

        captain, vice = _choose_captains(ordered_starting_pairs)

        bank = _float(hist.get("bank"), 0.0) / 10.0
        squad_value = _float(hist.get("value"), 0.0) / 10.0

        squad_id_set = set(squad_ids)

        # Transfer logic uses weighted next-3-GW horizon with mode-specific weights.
        squad_horizon_scored: List[Tuple[float, Player]] = []
        for _, p in squad_scored:
            hxpts = _expected_points_horizon(p, fixtures, gw, horizon=3, weights=horizon_weights)
            squad_horizon_scored.append((hxpts, p))

        weakest_hxpts, weakest_player = sorted(squad_horizon_scored, key=lambda x: x[0])[0]
        max_affordable = weakest_player.now_cost / 10.0 + bank

        replacement_pool: List[Tuple[float, Player]] = []
        for p in players:
            if p.id in squad_id_set:
                continue
            if p.element_type != weakest_player.element_type:
                continue
            price = p.now_cost / 10.0
            if price > max_affordable:
                continue
            hxpts = _expected_points_horizon(p, fixtures, gw, horizon=3, weights=horizon_weights)
            replacement_pool.append((hxpts, p))

        replacement_pool.sort(key=lambda x: x[0], reverse=True)

        if replacement_pool and replacement_pool[0][0] > weakest_hxpts + transfer_threshold:
            best_hxpts, best_player = replacement_pool[0]
            transfer_out = weakest_player.web_name
            transfer_in = best_player.web_name
            gain = round(best_hxpts - weakest_hxpts, 2)
            transfer_reason = (
                f"[{mode}] Estimated +{gain} weighted xP over next 3 GWs (starting GW {gw}) "
                f"within budget (£{max_affordable:.1f})."
            )

            # Consistency guardrails
            if best_player.id in squad_id_set or best_player.id == weakest_player.id:
                transfer_out = "No urgent sale"
                transfer_in = "Roll transfer"
                transfer_reason = (
                    f"[{mode}] Guardrail: suggested transfer was invalid (duplicate/self transfer). "
                    "Rolled transfer instead."
                )
        else:
            transfer_out = "No urgent sale"
            transfer_in = "Roll transfer"
            transfer_reason = (
                f"[{mode}] No same-position replacement offers a clear weighted gain over "
                f"the next 3 GWs within budget."
            )

        confidence = min(0.9, max(0.55, sum(p.expected_points for p in starting_xi) / 70.0))

        return TeamRecommendation(
            entry_id=entry_id,
            gameweek=gw,
            strategy_mode=mode,
            formation=formation,
            starting_xi=starting_xi,
            bench=bench,
            captain=captain,
            vice_captain=vice,
            transfer_out=transfer_out,
            transfer_in=transfer_in,
            transfer_reason=transfer_reason,
            bank=round(bank, 1),
            squad_value=round(squad_value, 1),
            confidence=round(confidence, 2),
            last_ingested_at=_get_meta(db, "last_ingested_at"),
            summary=f"Team-specific XI from your current squad, with {mode} transfer suggestions optimized on a weighted next-3-GW horizon.",
        )
    finally:
        db.close()

@router.get("/api/fpl/team/{entry_id}/what-if")
def what_if_simulator(
    entry_id: int,
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    horizon: int = Query(default=3, ge=1, le=5),
    max_transfers: int = Query(default=2, ge=1, le=2),
    free_transfers: int = Query(default=1, ge=0, le=2),
    hit_cost: int = Query(default=4, ge=0, le=12),
    per_out_limit: int = Query(default=5, ge=2, le=12),
    limit: int = Query(default=10, ge=1, le=25),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No player data found. Run POST /api/fpl/ingest/bootstrap first.")

        gw = _resolve_gameweek(db, gameweek)
        current_gw = _int(_get_meta(db, "current_gw"), 0)
        payload, resolved_gw = _fetch_entry_picks_with_fallback(entry_id, gw, [current_gw, gw - 1])
        gw = resolved_gw
        picks = payload.get("picks", [])
        hist = payload.get("entry_history", {})

        squad_ids = [_int(p.get("element")) for p in picks]
        if len(squad_ids) < 11:
            raise HTTPException(status_code=400, detail="FPL returned incomplete squad data")

        player_by_id = {p.id: p for p in players}
        fixtures = db.query(Fixture).all()

        squad_players = [player_by_id.get(pid) for pid in squad_ids]
        squad_players = [p for p in squad_players if p is not None]
        if len(squad_players) < 11:
            raise HTTPException(status_code=400, detail="Your squad has players missing from local DB. Re-run bootstrap ingest.")

        bank = _float(hist.get("bank"), 0.0) / 10.0
        squad_id_set = {p.id for p in squad_players}

        horizon_score = {
            p.id: _expected_points_horizon(p, fixtures, gw, horizon=horizon)
            for p in squad_players
        }

        # Build replacement options for each outbound player.
        replacements: dict[int, list[tuple[float, Player]]] = {}
        for out_p in squad_players:
            budget = (out_p.now_cost / 10.0) + bank
            options: list[tuple[float, Player]] = []
            for cand in players:
                if cand.id in squad_id_set:
                    continue
                if cand.element_type != out_p.element_type:
                    continue
                if (cand.now_cost / 10.0) > budget:
                    continue
                cand_h = _expected_points_horizon(cand, fixtures, gw, horizon=horizon)
                gain = cand_h - horizon_score[out_p.id]
                options.append((gain, cand))
            options.sort(key=lambda x: x[0], reverse=True)
            replacements[out_p.id] = options[:per_out_limit]

        scenarios: list[dict] = []

        # Single-transfer scenarios
        for out_p in squad_players:
            for gain, in_p in replacements.get(out_p.id, []):
                if in_p.id == out_p.id or in_p.id in squad_id_set:
                    continue
                transfers = 1
                hit = max(0, transfers - free_transfers) * hit_cost
                net = round(gain - hit, 2)
                scenarios.append(
                    {
                        "transfers": [
                            {
                                "out": out_p.web_name,
                                "out_id": out_p.id,
                                "in": in_p.web_name,
                                "in_id": in_p.id,
                                "position": POSITION_MAP.get(out_p.element_type, str(out_p.element_type)),
                                "gain": round(gain, 2),
                            }
                        ],
                        "hit": hit,
                        "projected_gain": round(gain, 2),
                        "net_gain": net,
                        "horizon": horizon,
                    }
                )

        # Two-transfer scenarios
        if max_transfers >= 2:
            for out_a, out_b in combinations(squad_players, 2):
                for gain_a, in_a in replacements.get(out_a.id, []):
                    for gain_b, in_b in replacements.get(out_b.id, []):
                        if in_a.id == in_b.id:
                            continue

                        total_in_price = (in_a.now_cost + in_b.now_cost) / 10.0
                        total_out_price = (out_a.now_cost + out_b.now_cost) / 10.0
                        if total_in_price > total_out_price + bank:
                            continue

                        projected = gain_a + gain_b
                        transfers = 2
                        hit = max(0, transfers - free_transfers) * hit_cost
                        net = round(projected - hit, 2)
                        scenarios.append(
                            {
                                "transfers": [
                                    {
                                        "out": out_a.web_name,
                                        "out_id": out_a.id,
                                        "in": in_a.web_name,
                                        "in_id": in_a.id,
                                        "position": POSITION_MAP.get(out_a.element_type, str(out_a.element_type)),
                                        "gain": round(gain_a, 2),
                                    },
                                    {
                                        "out": out_b.web_name,
                                        "out_id": out_b.id,
                                        "in": in_b.web_name,
                                        "in_id": in_b.id,
                                        "position": POSITION_MAP.get(out_b.element_type, str(out_b.element_type)),
                                        "gain": round(gain_b, 2),
                                    },
                                ],
                                "hit": hit,
                                "projected_gain": round(projected, 2),
                                "net_gain": net,
                                "horizon": horizon,
                            }
                        )

        scenarios.sort(key=lambda x: x["net_gain"], reverse=True)

        return {
            "entry_id": entry_id,
            "gameweek": gw,
            "horizon": horizon,
            "bank": round(bank, 1),
            "free_transfers": free_transfers,
            "hit_cost": hit_cost,
            "count": min(len(scenarios), limit),
            "scenarios": scenarios[:limit],
            "summary": "What-if transfer simulator ranked by projected net gain over selected horizon.",
        }
    finally:
        db.close()


@router.get("/api/fpl/team/{entry_id}/rank-history", response_model=RankHistoryResponse)
def team_rank_history(entry_id: int):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    payload = fetch_json(
        url,
        timeout=20,
        not_found_detail=f"FPL team {entry_id} not found",
        upstream_error_prefix="Could not fetch rank history from FPL",
    )

    current = payload.get("current", [])
    points: List[RankHistoryPoint] = []
    for row in current:
        event = _int(row.get("event"), 0)
        overall_rank = _int(row.get("overall_rank"), 0)
        event_points = _int(row.get("points"), 0)
        total_points = _int(row.get("total_points"), 0)
        if event <= 0 or overall_rank <= 0:
            continue
        points.append(
            RankHistoryPoint(
                event=event,
                overall_rank=overall_rank,
                event_points=event_points,
                total_points=total_points,
            )
        )

    points.sort(key=lambda x: x.event)

    if not points:
        return RankHistoryResponse(
            entry_id=entry_id,
            points=[],
            summary="No rank history available yet for this team.",
        )

    ranks = [p.overall_rank for p in points]
    return RankHistoryResponse(
        entry_id=entry_id,
        points=points,
        best_rank=min(ranks),
        worst_rank=max(ranks),
        summary="Overall rank trend by gameweek (lower is better).",
    )
