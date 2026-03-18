from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Optional

import numpy as np
from xgboost import XGBRegressor

from app.models import Fixture, Player

MODEL_VERSION = "xgb_v1"
MODEL_DIR = Path(__file__).resolve().parents[2] / "model_artifacts"
MODEL_PATH = MODEL_DIR / f"fpl_{MODEL_VERSION}.json"
META_PATH = MODEL_DIR / f"fpl_{MODEL_VERSION}.meta.json"


def _minutes_factor(minutes: int) -> float:
    return min(max(minutes / 900.0, 0.0), 1.2)


def _availability_factor(chance: Optional[int], news: str) -> float:
    if chance is not None:
        return max(0.0, min(chance / 100.0, 1.0))
    if news and news.strip():
        return 0.85
    return 1.0


def _fixture_factor(player: Player, fixture_rows: List[Fixture], target_gw: Optional[int]) -> float:
    if target_gw is None:
        return 1.0

    selected = None
    for row in fixture_rows:
        if row.event != target_gw:
            continue
        if row.team_h == player.team_id or row.team_a == player.team_id:
            selected = row
            break

    if selected is None:
        return 1.0

    difficulty = selected.team_h_difficulty if selected.team_h == player.team_id else selected.team_a_difficulty
    return {1: 1.12, 2: 1.06, 3: 1.0, 4: 0.94, 5: 0.88}.get(difficulty, 1.0)


def _position_one_hot(element_type: int) -> list[float]:
    return [
        1.0 if element_type == 1 else 0.0,
        1.0 if element_type == 2 else 0.0,
        1.0 if element_type == 3 else 0.0,
        1.0 if element_type == 4 else 0.0,
    ]


def _features(player: Player, fixtures: List[Fixture], target_gw: Optional[int]) -> list[float]:
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
        feats.append(_features(p, fixtures, target_gw))
        targets.append(_target_proxy(p, fixtures, target_gw))

    if len(feats) < 40:
        raise ValueError("Not enough player rows to train ML model")

    return np.array(feats, dtype=float), np.array(targets, dtype=float)


def train_and_save_model(players: Iterable[Player], fixtures: List[Fixture], target_gw: Optional[int]) -> dict[str, Any]:
    X, y = _build_training_set(players, fixtures, target_gw)

    model = XGBRegressor(
        n_estimators=220,
        max_depth=4,
        learning_rate=0.06,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=2,
    )
    model.fit(X, y)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_PATH))

    meta = {
        "model_version": MODEL_VERSION,
        "rows": int(X.shape[0]),
        "features": int(X.shape[1]),
        "target_gw": target_gw,
        "y_mean": float(np.mean(y)),
        "y_std": float(np.std(y)),
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_model() -> XGBRegressor | None:
    if not MODEL_PATH.exists():
        return None
    model = XGBRegressor()
    model.load_model(str(MODEL_PATH))
    return model


def predict_expected_points(
    model: XGBRegressor,
    players: Iterable[Player],
    fixtures: List[Fixture],
    target_gw: Optional[int],
) -> list[tuple[float, Player]]:
    rows: list[tuple[list[float], Player]] = []
    for p in players:
        rows.append((_features(p, fixtures, target_gw), p))

    X = np.array([r[0] for r in rows], dtype=float)
    preds = model.predict(X)

    out: list[tuple[float, Player]] = []
    for pred, (_, player) in zip(preds, rows):
        out.append((round(float(max(0.0, pred)), 2), player))

    out.sort(key=lambda x: x[0], reverse=True)
    return out


def model_meta() -> dict[str, Any] | None:
    if not META_PATH.exists():
        return None
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
