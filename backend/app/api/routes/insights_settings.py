from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import rate_limit_write_ops, request_scope_identity, require_authenticated

from .base import SessionLocal, _get_meta, _int, _set_meta, router
from app.services.ml_recommender import DEFAULT_MODEL_VERSION


def _meta_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _user_scope(request: Request) -> str:
    raw = request_scope_identity(request)
    scope = "".join(ch for ch in raw.lower() if ch.isalnum() or ch in {"@", ".", "_", "-", ":"})
    return scope[:120] or "default"


def _settings_key(scope: str, name: str) -> str:
    return f"settings:{scope}:{name}"


@router.get("/api/fpl/settings")
def app_settings_get(request: Request):
    scope = _user_scope(request)
    db = SessionLocal()
    try:
        fpl_entry_id = _int(_get_meta(db, _settings_key(scope, "fpl_entry_id")), 0) or None
        league_id = _int(_get_meta(db, _settings_key(scope, "league_id")), 0) or None
        rival_entry_id = _int(_get_meta(db, _settings_key(scope, "rival_entry_id")), 0) or None

        # Fetch cached names if available for the main team
        entry_name = None
        player_name = None
        if fpl_entry_id:
            entry_name = _get_meta(db, f"entry:{fpl_entry_id}:entry_name")
            player_name = _get_meta(db, f"entry:{fpl_entry_id}:player_name")

            # Proactive fetch if names are missing from DB
            if not entry_name or not player_name:
                try:
                    from app.services.http_client import fetch_json as f_json
                    info = f_json(f"https://fantasy.premierleague.com/api/entry/{fpl_entry_id}/", timeout=5)
                    if not entry_name:
                        entry_name = str(info.get("name") or "")
                        _set_meta(db, f"entry:{fpl_entry_id}:entry_name", entry_name)
                    if not player_name:
                        player_name = str(info.get("player_first_name", "") + " " + info.get("player_last_name", "")).strip()
                        _set_meta(db, f"entry:{fpl_entry_id}:player_name", player_name)
                    db.commit()
                except Exception:
                    pass

        return {
            "scope": scope,
            "fpl_entry_id": fpl_entry_id,
            "entry_name": entry_name,
            "player_name": player_name,
            "league_id": league_id,
            "rival_entry_id": rival_entry_id,
        }
    finally:
        db.close()


@router.post(
    "/api/fpl/settings",
    dependencies=[Depends(require_authenticated), Depends(rate_limit_write_ops)],
)
def app_settings_set(
    request: Request,
    fpl_entry_id: Optional[int] = Query(default=None, ge=1),
    league_id: Optional[int] = Query(default=None, ge=1),
    rival_entry_id: Optional[int] = Query(default=None, ge=1),
    clear_missing: bool = Query(default=False),
):
    scope = _user_scope(request)
    db = SessionLocal()
    try:
        updates = {
            "fpl_entry_id": fpl_entry_id,
            "league_id": league_id,
            "rival_entry_id": rival_entry_id,
        }
        for k, v in updates.items():
            if v is not None:
                _set_meta(db, _settings_key(scope, k), str(v))
            elif clear_missing:
                _set_meta(db, _settings_key(scope, k), "")
        db.commit()
        return app_settings_get(request)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save app settings: {e}")
    finally:
        db.close()


@router.get("/api/fpl/notification-settings")
def notification_settings_get():
    db = SessionLocal()
    try:
        enabled = _meta_bool(_get_meta(db, "notif_enabled"), False)
        lead_hours = _int(_get_meta(db, "notif_lead_hours"), 6)
        mode = _get_meta(db, "notif_mode") or "balanced"
        model_version = _get_meta(db, "notif_model_version") or DEFAULT_MODEL_VERSION

        return {
            "enabled": enabled,
            "lead_hours": max(1, min(72, lead_hours)),
            "mode": mode if mode in {"safe", "balanced", "aggressive"} else "balanced",
            "model_version": model_version if model_version in {"xgb_v1", "xgb_hist_v1"} else DEFAULT_MODEL_VERSION,
        }
    finally:
        db.close()


@router.post(
    "/api/fpl/notification-settings",
    dependencies=[Depends(require_authenticated), Depends(rate_limit_write_ops)],
)
def notification_settings_set(
    enabled: bool = Query(default=True),
    lead_hours: int = Query(default=6, ge=1, le=72),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
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
