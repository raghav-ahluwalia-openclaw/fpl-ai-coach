from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Query

from .base import SessionLocal, _get_meta, _int, _set_meta, router
from .insights import NOTIF_CHECK_INTERVAL_MINUTES, REMINDER_STATE_PATH
from .insights_settings import notification_settings_get
from app.services.ml_recommender import DEFAULT_MODEL_VERSION


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


@router.get("/api/fpl/notification-status")
def notification_status():
    settings = notification_settings_get()
    reminder = deadline_reminder(
        lead_hours=settings["lead_hours"],
        mode=settings["mode"],
        model_version=settings["model_version"],
    )

    now_dt = datetime.now(timezone.utc)
    next_check_dt = now_dt + timedelta(minutes=max(1, NOTIF_CHECK_INTERVAL_MINUTES))

    db = SessionLocal()
    try:
        _set_meta(db, "notif_last_check_at", now_dt.isoformat())
        _set_meta(db, "notif_next_check_eta", next_check_dt.isoformat())
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()

    last_sent = None
    if REMINDER_STATE_PATH.exists():
        try:
            last_sent = json.loads(REMINDER_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            last_sent = None

    return {
        "enabled": settings["enabled"],
        "settings": settings,
        "status": {
            "is_due": bool(settings["enabled"] and reminder.get("is_reminder_due")),
            "seconds_until_deadline": reminder.get("seconds_until_deadline"),
            "deadline_utc": reminder.get("deadline_utc"),
            "reminder_utc": reminder.get("reminder_utc"),
            "last_check_utc": now_dt.isoformat(),
            "next_check_utc": next_check_dt.isoformat(),
        },
        "last_sent": last_sent,
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


@router.get("/api/fpl/deadline-reminder")
def deadline_reminder(
    lead_hours: int = Query(default=6, ge=1, le=72),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
):
    from .insights_brief import weekly_brief

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
