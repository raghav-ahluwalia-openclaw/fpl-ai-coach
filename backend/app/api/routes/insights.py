from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from .base import *  # noqa: F403
from app.services.ml_recommender import (
    DEFAULT_MODEL_VERSION,
    HISTORICAL_MODEL_VERSION,
    load_model,
    model_meta,
    predict_expected_points,
    train_and_save_model,
)

DIGEST_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "creator_digest.json"


@router.get("/api/fpl/deadline-next")
def deadline_next(lead_hours: int = Query(default=6, ge=1, le=72)):
    db = SessionLocal()
    try:
        next_gw = _int(_get_meta(db, "next_gw"), 0) or None
        next_deadline_utc = _get_meta(db, "next_deadline_utc")
        if not next_deadline_utc:
            raise HTTPException(
                status_code=404,
                detail="next_deadline_utc not available. Run POST /api/fpl/ingest/bootstrap first.",
            )

        deadline_dt = datetime.fromisoformat(next_deadline_utc.replace("Z", "+00:00"))
        reminder_dt = deadline_dt - timedelta(hours=lead_hours)
        now_dt = datetime.now(timezone.utc)

        return {
            "next_gw": next_gw,
            "deadline_utc": deadline_dt.isoformat(),
            "lead_hours": lead_hours,
            "reminder_utc": reminder_dt.isoformat(),
            "seconds_until_deadline": int((deadline_dt - now_dt).total_seconds()),
            "seconds_until_reminder": int((reminder_dt - now_dt).total_seconds()),
            "is_reminder_due": reminder_dt <= now_dt,
        }
    finally:
        db.close()


def _meta_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@router.get("/api/fpl/notification-settings")
def notification_settings_get():
    db = SessionLocal()
    try:
        enabled = _meta_bool(_get_meta(db, "notif_enabled"), False)
        lead_hours = _int(_get_meta(db, "notif_lead_hours"), 6)
        mode = _get_meta(db, "notif_mode") or "balanced"
        model_version = _get_meta(db, "notif_model_version") or HISTORICAL_MODEL_VERSION

        return {
            "enabled": enabled,
            "lead_hours": max(1, min(72, lead_hours)),
            "mode": mode if mode in {"safe", "balanced", "aggressive"} else "balanced",
            "model_version": model_version if model_version in {"xgb_v1", "xgb_hist_v1"} else HISTORICAL_MODEL_VERSION,
        }
    finally:
        db.close()


