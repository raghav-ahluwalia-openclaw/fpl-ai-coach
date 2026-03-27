from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Query

from app.core.security import rate_limit_admin_ops, require_admin

from .base import (
    POSITION_MAP,
    Fixture,
    Player,
    Team,
    SessionLocal,
    _expected_points,
    _expected_points_horizon,
    _get_meta,
    _reason,
    _resolve_gameweek,
    router,
)
from app.services.captaincy_service import build_captaincy_lab, build_explainability_top

DIGEST_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "creator_digest.json"
ENRICHED_SOCIALS_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "socials_enriched.json"
EXCLUDED_CREATORS = {"fpl focal"}
DRAFT_PATTERNS = {"fpl draft", "draft waiver", "waiver tips", "waiver wire", "draft picks", "draft strategy", "draft gw"}

POS_WEIGHTS = {
    "great": 2, "good": 1, "best": 2, "nailed": 2, "essential": 2, "must": 1, "strong": 1, "haul": 2,
    "buy": 1, "start": 1, "captain": 1, "value": 1, "love": 2, "solid": 1, "safe": 1, "upside": 1,
    "form": 1, "improving": 1, "returns": 1, "clean": 1,
}
NEG_WEIGHTS = {
    "bad": 2, "poor": 2, "awful": 3, "bench": 2, "drop": 1, "sell": 2, "avoid": 2, "injury": 3,
    "injured": 3, "rotation": 2, "risk": 2, "doubt": 2, "blank": 2, "trap": 2, "weak": 1,
    "suspended": 3, "minutes": 1, "concern": 2, "uncertain": 2, "out": 1,
}

OFFICIAL_FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
OFFICIAL_FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"


def _summarize_text(text: str, max_sentences: int = 3) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return "No detailed summary available yet."
    parts = re.split(r"(?<=[.!?])\s+", clean)
    parts = [p.strip() for p in parts if len(p.strip()) > 20]
    return " ".join(parts[:max_sentences]) if parts else clean[:300]


def _sentiment_score(text: str) -> int:
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    pos = sum(POS_WEIGHTS.get(w, 0) for w in words)
    neg = sum(NEG_WEIGHTS.get(w, 0) for w in words)
    return int(pos - neg)


def _sentiment_label(score: int) -> str:
    if score >= 2:
        return "positive"
    if score <= -2:
        return "negative"
    return "neutral"


def _extract_player_mentions(text: str, player_names: list[str], max_items: int = 8) -> list[dict]:
    raw = (text or "")
    low = raw.lower()
    mentions = []
    for name in player_names:
        n = (name or "").strip()
        if len(n) < 3:
            continue

        pattern = re.compile(rf"\b{re.escape(n.lower())}\b")
        matches = list(pattern.finditer(low))
        if not matches:
            continue

        local_scores = []
        for m in matches[:6]:
            a = max(0, m.start() - 80)
            b = min(len(low), m.end() + 80)
            ctx = low[a:b]
            local_scores.append(_sentiment_score(ctx))

        score = int(round(sum(local_scores) / max(1, len(local_scores))))
        mentions.append({"name": n, "sentiment": _sentiment_label(score), "score": score})

    mentions.sort(key=lambda x: abs(int(x.get("score", 0))), reverse=True)
    return mentions[:max_items]


def _is_draft_centric_video(v: dict) -> bool:
    title = str((v or {}).get("title") or "").lower()
    hay = title
    if any(p in hay for p in DRAFT_PATTERNS):
        return True
    return bool(re.search(r"\bdraft\b", hay))


