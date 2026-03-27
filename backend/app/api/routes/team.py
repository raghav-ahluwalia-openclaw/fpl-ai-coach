from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from statistics import median
from typing import List, Optional, Tuple

from fastapi import Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import rate_limit_write_ops, require_authenticated

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
    logger,
    router,
)

@router.post(
    "/api/fpl/team/{entry_id}/import",
    dependencies=[Depends(require_authenticated), Depends(rate_limit_write_ops)],
)
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

        now_iso = datetime.now(timezone.utc).isoformat()
        _set_meta(db, f"entry:{entry_id}:last_import", now_iso)

        # Persist optional team snapshot metadata for rival context.
        # Use lightweight caching to avoid hitting FPL entry endpoint on every import.
        player_name_key = f"entry:{entry_id}:player_name"
        entry_name_key = f"entry:{entry_id}:entry_name"
        last_profile_sync_key = f"entry:{entry_id}:last_profile_sync"

        cached_player_name = (_get_meta(db, player_name_key) or "").strip()
        cached_entry_name = (_get_meta(db, entry_name_key) or "").strip()
        last_profile_sync_raw = _get_meta(db, last_profile_sync_key)

        should_refresh_profile = (not cached_player_name) or (not cached_entry_name)
        if not should_refresh_profile and last_profile_sync_raw:
            try:
                last_profile_sync = datetime.fromisoformat(last_profile_sync_raw.replace("Z", "+00:00"))
                if last_profile_sync.tzinfo is None:
                    last_profile_sync = last_profile_sync.replace(tzinfo=timezone.utc)
                # Refresh at most every 6 hours.
                should_refresh_profile = (datetime.now(timezone.utc) - last_profile_sync).total_seconds() >= 6 * 3600
            except ValueError:
                should_refresh_profile = True

        player_name = cached_player_name
        entry_name = cached_entry_name

        if should_refresh_profile:
            try:
                entry_info = fetch_json(f"https://fantasy.premierleague.com/api/entry/{entry_id}/", timeout=10)
                first = str(entry_info.get("player_first_name") or "").strip()
                last = str(entry_info.get("player_last_name") or "").strip()
                combined_name = " ".join([x for x in [first, last] if x]).strip()

                player_name = combined_name or player_name or str(payload.get("player_name") or "").strip()
                entry_name = str(entry_info.get("name") or "").strip() or entry_name or str(payload.get("name") or "").strip()
                _set_meta(db, last_profile_sync_key, now_iso)
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    "entry profile refresh failed; using cached/fallback names",
                    extra={"entry_id": entry_id, "error": str(e)},
                )
                # Fallback to existing cache, then picks payload if available.
                if not player_name:
                    player_name = str(payload.get("player_name") or "").strip()
                if not entry_name:
                    entry_name = str(payload.get("name") or "").strip()

        _set_meta(db, player_name_key, player_name)
        _set_meta(db, entry_name_key, entry_name)
        db.commit()

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

def _price_rise_pressure(p: Player) -> float:
    ownership = max(0.0, min(_float(p.selected_by_percent), 100.0))
    form = max(0.0, _float(p.form))
    ppg = max(0.0, _float(p.points_per_game))
    pressure = (ownership / 45.0) * 0.45 + (form / 8.0) * 0.35 + (ppg / 8.0) * 0.20
    return round(min(1.0, max(0.0, pressure)), 3)


def _price_fall_pressure(p: Player) -> float:
    form = max(0.0, _float(p.form))
    ppg = max(0.0, _float(p.points_per_game))
    availability_risk = max(0.0, 1.0 - _availability_factor(p.chance_of_playing_next_round, p.news))
    pressure = ((max(0.0, 4.0 - form) / 4.0) * 0.45) + ((max(0.0, 4.0 - ppg) / 4.0) * 0.25) + (availability_risk * 0.30)
    return round(min(1.0, max(0.0, pressure)), 3)


def _calibrate_confidence(raw: float, *, risk_score: float, hit: int, value_urgency: float) -> tuple[float, str]:
    calibrated = raw
    calibrated += value_urgency * 0.06
    calibrated -= risk_score * 0.10
    if hit > 0:
        calibrated -= 0.03
    calibrated = max(0.2, min(0.94, calibrated))

    if calibrated >= 0.72:
        bucket = "high"
    elif calibrated >= 0.5:
        bucket = "medium"
    else:
        bucket = "low"
    return round(calibrated, 3), bucket


def _price_change_eta_hours(pressure: float) -> int:
    """Heuristic ETA in hours for next price move.

    Higher pressure => sooner move. Clamped to [6h, 14d].
    """
    p = max(0.0, min(1.0, pressure))
    # Non-linear curve for sharper response at high pressure.
    hours = int(round(6 + ((1.0 - p) ** 1.6) * (14 * 24 - 6)))
    return max(6, min(14 * 24, hours))


