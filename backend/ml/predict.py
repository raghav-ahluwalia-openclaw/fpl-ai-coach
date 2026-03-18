#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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

from app.db import SessionLocal  # noqa: E402
from app.models import Fixture, Player  # noqa: E402
from app.services.ml_recommender import load_model, predict_expected_points  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview top FPL ML projections")
    parser.add_argument("--gameweek", type=int, default=None)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    model = load_model()
    if model is None:
        print("❌ No model artifact found. Run backend/ml/train_xgb.py first.")
        return 1

    db = SessionLocal()
    try:
        players = db.query(Player).all()
        fixtures = db.query(Fixture).all()
        scored = predict_expected_points(model, players, fixtures, args.gameweek)
        out = [
            {
                "id": p.id,
                "name": p.web_name,
                "position": p.element_type,
                "price": p.now_cost / 10.0,
                "ml_xp": xp,
            }
            for xp, p in scored[: args.limit]
        ]
        print(json.dumps(out, indent=2))
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"❌ Prediction failed: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
