import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.db.models import Player, Fixture, UserSquadPick

client = TestClient(app)

@pytest.fixture
def mock_auth():
    with patch("app.core.security.API_KEY", "test_api_key"):
        with patch("app.core.security.ADMIN_API_KEY", "test_admin_key"):
            yield

@pytest.fixture
def mock_db_data():
    players = []
    for i in range(1, 16):
        p = Player(
            id=i,
            first_name=f"Player{i}",
            second_name=str(i),
            web_name=f"Player {i}",
            element_type=(i % 4) + 1,
            now_cost=50,
            form=5.0,
            points_per_game=5.0,
            minutes=2000,
            chance_of_playing_next_round=100,
            selected_by_percent=10.0,
            team_id=(i % 20) + 1,
            news="",
            goals_scored=0,
            assists=0,
            clean_sheets=0
        )
        players.append(p)
    return players

@pytest.fixture
def mock_db(mock_db_data):
    with patch("app.api.routes.team.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        def query_side_effect(model):
            query_mock = MagicMock()
            if model is Player:
                query_mock.all.return_value = mock_db_data
            elif model is Fixture:
                query_mock.all.return_value = []
            elif model is UserSquadPick:
                query_mock.filter.return_value.delete.return_value = None
            else:
                query_mock.all.return_value = []
            return query_mock
        
        mock_session.query.side_effect = query_side_effect
        mock_session.get.return_value = None
        yield mock_session

def test_team_recommendation_endpoint(mock_auth, mock_db, mock_db_data):
    entry_id = 12345
    picks = [{"element": i, "position": i} for i in range(1, 16)]
    with patch("app.api.routes.team._resolve_gameweek", return_value=10):
        with patch("app.api.routes.team._fetch_entry_picks_with_fallback", return_value=({"picks": picks, "entry_history": {}}, 10)):
            with patch("app.api.routes.team._build_lineup_from_squad") as mock_build:
                starting = [(5.0, p) for p in mock_db_data[:11]]
                bench = [(2.0, p) for p in mock_db_data[11:15]]
                mock_build.return_value = (starting, bench, "4-4-2")
                with patch("app.api.routes.team._choose_captains") as mock_cap:
                    mock_cap.return_value = (mock_db_data[0].web_name, mock_db_data[1].web_name)
                    response = client.get(f"/api/fpl/team/{entry_id}/recommendation?mode=balanced")
                    assert response.status_code == 200
                    data = response.json()
                    assert "starting_xi" in data
                    assert data["strategy_mode"] == "balanced"

def test_team_what_if_endpoint(mock_auth, mock_db, mock_db_data):
    entry_id = 12345
    picks = [{"element": i, "position": i} for i in range(1, 16)]
    with patch("app.api.routes.team._resolve_gameweek", return_value=10):
        with patch("app.api.routes.team._fetch_entry_picks_with_fallback", return_value=({"picks": picks, "entry_history": {}}, 10)):
            response = client.get(f"/api/fpl/team/{entry_id}/what-if?horizon=3&max_transfers=1")
            assert response.status_code == 200
            assert "scenarios" in response.json()

def test_chip_planner_endpoint(mock_auth, mock_db):
    with patch("app.api.routes.team._resolve_gameweek", return_value=10):
        with patch("app.api.routes.team._int", return_value=10):
            response = client.get("/api/fpl/chip-planner?horizon=6")
            assert response.status_code == 200
            assert "chip_scores" in response.json()

def test_rival_intelligence_endpoint(mock_auth, mock_db):
    with patch("app.api.routes.team._resolve_gameweek", return_value=10):
        with patch("app.api.routes.team._int", return_value=10):
            with patch("app.api.routes.team._fetch_entry_picks_with_fallback", return_value=({"picks": []}, 10)):
                response = client.get("/api/fpl/rival-intelligence?entry_id=123&rival_entry_id=456")
                assert response.status_code == 200
                assert "overlap_count" in response.json()

def test_weekly_digest_card_endpoint(mock_auth, mock_db):
    with patch("app.api.routes.team._resolve_gameweek", return_value=10):
        with patch("app.api.routes.team._get_meta", return_value="10"):
            response = client.get("/api/fpl/weekly-digest-card?mode=balanced")
            assert response.status_code == 200
            assert "final" in response.json()