@router.post("/api/fpl/notification-settings")
def notification_settings_set(
    enabled: bool = Query(default=True),
    lead_hours: int = Query(default=6, ge=1, le=72),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=HISTORICAL_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
):
    db = SessionLocal()
    try:
        _set_meta(db, "notif_enabled", "true" if enabled else "false")
        _set_meta(db, "notif_lead_hours", str(lead_hours))
        _set_meta(db, "notif_mode", mode)
        _set_meta(db, "notif_model_version", model_version)
        db.commit()
        return {
            "ok": True,
            "enabled": enabled,
            "lead_hours": lead_hours,
            "mode": mode,
            "model_version": model_version,
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save notification settings: {e}")
    finally:
        db.close()


@router.get("/api/fpl/notification-status")
def notification_status():
    settings = notification_settings_get()
    reminder = deadline_reminder(
        lead_hours=settings["lead_hours"],
        mode=settings["mode"],
        model_version=settings["model_version"],
    )
    return {
        "enabled": settings["enabled"],
        "settings": settings,
        "status": {
            "is_due": bool(settings["enabled"] and reminder.get("is_reminder_due")),
            "seconds_until_deadline": reminder.get("seconds_until_deadline"),
            "deadline_utc": reminder.get("deadline_utc"),
            "reminder_utc": reminder.get("reminder_utc"),
        },
        "preview_message": reminder.get("message"),
    }


@router.get("/api/fpl/notification-test")
def notification_test():
    settings = notification_settings_get()
    reminder = deadline_reminder(
        lead_hours=settings["lead_hours"],
        mode=settings["mode"],
        model_version=settings["model_version"],
    )
    return {
        "ok": True,
        "dry_run": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
        "test_message": reminder.get("message"),
        "deadline_utc": reminder.get("deadline_utc"),
        "reminder_utc": reminder.get("reminder_utc"),
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
        next_gw = _resolve_gameweek(db, None)

        scored = []
        for p in players:
            xpts = _expected_points(p, fixtures, next_gw)
            scored.append((xpts, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for xpts, p in scored[:limit]:
            out.append(
                {
                    "id": p.id,
                    "name": p.web_name,
                    "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                    "team_id": p.team_id,
                    "price": p.now_cost / 10.0,
                    "xP": xpts,
                    "form": p.form,
                    "ppg": p.points_per_game,
                }
            )

        return {
            "count": len(out),
            "next_gw": next_gw,
            "players": out,
            "last_ingested_at": _get_meta(db, "last_ingested_at"),
        }
    finally:
        db.close()


@router.get("/api/fpl/recommendation", response_model=Recommendation)
def recommendation(gameweek: Optional[int] = Query(default=None, ge=1, le=38)):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, gameweek)

        by_pos: Dict[int, List[Tuple[float, Player]]] = {1: [], 2: [], 3: [], 4: []}
        for p in players:
            xpts = _expected_points(p, fixtures, gw)
            by_pos.setdefault(p.element_type, []).append((xpts, p))

        for k in by_pos:
            by_pos[k].sort(key=lambda x: x[0], reverse=True)

        lineup_pairs = by_pos.get(1, [])[:1] + by_pos.get(2, [])[:3] + by_pos.get(3, [])[:4] + by_pos.get(4, [])[:3]
        if len(lineup_pairs) < 11:
            raise HTTPException(status_code=500, detail="Not enough players by position to build lineup")

        lineup = [_pick_to_response(p, xpts) for xpts, p in lineup_pairs]
        captain, vice = _choose_captains(lineup_pairs)

        lineup_ids = {p.id for p in lineup}
        candidates = []
        for xpts, p in (by_pos.get(3, [])[:25] + by_pos.get(4, [])[:25]):
            if p.id not in lineup_ids:
                candidates.append((xpts, p))
        candidates.sort(key=lambda x: x[0], reverse=True)

        transfer_in = candidates[0][1].web_name if candidates else "TBD"
        attack_line = [p for p in lineup if p.position in {"MID", "FWD"}]
        attack_line.sort(key=lambda x: x.expected_points)
        transfer_out = attack_line[0].name if attack_line else "TBD"

        confidence = min(0.9, max(0.55, sum(p.expected_points for p in lineup) / 70.0))

        return Recommendation(
            gameweek=gw,
            formation="3-4-3",
            lineup=lineup,
            captain=captain,
            vice_captain=vice,
            transfer_out=transfer_out,
            transfer_in=transfer_in,
            confidence=round(confidence, 2),
            last_ingested_at=_get_meta(db, "last_ingested_at"),
            summary="v1 global model combines points-per-game, form, minutes, fixture difficulty, and availability risk.",
        )
    finally:
        db.close()

@router.get("/api/fpl/recommendation-ml", response_model=Recommendation)
def recommendation_ml(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    force_train: bool = Query(default=False),
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, gameweek)

        model = None if force_train else load_model(model_version)
        if model is None:
            if model_version == DEFAULT_MODEL_VERSION:
                train_and_save_model(players, fixtures, gw, model_version=DEFAULT_MODEL_VERSION)
                model = load_model(DEFAULT_MODEL_VERSION)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Historical model artifact not found. "
                        "Run ./backend/ml/build_historical_dataset.py then ./backend/ml/train_xgb_historical.py"
                    ),
                )
        if model is None:
            raise HTTPException(status_code=500, detail="Failed to load ML model")

        scored = predict_expected_points(model, players, fixtures, gw, model_version=model_version)
        by_pos: Dict[int, List[Tuple[float, Player]]] = {1: [], 2: [], 3: [], 4: []}
        for xpts, p in scored:
            by_pos.setdefault(p.element_type, []).append((xpts, p))

        lineup_pairs = by_pos.get(1, [])[:1] + by_pos.get(2, [])[:3] + by_pos.get(3, [])[:4] + by_pos.get(4, [])[:3]
        if len(lineup_pairs) < 11:
            raise HTTPException(status_code=500, detail="Not enough players by position to build ML lineup")

        lineup = [_pick_to_response(p, xpts) for xpts, p in lineup_pairs]
        captain, vice = _choose_captains(lineup_pairs)

        lineup_ids = {p.id for p in lineup}
        candidates = []
        for xpts, p in (by_pos.get(3, [])[:30] + by_pos.get(4, [])[:30]):
            if p.id not in lineup_ids:
                candidates.append((xpts, p))
        candidates.sort(key=lambda x: x[0], reverse=True)

        transfer_in = candidates[0][1].web_name if candidates else "TBD"
        attack_line = [p for p in lineup if p.position in {"MID", "FWD"}]
        attack_line.sort(key=lambda x: x.expected_points)
        transfer_out = attack_line[0].name if attack_line else "TBD"

        confidence = min(0.92, max(0.56, sum(p.expected_points for p in lineup) / 68.0))
        meta = model_meta(model_version) or {}

        return Recommendation(
            gameweek=gw,
            formation="3-4-3",
            lineup=lineup,
            captain=captain,
            vice_captain=vice,
            transfer_out=transfer_out,
            transfer_in=transfer_in,
            confidence=round(confidence, 2),
            last_ingested_at=_get_meta(db, "last_ingested_at"),
            summary=(
                "ML recommendation (XGBoost) using selected model artifact; "
                f"model={meta.get('model_version', model_version)} rows={meta.get('rows', 'n/a')}"
            ),
        )
    finally:
        db.close()


@router.get("/api/fpl/deadline-reminder")
def deadline_reminder(
    lead_hours: int = Query(default=6, ge=1, le=72),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=HISTORICAL_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
):
    deadline = deadline_next(lead_hours=lead_hours)
    brief = weekly_brief(gameweek=None, mode=mode, model_version=model_version)

    return {
        "next_gw": deadline["next_gw"],
        "deadline_utc": deadline["deadline_utc"],
        "reminder_utc": deadline["reminder_utc"],
        "is_reminder_due": deadline["is_reminder_due"],
        "seconds_until_deadline": deadline["seconds_until_deadline"],
        "brief": brief,
        "message": (
            f"Reminder: FPL GW{deadline['next_gw']} deadline is approaching. "
            f"Captain {brief['final']['captain']}, transfer {brief['final']['transfer_out']} -> {brief['final']['transfer_in']}."
        ),
    }


@router.get("/api/fpl/weekly-brief")
def weekly_brief(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=HISTORICAL_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
):
    base = recommendation(gameweek=gameweek)

    ml = None
    try:
        ml = recommendation_ml(gameweek=gameweek, force_train=False, model_version=model_version)
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

    if mode == "safe":
        final_captain = base.captain
        final_vice = base.vice_captain
        transfer_out, transfer_in = base.transfer_out, base.transfer_in
    elif mode == "aggressive" and ml is not None:
        final_captain = ml.captain
        final_vice = ml.vice_captain
        transfer_out, transfer_in = ml.transfer_out, ml.transfer_in
    else:
        final_captain = base.captain if ml is None else (base.captain if base.confidence >= ml.confidence else ml.captain)
        final_vice = base.vice_captain if ml is None else (base.vice_captain if base.confidence >= ml.confidence else ml.vice_captain)
        transfer_out, transfer_in = base.transfer_out, base.transfer_in
        if ml is not None and ml.transfer_in == base.transfer_in:
            transfer_out, transfer_in = ml.transfer_out, ml.transfer_in

    rationale = [
        f"Mode: {mode}",
        f"Baseline captain: {base.captain}",
        f"ML captain: {ml.captain if ml else 'n/a'}",
        f"Creator consensus top topics: {', '.join(t.get('topic', '') for t in (consensus or {}).get('top_topics', [])[:3]) or 'n/a'}",
    ]

    return {
        "gameweek": base.gameweek,
        "mode": mode,
        "final": {
            "captain": final_captain,
            "vice_captain": final_vice,
            "transfer_out": transfer_out,
            "transfer_in": transfer_in,
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


@router.get("/api/fpl/targets", response_model=TargetsResponse)
def target_insights(
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    horizon: int = Query(default=3, ge=1, le=5),
    limit: int = Query(default=12, ge=3, le=30),
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No player data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, gameweek)
        mode_weights, _ = _strategy_config(mode)

        scored: List[TargetPlayer] = []
        for p in players:
            # Keep common FPL range to avoid extreme edge cases
            price = p.now_cost / 10.0
            if price < 4.0 or price > 15.5:
                continue
            target = _build_target_player(p, fixtures, gw, mode=mode, mode_weights=mode_weights)

            # Recompute primary score on requested horizon for sorting consistency
            horizon_score = _expected_points_horizon(p, fixtures, gw, horizon=horizon, weights=mode_weights)
            risk = (target.minutes_risk * 0.35) + (target.availability_risk * 0.65)
            adjusted = horizon_score * (1.0 - min(0.5, risk))
            target.target_score = round(adjusted, 2)
            target.tier = _target_tier(adjusted)
            scored.append(target)

        scored.sort(key=lambda x: x.target_score, reverse=True)

        # Safe board: reliable + generally owned
        safe_targets = [t for t in scored if t.availability_risk <= 0.25 and t.minutes_risk <= 0.35]
        safe_targets = safe_targets[:limit]

        # Differential board: lower ownership but still good score
        differential_targets = [t for t in scored if t.ownership_pct <= 20.0 and t.target_score >= 5.5]
        differential_targets = differential_targets[: max(5, limit // 2)]

        return TargetsResponse(
            gameweek=gw,
            strategy_mode=mode,
            horizon=horizon,
            safe_targets=safe_targets,
            differential_targets=differential_targets,
            last_ingested_at=_get_meta(db, "last_ingested_at"),
            summary="Multi-source target radar: projections from form/minutes/fixtures/availability with mode-specific risk posture.",
        )
    finally:
        db.close()
