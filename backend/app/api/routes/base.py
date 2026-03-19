from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
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


def _resolve_gameweek(db, requested_gw: Optional[int]) -> int:
    if requested_gw:
        return requested_gw
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
