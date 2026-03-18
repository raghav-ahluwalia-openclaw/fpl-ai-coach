#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
from app.services.ml_recommender import train_and_save_model  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Train FPL XGBoost recommender model")
    parser.add_argument("--gameweek", type=int, default=None, help="Optional GW for fixture-context features")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        players = db.query(Player).all()
        fixtures = db.query(Fixture).all()
        meta = train_and_save_model(players, fixtures, args.gameweek)
        print("✅ Trained model", meta)
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"❌ Training failed: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
