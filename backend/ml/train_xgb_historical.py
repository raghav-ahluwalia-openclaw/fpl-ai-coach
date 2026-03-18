#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "bin" / "python"
if os.environ.get("FPL_ML_VENV_BOOTSTRAPPED") != "1" and VENV_PY.exists() and Path(sys.executable) != VENV_PY:
    env = os.environ.copy()
    env["FPL_ML_VENV_BOOTSTRAPPED"] = "1"
    os.execve(str(VENV_PY), [str(VENV_PY), __file__, *sys.argv[1:]], env)

os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from app.services.ml_recommender import HISTORICAL_MODEL_VERSION, train_from_arrays  # noqa: E402

DEFAULT_DATASET = ROOT / "data" / "historical" / "training_rows.csv"

FEATURE_COLUMNS = [
    "points_rolling_3",
    "points_rolling_5",
    "minutes_rolling_3",
    "goals_rolling_5",
    "assists_rolling_5",
    "ict_rolling_3",
    "points_volatility_5",
    "selected_by",
    "price",
    "position",
    "was_home",
    "opponent_team",
]
TARGET_COLUMN = "target_next_points"


def _safe_float(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return default


def _load_csv(path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    rows_x: list[list[float]] = []
    rows_y: list[float] = []
    seasons: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            x = [_safe_float(r.get(col, "0")) for col in FEATURE_COLUMNS]
            y = _safe_float(r.get(TARGET_COLUMN, "0"))
            rows_x.append(x)
            rows_y.append(y)
            seasons.append(str(r.get("season", "unknown")))

    if len(rows_x) < 200:
        raise ValueError(f"Not enough rows in dataset: {len(rows_x)}")

    return np.array(rows_x, dtype=float), np.array(rows_y, dtype=float), seasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Train historical-season XGBoost model for FPL")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to historical training CSV")
    args = parser.parse_args()

    dataset = Path(args.dataset)
    if not dataset.exists():
        print(f"❌ Dataset not found: {dataset}")
        print("   Run: ./backend/ml/build_historical_dataset.py")
        return 1

    try:
        X, y, seasons = _load_csv(dataset)
        # Chronological split proxy (first 80% train, last 20% validation)
        split = int(len(X) * 0.8)
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]

        meta = train_from_arrays(
            X_train,
            y_train,
            model_version=HISTORICAL_MODEL_VERSION,
            extra_meta={
                "source": "historical_gw_rows",
                "dataset": str(dataset),
                "train_rows": int(len(X_train)),
                "val_rows": int(len(X_val)),
                "feature_columns": FEATURE_COLUMNS,
                "seasons": sorted(set(seasons)),
                "val_y_mean": float(np.mean(y_val)) if len(y_val) else None,
            },
        )

        print("✅ Trained historical model", meta)
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"❌ Historical training failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
