from __future__ import annotations

from typing import Optional

from .base import *  # noqa: F403
from app.services.planner_service import build_chip_planner, build_rival_intelligence


@router.get("/api/fpl/chip-planner")
def chip_planner(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    horizon: int = Query(default=6, ge=3, le=10),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, gameweek)
        return build_chip_planner(players, fixtures, gw, horizon)
    finally:
        db.close()


@router.get("/api/fpl/rival-intelligence")
def rival_intelligence(
    entry_id: int = Query(..., ge=1),
    rival_entry_id: int = Query(..., ge=1),
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
):
    db = SessionLocal()
    try:
        gw = _resolve_gameweek(db, gameweek)
        current_gw = _int(_get_meta(db, "current_gw"), 0)

        players = db.query(Player).all()
        fixtures = db.query(Fixture).all()
        return build_rival_intelligence(
            db=db,
            players=players,
            fixtures=fixtures,
            entry_id=entry_id,
            rival_entry_id=rival_entry_id,
            gameweek=gw,
            current_gw=current_gw,
        )
    finally:
        db.close()
