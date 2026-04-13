import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.db.models import UserSquadPick

client = TestClient(app)

def test_import_user_team_success():
    entry_id = 12345
    fake_picks_payload = {
        "picks": [
            {"element": 1, "position": 1, "multiplier": 1, "is_captain": False, "is_vice_captain": True},
            {"element": 2, "position": 2, "multiplier": 1, "is_captain": True, "is_vice_captain": False},
        ],
        "entry_history": {"points": 50, "bank": 50, "value": 1000}
    }
    
    with patch("app.api.routes.team._resolve_gameweek", return_value=10):
        with patch("app.api.routes.team._get_meta", return_value="10"):
            with patch("app.api.routes.team._fetch_entry_picks_with_fallback", return_value=(fake_picks_payload, 10)):
                with patch("app.api.routes.team._set_meta") as mock_set_meta:
                    with patch("app.core.security.API_KEY", "test_api_key"):
                        with patch("app.core.security.ADMIN_API_KEY", "test_admin_key"):
                            response = client.post(
                                f"/api/fpl/team/{entry_id}/import",
                                headers={"x-api-key": "test_api_key"}
                            )
    
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "entry_id": entry_id,
        "gameweek": 10,
        "picks_imported": 2,
        "bank": 5.0,
        "value": 100.0
    }
