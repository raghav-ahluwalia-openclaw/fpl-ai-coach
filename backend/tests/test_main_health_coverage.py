import os
from unittest.mock import MagicMock, patch

import pytest

from app import main


def test_check_database_up_and_down():
    ok_ctx = MagicMock()
    ok_ctx.__enter__.return_value = MagicMock()
    ok_ctx.__exit__.return_value = False

    with patch.object(main.engine, "connect", return_value=ok_ctx):
        up = main._check_database()
    assert up["status"] == "up"

    with patch.object(main.engine, "connect", side_effect=RuntimeError("db down")):
        down = main._check_database()
    assert down["status"] == "down"
    assert "db down" in down["error"]


@pytest.mark.asyncio
async def test_check_fpl_upstream_skip_and_down():
    os.environ["HEALTHCHECK_FPL_UPSTREAM"] = "0"
    skipped = await main._check_fpl_upstream()
    assert skipped["status"] == "skipped"

    os.environ["HEALTHCHECK_FPL_UPSTREAM"] = "1"

    class BrokenClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url):
            raise RuntimeError("timeout")

    with patch("app.main.httpx.AsyncClient", return_value=BrokenClient()):
        down = await main._check_fpl_upstream()
    assert down["status"] == "down"


@pytest.mark.asyncio
async def test_health_ready_live_and_root_shapes():
    class Mem:
        rss = 10 * 1024 * 1024
        vms = 50 * 1024 * 1024

    proc = MagicMock()
    proc.memory_info.return_value = Mem()

    with patch("psutil.Process", return_value=proc), patch.object(
        main, "_check_database", return_value={"status": "up", "latency_ms": 1.0}
    ), patch.object(main, "_check_fpl_upstream", return_value={"status": "up", "http_status": 200, "latency_ms": 2.0}):
        health = await main.health_check()
        ready = await main.readiness_check()
        live = await main.liveness_check()
        root = await main.root()

    assert health.status_code == 200
    assert ready.status_code == 200
    assert live["ok"] is True
    assert root["name"] == "FPL AI Coach API"
