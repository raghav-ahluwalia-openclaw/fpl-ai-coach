from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class LiveAndDiagnosticsEndpointsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

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
        # Mock environment variables for authentication
        with patch("app.core.security.API_KEY", "test_api_key"):
            with patch("app.core.security.ADMIN_API_KEY", "test_admin_key"):
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