def _format_eta(hours: int) -> str:
    if hours < 24:
        return f"{hours}h"
    days = max(1, int(round(hours / 24)))
    return f"{days}d"


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
                rise_in = _price_rise_pressure(in_p)
                fall_out = _price_fall_pressure(out_p)
                value_urgency = round(min(1.0, (rise_in * 0.55) + (fall_out * 0.45)), 3)
                price_change_bonus = round(value_urgency * 0.6, 3)
                net = round(gain - hit, 2)
                ranking_score = round(net + price_change_bonus, 3)
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
                                "price_rise_pressure_in": rise_in,
                                "price_fall_pressure_out": fall_out,
                                "value_urgency_score": value_urgency,
                            }
                        ],
                        "hit": hit,
                        "projected_gain": round(gain, 2),
                        "net_gain": net,
                        "price_change_bonus": price_change_bonus,
                        "value_urgency_score": value_urgency,
                        "ranking_score": ranking_score,
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

                        rise_a = _price_rise_pressure(in_a)
                        rise_b = _price_rise_pressure(in_b)
                        fall_a = _price_fall_pressure(out_a)
                        fall_b = _price_fall_pressure(out_b)
                        value_urgency = round(min(1.0, ((rise_a + rise_b) * 0.275) + ((fall_a + fall_b) * 0.225)), 3)
                        price_change_bonus = round(value_urgency * 0.6, 3)
                        ranking_score = round(net + price_change_bonus, 3)

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
                                        "price_rise_pressure_in": rise_a,
                                        "price_fall_pressure_out": fall_a,
                                        "value_urgency_score": round(min(1.0, rise_a * 0.55 + fall_a * 0.45), 3),
                                    },
                                    {
                                        "out": out_b.web_name,
                                        "out_id": out_b.id,
                                        "in": in_b.web_name,
                                        "in_id": in_b.id,
                                        "position": POSITION_MAP.get(out_b.element_type, str(out_b.element_type)),
                                        "gain": round(gain_b, 2),
                                        "price_rise_pressure_in": rise_b,
                                        "price_fall_pressure_out": fall_b,
                                        "value_urgency_score": round(min(1.0, rise_b * 0.55 + fall_b * 0.45), 3),
                                    },
                                ],
                                "hit": hit,
                                "projected_gain": round(projected, 2),
                                "net_gain": net,
                                "price_change_bonus": price_change_bonus,
                                "value_urgency_score": value_urgency,
                                "ranking_score": ranking_score,
                                "horizon": horizon,
                            }
                        )

        scenarios.sort(key=lambda x: (x.get("ranking_score", x.get("net_gain", 0.0))), reverse=True)

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


