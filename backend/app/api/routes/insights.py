from __future__ import annotations

from .base import *  # noqa: F403
from app.services.ml_recommender import load_model, model_meta, predict_expected_points, train_and_save_model

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
):
    db = SessionLocal()
    try:
        players = db.query(Player).all()
        if not players:
            raise HTTPException(status_code=400, detail="No data found. Run POST /api/fpl/ingest/bootstrap first.")

        fixtures = db.query(Fixture).all()
        gw = _resolve_gameweek(db, gameweek)

        model = None if force_train else load_model()
        if model is None:
            train_and_save_model(players, fixtures, gw)
            model = load_model()
        if model is None:
            raise HTTPException(status_code=500, detail="Failed to load ML model")

        scored = predict_expected_points(model, players, fixtures, gw)
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
        meta = model_meta() or {}

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
                "ML recommendation (XGBoost) trained on current-season aggregates; "
                f"model={meta.get('model_version', 'xgb_v1')} rows={meta.get('rows', 'n/a')}"
            ),
        )
    finally:
        db.close()


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
