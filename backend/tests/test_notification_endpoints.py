from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("API_KEY", "test_api_key")
os.environ.setdefault("ADMIN_API_KEY", "test_admin_key")

from app.db import SessionLocal
from app.db.models import Meta
from app.main import app


class NotificationEndpointsTest(unittest.TestCase):
    auth_headers = {"X-Admin-Token": os.environ.get("ADMIN_API_KEY", "test_admin_key")}

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def _set_meta(self, key: str, value: str) -> None:
        db = SessionLocal()
        try:
            row = db.get(Meta, key)
            if row is None:
                row = Meta(key=key, value=value)
                db.add(row)
            else:
                row.value = value
                row.updated_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    def setUp(self) -> None:
        now = datetime.now(timezone.utc)
        self._set_meta("next_gw", "31")
        self._set_meta("next_deadline_utc", (now + timedelta(hours=48)).isoformat())
        self._set_meta("notif_enabled", "false")
        self._set_meta("notif_lead_hours", "6")
        self._set_meta("notif_mode", "balanced")
        self._set_meta("notif_model_version", "xgb_hist_v1")

    def test_settings_roundtrip(self) -> None:
        r = self.client.post(
            "/api/fpl/notification-settings",
            params={
                "enabled": True,
                "lead_hours": 8,
                "mode": "safe",
                "model_version": "xgb_v1",
            },
            headers=self.auth_headers,
        )
        self.assertEqual(r.status_code, 200)

        g = self.client.get("/api/fpl/notification-settings")
        self.assertEqual(g.status_code, 200)
        payload = g.json()
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["lead_hours"], 8)
        self.assertEqual(payload["mode"], "safe")
        self.assertEqual(payload["model_version"], "xgb_v1")

    def test_notification_status_shape(self) -> None:
        r = self.client.get("/api/fpl/notification-status")
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertIn("status", payload)
        self.assertIn("preview_message", payload)
        self.assertIn("next_check_utc", payload["status"])
        self.assertIn("last_check_utc", payload["status"])

    def test_notification_test_endpoint(self) -> None:
        r = self.client.get("/api/fpl/notification-test")
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("dry_run"))
        self.assertIsInstance(payload.get("test_message"), str)

    def test_gameweek_status_shape(self) -> None:
        fake_bootstrap = {
            "events": [
                {"id": 31, "is_current": True, "is_next": False, "finished": True, "data_checked": True},
                {"id": 32, "is_current": False, "is_next": True, "deadline_time": "2026-04-10T17:30:00Z"},
            ]
        }
        with patch("app.api.routes.insights_notifications.fetch_json", return_value=fake_bootstrap):
            r = self.client.get("/api/fpl/gameweek-status")
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        for key in [
            "current_gw",
            "next_gw",
            "current_gw_status",
            "gw_in_progress",
            "transfer_deadline_utc",
            "seconds_until_deadline",
            "season_phase",
        ]:
            self.assertIn(key, payload)
        self.assertEqual(payload.get("current_gw"), 32)
        self.assertEqual(payload.get("next_gw"), 33)
        self.assertEqual(payload.get("completed_gw"), 31)
        self.assertEqual(payload.get("current_gw_status"), "upcoming")


if __name__ == "__main__":
    unittest.main()