@router.get("/api/fpl/team/{entry_id}/gameweek-hub")
@router.get("/api/fpl/team/{entry_id}/weekly-cockpit")  # backward-compatible alias
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

            rise_pressure = _price_rise_pressure(p)
            fall_pressure = _price_fall_pressure(p)

            # Direction + ETA estimate (rebalance to avoid "always up" bias)
            score = rise_pressure - (fall_pressure * 1.08)
            if action == "sell" and fall_pressure >= 0.28 and score < 0.18:
                direction = "down"
                dir_pressure = fall_pressure
            elif score >= 0.18:
                direction = "up"
                dir_pressure = rise_pressure
            elif score <= -0.06:
                direction = "down"
                dir_pressure = fall_pressure
            else:
                direction = "flat"
                dir_pressure = max(rise_pressure, fall_pressure)

            eta_hours = _price_change_eta_hours(dir_pressure)

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
                    "price_rise_pressure": rise_pressure,
                    "price_fall_pressure": fall_pressure,
                    "price_change_direction": direction,
                    "price_change_eta_hours": eta_hours,
                    "price_change_eta": _format_eta(eta_hours),
                    "action": action,
                }
            )

        sells = sorted([x for x in health_rows if x["action"] == "sell"], key=lambda x: (x["projected_points_3"], -x["minutes_risk"]))[:5]
        holds = sorted([x for x in health_rows if x["action"] == "hold"], key=lambda x: x["projected_points_3"], reverse=True)[:6]
        watch = sorted([x for x in health_rows if x["action"] == "watch"], key=lambda x: (x["minutes_risk"] + x["availability_risk"]), reverse=True)[:6]

        action_rank = {"sell": 0, "watch": 1, "hold": 2}
        all_rows = sorted(
            health_rows,
            key=lambda x: (
                action_rank.get(str(x.get("action")), 9),
                -float(x.get("projected_points_3", 0)),
                str(x.get("name", "")),
            ),
        )

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
                rise_in = _price_rise_pressure(in_p)
                fall_out = _price_fall_pressure(out_p)
                value_urgency = round(min(1.0, (rise_in * 0.55) + (fall_out * 0.45)), 3)
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
                        "price_rise_pressure_in": rise_in,
                        "price_fall_pressure_out": fall_out,
                        "value_urgency_score": value_urgency,
                    }
                )

            hit = int(plan.get("hit", 0) or 0)

            projected_gain_1 = round(
                sum((float(t.get("projected_points_1_in", 0.0) or 0.0) - float(t.get("projected_points_1_out", 0.0) or 0.0)) for t in transfers),
                2,
            )
            projected_gain_3 = round(
                sum((float(t.get("projected_points_3_in", 0.0) or 0.0) - float(t.get("projected_points_3_out", 0.0) or 0.0)) for t in transfers),
                2,
            )
            projected_gain_5 = round(
                sum((float(t.get("projected_points_5_in", 0.0) or 0.0) - float(t.get("projected_points_5_out", 0.0) or 0.0)) for t in transfers),
                2,
            )

            net_gain_1 = round(projected_gain_1 - hit, 2)
            net_gain_3 = round(projected_gain_3 - hit, 2)
            net_gain_5 = round(projected_gain_5 - hit, 2)

            # Backward-compatible aliases default to 3GW horizon values.
            projected_gain = projected_gain_3
            net_gain = net_gain_3
            avg_risk = sum(risk_components) / len(risk_components) if risk_components else 0.0
            risk_score = min(1.0, avg_risk + (0.08 if hit > 0 else 0.0))

            value_urgency_score = max(
                0.0,
                min(1.0, sum(float(t.get("value_urgency_score", 0.0) or 0.0) for t in transfers) / max(1, len(transfers))),
            )
            price_change_bonus = round(value_urgency_score * 0.6, 3)

            gain_signal = max(0.0, min(1.0, (net_gain + price_change_bonus) / 6.0))
            raw_confidence = max(0.25, min(0.92, (0.35 + (gain_signal * 0.55)) - (risk_score * 0.28)))
            confidence, confidence_bucket = _calibrate_confidence(
                raw_confidence,
                risk_score=risk_score,
                hit=hit,
                value_urgency=value_urgency_score,
            )

            return {
                "plan": label,
                "transfer_count": len(transfers),
                "projected_gain": round(projected_gain, 2),
                "projected_gain_1": projected_gain_1,
                "projected_gain_3": projected_gain_3,
                "projected_gain_5": projected_gain_5,
                "net_gain": round(net_gain, 2),
                "net_gain_1": net_gain_1,
                "net_gain_3": net_gain_3,
                "net_gain_5": net_gain_5,
                "hit": hit,
                "ev": round(net_gain + price_change_bonus, 2),
                "risk_score": round(risk_score, 2),
                "price_change_bonus": round(price_change_bonus, 3),
                "value_urgency_score": round(value_urgency_score, 3),
                "confidence_raw": round(raw_confidence, 3),
                "confidence": round(confidence, 2),
                "confidence_bucket": confidence_bucket,
                "confidence_calibration": {
                    "version": "cal_v1",
                    "method": "rule-calibrated",
                },
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
                        "projected_gain_1": 0.0,
                        "projected_gain_3": 0.0,
                        "projected_gain_5": 0.0,
                        "net_gain": 0.0,
                        "net_gain_1": 0.0,
                        "net_gain_3": 0.0,
                        "net_gain_5": 0.0,
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
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
                "all": all_rows,
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
            "summary": "Gameweek Hub with team health, top transfer plans (1FT/2FT), captain matrix, and latest changes.",
        }
    finally:
        db.close()


