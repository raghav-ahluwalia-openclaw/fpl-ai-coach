from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal, engine
from app.db.models import Fixture, Meta, Player, Team, UserSquadPick
from app.schemas import (
    POSITION_MAP,
    Pick,
    RankHistoryPoint,
    RankHistoryResponse,
    Recommendation,
    TargetPlayer,
    TargetsResponse,
    TeamRecommendation,
)
from app.services.http_client import fetch_json
from app.services.scoring import (
    _availability_factor,
    _build_lineup_from_squad,
    _build_target_player,
    _captain_weight,
    _choose_captains,
    _expected_points,
    _expected_points_horizon,
    _fixture_badge_for_gw,
    _fixture_count_for_gw,
    _fixture_factor,
    _fixture_rows_for_gw,
    _float,
    _int,
    _minutes_factor,
    _pick_to_response,
    _position_base,
    _reason,
    _strategy_config,
    _target_tier,
)

FPL_BOOTSTRAP_URL = os.getenv("FPL_BOOTSTRAP_URL", "https://fantasy.premierleague.com/api/bootstrap-static/")
FPL_FIXTURES_URL = os.getenv("FPL_FIXTURES_URL", "https://fantasy.premierleague.com/api/fixtures/")
INGEST_TTL_MINUTES = int(os.getenv("INGEST_TTL_MINUTES", "30"))
GAMEWEEK_META_SYNC_CHECK_MINUTES = int(os.getenv("GAMEWEEK_META_SYNC_CHECK_MINUTES", "30"))
GAMEWEEK_PRE_DEADLINE_SYNC_HOURS = int(os.getenv("GAMEWEEK_PRE_DEADLINE_SYNC_HOURS", "24"))
GAMEWEEK_POST_MATCHDAY_BUFFER_HOURS = int(os.getenv("GAMEWEEK_POST_MATCHDAY_BUFFER_HOURS", "2"))

logger = logging.getLogger("fpl.api")
router = APIRouter()


def _set_meta(db, key: str, value: str) -> None:
    row = db.get(Meta, key)
    if row is None:
        row = Meta(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)


def _get_meta(db, key: str) -> Optional[str]:
    row = db.get(Meta, key)
    return row.value if row else None


def _parse_meta_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _load_gw_sync_markers(db) -> dict:
    raw = _get_meta(db, "gw_meta_sync_markers")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_gw_sync_markers(db, markers: dict) -> None:
    _set_meta(db, "gw_meta_sync_markers", json.dumps(markers, separators=(",", ":")))


