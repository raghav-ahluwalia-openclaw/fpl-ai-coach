from unittest.mock import MagicMock, patch

from starlette.requests import Request

from app.api.routes import insights_settings as s


def _req() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/api/fpl/settings", "headers": []})


def test_helpers_meta_bool_and_key_user_scope():
    assert s._meta_bool("true") is True
    assert s._meta_bool("0") is False
    assert s._settings_key("scope", "fpl_entry_id") == "settings:scope:fpl_entry_id"

    with patch.object(s, "request_scope_identity", return_value="User+One@Telegram!#"):
        scope = s._user_scope(_req())
    assert scope == "userone@telegram"


def test_app_settings_get_with_name_backfill():
    db = MagicMock()

    def _meta(_db, key):
        vals = {
            "settings:default:fpl_entry_id": "12345",
            "settings:default:league_id": "777",
            "settings:default:rival_entry_id": "54321",
            "entry:12345:entry_name": "",
            "entry:12345:player_name": "",
        }
        return vals.get(key, "")

    with patch.object(s, "SessionLocal", return_value=db), patch.object(
        s, "request_scope_identity", return_value="default"
    ), patch.object(s, "_get_meta", side_effect=_meta), patch(
        "app.services.http_client.fetch_json",
        return_value={"name": "My Team", "player_first_name": "Raghav", "player_last_name": "A"},
    ):
        out = s.app_settings_get(_req())

    assert out["fpl_entry_id"] == 12345
    assert out["league_id"] == 777
    assert out["entry_name"] == "My Team"
    assert out["player_name"] == "Raghav A"


def test_app_settings_set_and_notification_roundtrip():
    db = MagicMock()
    with patch.object(s, "SessionLocal", return_value=db), patch.object(
        s, "request_scope_identity", return_value="default"
    ), patch.object(s, "_set_meta") as set_meta, patch.object(
        s, "app_settings_get", return_value={"scope": "default", "fpl_entry_id": 1}
    ):
        out = s.app_settings_set(_req(), fpl_entry_id=1, league_id=2, rival_entry_id=3, clear_missing=False)

    assert out["fpl_entry_id"] == 1
    assert set_meta.call_count == 3
    db.commit.assert_called()

    # notification get clamps and normalizes values
    with patch.object(s, "SessionLocal", return_value=db), patch.object(
        s, "_get_meta", side_effect=lambda _db, k: {
            "notif_enabled": "true",
            "notif_lead_hours": "500",
            "notif_mode": "bad_mode",
            "notif_model_version": "unknown",
        }.get(k, "")
    ):
        ng = s.notification_settings_get()
    assert ng["enabled"] is True
    assert ng["lead_hours"] == 72
    assert ng["mode"] == "balanced"

    with patch.object(s, "SessionLocal", return_value=db), patch.object(s, "_set_meta") as set_meta2:
        ns = s.notification_settings_set(enabled=False, lead_hours=4, mode="safe", model_version="xgb_hist_v1")
    assert ns["ok"] is True
    assert set_meta2.call_count == 4
