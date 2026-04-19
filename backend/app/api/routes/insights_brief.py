from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .base import (
    Fixture,
    Player,
    SessionLocal,
    get_db,
    _fixture_count_for_gw,
    router,
)
from .insights import recommendation, recommendation_ml
from .insights_planner import chip_planner
from .insights_research import captaincy_lab
from app.services.ml_recommender import DEFAULT_MODEL_VERSION
from app.services.ttl_cache import api_ttl_cache

DIGEST_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "creator_digest.json"


@router.get("/api/fpl/weekly-digest-card")
def weekly_digest_card(
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
    db: Session = Depends(get_db),
):
    cache_key = ("weekly_digest_card", mode, model_version)

    def _build() -> dict:
        # Cache builders run outside the request lifecycle, so we pass db explicitly.
        brief = weekly_brief(gameweek=None, mode=mode, model_version=model_version, db=db)
        cap = captaincy_lab(gameweek=None, limit=3, db=db)
        chip = chip_planner(gameweek=brief["gameweek"], horizon=6, db=db)

        final = brief["final"]
        safe_top3 = cap.get("safe_captains", [])[:3]
        upside_top3 = cap.get("upside_captains", [])[:3]

        lines = [
            f"GW{brief['gameweek']} Weekly Digest ({mode})",
            f"Captain: {final['captain']} | Vice: {final['vice_captain']}",
            f"Transfer: {final['transfer_out']} -> {final['transfer_in']}",
            f"Chip: {chip.get('recommendation')} (alt: {chip.get('alternative')}, conf: {chip.get('confidence')})",
            "Safe C picks: " + ", ".join(p.get("name", "") for p in safe_top3),
            "Upside C picks: " + ", ".join(p.get("name", "") for p in upside_top3),
        ]

        return {
            "title": f"GW{brief['gameweek']} Weekly Digest",
            "mode": mode,
            "final": final,
            "safe_captains_top3": safe_top3,
            "upside_captains_top3": upside_top3,
            "chip": {
                "recommendation": chip.get("recommendation"),
                "alternative": chip.get("alternative"),
                "confidence": chip.get("confidence"),
                "scores": chip.get("chip_scores"),
            },
            "rationale": brief.get("rationale", [])[:4],
            "card": {
                "version": "v3",
                "sections": {
                    "captaincy": {
                        "captain": final["captain"],
                        "vice": final["vice_captain"],
                    },
                    "transfer": {
                        "out": final["transfer_out"],
                        "in": final["transfer_in"],
                    },
                    "chip": {
                        "play": chip.get("recommendation"),
                        "alternative": chip.get("alternative"),
                        "confidence": chip.get("confidence"),
                    },
                },
                "lines": lines,
                "meta": {
                    "gameweek": brief["gameweek"],
                    "generated_at": brief.get("generated_at"),
                },
            },
            "summary": "Rich weekly digest payload for messaging cards and Telegram reminders.",
        }

    return api_ttl_cache.get_or_set(cache_key, _build, ttl_seconds=90)


@router.get("/api/fpl/weekly-brief")
def weekly_brief(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
    db: Session = Depends(get_db),
):
    cache_key = ("weekly_brief", gameweek, mode, model_version)

    def _build() -> dict:
        base = recommendation(gameweek=gameweek, db=db)

        ml = None
        try:
            ml = recommendation_ml(gameweek=gameweek, force_train=False, model_version=model_version, db=db)
        except HTTPException:
            ml = None

        consensus = None
        if DIGEST_PATH.exists():
            try:
                payload = json.loads(DIGEST_PATH.read_text(encoding="utf-8"))
                consensus = {
                    "generated_at": payload.get("generated_at"),
                    "top_topics": payload.get("top_topics", [])[:5],
                    "top_videos": payload.get("videos", [])[:5],
                }
            except Exception:  # noqa: BLE001
                consensus = None

        min_ml_confidence = 0.62
        ml_eligible = ml is not None and ml.confidence >= min_ml_confidence

        if mode == "safe":
            final_captain = base.captain
            final_vice = base.vice_captain
            transfer_out, transfer_in = base.transfer_out, base.transfer_in
        elif mode == "aggressive" and ml_eligible:
            final_captain = ml.captain
            final_vice = ml.vice_captain
            transfer_out, transfer_in = ml.transfer_out, ml.transfer_in
        else:
            final_captain = base.captain if not ml_eligible else (base.captain if base.confidence >= ml.confidence else ml.captain)
            final_vice = base.vice_captain if not ml_eligible else (base.vice_captain if base.confidence >= ml.confidence else ml.vice_captain)
            transfer_out, transfer_in = base.transfer_out, base.transfer_in
            if ml_eligible and ml.transfer_in == base.transfer_in:
                transfer_out, transfer_in = ml.transfer_out, ml.transfer_in

        rationale = [
            f"Mode: {mode}",
            f"Baseline captain: {base.captain}",
            f"ML captain: {ml.captain if ml else 'n/a'}",
            f"Creator consensus top topics: {', '.join(t.get('topic', '') for t in (consensus or {}).get('top_topics', [])[:3]) or 'n/a'}",
        ]
        if ml is not None and not ml_eligible:
            rationale.append(f"ML confidence below threshold ({ml.confidence:.2f} < {min_ml_confidence:.2f}); baseline fallback applied")

        badge_map = {
            "captain": "SGW",
            "vice_captain": "SGW",
            "transfer_out": "SGW",
            "transfer_in": "SGW",
        }
        try:
            fixtures = db.query(Fixture).all()
            players = db.query(Player).all()
            by_name = {p.web_name: p for p in players}

            def badge_for_name(name: str) -> str:
                p = by_name.get(name)
                if not p:
                    return "SGW"
                count = _fixture_count_for_gw(p, fixtures, base.gameweek)
                if count >= 2:
                    return "DGW"
                if count == 0:
                    return "BLANK"
                return "SGW"

            badge_map = {
                "captain": badge_for_name(final_captain),
                "vice_captain": badge_for_name(final_vice),
                "transfer_out": badge_for_name(transfer_out),
                "transfer_in": badge_for_name(transfer_in),
            }
        except Exception:  # noqa: BLE001
            pass

        return {
            "gameweek": base.gameweek,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "final": {
                "captain": final_captain,
                "vice_captain": final_vice,
                "transfer_out": transfer_out,
                "transfer_in": transfer_in,
                "fixture_badges": badge_map,
            },
            "baseline": {
                "captain": base.captain,
                "vice_captain": base.vice_captain,
                "transfer_out": base.transfer_out,
                "transfer_in": base.transfer_in,
                "confidence": base.confidence,
            },
            "ml": (
                {
                    "captain": ml.captain,
                    "vice_captain": ml.vice_captain,
                    "transfer_out": ml.transfer_out,
                    "transfer_in": ml.transfer_in,
                    "confidence": ml.confidence,
                    "model_version": model_version,
                }
                if ml is not None
                else None
            ),
            "creator_consensus": consensus,
            "rationale": rationale,
        }

    return api_ttl_cache.get_or_set(cache_key, _build, ttl_seconds=90)
