from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from fastapi import Request

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
REMINDER_STATE_PATH = Path(__file__).resolve().parents[5] / "memory" / "fpl-reminder-state.json"
NOTIF_CHECK_INTERVAL_MINUTES = int(os.getenv("FPL_NOTIFICATION_CHECK_INTERVAL_MINUTES", "30"))


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


def _user_scope(request: Request) -> str:
    raw = (
        request.headers.get("cf-access-authenticated-user-email")
        or request.headers.get("x-user-email")
        or request.headers.get("x-forwarded-user")
        or "default"
    )
    # Keep meta keys safe/short
    scope = "".join(ch for ch in raw.lower() if ch.isalnum() or ch in {"@", ".", "_", "-"})
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
        return {
            "scope": scope,
            "fpl_entry_id": fpl_entry_id,
            "league_id": league_id,
            "rival_entry_id": rival_entry_id,
        }
    finally:
        db.close()


@router.post("/api/fpl/settings")
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


@router.post("/api/fpl/notification-settings")
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

    # Keep lightweight runtime metadata for UI status.
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


def _explainability_breakdown(player: Player, fixtures: List[Fixture], gw: Optional[int]) -> dict:
    fixture_factor = _fixture_factor(player, fixtures, gw)
    availability = _availability_factor(player.chance_of_playing_next_round, player.news)
    minutes_factor = _minutes_factor(player.minutes)

    form_score = round(min(10.0, player.form * 1.6), 2)
    fixture_score = round(min(10.0, fixture_factor * 8.5), 2)
    minutes_security = round(min(10.0, minutes_factor * 8.3), 2)
    availability_score = round(min(10.0, availability * 10.0), 2)

    ownership = max(0.0, min(player.selected_by_percent, 100.0))
    ownership_risk = round(max(0.0, min(10.0, ownership / 10.0)), 2)
    volatility = round(max(0.0, min(10.0, (8.0 - player.form) + (2.0 * (1.0 - availability)))), 2)

    return {
        "form_score": form_score,
        "fixture_score": fixture_score,
        "minutes_security": minutes_security,
        "availability_score": availability_score,
        "ownership_risk": ownership_risk,
        "volatility": volatility,
    }


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

        pool = [p for p in players if p.element_type in {3, 4}]
        safe_board = []
        upside_board = []

        for p in pool:
            xp1 = _expected_points(p, fixtures, gw)
            xp3 = _expected_points_horizon(p, fixtures, gw, horizon=3)
            availability = _availability_factor(p.chance_of_playing_next_round, p.news)
            minutes_security = _minutes_factor(p.minutes)
            ownership = max(0.0, min(p.selected_by_percent, 100.0))

            risk = (1 - availability) * 0.6 + (1 - min(minutes_security, 1.0)) * 0.4
            safe_score = xp3 * (1 - risk * 0.75) + (ownership * 0.01)
            upside_score = xp3 * (1 - risk * 0.25) + (max(0.0, 25.0 - ownership) / 25.0) * 1.8 + (p.form * 0.12)

            common = {
                "id": p.id,
                "name": p.web_name,
                "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                "price": round(p.now_cost / 10.0, 1),
                "xP_next_1": xp1,
                "xP_next_3": xp3,
                "ownership_pct": round(ownership, 1),
                "risk": round(risk, 2),
                "form": round(p.form, 2),
            }

            safe_board.append({**common, "captain_score": round(safe_score, 2)})
            upside_board.append({**common, "captain_score": round(upside_score, 2)})

        safe_board.sort(key=lambda x: x["captain_score"], reverse=True)
        upside_board.sort(key=lambda x: x["captain_score"], reverse=True)

        return {
            "gameweek": gw,
            "safe_captains": safe_board[:limit],
            "upside_captains": upside_board[:limit],
            "summary": "Captaincy lab ranks stable vs upside captain options using xP horizon, risk, and ownership pressure.",
        }
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

        scored = []
        for p in players:
            xp = _expected_points(p, fixtures, gw)
            breakdown = _explainability_breakdown(p, fixtures, gw)
            scored.append((xp, p, breakdown))

        scored.sort(key=lambda x: x[0], reverse=True)

        out = []
        for xp, p, breakdown in scored[:limit]:
            out.append(
                {
                    "id": p.id,
                    "name": p.web_name,
                    "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                    "price": round(p.now_cost / 10.0, 1),
                    "xP": round(xp, 2),
                    "breakdown": breakdown,
                    "reason": _reason(p, xp),
                }
            )

        return {
            "gameweek": gw,
            "count": len(out),
            "players": out,
            "summary": "Top players with explainability factors (form, fixture, minutes, availability, risk, volatility).",
        }
    finally:
        db.close()


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

        team_ids = sorted({p.team_id for p in players})

        # Team-level fixture strength proxy for upcoming horizon.
        team_strength: Dict[int, float] = {}
        for team_id in team_ids:
            vals = []
            for f in fixtures:
                if f.event is None or f.event < gw or f.event >= gw + horizon:
                    continue
                if f.team_h == team_id:
                    vals.append(f.team_h_difficulty)
                elif f.team_a == team_id:
                    vals.append(f.team_a_difficulty)
            team_strength[team_id] = (sum(vals) / len(vals)) if vals else 3.0

        easy_teams = sorted(team_strength.items(), key=lambda x: x[1])[:5]
        hard_teams = sorted(team_strength.items(), key=lambda x: x[1], reverse=True)[:5]

        # Blank/Double GW detection for near-term planning windows.
        gw_fixture_stats = []
        for ev in range(gw, gw + min(horizon, 6)):
            counts = {tid: 0 for tid in team_ids}
            for f in fixtures:
                if f.event != ev:
                    continue
                counts[f.team_h] = counts.get(f.team_h, 0) + 1
                counts[f.team_a] = counts.get(f.team_a, 0) + 1

            blank_teams = sum(1 for _, c in counts.items() if c == 0)
            double_teams = sum(1 for _, c in counts.items() if c >= 2)
            gw_fixture_stats.append(
                {
                    "gameweek": ev,
                    "blank_teams": blank_teams,
                    "double_teams": double_teams,
                }
            )

        max_blank = max((x["blank_teams"] for x in gw_fixture_stats), default=0)
        max_double = max((x["double_teams"] for x in gw_fixture_stats), default=0)

        # Chip heuristics (v2): include blank/double structure.
        wildcard_score = max(0.0, min(10.0, (sum(v for _, v in hard_teams) / max(1, len(hard_teams))) * 1.2))

        # Free Hit spikes with large blank GW pressure.
        free_hit_score = max(0.0, min(10.0, 2.0 + (max_blank * 0.45)))

        # Bench boost benefits from doubles and bench depth.
        playable_bench = 0
        for p in players:
            if p.now_cost / 10.0 <= 5.8 and p.minutes >= 450:
                if _expected_points_horizon(p, fixtures, gw, horizon=3) >= 4.2:
                    playable_bench += 1
        bench_boost_score = max(0.0, min(10.0, (playable_bench / 2.2) + (max_double * 0.35)))

        # Triple captain likes elite short-horizon xP + doubles.
        premiums = [p for p in players if p.now_cost / 10.0 >= 10.0]
        top_premium_xp = max((_expected_points_horizon(p, fixtures, gw, horizon=2) for p in premiums), default=0.0)
        triple_captain_score = max(0.0, min(10.0, (top_premium_xp * 1.0) + (max_double * 0.28)))

        ranked = sorted(
            [
                ("wildcard", wildcard_score),
                ("free_hit", free_hit_score),
                ("bench_boost", bench_boost_score),
                ("triple_captain", triple_captain_score),
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        best_chip = ranked[0]
        alt_chip = ranked[1]

        recommendation = "hold"
        confidence = 0.45
        if best_chip[1] >= 7.4:
            recommendation = f"play_{best_chip[0]}"
            confidence = min(0.9, 0.55 + ((best_chip[1] - alt_chip[1]) / 10.0))

        return {
            "gameweek": gw,
            "horizon": horizon,
            "chip_scores": {
                "wildcard": round(wildcard_score, 2),
                "free_hit": round(free_hit_score, 2),
                "bench_boost": round(bench_boost_score, 2),
                "triple_captain": round(triple_captain_score, 2),
            },
            "fixture_windows": gw_fixture_stats,
            "easy_fixture_teams": [{"team_id": t, "avg_difficulty": round(s, 2)} for t, s in easy_teams],
            "hard_fixture_teams": [{"team_id": t, "avg_difficulty": round(s, 2)} for t, s in hard_teams],
            "recommendation": recommendation,
            "alternative": f"play_{alt_chip[0]}" if alt_chip[1] >= 6.8 else "hold",
            "confidence": round(confidence, 2),
            "summary": "Chip planner scores chip timing using fixture swings plus blank/double GW pressure.",
        }
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

        my_payload, my_gw = _fetch_entry_picks_with_fallback(entry_id, gw, [current_gw, gw - 1])
        rival_payload, _ = _fetch_entry_picks_with_fallback(rival_entry_id, my_gw, [current_gw, my_gw - 1])

        my_picks = my_payload.get("picks", [])
        rival_picks = rival_payload.get("picks", [])

        my_ids = {_int(p.get("element")) for p in my_picks}
        rival_ids = {_int(p.get("element")) for p in rival_picks}

        overlap = sorted(my_ids.intersection(rival_ids))
        my_only = sorted(my_ids - rival_ids)
        rival_only = sorted(rival_ids - my_ids)

        players = db.query(Player).all()
        fixtures = db.query(Fixture).all()
        by_id = {p.id: p for p in players}

        my_captain_id = next((_int(p.get("element")) for p in my_picks if bool(p.get("is_captain", False))), None)
        rival_captain_id = next((_int(p.get("element")) for p in rival_picks if bool(p.get("is_captain", False))), None)

        def names(ids: List[int]) -> List[str]:
            out = []
            for pid in ids:
                p = by_id.get(pid)
                if p:
                    out.append(p.web_name)
            return out

        # Differential impact scoring
        my_diff_scored = []
        for pid in my_only:
            p = by_id.get(pid)
            if not p:
                continue
            xp = _expected_points_horizon(p, fixtures, my_gw, horizon=3)
            eo_pressure = min(1.0, max(0.0, p.selected_by_percent / 100.0))
            impact = xp * (1.0 - eo_pressure)
            my_diff_scored.append({
                "id": p.id,
                "name": p.web_name,
                "xP_3": round(xp, 2),
                "ownership_pct": round(p.selected_by_percent, 1),
                "impact_score": round(impact, 2),
            })

        rival_diff_scored = []
        for pid in rival_only:
            p = by_id.get(pid)
            if not p:
                continue
            xp = _expected_points_horizon(p, fixtures, my_gw, horizon=3)
            eo_pressure = min(1.0, max(0.0, p.selected_by_percent / 100.0))
            impact = xp * (1.0 - eo_pressure)
            rival_diff_scored.append({
                "id": p.id,
                "name": p.web_name,
                "xP_3": round(xp, 2),
                "ownership_pct": round(p.selected_by_percent, 1),
                "impact_score": round(impact, 2),
            })

        my_diff_scored.sort(key=lambda x: x["impact_score"], reverse=True)
        rival_diff_scored.sort(key=lambda x: x["impact_score"], reverse=True)

        my_captain_name = by_id.get(my_captain_id).web_name if my_captain_id in by_id else None
        rival_captain_name = by_id.get(rival_captain_id).web_name if rival_captain_id in by_id else None
        captain_overlap = my_captain_id is not None and my_captain_id == rival_captain_id

        captain_risk = "high_if_diff" if not captain_overlap else "hedged"

        return {
            "gameweek": my_gw,
            "entry_id": entry_id,
            "rival_entry_id": rival_entry_id,
            "overlap_count": len(overlap),
            "my_only_count": len(my_only),
            "rival_only_count": len(rival_only),
            "overlap_players": names(overlap),
            "my_differentials": names(my_only),
            "rival_differentials": names(rival_only),
            "captaincy": {
                "my_captain": my_captain_name,
                "rival_captain": rival_captain_name,
                "overlap": captain_overlap,
                "risk": captain_risk,
            },
            "differential_impact": {
                "my_top": my_diff_scored[:8],
                "rival_top": rival_diff_scored[:8],
            },
            "summary": "Rival intelligence compares overlap, captaincy exposure, and differential impact scores.",
        }
    finally:
        db.close()


@router.get("/api/fpl/weekly-digest-card")
def weekly_digest_card(
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
):
    brief = weekly_brief(gameweek=None, mode=mode, model_version=model_version)
    cap = captaincy_lab(gameweek=None, limit=3)
    chip = chip_planner(gameweek=brief["gameweek"], horizon=6)

    final = brief["final"]
    safe_top3 = cap.get("safe_captains", [])[:3]
    upside_top3 = cap.get("upside_captains", [])[:3]

    lines = [
        f"📊 GW{brief['gameweek']} Weekly Digest ({mode})",
        f"🧢 Captain: {final['captain']} | Vice: {final['vice_captain']}",
        f"🔁 Transfer: {final['transfer_out']} → {final['transfer_in']}",
        f"🧩 Chip: {chip.get('recommendation')} (alt: {chip.get('alternative')}, conf: {chip.get('confidence')})",
        "✅ Safe C picks: " + ", ".join(p.get("name", "") for p in safe_top3),
        "🎯 Upside C picks: " + ", ".join(p.get("name", "") for p in upside_top3),
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
            "emoji_header": "📊",
            "sections": {
                "captaincy": {
                    "icon": "🧢",
                    "captain": final["captain"],
                    "vice": final["vice_captain"],
                },
                "transfer": {
                    "icon": "🔁",
                    "out": final["transfer_out"],
                    "in": final["transfer_in"],
                },
                "chip": {
                    "icon": "🧩",
                    "play": chip.get("recommendation"),
                    "alternative": chip.get("alternative"),
                    "confidence": chip.get("confidence"),
                },
            },
            "lines": lines,
            "telegram_text": "\n".join(lines),
        },
        "summary": "Rich weekly digest payload for messaging cards and Telegram reminders.",
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
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
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
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
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