def _dedupe_videos_by_exact_title(videos: list[dict]) -> list[dict]:
    """Drop duplicate creator rows that point to videos with the same exact title.

    Normalization is intentionally light (strip + lowercase) to match "exact name"
    dedupe while handling accidental casing/spacing differences.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for v in videos:
        title = str((v or {}).get("title") or "").strip().lower()
        if not title:
            out.append(v)
            continue
        if title in seen:
            continue
        seen.add(title)
        out.append(v)
    return out


def _official_news_payload(limit: int = 8) -> dict:
    """Build official FPL-driven updates for fixture schedule changes + player availability."""
    try:
        headers = {"User-Agent": "fpl-ai-coach/1.0"}
        b_resp = requests.get(OFFICIAL_FPL_BOOTSTRAP_URL, timeout=20, headers=headers)
        b_resp.raise_for_status()
        bootstrap = b_resp.json()

        f_resp = requests.get(OFFICIAL_FPL_FIXTURES_URL, timeout=20, headers=headers)
        f_resp.raise_for_status()
        fixtures = f_resp.json()

        teams = {int(t.get("id")): str(t.get("short_name") or t.get("name") or "") for t in bootstrap.get("teams", [])}

        severity_order = {"i": 0, "s": 1, "u": 2, "d": 3, "a": 4}
        injuries = []
        for e in bootstrap.get("elements", []):
            status = str(e.get("status") or "a").lower()
            news = str(e.get("news") or "").strip()
            chance_next = e.get("chance_of_playing_next_round")
            is_flagged = status != "a" or (isinstance(chance_next, int) and chance_next < 100)
            if not is_flagged:
                continue

            team_short = teams.get(int(e.get("team") or 0), "")
            player = str(e.get("web_name") or e.get("first_name") or "Unknown")
            try:
                selected_by_percent = float(e.get("selected_by_percent") or 0.0)
            except Exception:  # noqa: BLE001
                selected_by_percent = 0.0

            injuries.append(
                {
                    "player": player,
                    "team": team_short,
                    "status": status,
                    "chance_of_playing_next_round": chance_next,
                    "selected_by_percent": selected_by_percent,
                    "news": news or "Flagged in official FPL data",
                }
            )

        # User requested ordering by FPL ownership %. Highest-owned flagged players first.
        injuries.sort(
            key=lambda x: (
                -float(x.get("selected_by_percent") or 0.0),
                severity_order.get(str(x.get("status") or "a"), 9),
                int(x.get("chance_of_playing_next_round") or 100),
                str(x.get("player") or ""),
            )
        )

        fixture_updates = []
        for fx in fixtures:
            if not isinstance(fx, dict):
                continue
            if not bool(fx.get("provisional_start_time")):
                continue
            if bool(fx.get("finished")):
                continue

            h = teams.get(int(fx.get("team_h") or 0), "?")
            a = teams.get(int(fx.get("team_a") or 0), "?")
            fixture_updates.append(
                {
                    "gw": fx.get("event"),
                    "fixture": f"{h} vs {a}",
                    "kickoff_time": fx.get("kickoff_time"),
                    "note": "Kickoff marked provisional by official FPL API (possible schedule change).",
                }
            )

        fixture_updates.sort(key=lambda x: str(x.get("kickoff_time") or ""))

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Official FPL API",
            "fixture_updates": fixture_updates[:limit],
            "injuries": injuries[: max(limit, 10)],
        }
    except Exception as e:  # noqa: BLE001
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Official FPL API",
            "fixture_updates": [],
            "injuries": [],
            "error": str(e),
        }


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
    creator_coverage = {
        k: v
        for k, v in (payload.get("creator_coverage", {}) or {}).items()
        if str(k or "").strip().lower() not in EXCLUDED_CREATORS
    }
    videos_all = payload.get("videos", [])
    videos_all = [
        v for v in videos_all
        if str((v or {}).get("creator") or "").strip().lower() not in EXCLUDED_CREATORS
        and not _is_draft_centric_video(v)
    ]
    videos = videos_all[:limit] if include_videos else []

    return {
        "generated_at": payload.get("generated_at"),
        "creator_coverage": creator_coverage,
        "top_topics": top_topics,
        "top_title_terms": payload.get("top_title_terms", [])[: min(limit, 15)],
        "top_player_mentions": payload.get("top_player_mentions", [])[: min(limit, 20)],
        "videos": videos,
        "source": str(DIGEST_PATH),
    }


@router.post(
    "/api/fpl/socials/refresh",
    dependencies=[Depends(require_admin), Depends(rate_limit_admin_ops)],
)
def fpl_socials_refresh(videos_per_creator: int = Query(default=4, ge=1, le=8)):
    project_root = Path(__file__).resolve().parents[4]
    digest_script = project_root / "scripts" / "fpl_creator_digest.py"
    enrich_script = project_root / "scripts" / "fpl_socials_enrich.py"

    if not digest_script.exists() or not enrich_script.exists():
        raise HTTPException(status_code=500, detail="Socials refresh scripts are missing")

    try:
        digest = subprocess.run(
            ["python3", str(digest_script), "--videos-per-creator", str(videos_per_creator)],
            cwd=str(project_root),
            text=True,
            capture_output=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stage": "digest",
            "videos_per_creator": videos_per_creator,
            "message": "Digest refresh timed out",
        }

    if digest.returncode != 0:
        return {
            "ok": False,
            "stage": "digest",
            "videos_per_creator": videos_per_creator,
            "message": "Digest refresh failed",
            "error": (digest.stderr.strip() or digest.stdout.strip())[:1200],
        }

    try:
        enrich = subprocess.run(
            ["python3", str(enrich_script)],
            cwd=str(project_root),
            text=True,
            capture_output=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stage": "enrich",
            "videos_per_creator": videos_per_creator,
            "digest": digest.stdout.strip().splitlines()[-3:],
            "message": "Enrichment refresh timed out",
        }

    if enrich.returncode != 0:
        return {
            "ok": False,
            "stage": "enrich",
            "videos_per_creator": videos_per_creator,
            "digest": digest.stdout.strip().splitlines()[-3:],
            "message": "Enrichment refresh failed",
            "error": (enrich.stderr.strip() or enrich.stdout.strip())[:1200],
        }

    return {
        "ok": True,
        "videos_per_creator": videos_per_creator,
        "digest": digest.stdout.strip().splitlines()[-3:],
        "enrich": enrich.stdout.strip().splitlines()[-3:],
        "message": "Socials data refreshed successfully",
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
            top_topics = payload.get("top_topics", [])[: min(limit, 10)]

            # Prefer transcript-enriched dataset if present.
            if ENRICHED_SOCIALS_PATH.exists():
                enriched = json.loads(ENRICHED_SOCIALS_PATH.read_text(encoding="utf-8"))
                evideos_all = enriched.get("videos", [])
                evideos_all = [
                    x for x in evideos_all
                    if str((x or {}).get("creator") or "").strip().lower() not in EXCLUDED_CREATORS
                    and not _is_draft_centric_video(x)
                ]
                evideos_all = sorted(
                    evideos_all,
                    key=lambda x: (str(x.get("upload_date") or ""), int(x.get("view_count") or 0)),
                    reverse=True,
                )
                evideos_all = _dedupe_videos_by_exact_title(evideos_all)
                # diversify feed: max 2 videos per creator
                creator_counts: dict[str, int] = {}
                evideos = []
                for v in evideos_all:
                    creator = str(v.get("creator") or "unknown")
                    if creator_counts.get(creator, 0) >= 2:
                        continue
                    evideos.append(v)
                    creator_counts[creator] = creator_counts.get(creator, 0) + 1
                    if len(evideos) >= limit:
                        break

                videos = []
                for v in evideos:
                    videos.append(
                        {
                            "creator": v.get("creator"),
                            "title": v.get("title"),
                            "url": v.get("url"),
                            "upload_date": v.get("upload_date"),
                            "view_count": int(v.get("view_count") or 0),
                            "summary": v.get("summary") or "",
                            "summary_struct": v.get("summary_struct") or {},
                            "transcript": v.get("transcript") or "",
                            "player_mentions": v.get("player_mentions") or [],
                            "sentiment": v.get("sentiment") or {"label": "neutral", "score": 0},
                            "transcript_path": v.get("transcript_path"),
                        }
                    )
                consensus = {
                    "generated_at": enriched.get("generated_at") or payload.get("generated_at"),
                    "top_topics": top_topics,
                    "videos": videos,
                }
            else:
                raw_videos_all = payload.get("videos", [])
                raw_videos_all = [
                    x for x in raw_videos_all
                    if str((x or {}).get("creator") or "").strip().lower() not in EXCLUDED_CREATORS
                    and not _is_draft_centric_video(x)
                ]
                raw_videos_all = sorted(
                    raw_videos_all,
                    key=lambda x: (str(x.get("upload_date") or ""), int(x.get("view_count") or 0)),
                    reverse=True,
                )
                raw_videos_all = _dedupe_videos_by_exact_title(raw_videos_all)
                creator_counts: dict[str, int] = {}
                raw_videos = []
                for v in raw_videos_all:
                    creator = str(v.get("creator") or "unknown")
                    if creator_counts.get(creator, 0) >= 2:
                        continue
                    raw_videos.append(v)
                    creator_counts[creator] = creator_counts.get(creator, 0) + 1
                    if len(raw_videos) >= limit:
                        break

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
                            "upload_date": v.get("upload_date"),
                            "view_count": int(v.get("view_count") or 0),
                            "summary": _summarize_text(combined, max_sentences=5),
                            "summary_struct": {},
                            "transcript": "",
                            "player_mentions": _extract_player_mentions(combined, player_names, max_items=8),
                            "sentiment": {
                                "label": _sentiment_label(sentiment_score),
                                "score": sentiment_score,
                            },
                        }
                    )

                consensus = {
                    "generated_at": payload.get("generated_at"),
                    "top_topics": top_topics,
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

    official_news = _official_news_payload(limit=max(6, limit))

    return {
        "subreddit": "FantasyPL",
        "reddit_window": reddit_window,
        "youtube_creators": consensus,
        "reddit_threads": reddit_threads,
        "official_news": official_news,
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
            xpts3 = _expected_points_horizon(p, fixtures, gw, horizon=3)
            xpts5 = _expected_points_horizon(p, fixtures, gw, horizon=5)
            top.append(
                {
                    "id": p.id,
                    "name": p.web_name,
                    "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                    "price": round(p.now_cost / 10.0, 1),
                    "xP": xpts,
                    "expected_points": xpts,
                    "expected_points_1": round(xpts, 2),
                    "expected_points_3": round(xpts3, 2),
                    "expected_points_5": round(xpts5, 2),
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
        teams = db.query(Team).all()
        team_names = {int(t.id): str(t.short_name or t.name or t.id) for t in teams}
        gw = _resolve_gameweek(db, gameweek)
        return build_explainability_top(players, fixtures, gw, limit, team_names=team_names)
    finally:
        db.close()
