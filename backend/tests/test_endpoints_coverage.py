import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.db import get_db
from app.db.models import Player, Fixture, UserSquadPick
from app.services.ttl_cache import api_ttl_cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    api_ttl_cache.clear()
    yield
    api_ttl_cache.clear()


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
    mock_session = MagicMock()

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

    app.dependency_overrides[get_db] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.clear()


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


def test_team_simulation_lab_endpoint(mock_auth, mock_db, mock_db_data):
    entry_id = 12345
    picks = [{"element": i, "position": i} for i in range(1, 16)]
    with patch("app.api.routes.team._resolve_gameweek", return_value=10):
        with patch("app.api.routes.team._fetch_entry_picks_with_fallback", return_value=({"picks": picks, "entry_history": {}}, 10)):
            response = client.get(f"/api/fpl/team/{entry_id}/simulation-lab?iterations=500")
            assert response.status_code == 200
            payload = response.json()
            assert payload["schema"] == "simulation-lab-v1"
            assert "captain_outcome_bands" in payload
            assert "transfer_outcome_bands" in payload


def test_chip_planner_endpoint(mock_auth, mock_db):
    with patch("app.api.routes.insights_planner._resolve_gameweek", return_value=10):
        response = client.get("/api/fpl/chip-planner?horizon=6")
        assert response.status_code == 200
        assert "chip_scores" in response.json()


def test_rival_intelligence_endpoint(mock_auth, mock_db):
    with patch("app.api.routes.insights_planner._resolve_gameweek", return_value=10):
        with patch("app.services.planner_service._fetch_entry_picks_with_fallback", return_value=({"picks": []}, 10)):
            response = client.get("/api/fpl/rival-intelligence?entry_id=123&rival_entry_id=456")
            assert response.status_code == 200
            assert "overlap_count" in response.json()


def test_weekly_digest_card_endpoint(mock_auth, mock_db):
    with patch("app.api.routes.insights._resolve_gameweek", return_value=10), \
         patch("app.api.routes.insights_brief.recommendation_ml", side_effect=HTTPException(status_code=503)):
        response = client.get("/api/fpl/weekly-digest-card?mode=balanced")
        assert response.status_code == 200
        assert "final" in response.json()


def test_recommendation_endpoint(mock_auth, mock_db, mock_db_data):
    with patch("app.api.routes.insights._resolve_gameweek", return_value=10):
        response = client.get("/api/fpl/recommendation")
    assert response.status_code == 200
    data = response.json()
    assert "lineup" in data
    assert "captain" in data
    assert "gameweek" in data


def test_recommendation_no_players(mock_auth):
    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = []
    mock_session.get.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/api/fpl/recommendation")
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_rank_history_endpoint(mock_auth, mock_db):
    fake_history = {
        "current": [
            {"event": 1, "overall_rank": 500000, "points": 65, "total_points": 65},
            {"event": 2, "overall_rank": 400000, "points": 72, "total_points": 137},
        ]
    }
    with patch("app.api.routes.team.fetch_json", return_value=fake_history):
        response = client.get("/api/fpl/team/12345/rank-history")
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    assert data["best_rank"] == 400000


def test_rank_history_empty(mock_auth, mock_db):
    with patch("app.api.routes.team.fetch_json", return_value={"current": []}):
        response = client.get("/api/fpl/team/12345/rank-history")
    assert response.status_code == 200
    assert response.json()["points"] == []


def test_performance_weekly_endpoint(mock_auth, mock_db):
    fake_history = {
        "current": [
            {"event": i, "points": 60 + i, "total_points": 60 * i, "overall_rank": 500000 - i * 1000,
             "event_transfers": 0, "event_transfers_cost": 0}
            for i in range(1, 4)
        ]
    }
    # _performance_weekly calls fetch_json for: history, transfers, then per-event live + picks
    # Return empty transfers and empty data for subsequent calls to avoid complexity
    def _side_effect(url, **kwargs):
        if "history" in url and "entry" in url:
            return fake_history
        if "transfers" in url:
            return []
        if "live" in url:
            return {"elements": []}
        if "entry" in url:
            return {"picks": [], "active_chip": None}
        return {}
    with patch("app.api.routes.team.fetch_json", side_effect=_side_effect):
        response = client.get("/api/fpl/performance/weekly?entry_id=12345&lookback=5")
    assert response.status_code == 200
    data = response.json()
    assert "weeks" in data or "gameweeks" in data or "summary" in data


def test_gameweek_hub_endpoint(mock_auth, mock_db, mock_db_data):
    picks = [{"element": i, "position": i, "multiplier": 1, "is_captain": i == 1, "is_vice_captain": i == 2} for i in range(1, 16)]
    with patch("app.api.routes.team._resolve_gameweek", return_value=10), \
         patch("app.api.routes.team._fetch_entry_picks_with_fallback", return_value=({"picks": picks, "entry_history": {}}, 10)):
        response = client.get("/api/fpl/team/12345/gameweek-hub?mode=balanced")
    assert response.status_code == 200
    data = response.json()
    assert "entry_id" in data or "gameweek" in data


def test_leagues_endpoint(mock_auth, mock_db):
    fake_entry = {
        "leagues": {
            "classic": [
                {"id": 1, "name": "My League", "entry_rank": 5, "last_rank": 7}
            ],
            "h2h": []
        }
    }
    fake_standings = {
        "standings": {
            "results": [{"entry": 12345, "total": 300, "entry_name": "My Team", "player_name": "Player",
                         "rank": 5, "last_rank": 7, "rank_sort": 5}]
        }
    }

    call_count = [0]
    def _fetch_json_side_effect(url, **kwargs):
        call_count[0] += 1
        if "entry/12345/" in url:
            return fake_entry
        return fake_standings

    with patch("app.api.routes.team.fetch_json", side_effect=_fetch_json_side_effect):
        response = client.get("/api/fpl/team/12345/leagues")
    assert response.status_code == 200
    data = response.json()
    assert "leagues" in data
