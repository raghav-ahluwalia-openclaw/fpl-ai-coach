from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import requests

from .base import *  # noqa: F403
from app.services.captaincy_service import build_captaincy_lab, build_explainability_top

DIGEST_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "creator_digest.json"

POS_WORDS = {
    "great", "good", "best", "nailed", "essential", "must", "strong", "haul", "buy", "start", "captain", "value", "love", "solid", "safe", "upside", "form"
}
NEG_WORDS = {
    "bad", "poor", "awful", "bench", "drop", "sell", "avoid", "injury", "injured", "rotation", "risk", "doubt", "blank", "trap", "weak"
}


def _summarize_text(text: str, max_sentences: int = 3) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return "No detailed summary available yet."
    parts = re.split(r"(?<=[.!?])\s+", clean)
    parts = [p.strip() for p in parts if len(p.strip()) > 20]
    return " ".join(parts[:max_sentences]) if parts else clean[:300]


def _sentiment_score(text: str) -> int:
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    pos = sum(1 for w in words if w in POS_WORDS)
    neg = sum(1 for w in words if w in NEG_WORDS)
    return pos - neg


def _sentiment_label(score: int) -> str:
    if score >= 2:
        return "positive"
    if score <= -2:
        return "negative"
    return "neutral"


def _extract_player_mentions(text: str, player_names: list[str], max_items: int = 8) -> list[dict]:
    low = (text or "").lower()
    mentions = []
    for name in player_names:
        n = (name or "").strip()
        if len(n) < 3:
            continue
        if re.search(rf"\b{re.escape(n.lower())}\b", low):
            score = _sentiment_score(low)
            mentions.append({"name": n, "sentiment": _sentiment_label(score), "score": score})
        if len(mentions) >= max_items:
            break
    return mentions


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
    db = SessionLocal()
    try:
        player_names = [p.web_name for p in db.query(Player).all()]
    finally:
        db.close()

    consensus = {
        "generated_at": None,
        "top_topics": [],
        "videos": [],
    }
    if DIGEST_PATH.exists():
        try:
            payload = json.loads(DIGEST_PATH.read_text(encoding="utf-8"))
            raw_videos = payload.get("videos", [])[:limit]
            videos = []
            for v in raw_videos:
                title = v.get("title") or "Untitled"
                base_summary = v.get("summary") or ""
                tags = v.get("transcript_tags") or []
                transcript_hint = " ".join(tags[:20]) if isinstance(tags, list) else ""
                combined = " ".join([title, base_summary, transcript_hint]).strip()
                sentiment_score = _sentiment_score(combined)
                videos.append(
                    {
                        "creator": v.get("creator"),
                        "title": title,
                        "url": v.get("url"),
                        "summary": _summarize_text(combined, max_sentences=5),
                        "player_mentions": _extract_player_mentions(combined, player_names, max_items=8),
                        "sentiment": {
                            "label": _sentiment_label(sentiment_score),
                            "score": sentiment_score,
                        },
                    }
                )

            consensus = {
                "generated_at": payload.get("generated_at"),
                "top_topics": payload.get("top_topics", [])[: min(limit, 10)],
                "videos": videos,
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

            combined = " ".join([title, selftext] + top_comment_bodies[:2]).strip()
            sentiment_score = _sentiment_score(combined)
            reddit_threads.append(
                {
                    "title": title,
                    "url": url,
                    "score": score,
                    "num_comments": comments_count,
                    "summary": _summarize_text(combined or title, max_sentences=5),
                    "player_mentions": _extract_player_mentions(combined, player_names, max_items=8),
                    "sentiment": {
                        "label": _sentiment_label(sentiment_score),
                        "score": sentiment_score,
                    },
                }
            )
    except Exception as e:  # noqa: BLE001
        reddit_threads = [{
            "title": "Reddit fetch unavailable",
            "url": None,
            "score": 0,
            "num_comments": 0,
            "summary": str(e),
            "player_mentions": [],
            "sentiment": {"label": "neutral", "score": 0},
        }]

    return {
        "subreddit": "FantasyPL",
        "reddit_window": reddit_window,
        "youtube_creators": consensus,
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
