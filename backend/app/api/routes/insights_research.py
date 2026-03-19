from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .base import *  # noqa: F403
from app.services.captaincy_service import build_captaincy_lab, build_explainability_top

DIGEST_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "creator_digest.json"


@router.get("/api/fpl/content-consensus")
def content_consensus(limit: int = Query(default=10, ge=1, le=50), include_videos: bool = Query(default=True)):
    if not DIGEST_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Creator digest not found. "
                "Run ./scripts/fpl_creator_digest.py from project root first."
            ),
        )

    try:
        payload = json.loads(DIGEST_PATH.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to parse creator digest: {e}")

    top_topics = payload.get("top_topics", [])[:limit]
    videos = payload.get("videos", [])[:limit] if include_videos else []

    return {
        "generated_at": payload.get("generated_at"),
        "creator_coverage": payload.get("creator_coverage", {}),
        "top_topics": top_topics,
        "top_title_terms": payload.get("top_title_terms", [])[: min(limit, 15)],
        "top_player_mentions": payload.get("top_player_mentions", [])[: min(limit, 20)],
        "videos": videos,
        "source": str(DIGEST_PATH),
    }


@router.get("/api/fpl/top")
def top_players(limit: int = Query(default=20, ge=1, le=100)):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, None)

        scored = []
        for p in players:
            xpts = _expected_points(p, fixtures, gw)
            scored.append((xpts, p))

        scored.sort(key=lambda x: x[0], reverse=True)

        top = []
        for xpts, p in scored[:limit]:
            top.append(
                {
                    "id": p.id,
                    "name": p.web_name,
                    "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                    "price": round(p.now_cost / 10.0, 1),
                    "expected_points": xpts,
                    "reason": _reason(p, xpts),
                }
            )

        return {
            "count": len(top),
            "next_gw": gw,
            "players": top,
            "last_ingested_at": _get_meta(db, "last_ingested_at"),
        }
    finally:
        db.close()


@router.get("/api/fpl/captaincy-lab")
def captaincy_lab(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    limit: int = Query(default=10, ge=3, le=20),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, gameweek)
        return build_captaincy_lab(players, fixtures, gw, limit)
    finally:
        db.close()


@router.get("/api/fpl/explainability/top")
def explainability_top(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    limit: int = Query(default=20, ge=5, le=50),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, gameweek)
        return build_explainability_top(players, fixtures, gw, limit)
    finally:
        db.close()
