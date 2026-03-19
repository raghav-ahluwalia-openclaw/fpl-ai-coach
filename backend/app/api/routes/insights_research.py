from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import requests

from .base import *  # noqa: F403
from app.services.captaincy_service import build_captaincy_lab, build_explainability_top

DIGEST_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "creator_digest.json"


def _summarize_text(text: str, max_sentences: int = 3) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return "No detailed summary available yet."
    parts = re.split(r"(?<=[.!?])\s+", clean)
    parts = [p.strip() for p in parts if len(p.strip()) > 20]
    return " ".join(parts[:max_sentences]) if parts else clean[:300]


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


@router.get("/api/fpl/socials")
def fpl_socials(limit: int = Query(default=5, ge=1, le=10), reddit_window: str = Query(default="week", pattern="^(day|week|month|year|all)$")):
    consensus = {
        "generated_at": None,
        "top_topics": [],
        "videos": [],
    }
    if DIGEST_PATH.exists():
        try:
            payload = json.loads(DIGEST_PATH.read_text(encoding="utf-8"))
            consensus = {
                "generated_at": payload.get("generated_at"),
                "top_topics": payload.get("top_topics", [])[: min(limit, 10)],
                "videos": payload.get("videos", [])[:limit],
            }
        except Exception:  # noqa: BLE001
            pass

    reddit_threads = []
    try:
        headers = {"User-Agent": "fpl-ai-coach/1.0 (by /u/fpl_ai_coach)"}
        listing = requests.get(
            f"https://www.reddit.com/r/FantasyPL/top/.json?t={reddit_window}&limit={limit}",
            timeout=20,
            headers=headers,
        )
        listing.raise_for_status()
        children = listing.json().get("data", {}).get("children", [])

        for c in children[:limit]:
            d = c.get("data", {})
            title = d.get("title") or "Untitled"
            permalink = d.get("permalink") or ""
            url = f"https://www.reddit.com{permalink}" if permalink else d.get("url")
            selftext = d.get("selftext") or ""
            score = int(d.get("score") or 0)
            comments_count = int(d.get("num_comments") or 0)

            top_comment_bodies = []
            if permalink:
                try:
                    comments_resp = requests.get(
                        f"https://www.reddit.com{permalink}.json?sort=top&limit=3",
                        timeout=20,
                        headers=headers,
                    )
                    comments_resp.raise_for_status()
                    comments_payload = comments_resp.json()
                    if isinstance(comments_payload, list) and len(comments_payload) > 1:
                        comment_children = comments_payload[1].get("data", {}).get("children", [])
                        for cc in comment_children:
                            body = (cc.get("data", {}) or {}).get("body")
                            if body and isinstance(body, str):
                                top_comment_bodies.append(body)
                except Exception:  # noqa: BLE001
                    pass

            combined = " ".join([selftext] + top_comment_bodies[:2]).strip()
            summary = _summarize_text(combined or title, max_sentences=3)

            reddit_threads.append(
                {
                    "title": title,
                    "url": url,
                    "score": score,
                    "num_comments": comments_count,
                    "summary": summary,
                }
            )
    except Exception as e:  # noqa: BLE001
        reddit_threads = [{"title": "Reddit fetch unavailable", "url": None, "score": 0, "num_comments": 0, "summary": str(e)}]

    return {
        "subreddit": "FantasyPL",
        "reddit_window": reddit_window,
        "creator_consensus": consensus,
        "reddit_threads": reddit_threads,
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
                    "xP": xpts,
                    "expected_points": xpts,
                    "form": round(p.form, 2),
                    "ppg": round(p.points_per_game, 2),
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
