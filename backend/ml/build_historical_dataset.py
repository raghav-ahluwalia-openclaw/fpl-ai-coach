#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "bin" / "python"
if os.environ.get("FPL_ML_VENV_BOOTSTRAPPED") != "1" and VENV_PY.exists() and Path(sys.executable) != VENV_PY:
    env = os.environ.copy()
    env["FPL_ML_VENV_BOOTSTRAPPED"] = "1"
    os.execve(str(VENV_PY), [str(VENV_PY), __file__, *sys.argv[1:]], env)

DATA_DIR = ROOT / "data" / "historical"
DEFAULT_OUT = DATA_DIR / "training_rows.csv"


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-ai-coach/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:  # noqa: BLE001
        return default


def _rolling_mean(values: list[float], n: int) -> float:
    if not values:
        return 0.0
    window = values[-n:]
    return float(sum(window) / len(window))


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(statistics.pstdev(values))


def _season_urls(season: str) -> list[str]:
    base = f"https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{season}/gws"
    return [f"{base}/merged_gw.csv", f"{base}/merged_gw_updated.csv"]


def _download_season_gw(season: str) -> list[dict[str, Any]]:
    last_err = None
    for url in _season_urls(season):
        try:
            raw = _get(url)
            rows = list(csv.DictReader(raw.splitlines()))
            if rows:
                return rows
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"failed to fetch gw data for {season}: {last_err}")


def build_training_rows(seasons: list[str]) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []

    for season in seasons:
        season_rows = _download_season_gw(season)

        by_player: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in season_rows:
            player_name = row.get("name") or row.get("player_name") or ""
            if not player_name:
                continue
            by_player[player_name].append(row)

        for player_name, gw_rows in by_player.items():
            gw_rows.sort(key=lambda r: _safe_int(r.get("GW"), 0))

            points_hist: list[float] = []
            minutes_hist: list[float] = []
            goals_hist: list[float] = []
            assists_hist: list[float] = []
            ict_hist: list[float] = []

            for i, cur in enumerate(gw_rows[:-1]):
                nxt = gw_rows[i + 1]

                gw = _safe_int(cur.get("GW"), 0)
                next_points = _safe_float(nxt.get("total_points"), 0.0)
                cur_points = _safe_float(cur.get("total_points"), 0.0)
                cur_minutes = _safe_float(cur.get("minutes"), 0.0)
                cur_goals = _safe_float(cur.get("goals_scored"), 0.0)
                cur_assists = _safe_float(cur.get("assists"), 0.0)
                cur_ict = _safe_float(cur.get("ict_index"), 0.0)
                cur_selected = _safe_float(cur.get("selected"), _safe_float(cur.get("selected_by_percent"), 0.0))
                cur_value = _safe_float(cur.get("value"), _safe_float(cur.get("now_cost"), 0.0)) / 10.0

                points_hist.append(cur_points)
                minutes_hist.append(cur_minutes)
                goals_hist.append(cur_goals)
                assists_hist.append(cur_assists)
                ict_hist.append(cur_ict)

                if len(points_hist) < 3:
                    continue

                row_out = {
                    "season": season,
                    "player_name": player_name,
                    "gw": gw,
                    "points_rolling_3": round(_rolling_mean(points_hist[:-1], 3), 4),
                    "points_rolling_5": round(_rolling_mean(points_hist[:-1], 5), 4),
                    "minutes_rolling_3": round(_rolling_mean(minutes_hist[:-1], 3), 4),
                    "goals_rolling_5": round(_rolling_mean(goals_hist[:-1], 5), 4),
                    "assists_rolling_5": round(_rolling_mean(assists_hist[:-1], 5), 4),
                    "ict_rolling_3": round(_rolling_mean(ict_hist[:-1], 3), 4),
                    "points_volatility_5": round(_stdev(points_hist[:-1][-5:]), 4),
                    "selected_by": round(cur_selected, 4),
                    "price": round(cur_value, 4),
                    "position": _safe_int(cur.get("position"), 0),
                    "was_home": 1 if str(cur.get("was_home", "False")).lower() == "true" else 0,
                    "opponent_team": _safe_int(cur.get("opponent_team"), 0),
                    "target_next_points": round(next_points, 4),
                }
                rows_out.append(row_out)

    return rows_out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build historical FPL training rows from public season GW files")
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=["2022-23", "2023-24", "2024-25"],
        help="Season folders from vaastav/Fantasy-Premier-League data/",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output CSV path")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        rows = build_training_rows(args.seasons)
    except Exception as e:  # noqa: BLE001
        print(f"❌ Failed to build historical dataset: {e}")
        return 1

    if len(rows) < 200:
        print(f"❌ Too few training rows: {len(rows)}")
        return 1

    fieldnames = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "rows": len(rows),
                "seasons": args.seasons,
                "output": str(out_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"✅ Built historical dataset: {out_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
