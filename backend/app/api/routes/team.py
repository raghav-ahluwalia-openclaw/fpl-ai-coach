from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from typing import List, Optional, Tuple

from fastapi import HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from .base import (
    POSITION_MAP,
    Fixture,
    Player,
    RankHistoryPoint,
    RankHistoryResponse,
    SessionLocal,
    TeamRecommendation,
    UserSquadPick,
    _availability_factor,
    _build_lineup_from_squad,
    _choose_captains,
    _expected_points,
    _expected_points_horizon,
    _fetch_entry_picks_with_fallback,
    _fixture_badge_for_gw,
    _fixture_count_for_gw,
    _fixture_factor,
    _float,
    _get_meta,
    _int,
    _minutes_factor,
    _pick_to_response,
    _resolve_gameweek,
    _set_meta,
    _strategy_config,
    fetch_json,
    router,
)

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

        target_gw = _resolve_gameweek(db, gameweek)
        current_gw = _int(_get_meta(db, "current_gw"), 0)
        payload, _resolved_gw = _fetch_entry_picks_with_fallback(entry_id, target_gw, [current_gw, target_gw - 1])
        gw = target_gw
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
            xpts3 = _expected_points_horizon(p, fixtures, gw, horizon=3, weights=horizon_weights)
            xpts5 = _expected_points_horizon(p, fixtures, gw, horizon=5)
            starting_xi.append(
                _pick_to_response(
                    p,
                    xpts,
                    expected_points_1=round(xpts, 2),
                    expected_points_3=round(xpts3, 2),
                    expected_points_5=round(xpts5, 2),
                    fixture_count=fc,
                    fixture_badge=fb,
                )
            )

        bench = []
        for xpts, p in bench_pairs:
            fc, fb = _fixture_badge_for_gw(p, fixtures, gw)
            xpts3 = _expected_points_horizon(p, fixtures, gw, horizon=3, weights=horizon_weights)
            xpts5 = _expected_points_horizon(p, fixtures, gw, horizon=5)
            bench.append(
                _pick_to_response(
                    p,
                    xpts,
                    expected_points_1=round(xpts, 2),
                    expected_points_3=round(xpts3, 2),
                    expected_points_5=round(xpts5, 2),
                    fixture_count=fc,
                    fixture_badge=fb,
                )
            )

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

        target_gw = _resolve_gameweek(db, gameweek)
        current_gw = _int(_get_meta(db, "current_gw"), 0)
        payload, _resolved_gw = _fetch_entry_picks_with_fallback(entry_id, target_gw, [current_gw, target_gw - 1])
        gw = target_gw
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