def _sync_gameweek_meta_if_needed(db) -> None:
    """Refresh current/next GW meta only at key lifecycle points.

    Sync points:
    1) Start of new GW (a couple hours after previous GW last kickoff)
    2) 24h before next transfer deadline
    3) End of each match day in current GW (after buffer)

    Also allows a safety sync when metadata is missing/invalid.
    """

    now = datetime.now(timezone.utc)
    local_current = _int(_get_meta(db, "current_gw"), 0)
    local_next = _int(_get_meta(db, "next_gw"), 0)
    urgent_repair_needed = local_current <= 0 or local_next <= 0 or local_next <= local_current

    last_check_at = _parse_meta_datetime(_get_meta(db, "last_gw_meta_sync_check_at"))
    if (
        last_check_at
        and (now - last_check_at) < timedelta(minutes=GAMEWEEK_META_SYNC_CHECK_MINUTES)
        and not urgent_repair_needed
    ):
        return

    try:
        bootstrap = fetch_json(
            FPL_BOOTSTRAP_URL,
            timeout=20,
            upstream_error_prefix="FPL bootstrap source unavailable",
        )
        fixtures_payload = fetch_json(
            FPL_FIXTURES_URL,
            timeout=20,
            upstream_error_prefix="FPL fixtures source unavailable",
        )

        events = bootstrap.get("events", [])
        fixtures = fixtures_payload if isinstance(fixtures_payload, list) else []

        current_event = next((e for e in events if e.get("is_current")), None)
        next_event = next((e for e in events if e.get("is_next")), None)

        fresh_current = _int((current_event or {}).get("id"), 0) or None
        fresh_next = _int((next_event or {}).get("id"), 0) or None
        fresh_deadline = (next_event or {}).get("deadline_time")
        deadline_dt = _parse_meta_datetime(str(fresh_deadline) if fresh_deadline else None)

        # If official API marks current GW finished, treat next GW as active planning GW.
        current_finished = bool((current_event or {}).get("finished"))
        effective_current = fresh_next if (current_finished and fresh_next) else fresh_current

        markers = _load_gw_sync_markers(db)
        marker_key = None
        reason = None

        # Safety sync if metadata is clearly invalid/missing.
        if local_current <= 0 or local_next <= 0 or local_next <= local_current:
            marker_key = f"meta_invalid:{fresh_current or 'x'}:{fresh_next or 'x'}"
            reason = "metadata_invalid"

        # Immediate transition sync once a GW is officially finished.
        if marker_key is None and current_finished and fresh_next and local_current != fresh_next:
            marker_key = f"gw_transition:{fresh_next}"
            reason = "gw_completed_transition"

        # 1) Start of new GW: ~2h after previous GW's final kickoff.
        if marker_key is None and fresh_current and fresh_current > 1:
            prev_gw = fresh_current - 1
            prev_event = next((e for e in events if _int(e.get("id"), 0) == prev_gw), None)
            prev_fixtures = [f for f in fixtures if _int(f.get("event"), 0) == prev_gw and f.get("kickoff_time")]
            prev_kickoffs = [
                _parse_meta_datetime(str(f.get("kickoff_time")))
                for f in prev_fixtures
                if _parse_meta_datetime(str(f.get("kickoff_time"))) is not None
            ]
            last_prev_kickoff = max(prev_kickoffs) if prev_kickoffs else None
            after_prev_window = bool(
                last_prev_kickoff
                and now >= last_prev_kickoff + timedelta(hours=GAMEWEEK_POST_MATCHDAY_BUFFER_HOURS)
            )
            prev_finished = bool((prev_event or {}).get("finished"))
            k = f"gw_start:{fresh_current}"
            if prev_finished and after_prev_window and k not in markers:
                marker_key = k
                reason = "gw_start_window"

        # 2) 24h before next transfer deadline.
        if marker_key is None and fresh_next and deadline_dt is not None:
            secs_to_deadline = (deadline_dt - now).total_seconds()
            k = f"deadline_24h:{fresh_next}"
            if 0 <= secs_to_deadline <= (GAMEWEEK_PRE_DEADLINE_SYNC_HOURS * 3600) and k not in markers:
                marker_key = k
                reason = "pre_deadline_window"

        # 3) End of each match day in current GW (once per UTC match date).
        if marker_key is None and fresh_current:
            current_fixtures = [f for f in fixtures if _int(f.get("event"), 0) == fresh_current and f.get("kickoff_time")]
            by_date: dict[str, list[dict]] = {}
            for fx in current_fixtures:
                kdt = _parse_meta_datetime(str(fx.get("kickoff_time")))
                if not kdt:
                    continue
                date_key = kdt.date().isoformat()
                by_date.setdefault(date_key, []).append(fx)

            for date_key, day_fixtures in sorted(by_date.items()):
                k = f"matchday_end:{fresh_current}:{date_key}"
                if k in markers:
                    continue
                kickoffs = [
                    _parse_meta_datetime(str(fx.get("kickoff_time")))
                    for fx in day_fixtures
                    if _parse_meta_datetime(str(fx.get("kickoff_time"))) is not None
                ]
                if not kickoffs:
                    continue
                day_last_kickoff = max(kickoffs)
                day_done = all(bool(fx.get("finished")) for fx in day_fixtures)
                window_open = now >= day_last_kickoff + timedelta(hours=GAMEWEEK_POST_MATCHDAY_BUFFER_HOURS)
                if day_done and window_open:
                    marker_key = k
                    reason = "matchday_end_window"
                    break

        if marker_key is not None:
            if effective_current is not None:
                _set_meta(db, "current_gw", str(effective_current))
            if fresh_next is not None:
                _set_meta(db, "next_gw", str(fresh_next))
            if fresh_deadline:
                _set_meta(db, "next_deadline_utc", str(fresh_deadline))
            _set_meta(db, "last_gw_meta_sync_at", now.isoformat())
            markers[marker_key] = now.isoformat()
            _save_gw_sync_markers(db, markers)
            logger.info(
                "gameweek meta synced",
                extra={
                    "reason": reason,
                    "marker": marker_key,
                    "current_gw_effective": effective_current,
                    "current_gw_official": fresh_current,
                    "next_gw": fresh_next,
                    "next_deadline_utc": fresh_deadline,
                },
            )

        _set_meta(db, "last_gw_meta_sync_check_at", now.isoformat())
        db.commit()
    except (HTTPException, SQLAlchemyError, Exception):  # noqa: BLE001
        db.rollback()
        # Never fail user requests due to metadata refresh errors.
        logger.exception("gameweek meta sync skipped due to error")


def _resolve_gameweek(db, requested_gw: Optional[int]) -> int:
    if requested_gw:
        return requested_gw
    _sync_gameweek_meta_if_needed(db)
    next_gw = _int(_get_meta(db, "next_gw"), 0)
    current_gw = _int(_get_meta(db, "current_gw"), 0)
    return next_gw or current_gw or 1


def _is_recently_ingested(db, ttl_minutes: int) -> bool:
    last_ingested_at = _get_meta(db, "last_ingested_at")
    if not last_ingested_at:
        return False
    try:
        parsed = datetime.fromisoformat(last_ingested_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return False

    return (datetime.now(timezone.utc) - parsed).total_seconds() < (ttl_minutes * 60)


def _fetch_entry_picks(entry_id: int, gameweek: int) -> dict:
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gameweek}/picks/"
    return fetch_json(
        url,
        timeout=20,
        not_found_detail=f"FPL team {entry_id} not found for GW {gameweek}",
        upstream_error_prefix="Could not fetch team picks from FPL",
    )


def _fetch_entry_picks_with_fallback(entry_id: int, preferred_gw: int, fallback_gws: List[int]) -> Tuple[dict, int]:
    seen = set()
    candidates = [preferred_gw] + fallback_gws
    for gw in candidates:
        if gw in seen or gw <= 0:
            continue
        seen.add(gw)
        try:
            payload = _fetch_entry_picks(entry_id, gw)
            return payload, gw
        except HTTPException as e:
            if e.status_code == 404:
                continue
            raise
    raise HTTPException(status_code=404, detail=f"FPL team {entry_id} not found for tested gameweeks: {sorted(seen)}")


# Export all shared symbols (including internal helper names) for route modules.
__all__ = [name for name in globals() if not name.startswith("__")]
