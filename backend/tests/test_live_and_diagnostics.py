from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import Player, Fixture
from app.main import app
from app.services.ttl_cache import api_ttl_cache


def _make_mock_session():
    mock_session = MagicMock()
    mock_session.get.return_value = None

    def _query(model):
        q = MagicMock()
        if model is Player:
            q.all.return_value = []
        elif model is Fixture:
            q.all.return_value = []
        else:
            q.all.return_value = []
        return q

    mock_session.query.side_effect = _query
    return mock_session


class LiveAndDiagnosticsEndpointsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mock_session = _make_mock_session()
        app.dependency_overrides[get_db] = lambda: cls.mock_session
        cls.client = TestClient(app)
        api_ttl_cache.clear()

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()
        api_ttl_cache.clear()

    def test_team_live_view_shape(self) -> None:
        fake_picks_payload = {
            "picks": [
                {"element": 1, "position": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False},
                {"element": 2, "position": 12, "multiplier": 0, "is_captain": False, "is_vice_captain": True},
            ]
        }
        fake_live_payload = {
            "elements": [
                {"id": 1, "stats": {"total_points": 5}},
                {"id": 2, "stats": {"total_points": 3}},
            ]
        }

        with patch("app.api.routes.team._fetch_entry_picks_with_fallback", return_value=(fake_picks_payload, 31)):
            with patch("app.api.routes.team.fetch_json", return_value=fake_live_payload):
                r = self.client.get("/api/fpl/team/538572/live")

        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertEqual(payload["gameweek"], 31)
        self.assertIn("live_summary", payload)
        self.assertEqual(payload["live_summary"]["total_live_points"], 10)
        self.assertIn("players", payload)
        self.assertTrue(any(p.get("is_captain") for p in payload["players"]))

    def test_diagnostics_shape(self) -> None:
        with patch("app.core.security.API_KEY", "test_api_key"):
            with patch("app.core.security.ADMIN_API_KEY", "test_admin_key"):
                with patch("app.api.routes.ingest.diagnostics_access_check", return_value=None):
                    with patch("app.api.routes.ingest.engine") as mock_engine:
                        mock_conn = MagicMock()
                        mock_conn.__enter__.return_value = mock_conn
                        mock_conn.__exit__.return_value = False
                        mock_engine.connect.return_value = mock_conn
                        r = self.client.get(
                            "/api/fpl/diagnostics",
                            headers={"x-admin-token": "test_admin_key"}
                        )
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("counts", payload)
        self.assertIn("meta", payload)
        self.assertIn("troubleshooting", payload)


if __name__ == "__main__":
    unittest.main()