@router.get("/api/fpl/team/{entry_id}/leagues")
def team_leagues(entry_id: int):
    entry_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/"
    payload = fetch_json(
        entry_url,
        timeout=20,
        not_found_detail=f"FPL team {entry_id} not found",
        upstream_error_prefix="Could not fetch team leagues from FPL",
    )

    leagues = payload.get("leagues", {}) or {}
    classic = leagues.get("classic", []) or []
    h2h = leagues.get("h2h", []) or []

    league_rows = []

    def _standings_url(kind: str, league_id: int, page: int) -> str:
        if kind == "h2h":
            return f"https://fantasy.premierleague.com/api/leagues-h2h/{league_id}/standings/?page_standings={page}"
        return f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/?page_standings={page}"

    def _to_points(row: dict) -> int:
        return _int(row.get("total"), 0)

    for kind, items in (("classic", classic), ("h2h", h2h)):
        for lg in items:
            league_id = _int(lg.get("id"), 0)
            if league_id <= 0:
                continue

            entry_rank = _int(lg.get("entry_rank"), 0)
            entry_last_rank = _int(lg.get("entry_last_rank"), 0)
            page = max(1, ((entry_rank - 1) // 50) + 1) if entry_rank > 0 else 1

            try:
                details = fetch_json(
                    _standings_url(kind, league_id, page),
                    timeout=20,
                    upstream_error_prefix=f"Could not fetch standings for league {league_id}",
                )
                standings = (details.get("standings") or {}).get("results", []) or []

                first_page = details
                if page != 1:
                    first_page = fetch_json(
                        _standings_url(kind, league_id, 1),
                        timeout=20,
                        upstream_error_prefix=f"Could not fetch leader data for league {league_id}",
                    )

                first_results = (first_page.get("standings") or {}).get("results", []) or []
                leader_row = first_results[0] if first_results else {}
                leader_points = _to_points(leader_row)

                your_row = None
                for r in standings:
                    if _int(r.get("entry"), 0) == entry_id:
                        your_row = r
                        break
                if your_row is None and standings:
                    # fallback by rank if entry id is absent in this page payload
                    your_row = next((r for r in standings if _int(r.get("rank"), 0) == entry_rank), None)

                your_points = _to_points(your_row or {})
                your_rank = _int((your_row or {}).get("rank"), entry_rank)
                last_rank = _int((your_row or {}).get("last_rank"), entry_last_rank)

                # Rank can be tied/skipped; derive neighbors via rank_sort (strict ordering).
                combined_rows = list(standings)
                for neighbor_page in [page - 1, page + 1]:
                    if neighbor_page < 1:
                        continue
                    try:
                        neighbor = fetch_json(
                            _standings_url(kind, league_id, neighbor_page),
                            timeout=20,
                            upstream_error_prefix=f"Could not fetch neighboring standings for league {league_id}",
                        )
                        combined_rows.extend((neighbor.get("standings") or {}).get("results", []) or [])
                    except HTTPException:
                        pass

                # De-duplicate by entry id.
                uniq = {}
                for r in combined_rows:
                    rid = _int(r.get("entry"), 0)
                    if rid <= 0:
                        continue
                    uniq[rid] = r
                combined_rows = list(uniq.values())

                # Always prefer exact entry match once neighbor pages are loaded.
                exact_row = next((r for r in combined_rows if _int(r.get("entry"), 0) == entry_id), None)
                if exact_row is not None:
                    your_row = exact_row
                    your_points = _to_points(your_row)
                    your_rank = _int(your_row.get("rank"), your_rank)
                    last_rank = _int(your_row.get("last_rank"), last_rank)

                above = None
                below = None
                if your_row is not None:
                    your_sort = _int(your_row.get("rank_sort"), 0)
                    if your_sort > 0:
                        above_cands = [r for r in combined_rows if 0 < _int(r.get("rank_sort"), 0) < your_sort]
                        below_cands = [r for r in combined_rows if _int(r.get("rank_sort"), 0) > your_sort]
                        if above_cands:
                            above = max(above_cands, key=lambda r: _int(r.get("rank_sort"), 0))
                        if below_cands:
                            below = min(below_cands, key=lambda r: _int(r.get("rank_sort"), 0))

                # For large public leagues, adjacent rank_sort entries can have equal points.
                # Use nearest distinct points when available so gaps remain decision-useful.
                higher_points = sorted({_to_points(r) for r in combined_rows if _to_points(r) > your_points})
                lower_points = sorted({_to_points(r) for r in combined_rows if _to_points(r) < your_points})

                if higher_points:
                    gap_above = max(1, higher_points[0] - your_points)
                else:
                    gap_above = (_to_points(above) - your_points) if above else None
                    if gap_above == 0 and your_rank > 1:
                        gap_above = 1

                if lower_points:
                    gap_below = max(1, your_points - lower_points[-1])
                else:
                    gap_below = (your_points - _to_points(below)) if below else None
                    if gap_below == 0 and below is not None:
                        gap_below = 1

                league_meta = details.get("league") or {}
                entry_count = (
                    _int(lg.get("rank_count"), 0)
                    or _int(league_meta.get("max_entries"), 0)
                    or _int((details.get("standings") or {}).get("entry_count"), 0)
                )
                if entry_count <= 0 and your_rank > 0:
                    # fallback for h2h/private leagues when count isn't provided
                    entry_count = max(your_rank, _int((leader_row or {}).get("rank"), 0), len((first_page.get("standings") or {}).get("results", []) or []))

                percentile = round((1.0 - ((max(your_rank, 1) - 1) / max(entry_count - 1, 1))) * 100.0, 1) if entry_count > 1 else 100.0

                around_sorted = sorted(standings, key=lambda x: _int(x.get("rank"), 10**9))
                around = []
                for r in around_sorted:
                    rr = _int(r.get("rank"), 0)
                    if your_rank > 0 and abs(rr - your_rank) <= 2:
                        around.append(
                            {
                                "rank": rr,
                                "entry": _int(r.get("entry"), 0),
                                "entry_name": r.get("entry_name"),
                                "manager": r.get("player_name"),
                                "points": _to_points(r),
                                "event_points": _int(r.get("event_total"), 0),
                            }
                        )

                league_rows.append(
                    {
                        "league_id": league_id,
                        "name": lg.get("name"),
                        "type": kind,
                        "entry_count": entry_count,
                        "your_rank": your_rank,
                        "last_rank": last_rank,
                        "rank_delta": (last_rank - your_rank) if your_rank > 0 and last_rank > 0 else 0,
                        "you_points": your_points,
                        "leader_points": leader_points,
                        "gap_to_leader": (leader_points - your_points) if leader_points >= your_points else 0,
                        "gap_to_next_above": gap_above,
                        "gap_to_next_below": gap_below,
                        "percentile": percentile,
                        "last_updated_data": details.get("last_updated_data") or first_page.get("last_updated_data"),
                        "around": around,
                    }
                )
            except HTTPException:
                league_rows.append(
                    {
                        "league_id": league_id,
                        "name": lg.get("name"),
                        "type": kind,
                        "entry_count": _int(lg.get("rank_count"), 0),
                        "your_rank": entry_rank,
                        "last_rank": entry_last_rank,
                        "rank_delta": (entry_last_rank - entry_rank) if entry_rank > 0 and entry_last_rank > 0 else 0,
                        "you_points": 0,
                        "leader_points": 0,
                        "gap_to_leader": 0,
                        "gap_to_next_above": None,
                        "gap_to_next_below": None,
                        "percentile": 0.0,
                        "last_updated_data": None,
                        "around": [],
                    }
                )

    type_order = {"classic": 0, "h2h": 1}
    league_rows.sort(
        key=lambda x: (
            type_order.get(str(x.get("type") or "").lower(), 9),
            -float(x.get("percentile") or 0.0),
            x.get("your_rank") or 10**9,
            x.get("name") or "",
        )
    )

    insights = []
    if league_rows:
        overtake_candidates = [
            l for l in league_rows
            if isinstance(l.get("gap_to_next_above"), int) and l.get("gap_to_next_above") is not None and int(l.get("gap_to_next_above") or 0) > 1
        ]
        if not overtake_candidates:
            overtake_candidates = [
                l for l in league_rows
                if isinstance(l.get("gap_to_next_above"), int) and l.get("gap_to_next_above") is not None
            ]
        closest_overtake = min(
            overtake_candidates,
            key=lambda x: x.get("gap_to_next_above", 10**9),
            default=None,
        )
        if closest_overtake and closest_overtake.get("gap_to_next_above") is not None:
            insights.append(
                {
                    "type": "closest_overtake",
                    "text": f"Closest overtake: {closest_overtake['name']} (need {closest_overtake['gap_to_next_above']} pts).",
                }
            )

        pressure_candidates = [
            l for l in league_rows
            if isinstance(l.get("gap_to_next_below"), int) and l.get("gap_to_next_below") is not None and int(l.get("gap_to_next_below") or 0) > 1
        ]
        if not pressure_candidates:
            pressure_candidates = [
                l for l in league_rows
                if isinstance(l.get("gap_to_next_below"), int) and l.get("gap_to_next_below") is not None
            ]
        pressure_league = min(
            pressure_candidates,
            key=lambda x: x.get("gap_to_next_below", 10**9),
            default=None,
        )
        if pressure_league and pressure_league.get("gap_to_next_below") is not None:
            insights.append(
                {
                    "type": "pressure_alert",
                    "text": f"Pressure alert: only {pressure_league['gap_to_next_below']} pts ahead in {pressure_league['name']}.",
                }
            )

        best_league = max(league_rows, key=lambda x: float(x.get("percentile") or 0.0), default=None)
        if best_league:
            insights.append(
                {
                    "type": "best_league",
                    "text": f"Best standing: {best_league['name']} at top {round(100 - float(best_league.get('percentile') or 0.0), 1)}% (rank {best_league['your_rank']}).",
                }
            )

        biggest_climb = max(league_rows, key=lambda x: int(x.get("rank_delta") or 0), default=None)
        if biggest_climb and int(biggest_climb.get("rank_delta") or 0) > 0:
            insights.append(
                {
                    "type": "momentum",
                    "text": f"Best momentum: +{biggest_climb['rank_delta']} places in {biggest_climb['name']}.",
                }
            )

    return {
        "entry_id": entry_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "league_count": len(league_rows),
            "classic_count": len([x for x in league_rows if x.get("type") == "classic"]),
            "h2h_count": len([x for x in league_rows if x.get("type") == "h2h"]),
        },
        "insights": insights,
        "leagues": league_rows,
    }


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


@router.get("/api/fpl/performance/weekly")
def performance_weekly_query(
    entry_id: int = Query(..., ge=1),
    lookback: int = Query(default=8, ge=3, le=20),
):
    return _performance_weekly(entry_id=entry_id, lookback=lookback)


@router.get("/api/fpl/team/{entry_id}/performance/weekly")
def performance_weekly(entry_id: int, lookback: int = Query(default=8, ge=3, le=20)):
    return _performance_weekly(entry_id=entry_id, lookback=lookback)


def _performance_weekly(*, entry_id: int, lookback: int) -> dict:
    history = fetch_json(
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/",
        timeout=20,
        not_found_detail=f"FPL team {entry_id} not found",
        upstream_error_prefix="Could not fetch entry performance history",
    )

    rows = history.get("current", []) or []
    rows = [r for r in rows if _int(r.get("event"), 0) > 0]
    rows.sort(key=lambda r: _int(r.get("event"), 0))
    recent = rows[-lookback:]

    if not recent:
        return {
            "entry_id": entry_id,
            "lookback": lookback,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": "No performance rows available yet.",
            "weeks": [],
            "captain_hit_rate": None,
            "transfer_positive_rate": None,
            "confidence_calibration": {"status": "insufficient-data", "buckets": []},
            "dashboard_card": {},
        }

    transfers = fetch_json(
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/",
        timeout=20,
        not_found_detail=f"FPL team {entry_id} not found",
        upstream_error_prefix="Could not fetch transfers history",
    )
    transfers = transfers or []

    transfer_by_event: dict[int, list[dict]] = defaultdict(list)
    for t in transfers:
        ev = _int(t.get("event"), 0)
        if ev > 0:
            transfer_by_event[ev].append(t)

    live_cache: dict[int, dict[int, int]] = {}

    def _event_live_points(event: int) -> dict[int, int]:
        if event in live_cache:
            return live_cache[event]
        payload = fetch_json(
            f"https://fantasy.premierleague.com/api/event/{event}/live/",
            timeout=20,
            upstream_error_prefix=f"Could not fetch live points for GW {event}",
        )
        points_map: dict[int, int] = {}
        for e in payload.get("elements", []) or []:
            eid = _int(e.get("id"), 0)
            pts = _int((e.get("stats") or {}).get("total_points"), 0)
            if eid > 0:
                points_map[eid] = pts
        live_cache[event] = points_map
        return points_map

    week_rows = []
    captain_hits = 0
    captain_weeks = 0
    transfer_weeks = 0
    transfer_positive_weeks = 0

    total_missed_captain_points = 0.0
    total_transfers_made = 0
    total_transfer_gain_raw = 0.0
    total_transfer_gain_net = 0.0
    total_hit_cost = 0.0
    total_benching_loss = 0.0
    total_xi_opt_gap = 0.0
    bench_order_checks = 0
    bench_order_correct = 0

    calibration_rows: dict[str, list[bool]] = defaultdict(list)

    for row in recent:
        ev = _int(row.get("event"), 0)
        event_points = _int(row.get("points"), 0)
        total_points = _int(row.get("total_points"), 0)
        overall_rank = _int(row.get("overall_rank"), 0)
        transfers_count = _int(row.get("event_transfers"), 0)
        transfers_cost = _int(row.get("event_transfers_cost"), 0)

        picks_payload = fetch_json(
            f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{ev}/picks/",
            timeout=20,
            upstream_error_prefix=f"Could not fetch picks for GW {ev}",
        )
        picks = picks_payload.get("picks", []) or []
        live = _event_live_points(ev)

        starters = [p for p in picks if _int(p.get("position"), 0) <= 11]
        bench = [p for p in picks if _int(p.get("position"), 0) > 11]
        captain_pick = next((p for p in picks if bool(p.get("is_captain"))), None)
        captain_id = _int((captain_pick or {}).get("element"), 0)
        captain_base = live.get(captain_id, 0)
        starter_bases = [live.get(_int(p.get("element"), 0), 0) for p in starters]
        bench_bases = [live.get(_int(p.get("element"), 0), 0) for p in bench]
        all_xi_points = starter_bases + bench_bases
        max_starter_base = max(starter_bases) if starter_bases else 0
        captain_hit = captain_base >= max_starter_base
        missed_captain_points = max(0, max_starter_base - captain_base)

        if captain_id > 0:
            captain_weeks += 1
            if captain_hit:
                captain_hits += 1

        # Transfer baseline: compare in vs out realized points this GW.
        transfer_gain_raw = 0
        for t in transfer_by_event.get(ev, []):
            in_id = _int(t.get("element_in"), 0)
            out_id = _int(t.get("element_out"), 0)
            transfer_gain_raw += live.get(in_id, 0) - live.get(out_id, 0)

        transfer_gain_net = transfer_gain_raw - transfers_cost
        if transfers_count > 0:
            transfer_weeks += 1
            if transfer_gain_net > 0:
                transfer_positive_weeks += 1

        # KPI aggregates
        total_missed_captain_points += missed_captain_points
        total_transfers_made += transfers_count
        total_transfer_gain_raw += transfer_gain_raw
        total_transfer_gain_net += transfer_gain_net
        total_hit_cost += transfers_cost

        starter_sorted_asc = sorted(starter_bases)
        bench_sorted_desc = sorted(bench_bases, reverse=True)
        swaps = min(3, len(starter_sorted_asc), len(bench_sorted_desc))
        benching_loss = sum(max(0, bench_sorted_desc[i] - starter_sorted_asc[i]) for i in range(swaps))
        total_benching_loss += benching_loss

        xi_opt_gap = max(0, sum(sorted(all_xi_points, reverse=True)[:11]) - sum(starter_bases)) if all_xi_points else 0
        total_xi_opt_gap += xi_opt_gap

        # Bench order accuracy on outfield bench slots (12/13/14)
        bench_by_pos = sorted([p for p in bench if _int(p.get("position"), 0) in {12, 13, 14}], key=lambda x: _int(x.get("position"), 99))
        if len(bench_by_pos) == 3:
            bpts = [live.get(_int(p.get("element"), 0), 0) for p in bench_by_pos]
            bench_order_checks += 1
            if bpts[0] >= bpts[1] >= bpts[2]:
                bench_order_correct += 1

        if captain_base - median(starter_bases) >= 3 if starter_bases else False:
            bucket = "high"
        elif captain_base - median(starter_bases) >= 1 if starter_bases else False:
            bucket = "medium"
        else:
            bucket = "low"
        calibration_rows[bucket].append(bool(captain_hit))

        no_transfer_baseline_points = event_points - transfer_gain_net

        week_rows.append(
            {
                "gameweek": ev,
                "event_points": event_points,
                "total_points": total_points,
                "overall_rank": overall_rank,
                "transfers": transfers_count,
                "hit_cost": transfers_cost,
                "captain_points": captain_base * 2,
                "captain_base_points": captain_base,
                "captain_hit": captain_hit,
                "missed_captain_points": round(missed_captain_points, 2),
                "transfer_gain_raw": transfer_gain_raw,
                "transfer_gain_net": transfer_gain_net,
                "benching_loss": round(benching_loss, 2),
                "xi_optimization_gap": round(xi_opt_gap, 2),
                "baseline_no_transfer_points": round(no_transfer_baseline_points, 2),
            }
        )

    week_rows.sort(key=lambda x: x["gameweek"])

    captain_hit_rate = round(captain_hits / captain_weeks, 3) if captain_weeks else None
    transfer_positive_rate = round(transfer_positive_weeks / transfer_weeks, 3) if transfer_weeks else None

    calibration = []
    for b in ("high", "medium", "low"):
        vals = calibration_rows.get(b, [])
        if not vals:
            calibration.append({"bucket": b, "count": 0, "success_rate": None})
        else:
            calibration.append({"bucket": b, "count": len(vals), "success_rate": round(sum(1 for v in vals if v) / len(vals), 3)})

    recent_points = [r["event_points"] for r in week_rows]
    avg_points = round(sum(recent_points) / max(1, len(recent_points)), 2)

    missed_captain_points = round(total_missed_captain_points, 2)
    transfer_roi = round(total_transfer_gain_net / total_transfers_made, 3) if total_transfers_made > 0 else None
    hit_efficiency = round(total_transfer_gain_raw / total_hit_cost, 3) if total_hit_cost > 0 else None
    benching_loss = round(total_benching_loss, 2)
    bench_order_accuracy = round(bench_order_correct / bench_order_checks, 3) if bench_order_checks > 0 else None
    xi_optimization_gap = round(total_xi_opt_gap, 2)

    dashboard_card = {
        "captain_hit_rate": captain_hit_rate,
        "transfer_positive_rate": transfer_positive_rate,
        "missed_captain_points": missed_captain_points,
        "transfer_roi": transfer_roi,
        "hit_efficiency": hit_efficiency,
        "benching_loss": benching_loss,
        "bench_order_accuracy": bench_order_accuracy,
        "xi_optimization_gap": xi_optimization_gap,
        "avg_points_last_n": avg_points,
        "weeks_evaluated": len(week_rows),
        "lookback": lookback,
        "headline": (
            f"Captain hit {round((captain_hit_rate or 0) * 100)}% • "
            f"Transfer weeks positive {round((transfer_positive_rate or 0) * 100)}%"
        ),
    }

    return {
        "entry_id": entry_id,
        "lookback": lookback,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Weekly performance module with captain hit-rate, transfer baseline comparison, and confidence buckets.",
        "weeks": week_rows,
        "captain_hit_rate": captain_hit_rate,
        "transfer_positive_rate": transfer_positive_rate,
        "missed_captain_points": missed_captain_points,
        "transfer_roi": transfer_roi,
        "hit_efficiency": hit_efficiency,
        "benching_loss": benching_loss,
        "bench_order_accuracy": bench_order_accuracy,
        "xi_optimization_gap": xi_optimization_gap,
        "confidence_calibration": {
            "status": "heuristic",
            "buckets": calibration,
            "note": "Buckets are derived from captain edge vs starter median due to limited archived model confidence.",
        },
        "dashboard_card": dashboard_card,
    }


@router.get("/api/fpl/team/{entry_id}/live")
def team_live_view(
    entry_id: int,
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
):
    db = SessionLocal()
    try:
        current_gw = _int(_get_meta(db, "current_gw"), 0)
        target_gw = gameweek or current_gw or _resolve_gameweek(db, None)

        picks_payload, resolved_gw = _fetch_entry_picks_with_fallback(entry_id, target_gw, [current_gw, target_gw - 1])
        picks = picks_payload.get("picks", [])
        if not picks:
            raise HTTPException(status_code=404, detail=f"No picks found for entry {entry_id} in GW {resolved_gw}")

        live_payload = fetch_json(
            f"https://fantasy.premierleague.com/api/event/{resolved_gw}/live/",
            timeout=20,
            upstream_error_prefix="Could not fetch live event data from FPL",
        )
        live_elements = {int(e.get("id")): e for e in (live_payload.get("elements", []) or [])}

        players = db.query(Player).all()
        player_by_id = {p.id: p for p in players}

        starters_live = 0
        bench_live = 0
        total_live = 0
        captain = None
        vice_captain = None
        rows = []

        for p in sorted(picks, key=lambda x: _int(x.get("position"), 99)):
            pid = _int(p.get("element"), 0)
            pos = _int(p.get("position"), 0)
            mult = _int(p.get("multiplier"), 1)
            el = live_elements.get(pid, {})
            stats = el.get("stats", {}) if isinstance(el, dict) else {}
            base_points = _int(stats.get("total_points"), 0)
            live_points = base_points * max(0, mult)
            total_live += live_points
            if pos <= 11:
                starters_live += live_points
            else:
                bench_live += live_points

            if bool(p.get("is_captain")):
                captain = {
                    "id": pid,
                    "name": (player_by_id.get(pid).web_name if player_by_id.get(pid) else f"Player {pid}"),
                    "base_points": base_points,
                    "multiplier": mult,
                    "live_points": live_points,
                }
            if bool(p.get("is_vice_captain")):
                vice_captain = {
                    "id": pid,
                    "name": (player_by_id.get(pid).web_name if player_by_id.get(pid) else f"Player {pid}"),
                    "base_points": base_points,
                    "multiplier": mult,
                    "live_points": live_points,
                }

            rows.append(
                {
                    "id": pid,
                    "name": (player_by_id.get(pid).web_name if player_by_id.get(pid) else f"Player {pid}"),
                    "position": pos,
                    "role": "starter" if pos <= 11 else "bench",
                    "multiplier": mult,
                    "base_points": base_points,
                    "live_points": live_points,
                    "is_captain": bool(p.get("is_captain", False)),
                    "is_vice_captain": bool(p.get("is_vice_captain", False)),
                }
            )

        return {
            "entry_id": entry_id,
            "gameweek": resolved_gw,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "live_summary": {
                "total_live_points": total_live,
                "starters_live_points": starters_live,
                "bench_live_points": bench_live,
            },
            "captain": captain,
            "vice_captain": vice_captain,
            "players": rows,
        }
    finally:
        db.close()
