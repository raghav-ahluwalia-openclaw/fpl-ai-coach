from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.api.routes.base import _resolve_gameweek
from app.db import Base, SessionLocal, engine
from app.db.models import Meta


class GameweekMetaSyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.create_all(bind=engine)

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

    def _get_meta(self, key: str) -> str | None:
        db = SessionLocal()
        try:
            row = db.get(Meta, key)
            return row.value if row else None
        finally:
            db.close()

    def test_resolve_gameweek_auto_syncs_stale_meta(self) -> None:
        # Simulate stale state where current and next GW are stuck at the same value.
        self._set_meta("current_gw", "31")
        self._set_meta("next_gw", "31")
        self._set_meta("next_deadline_utc", "2026-03-24T06:26:20.890458Z")
        self._set_meta(
            "last_gw_meta_sync_at",
            (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        self._set_meta(
            "last_gw_meta_sync_check_at",
            (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )

        fake_bootstrap = {
            "events": [
                {"id": 31, "is_current": True, "is_next": False, "deadline_time": "2026-03-20T18:30:00Z"},
                {"id": 32, "is_current": False, "is_next": True, "deadline_time": "2026-04-10T17:30:00Z"},
            ]
        }

        db = SessionLocal()
        try:
            with patch("app.api.routes.base.fetch_json", return_value=fake_bootstrap):
                gw = _resolve_gameweek(db, None)
            self.assertEqual(gw, 32)
        finally:
            db.close()

        self.assertEqual(self._get_meta("next_gw"), "32")
        self.assertEqual(self._get_meta("current_gw"), "31")
        self.assertEqual(self._get_meta("next_deadline_utc"), "2026-04-10T17:30:00Z")

    def test_resolve_gameweek_shifts_to_next_after_completion(self) -> None:
        self._set_meta("current_gw", "31")
        self._set_meta("next_gw", "32")
        self._set_meta(
            "last_gw_meta_sync_check_at",
            (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )

        fake_bootstrap = {
            "events": [
                {"id": 31, "is_current": True, "is_next": False, "finished": True, "deadline_time": "2026-03-20T18:30:00Z"},
                {"id": 32, "is_current": False, "is_next": True, "deadline_time": "2026-04-10T17:30:00Z"},
            ]
        }
        fake_fixtures: list[dict] = []

        db = SessionLocal()
        try:
            with patch("app.api.routes.base.fetch_json", side_effect=[fake_bootstrap, fake_fixtures]):
                gw = _resolve_gameweek(db, None)
            self.assertEqual(gw, 32)
        finally:
            db.close()

        self.assertEqual(self._get_meta("current_gw"), "32")
        self.assertEqual(self._get_meta("next_gw"), "32")


if __name__ == "__main__":
    unittest.main()
