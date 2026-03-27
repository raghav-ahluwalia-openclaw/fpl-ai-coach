#!/usr/bin/env python3
"""Backend validation script for FPL AI Coach.

Best-practice goals:
- Start app in a clean subprocess (isolated port)
- Wait for readiness with timeout
- Hit core endpoints and validate response shape
- Exit non-zero on any failure
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"


def _pick_port() -> int:
    env_port = os.getenv("VALIDATION_PORT")
    if env_port:
        return int(env_port)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


PORT = _pick_port()
BASE = f"http://127.0.0.1:{PORT}"
TEAM_ID = int(os.getenv("FPL_TEAM_ID", "538572"))
TIMEOUT_SECONDS = int(os.getenv("VALIDATION_STARTUP_TIMEOUT", "20"))


def _read_env_file_value(key: str) -> str:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return ""


ADMIN_API_TOKEN = (
    os.getenv("VALIDATION_ADMIN_API_KEY")
    or os.getenv("ADMIN_API_KEY")
    or _read_env_file_value("ADMIN_API_KEY")
)
AUTH_HEADERS = {"X-Admin-Token": ADMIN_API_TOKEN} if ADMIN_API_TOKEN else {}


def _request(method: str, path: str, *, timeout: int = 25, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    req = urllib.request.Request(url=url, method=method)
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body else {}
            return resp.status, data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"raw": body}
        return e.code, payload


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _wait_for_health() -> None:
    deadline = time.time() + TIMEOUT_SECONDS
    last_err = None
    while time.time() < deadline:
        try:
            code, data = _request("GET", "/health", timeout=3)
            if code == 200 and isinstance(data, dict) and data.get("ok") is True:
                return
            last_err = f"Unexpected /health response: {code} {data}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(0.5)
    raise RuntimeError(f"Backend did not become healthy in {TIMEOUT_SECONDS}s. Last error: {last_err}")


def main() -> int:
    if not VENV_PYTHON.exists():
        print("❌ backend virtualenv not found at backend/.venv. Run setup first.")
        return 1

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_health()

        # 1) Ingest (fast path may return skipped=true if cache is warm)
        code, data = _request("POST", "/api/fpl/ingest/bootstrap", headers=AUTH_HEADERS)
        _assert(code == 200, f"ingest failed: {code} {data}")
        _assert(data.get("ok") is True, f"ingest response invalid: {data}")
        if not data.get("skipped"):
            _assert(int(data.get("players", 0)) > 100, f"unexpected players count: {data}")

        # 2) Global recommendation
        code, data = _request("GET", "/api/fpl/recommendation")
        _assert(code == 200, f"global recommendation failed: {code} {data}")
        for key in ["lineup", "captain", "vice_captain", "confidence"]:
            _assert(key in data, f"global recommendation missing key '{key}': {data}")

        # 3) ML recommendation (auto-trains model artifact if missing)
        code, data = _request("GET", "/api/fpl/recommendation-ml")
        _assert(code == 200, f"ml recommendation failed: {code} {data}")
        for key in ["lineup", "captain", "vice_captain", "confidence"]:
            _assert(key in data, f"ml recommendation missing key '{key}': {data}")

        # 4) Team import
        path = f"/api/fpl/team/{TEAM_ID}/import"
        code, data = _request("POST", path, headers=AUTH_HEADERS)
        _assert(code == 200, f"team import failed for team {TEAM_ID}: {code} {data}")
        _assert(data.get("ok") is True, f"team import invalid: {data}")

        # 4) Team recommendation (balanced)
        path = f"/api/fpl/team/{TEAM_ID}/recommendation?mode=balanced"
        code, data = _request("GET", path)
        _assert(code == 200, f"team recommendation failed for team {TEAM_ID}: {code} {data}")
        for key in ["starting_xi", "bench", "transfer_out", "transfer_in", "strategy_mode"]:
            _assert(key in data, f"team recommendation missing key '{key}': {data}")
        _assert(data.get("strategy_mode") == "balanced", f"strategy_mode mismatch: {data}")

        # 5) One lightweight insights endpoint
        code, data = _request("GET", "/api/fpl/top?limit=10")
        _assert(code == 200, f"top players failed: {code} {data}")
        _assert(isinstance(data.get("players"), list) and len(data["players"]) > 0, f"top players invalid: {data}")

        # 6) App settings + notification + weekly-brief endpoints
        code, data = _request("GET", "/api/fpl/settings")
        _assert(code == 200, f"settings GET failed: {code} {data}")

        code, data = _request(
            "POST",
            "/api/fpl/settings?fpl_entry_id=538572&league_id=12345&rival_entry_id=538573",
            headers=AUTH_HEADERS,
        )
        _assert(code == 200, f"settings POST failed: {code} {data}")
        _assert(data.get("fpl_entry_id") == 538572, f"settings response invalid: {data}")

        code, data = _request("GET", "/api/fpl/notification-status")
        _assert(code == 200, f"notification-status failed: {code} {data}")
        _assert("preview_message" in data and "status" in data, f"notification-status shape invalid: {data}")

        code, data = _request("GET", "/api/fpl/weekly-brief?mode=balanced&model_version=xgb_hist_v1")
        _assert(code == 200, f"weekly-brief failed: {code} {data}")
        _assert("final" in data and "captain" in data["final"], f"weekly-brief shape invalid: {data}")

        # 7) What-if simulator endpoint
        code, data = _request("GET", f"/api/fpl/team/{TEAM_ID}/what-if?horizon=3&max_transfers=2&limit=5")
        _assert(code == 200, f"what-if simulator failed: {code} {data}")
        _assert("scenarios" in data and isinstance(data["scenarios"], list), f"what-if response invalid: {data}")

        # 8) Captaincy + explainability + P3 planner endpoints
        code, data = _request("GET", "/api/fpl/captaincy-lab?limit=5")
        _assert(code == 200, f"captaincy-lab failed: {code} {data}")
        _assert("safe_captains" in data and "upside_captains" in data, f"captaincy-lab shape invalid: {data}")

        code, data = _request("GET", "/api/fpl/explainability/top?limit=10")
        _assert(code == 200, f"explainability failed: {code} {data}")
        _assert("players" in data and isinstance(data["players"], list), f"explainability shape invalid: {data}")

        code, data = _request("GET", "/api/fpl/chip-planner?horizon=6")
        _assert(code == 200, f"chip-planner failed: {code} {data}")
        _assert("chip_scores" in data and "recommendation" in data, f"chip-planner shape invalid: {data}")

        code, data = _request("GET", f"/api/fpl/rival-intelligence?entry_id={TEAM_ID}&rival_entry_id={TEAM_ID+1}")
        _assert(code == 200, f"rival-intelligence failed: {code} {data}")
        _assert("overlap_count" in data and "captaincy" in data and "differential_impact" in data, f"rival-intelligence shape invalid: {data}")

        code, data = _request("GET", "/api/fpl/weekly-digest-card?mode=balanced&model_version=xgb_hist_v1")
        _assert(code == 200, f"weekly-digest-card failed: {code} {data}")
        _assert("final" in data and "title" in data, f"weekly-digest-card shape invalid: {data}")

        # 9) Backend unit tests for notification endpoints
        test_run = subprocess.run(
            [str(VENV_PYTHON), "-m", "unittest", "tests.test_notification_endpoints", "-v"],
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
        )
        _assert(
            test_run.returncode == 0,
            "notification endpoint tests failed:\n"
            f"{(test_run.stdout or '')[-1200:]}\n{(test_run.stderr or '')[-1200:]}",
        )

        print("✅ Backend validation passed")
        return 0

    except Exception as e:  # noqa: BLE001
        print(f"❌ Backend validation failed: {e}")
        # Avoid blocking reads from live process pipes on failure paths.
        return 1
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
