from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Optional

import numpy as np
from xgboost import XGBRegressor

from app.models import Fixture, Player

DEFAULT_MODEL_VERSION = "xgb_v1"
HISTORICAL_MODEL_VERSION = "xgb_hist_v1"
MODEL_DIR = Path(__file__).resolve().parents[2] / "model_artifacts"


def _model_paths(model_version: str) -> tuple[Path, Path]:
    model_path = MODEL_DIR / f"fpl_{model_version}.json"
    meta_path = MODEL_DIR / f"fpl_{model_version}.meta.json"
    return model_path, meta_path


def _minutes_factor(minutes: int) -> float:
    return min(max(minutes / 900.0, 0.0), 1.2)


def _availability_factor(chance: Optional[int], news: str) -> float:
    if chance is not None:
        return max(0.0, min(chance / 100.0, 1.0))
    if news and news.strip():
        return 0.85
    return 1.0


def _fixture_row_for_gw(player: Player, fixture_rows: List[Fixture], target_gw: Optional[int]) -> Fixture | None:
    if target_gw is None:
        return None
    for row in fixture_rows:
        if row.event != target_gw:
            continue
        if row.team_h == player.team_id or row.team_a == player.team_id:
            return row
    return None


def _fixture_factor(player: Player, fixture_rows: List[Fixture], target_gw: Optional[int]) -> float:
    if target_gw is None:
        return 1.0

    selected = _fixture_row_for_gw(player, fixture_rows, target_gw)
    if selected is None:
        # Blank GW hard penalty: model should not rank non-playing players highly.
        return 0.03

    difficulty = selected.team_h_difficulty if selected.team_h == player.team_id else selected.team_a_difficulty
    return {1: 1.12, 2: 1.06, 3: 1.0, 4: 0.94, 5: 0.88}.get(difficulty, 1.0)


def _position_one_hot(element_type: int) -> list[float]:
    return [
        1.0 if element_type == 1 else 0.0,
        1.0 if element_type == 2 else 0.0,
        1.0 if element_type == 3 else 0.0,
        1.0 if element_type == 4 else 0.0,
    ]


def player_features(player: Player, fixtures: List[Fixture], target_gw: Optional[int]) -> list[float]:
    fixture = _fixture_factor(player, fixtures, target_gw)
    availability = _availability_factor(player.chance_of_playing_next_round, player.news)
    minutes_factor = _minutes_factor(player.minutes)
    return [
        float(player.form),
        float(player.points_per_game),
        float(player.now_cost) / 10.0,
        float(player.minutes),
        float(player.goals_scored),
        float(player.assists),
        float(player.clean_sheets),
        float(player.selected_by_percent),
        float(player.chance_of_playing_next_round or 100),
        float(minutes_factor),
        float(fixture),
        float(availability),
        *_position_one_hot(player.element_type),
    ]


def _target_proxy(player: Player, fixtures: List[Fixture], target_gw: Optional[int]) -> float:
    # Proxy target used for weakly supervised training from current-season aggregates.
    fixture = _fixture_factor(player, fixtures, target_gw)
    availability = _availability_factor(player.chance_of_playing_next_round, player.news)
    minutes_factor = _minutes_factor(player.minutes)
    base = (player.points_per_game * 0.62) + (player.form * 0.28) + (minutes_factor * 2.0)
    attack_bonus = (player.goals_scored * 0.05) + (player.assists * 0.04)
    clean_bonus = player.clean_sheets * 0.02
    return max(0.0, (base + attack_bonus + clean_bonus) * fixture * availability)


def _build_training_set(players: Iterable[Player], fixtures: List[Fixture], target_gw: Optional[int]) -> tuple[np.ndarray, np.ndarray]:
    feats: list[list[float]] = []
    targets: list[float] = []

    for p in players:
        # Exclude near-zero minute players from training noise
        if p.minutes < 90:
            continue
        feats.append(player_features(p, fixtures, target_gw))
        targets.append(_target_proxy(p, fixtures, target_gw))

    if len(feats) < 40:
        raise ValueError("Not enough player rows to train ML model")

    return np.array(feats, dtype=float), np.array(targets, dtype=float)