@router.get("/api/fpl/team/{entry_id}/weekly-cockpit")
def weekly_cockpit(
    entry_id: int,
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No player data found. Run POST /api/fpl/ingest/bootstrap first.")

        target_gw = _resolve_gameweek(db, gameweek)
        current_gw = _int(_get_meta(db, "current_gw"), 0)
        payload, picks_source_gw = _fetch_entry_picks_with_fallback(entry_id, target_gw, [current_gw, target_gw - 1])
        # Keep planning anchored to target_gw (upcoming decision GW), even if picks fallback uses last available squad snapshot.
        gw = target_gw
        picks = payload.get("picks", [])
        hist = payload.get("entry_history", {})

        if len(picks) < 11:
            raise HTTPException(status_code=400, detail="FPL returned incomplete squad data")

        fixtures = db.query(Fixture).all()
        player_by_id = {p.id: p for p in players}
        squad_ids = [_int(p.get("element")) for p in picks]
        squad_players = [player_by_id.get(pid) for pid in squad_ids if player_by_id.get(pid) is not None]
        if len(squad_players) < 11:
            raise HTTPException(status_code=400, detail="Your squad has players missing from local DB. Re-run bootstrap ingest.")

        mode_weights, _ = _strategy_config(mode)

        def _fixture_window_next_3(player: Player) -> dict:
            counts = [_fixture_count_for_gw(player, fixtures, gw + i) for i in range(3)]
            blanks = sum(1 for c in counts if c == 0)
            doubles = sum(1 for c in counts if c >= 2)
            singles = sum(1 for c in counts if c == 1)
            return {
                "counts": counts,
                "blanks": blanks,
                "doubles": doubles,
                "singles": singles,
                "label": f"B{blanks} / S{singles} / D{doubles}",
            }

        scored = [(_expected_points(p, fixtures, gw), p) for p in squad_players]
        starting_pairs, bench_pairs, formation = _build_lineup_from_squad(scored)

        picked_by_pos = sorted(
            [p for p in picks if _int(p.get("position"), 0) > 0],
            key=lambda r: _int(r.get("position"), 99),
        )
        current_start_ids = [_int(p.get("element")) for p in picked_by_pos if _int(p.get("position"), 0) <= 11]
        current_bench_ids = [_int(p.get("element")) for p in picked_by_pos if _int(p.get("position"), 0) > 11]

        rec_start_ids = [p.id for _, p in sorted(starting_pairs, key=lambda x: x[0], reverse=True)]
        rec_bench_ids = [p.id for _, p in bench_pairs]

        def _lineup_points(player_ids: list[int], horizon_points: bool = False) -> float:
            total = 0.0
            for pid in player_ids:
                p = player_by_id.get(pid)
                if not p:
                    continue
                if horizon_points:
                    total += _expected_points_horizon(p, fixtures, gw, horizon=3, weights=mode_weights)
                else:
                    total += _expected_points(p, fixtures, gw)
            return round(total, 2)

        def _bench_weighted_score(player_ids: list[int], horizon_points: bool = False) -> float:
            # Approximate autosub importance: bench 1 matters most.
            weights = [1.0, 0.65, 0.35, 0.15]
            total = 0.0
            for idx, pid in enumerate(player_ids[:4]):
                p = player_by_id.get(pid)
                if not p:
                    continue
                xp = _expected_points_horizon(p, fixtures, gw, horizon=3, weights=mode_weights) if horizon_points else _expected_points(p, fixtures, gw)
                total += xp * weights[idx]
            return round(total, 2)

        lineup_optimizer = {
            "formation": formation,
            "starting_xi": [
                {
                    "id": p.id,
                    "name": p.web_name,
                    "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                    "xP_next_1": round(xpts, 2),
                    "xP_next_3": round(_expected_points_horizon(p, fixtures, gw, horizon=3, weights=mode_weights), 2),
                    "xP_next_5": round(_expected_points_horizon(p, fixtures, gw, horizon=5), 2),
                    "fixture_badge": _fixture_badge_for_gw(p, fixtures, gw)[1],
                    "fixture_window_next_3": _fixture_window_next_3(p),
                }
                for xpts, p in sorted(starting_pairs, key=lambda x: x[0], reverse=True)
            ],
            "bench_order": [
                {
                    "id": p.id,
                    "name": p.web_name,
                    "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                    "bench_rank": idx + 1,
                    "xP_next_1": round(xpts, 2),
                    "xP_next_3": round(_expected_points_horizon(p, fixtures, gw, horizon=3, weights=mode_weights), 2),
                    "xP_next_5": round(_expected_points_horizon(p, fixtures, gw, horizon=5), 2),
                    "fixture_badge": _fixture_badge_for_gw(p, fixtures, gw)[1],
                    "fixture_window_next_3": _fixture_window_next_3(p),
                }
                for idx, (xpts, p) in enumerate(bench_pairs)
            ],
            "expected_gain_vs_current_xi_1": round(_lineup_points(rec_start_ids, horizon_points=False) - _lineup_points(current_start_ids, horizon_points=False), 2),
            "expected_gain_vs_current_xi_3": round(_lineup_points(rec_start_ids, horizon_points=True) - _lineup_points(current_start_ids, horizon_points=True), 2),
            "bench_order_gain_1": round(_bench_weighted_score(rec_bench_ids, horizon_points=False) - _bench_weighted_score(current_bench_ids, horizon_points=False), 2),
            "bench_order_gain_3": round(_bench_weighted_score(rec_bench_ids, horizon_points=True) - _bench_weighted_score(current_bench_ids, horizon_points=True), 2),
        }

        # Team health
        health_rows = []
        for p in squad_players:
            xp1 = _expected_points(p, fixtures, gw)
            xp3 = _expected_points_horizon(p, fixtures, gw, horizon=3, weights=mode_weights)
            xp5 = _expected_points_horizon(p, fixtures, gw, horizon=5)
            fc, fb = _fixture_badge_for_gw(p, fixtures, gw)
            fixture_window = _fixture_window_next_3(p)
            availability = _availability_factor(p.chance_of_playing_next_round, p.news)
            minutes_factor = _minutes_factor(p.minutes)
            minutes_risk = round(max(0.0, 1.0 - min(minutes_factor, 1.0)), 2)
            availability_risk = round(max(0.0, 1.0 - availability), 2)
            risk = round(min(1.0, availability_risk * 0.6 + minutes_risk * 0.4), 2)
            upside_safety = round(max(-2.5, min(2.5, (xp3 - 5.5) - (risk * 2.0))), 2)
            action = "hold"
            if fixture_window["blanks"] >= 1 and xp3 < 5.2:
                action = "watch"
            if fixture_window["blanks"] >= 2 or (risk >= 0.45 and xp3 < 4.8):
                action = "sell"
            elif action != "sell" and (risk >= 0.3 or xp3 < 5.3):
                action = "watch"

            health_rows.append(
                {
                    "id": p.id,
                    "name": p.web_name,
                    "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                    "price": round(p.now_cost / 10.0, 1),
                    "projected_points_1": round(xp1, 2),
                    "projected_points_3": round(xp3, 2),
                    "projected_points_5": round(xp5, 2),
                    "fixture_count": fc,
                    "fixture_badge": fb,
                    "fixture_window_next_3": fixture_window,
                    "fixture_difficulty_factor": round(_fixture_factor(p, fixtures, gw), 2),
                    "minutes_risk": minutes_risk,
                    "availability_risk": availability_risk,
                    "injury_news": p.news or "",
                    "upside_safety_score": upside_safety,
                    "action": action,
                }
            )

        sells = sorted([x for x in health_rows if x["action"] == "sell"], key=lambda x: (x["projected_points_3"], -x["minutes_risk"]))[:5]
        holds = sorted([x for x in health_rows if x["action"] == "hold"], key=lambda x: x["projected_points_3"], reverse=True)[:6]
        watch = sorted([x for x in health_rows if x["action"] == "watch"], key=lambda x: (x["minutes_risk"] + x["availability_risk"]), reverse=True)[:6]

        # Transfer plans (1FT + 2FT)
        sim = what_if_simulator(
            entry_id=entry_id,
            gameweek=gw,
            horizon=3,
            max_transfers=2,
            free_transfers=1,
            hit_cost=4,
            per_out_limit=6,
            limit=30,
        )
        scenarios = sim.get("scenarios", [])

        one_ft = [s for s in scenarios if len(s.get("transfers", [])) == 1 and s.get("hit", 0) == 0][:3]
        two_ft = [s for s in scenarios if len(s.get("transfers", [])) == 2][:3]

        def enrich_plan(plan: dict, label: str):
            transfers = []
            risk_components = []
            for t in plan.get("transfers", []):
                out_p = player_by_id.get(_int(t.get("out_id")))
                in_p = player_by_id.get(_int(t.get("in_id")))
                if not out_p or not in_p:
                    continue
                out_xp1 = _expected_points(out_p, fixtures, gw)
                in_xp1 = _expected_points(in_p, fixtures, gw)
                out_xp3 = _expected_points_horizon(out_p, fixtures, gw, horizon=3, weights=mode_weights)
                in_xp3 = _expected_points_horizon(in_p, fixtures, gw, horizon=3, weights=mode_weights)
                out_xp5 = _expected_points_horizon(out_p, fixtures, gw, horizon=5)
                in_xp5 = _expected_points_horizon(in_p, fixtures, gw, horizon=5)
                in_availability_risk = round(max(0.0, 1.0 - _availability_factor(in_p.chance_of_playing_next_round, in_p.news)), 2)
                in_minutes_risk = round(max(0.0, 1.0 - min(_minutes_factor(in_p.minutes), 1.0)), 2)
                in_upside_safety = round((in_xp3 - 5.5) - ((in_availability_risk * 0.6 + in_minutes_risk * 0.4) * 2.0), 2)
                in_fixture_window = _fixture_window_next_3(in_p)
                transfer_risk = min(1.0, (in_availability_risk * 0.6) + (in_minutes_risk * 0.25) + (0.15 if in_fixture_window["blanks"] > 0 else 0.0))
                risk_components.append(transfer_risk)
                transfers.append(
                    {
                        **t,
                        "projected_points_1_in": round(in_xp1, 2),
                        "projected_points_1_out": round(out_xp1, 2),
                        "projected_points_3_in": round(in_xp3, 2),
                        "projected_points_3_out": round(out_xp3, 2),
                        "projected_points_5_in": round(in_xp5, 2),
                        "projected_points_5_out": round(out_xp5, 2),
                        "fixture_difficulty_factor_in": round(_fixture_factor(in_p, fixtures, gw), 2),
                        "fixture_window_next_3_in": in_fixture_window,
                        "minutes_risk_in": in_minutes_risk,
                        "availability_risk_in": in_availability_risk,
                        "injury_news_in": in_p.news or "",
                        "upside_safety_score_in": in_upside_safety,
                        "risk_score_in": round(transfer_risk, 2),
                    }
                )

            projected_gain = float(plan.get("projected_gain", 0.0) or 0.0)
            net_gain = float(plan.get("net_gain", 0.0) or 0.0)
            hit = int(plan.get("hit", 0) or 0)
            avg_risk = sum(risk_components) / len(risk_components) if risk_components else 0.0
            risk_score = min(1.0, avg_risk + (0.08 if hit > 0 else 0.0))

            gain_signal = max(0.0, min(1.0, net_gain / 6.0))
            confidence = max(0.25, min(0.92, (0.35 + (gain_signal * 0.55)) - (risk_score * 0.28)))
            if confidence >= 0.75:
                confidence_bucket = "high"
            elif confidence >= 0.55:
                confidence_bucket = "medium"
            else:
                confidence_bucket = "low"

            return {
                "plan": label,
                "transfer_count": len(transfers),
                "projected_gain": round(projected_gain, 2),
                "net_gain": round(net_gain, 2),
                "hit": hit,
                "ev": round(net_gain, 2),
                "risk_score": round(risk_score, 2),
                "confidence": round(confidence, 2),
                "confidence_bucket": confidence_bucket,
                "transfers": transfers,
            }

        one_ft_plans = [enrich_plan(p, f"Plan {chr(65 + idx)}") for idx, p in enumerate(one_ft)]
        two_ft_plans = [enrich_plan(p, f"Plan {chr(65 + idx)}") for idx, p in enumerate(two_ft)]

        def _pad_plans(plans: list[dict], transfer_count: int) -> list[dict]:
            out = plans[:]
            while len(out) < 3:
                label = f"Plan {chr(65 + len(out))}"
                out.append(
                    {
                        "plan": label,
                        "transfer_count": transfer_count,
                        "projected_gain": 0.0,
                        "net_gain": 0.0,
                        "hit": 0,
                        "ev": 0.0,
                        "risk_score": 0.0,
                        "confidence": 0.65,
                        "confidence_bucket": "medium",
                        "transfers": [],
                        "note": "No higher-edge move found; rolling transfer is viable.",
                    }
                )
            return out[:3]

        one_ft_plans = _pad_plans(one_ft_plans, transfer_count=1)
        two_ft_plans = _pad_plans(two_ft_plans, transfer_count=2)

        bank = _float(hist.get("bank"), 0.0) / 10.0
        squad_value = _float(hist.get("value"), 0.0) / 10.0
        confidence = min(0.9, max(0.55, sum(x for x, _ in starting_pairs) / 70.0))

        # Captain matrix from likely starters
        matrix = []
        for xpts, p in sorted(starting_pairs, key=lambda x: x[0], reverse=True):
            xp1 = _expected_points(p, fixtures, gw)
            xp3 = _expected_points_horizon(p, fixtures, gw, horizon=3, weights=mode_weights)
            xp5 = _expected_points_horizon(p, fixtures, gw, horizon=5)
            ownership = max(0.0, min(p.selected_by_percent, 100.0))
            availability_risk = max(0.0, 1.0 - _availability_factor(p.chance_of_playing_next_round, p.news))
            minutes_risk = max(0.0, 1.0 - min(_minutes_factor(p.minutes), 1.0))
            risk = min(1.0, availability_risk * 0.6 + minutes_risk * 0.4)
            safe_score = round(xp3 * (1.0 - risk * 0.65) + (ownership * 0.01), 2)
            fixture_window = _fixture_window_next_3(p)
            fixture_swing_bonus = (fixture_window["doubles"] * 0.35) - (fixture_window["blanks"] * 0.6)
            differential_score = round(
                xp3 * (1.0 - risk * 0.2) + (max(0.0, 30.0 - ownership) / 30.0) * 1.6 + fixture_swing_bonus,
                2,
            )
            safe_score = round(safe_score + fixture_swing_bonus * 0.6, 2)
            matrix.append(
                {
                    "id": p.id,
                    "name": p.web_name,
                    "safe_score": safe_score,
                    "differential_score": differential_score,
                    "projected_points_1": round(xp1, 2),
                    "projected_points_3": round(xp3, 2),
                    "projected_points_5": round(xp5, 2),
                    "ownership_pct": round(ownership, 1),
                    "fixture_window_next_3": fixture_window,
                    "minutes_risk": round(minutes_risk, 2),
                    "availability_risk": round(availability_risk, 2),
                }
            )

        safe_caps = sorted(matrix, key=lambda x: x["safe_score"], reverse=True)[:5]
        safe_ids = {c["id"] for c in safe_caps}
        diff_caps = [c for c in sorted(matrix, key=lambda x: x["differential_score"], reverse=True) if c["id"] not in safe_ids][:5]

        # What changed since last week
        changes = []
        if gw > 1:
            try:
                prev_payload, _ = _fetch_entry_picks_with_fallback(entry_id, gw - 1, [gw - 1, gw - 2])
                prev_ids = {_int(p.get("element")) for p in prev_payload.get("picks", [])}
                curr_ids = set(squad_ids)
                out_ids = list(prev_ids - curr_ids)
                in_ids = list(curr_ids - prev_ids)
                if out_ids or in_ids:
                    changes.append(
                        {
                            "type": "squad_changes",
                            "summary": "Transfers since last GW",
                            "out": [player_by_id[i].web_name for i in out_ids if i in player_by_id],
                            "in": [player_by_id[i].web_name for i in in_ids if i in player_by_id],
                        }
                    )
            except HTTPException:
                pass

        injury_flags = [h for h in health_rows if h["injury_news"]][:5]
        if injury_flags:
            changes.append(
                {
                    "type": "injury_news",
                    "summary": "Current injury/news flags",
                    "players": [{"name": h["name"], "news": h["injury_news"]} for h in injury_flags],
                }
            )

        fixture_swings = []
        for p in squad_players:
            now_count = _fixture_count_for_gw(p, fixtures, gw)
            prev_count = _fixture_count_for_gw(p, fixtures, gw - 1)
            if now_count != prev_count:
                fixture_swings.append(
                    {
                        "name": p.web_name,
                        "from": "DGW" if prev_count >= 2 else ("BLANK" if prev_count == 0 else "SGW"),
                        "to": "DGW" if now_count >= 2 else ("BLANK" if now_count == 0 else "SGW"),
                    }
                )
        if fixture_swings:
            changes.append(
                {
                    "type": "fixture_swings",
                    "summary": "Fixture context changes",
                    "players": fixture_swings[:8],
                }
            )

        squad_window = {
            "blank_flags_next_3": sum(1 for p in squad_players if _fixture_window_next_3(p)["blanks"] > 0),
            "double_flags_next_3": sum(1 for p in squad_players if _fixture_window_next_3(p)["doubles"] > 0),
        }

        return {
            "entry_id": entry_id,
            "gameweek": gw,
            "picks_source_gw": picks_source_gw,
            "mode": mode,
            "team_overview": {
                "entry_id": entry_id,
                "gameweek": gw,
                "formation": formation,
                "strategy_mode": mode,
                "confidence": round(confidence, 2),
                "bank": round(bank, 1),
                "squad_value": round(squad_value, 1),
            },
            "fixture_context": {
                "gameweek": gw,
                "considered": True,
                "method": "All xP(1/3) and transfer/captain scores include SGW/DGW/BLANK via fixture-aware model.",
                "squad_window": squad_window,
            },
            "lineup_optimizer": lineup_optimizer,
            "team_health": {
                "sell": sells,
                "watch": watch,
                "hold": holds,
            },
            "top_transfer_plans": {
                "one_ft": one_ft_plans,
                "two_ft": two_ft_plans,
            },
            "captain_matrix": {
                "safe": safe_caps,
                "differential": diff_caps,
            },
            "what_changed": changes,
            "summary": "Weekly cockpit with team health, top transfer plans (1FT/2FT), captain matrix, and latest changes.",
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
