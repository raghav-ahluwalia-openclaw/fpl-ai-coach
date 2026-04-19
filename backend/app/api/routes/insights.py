from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .base import (
    Fixture,
    Player,
    Recommendation,
    get_db,
    _choose_captains,
    _expected_points,
    _expected_points_horizon,
    _get_meta,
    _pick_to_response,
    _resolve_gameweek,
    router,
)
from app.services.ml_recommender import (
    DEFAULT_MODEL_VERSION,
    load_model,
    model_meta,
    predict_expected_points,
    train_and_save_model,
)

DIGEST_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "creator_digest.json"
REMINDER_STATE_PATH = Path(__file__).resolve().parents[5] / "memory" / "fpl-reminder-state.json"
NOTIF_CHECK_INTERVAL_MINUTES = int(os.getenv("FPL_NOTIFICATION_CHECK_INTERVAL_MINUTES", "30"))


@router.get("/api/fpl/recommendation", response_model=Recommendation)
def recommendation(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    db: Session = Depends(get_db),
):
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

    lineup = [
        _pick_to_response(
            p,
            xpts,
            expected_points_1=round(xpts, 2),
            expected_points_3=round(_expected_points_horizon(p, fixtures, gw, horizon=3), 2),
            expected_points_5=round(_expected_points_horizon(p, fixtures, gw, horizon=5), 2),
        )
        for xpts, p in lineup_pairs
    ]
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


@router.get("/api/fpl/recommendation-ml", response_model=Recommendation)
def recommendation_ml(
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    force_train: bool = Query(default=False),
    model_version: str = Query(default=DEFAULT_MODEL_VERSION, pattern="^(xgb_v1|xgb_hist_v1)$"),
    db: Session = Depends(get_db),
):
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
        # Fallback to baseline recommendation rather than 500
        return recommendation(gameweek=gameweek, db=db)

    scored = predict_expected_points(model, players, fixtures, gw, model_version=model_version)
    by_pos: Dict[int, List[Tuple[float, Player]]] = {1: [], 2: [], 3: [], 4: []}
    for xpts, p in scored:
        by_pos.setdefault(p.element_type, []).append((xpts, p))

    lineup_pairs = by_pos.get(1, [])[:1] + by_pos.get(2, [])[:3] + by_pos.get(3, [])[:4] + by_pos.get(4, [])[:3]
    if len(lineup_pairs) < 11:
        raise HTTPException(status_code=500, detail="Not enough players by position to build ML lineup")

    lineup = [
        _pick_to_response(
            p,
            xpts,
            expected_points_1=round(xpts, 2),
            expected_points_3=round(_expected_points_horizon(p, fixtures, gw, horizon=3), 2),
            expected_points_5=round(_expected_points_horizon(p, fixtures, gw, horizon=5), 2),
        )
        for xpts, p in lineup_pairs
    ]
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