def _fit_model(X: np.ndarray, y: np.ndarray) -> XGBRegressor:
    model = XGBRegressor(
        n_estimators=280,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=2,
    )
    model.fit(X, y)
    return model


def _save_model_and_meta(model: XGBRegressor, model_version: str, meta: dict[str, Any]) -> dict[str, Any]:
    model_path, meta_path = _model_paths(model_version)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def train_and_save_model(
    players: Iterable[Player],
    fixtures: List[Fixture],
    target_gw: Optional[int],
    *,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> dict[str, Any]:
    X, y = _build_training_set(players, fixtures, target_gw)
    model = _fit_model(X, y)

    meta = {
        "model_version": model_version,
        "rows": int(X.shape[0]),
        "features": int(X.shape[1]),
        "target_gw": target_gw,
        "y_mean": float(np.mean(y)),
        "y_std": float(np.std(y)),
        "source": "current_season_proxy",
    }
    return _save_model_and_meta(model, model_version, meta)


def train_from_arrays(
    X: np.ndarray,
    y: np.ndarray,
    *,
    model_version: str,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(X.shape) != 2:
        raise ValueError("X must be a 2D array")
    if len(y.shape) != 1:
        raise ValueError("y must be a 1D array")
    if X.shape[0] < 100:
        raise ValueError("Need at least 100 rows for historical training")

    model = _fit_model(X, y)
    meta = {
        "model_version": model_version,
        "rows": int(X.shape[0]),
        "features": int(X.shape[1]),
        "y_mean": float(np.mean(y)),
        "y_std": float(np.std(y)),
    }
    if extra_meta:
        meta.update(extra_meta)

    return _save_model_and_meta(model, model_version, meta)


def load_model(model_version: str = DEFAULT_MODEL_VERSION) -> XGBRegressor | None:
    model_path, _ = _model_paths(model_version)
    if not model_path.exists():
        return None
    model = XGBRegressor()
    model.load_model(str(model_path))
    return model


def _next_opponent_team_id(player: Player, fixtures: List[Fixture], target_gw: Optional[int]) -> int:
    row = _fixture_row_for_gw(player, fixtures, target_gw)
    if row is None:
        return 0
    if row.team_h == player.team_id:
        return int(row.team_a)
    return int(row.team_h)


def _historical_style_features(player: Player, fixtures: List[Fixture], target_gw: Optional[int]) -> list[float]:
    # 12-feature vector used by xgb_hist_v1 training script.
    return [
        float(player.form),  # points_rolling_3 proxy
        float(player.points_per_game),  # points_rolling_5 proxy
        float(player.minutes),  # minutes_rolling_3 proxy
        float(player.goals_scored),  # goals_rolling_5 proxy
        float(player.assists),  # assists_rolling_5 proxy
        float(player.form) * 2.0,  # ict_rolling_3 proxy
        max(0.0, 8.0 - float(player.form)),  # points_volatility_5 proxy
        float(player.selected_by_percent),  # selected_by
        float(player.now_cost) / 10.0,  # price
        float(player.element_type),  # position
        1.0,  # was_home proxy
        float(_next_opponent_team_id(player, fixtures, target_gw)),  # opponent_team
    ]


def predict_expected_points(
    model: XGBRegressor,
    players: Iterable[Player],
    fixtures: List[Fixture],
    target_gw: Optional[int],
    *,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> list[tuple[float, Player]]:
    rows: list[tuple[list[float], Player]] = []
    for p in players:
        if model_version == HISTORICAL_MODEL_VERSION:
            rows.append((_historical_style_features(p, fixtures, target_gw), p))
        else:
            rows.append((player_features(p, fixtures, target_gw), p))

    X = np.array([r[0] for r in rows], dtype=float)
    preds = model.predict(X)

    out: list[tuple[float, Player]] = []
    for pred, (_, player) in zip(preds, rows):
        score = float(max(0.0, pred))
        if target_gw is not None and _fixture_row_for_gw(player, fixtures, target_gw) is None:
            # Additional hard clamp in case model still over-predicts blanks.
            score *= 0.03
        out.append((round(score, 2), player))

    out.sort(key=lambda x: x[0], reverse=True)
    return out


def model_meta(model_version: str = DEFAULT_MODEL_VERSION) -> dict[str, Any] | None:
    _, meta_path = _model_paths(model_version)
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
