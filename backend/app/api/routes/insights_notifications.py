from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Query

from .base import (
    FPL_BOOTSTRAP_URL,
    SessionLocal,
    _get_meta,
    _int,
    _set_meta,
    _sync_gameweek_meta_if_needed,
    fetch_json,
    router,
)
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


@router.get("/api/fpl/gameweek-status")
def gameweek_status():
    db = SessionLocal()
    try:
        now_dt = datetime.now(timezone.utc)
        _sync_gameweek_meta_if_needed(db)

        current_gw = _int(_get_meta(db, "current_gw"), 0) or None
        next_gw = _int(_get_meta(db, "next_gw"), 0) or None
        deadline_raw = _get_meta(db, "next_deadline_utc")

        deadline_dt = None
        if deadline_raw:
            try:
                deadline_dt = datetime.fromisoformat(str(deadline_raw).replace("Z", "+00:00"))
            except ValueError:
                deadline_dt = None

        current_gw_finished = None
        current_gw_data_checked = None
        completed_gw = None
        gw_in_progress = False
        current_gw_status = "unknown"
        source = "meta"

        try:
            bootstrap = fetch_json(
                FPL_BOOTSTRAP_URL,
                timeout=20,
                upstream_error_prefix="FPL bootstrap source unavailable",
            )
            events = bootstrap.get("events", [])
            current_event = next((e for e in events if e.get("is_current")), None)
            next_event = next((e for e in events if e.get("is_next")), None)

            if current_event:
                official_current = _int(current_event.get("id"), current_gw or 0) or current_gw
                current_gw_finished = bool(current_event.get("finished"))
                current_gw_data_checked = bool(current_event.get("data_checked"))
                completed_gw = official_current if current_gw_finished else None
                current_gw = official_current

            if next_event:
                next_gw = _int(next_event.get("id"), next_gw or 0) or next_gw
                nd = next_event.get("deadline_time")
                if nd:
                    deadline_dt = datetime.fromisoformat(str(nd).replace("Z", "+00:00"))

            # Product rule: once a GW is finished, shift planning current GW to the upcoming GW,
            # and surface "next_gw" as the GW after that.
            if current_gw_finished and next_gw:
                planning_gw = next_gw
                following_event = next((e for e in events if _int(e.get("id"), 0) == planning_gw + 1), None)
                current_gw = planning_gw
                next_gw = _int((following_event or {}).get("id"), planning_gw + 1) or (planning_gw + 1)
                current_gw_status = "upcoming"
                gw_in_progress = False
            else:
                gw_in_progress = not bool(current_gw_finished)
                current_gw_status = "in_progress" if gw_in_progress else "finished"

            source = "official_fpl_api"
        except Exception:  # noqa: BLE001
            if current_gw and next_gw and next_gw > current_gw:
                current_gw_status = "finished"
            elif current_gw:
                current_gw_status = "in_progress"
                gw_in_progress = True

        seconds_until_deadline = int((deadline_dt - now_dt).total_seconds()) if deadline_dt else None
        transfer_window_open = None if seconds_until_deadline is None else seconds_until_deadline > 0

        season_phase = "unknown"
        if gw_in_progress:
            season_phase = "current_gw_live"
        elif current_gw_status == "upcoming" and transfer_window_open is True:
            season_phase = "pre_deadline_window"
        elif current_gw_status == "finished" and transfer_window_open is True:
            season_phase = "between_gameweeks"
        elif current_gw_status == "finished" and transfer_window_open is False:
            season_phase = "deadline_passed_pending_update"

        return {
            "generated_at": now_dt.isoformat(),
            "source": source,
            "current_gw": current_gw,
            "planning_gw": current_gw,
            "completed_gw": completed_gw,
            "current_gw_status": current_gw_status,
            "current_gw_finished": current_gw_finished,
            "current_gw_data_checked": current_gw_data_checked,
            "gw_in_progress": gw_in_progress,
            "next_gw": next_gw,
            "next_deadline_utc": deadline_dt.isoformat() if deadline_dt else None,
            "transfer_deadline_utc": deadline_dt.isoformat() if deadline_dt else None,
            "seconds_until_deadline": seconds_until_deadline,
            "transfer_window_open": transfer_window_open,
            "season_phase": season_phase,
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
