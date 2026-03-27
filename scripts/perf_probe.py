#!/usr/bin/env python3
"""Lightweight perf probe for key endpoints (no external services required).

Usage:
  ./scripts/perf_probe.py --base http://127.0.0.1:8000 --runs 3
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def hit(url: str, timeout: int = 15) -> tuple[int, float]:
    started = time.perf_counter()
    req = urllib.request.Request(url=url, method="GET")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        _ = resp.read()
        status = resp.status
    elapsed_ms = (time.perf_counter() - started) * 1000
    return status, elapsed_ms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", default="outputs/perf-latest.json")
    args = parser.parse_args()

    targets = [
        "/health",
        "/api/fpl/gameweek-status",
        "/api/fpl/top?limit=20&compact=true",
        "/api/fpl/explainability/top?limit=20&include_next_5=false",
        "/api/fpl/captaincy-lab?limit=10",
    ]

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base": args.base,
        "runs": args.runs,
        "results": {},
    }

    for path in targets:
        samples = []
        status = 0
        for _ in range(max(1, args.runs)):
            status, elapsed_ms = hit(f"{args.base}{path}")
            samples.append(round(elapsed_ms, 2))
        report["results"][path] = {
            "status": status,
            "samples_ms": samples,
            "avg_ms": round(sum(samples) / len(samples), 2),
            "p95_ms": sorted(samples)[max(0, int(len(samples) * 0.95) - 1)],
        }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved perf report -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
