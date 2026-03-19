#!/usr/bin/env python3
"""Integration validation for frontend↔backend wiring.

Checks in one run:
- starts backend (isolated port)
- starts frontend production server with BACKEND_ORIGIN override
- verifies app pages load
- verifies frontend /api rewrite routes to backend
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
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"


def _pick_port(env_key: str, default_hint: int) -> int:  # noqa: ARG001
    env_port = os.getenv(env_key)
    if env_port:
        return int(env_port)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


BACKEND_PORT = _pick_port("INTEGRATION_BACKEND_PORT", 8093)
FRONTEND_PORT = _pick_port("INTEGRATION_FRONTEND_PORT", 3091)
BASE_FRONT = f"http://127.0.0.1:{FRONTEND_PORT}"
TEAM_ID = int(os.getenv("FPL_TEAM_ID", "538572"))
TIMEOUT_SECONDS = int(os.getenv("INTEGRATION_STARTUP_TIMEOUT", "30"))


def _request(method: str, url: str, *, timeout: int = 25) -> tuple[int, str]:
    req = urllib.request.Request(url=url, method=method)
    req.add_header("Accept", "application/json,text/html,*/*")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _wait(url: str) -> None:
    deadline = time.time() + TIMEOUT_SECONDS
    last = None
    while time.time() < deadline:
        try:
            code, _ = _request("GET", url, timeout=3)
            if code in (200, 302, 307):
                return
            last = f"status={code}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}; last={last}")


def _terminate(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    if not VENV_PYTHON.exists():
        print("❌ backend/.venv missing")
        return 1

    backend_proc = None
    frontend_proc = None

    try:
        print(f"[integration] backend_port={BACKEND_PORT} frontend_port={FRONTEND_PORT}")
        backend_env = os.environ.copy()
        backend_proc = subprocess.Popen(
            [
                str(VENV_PYTHON),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(BACKEND_PORT),
            ],
            cwd=str(BACKEND_DIR),
            env=backend_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        _wait(f"http://127.0.0.1:{BACKEND_PORT}/health")

        # Build frontend with BACKEND_ORIGIN so rewrites target this backend port.
        front_env = os.environ.copy()
        front_env["BACKEND_ORIGIN"] = f"http://127.0.0.1:{BACKEND_PORT}"

        skip_build = os.getenv("INTEGRATION_SKIP_FRONTEND_BUILD", "0") == "1"
        if not skip_build:
            build_proc = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(FRONTEND_DIR),
                env=front_env,
                capture_output=True,
                text=True,
            )
            if build_proc.returncode != 0:
                raise RuntimeError(
                    "frontend build failed in integration validation:\n"
                    f"{(build_proc.stdout or '')[-1200:]}\n{(build_proc.stderr or '')[-1200:]}"
                )

        frontend_proc = subprocess.Popen(
            [
                "npm",
                "run",
                "start",
                "--",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(FRONTEND_PORT),
            ],
            cwd=str(FRONTEND_DIR),
            env=front_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        _wait(f"{BASE_FRONT}/")

        # Core pages (smoke set)
        for path in ["/", "/team", "/captaincy", "/planner", "/settings"]:
            code, _ = _request("GET", f"{BASE_FRONT}{path}")
            _assert(code == 200, f"page load failed {path}: {code}")

        # Rewrites through frontend to backend
        code, body = _request("POST", f"{BASE_FRONT}/api/fpl/ingest/bootstrap")
        _assert(code == 200, f"frontend rewrite ingest failed: {code} {body[:200]}")

        for path in [
            "/api/fpl/recommendation",
            "/api/fpl/recommendation-ml",
            "/api/fpl/settings",
            "/api/fpl/notification-status",
            "/api/fpl/weekly-brief?mode=balanced&model_version=xgb_hist_v1",
            "/api/fpl/top?limit=10",
            f"/api/fpl/team/{TEAM_ID}/recommendation?mode=balanced",
            f"/api/fpl/team/{TEAM_ID}/what-if?horizon=3&max_transfers=2&limit=5",
            "/api/fpl/captaincy-lab?limit=5",
            "/api/fpl/explainability/top?limit=10",
            "/api/fpl/chip-planner?horizon=6",
            f"/api/fpl/rival-intelligence?entry_id={TEAM_ID}&rival_entry_id={TEAM_ID+1}",
            "/api/fpl/weekly-digest-card?mode=balanced&model_version=xgb_hist_v1",
        ]:
            code, body = _request("GET", f"{BASE_FRONT}{path}")
            _assert(code == 200, f"frontend rewrite failed {path}: {code} {body[:200]}")
            try:
                json.loads(body)
            except Exception as e:  # noqa: BLE001
                raise AssertionError(f"non-json API response for {path}: {e}")

        print("✅ Integration validation passed")
        return 0

    except Exception as e:  # noqa: BLE001
        print(f"❌ Integration validation failed: {e}")
        return 1

    finally:
        _terminate(frontend_proc)
        _terminate(backend_proc)


if __name__ == "__main__":
    sys.exit(main())
