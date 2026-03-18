from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Meta


class NotificationEndpointsTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
