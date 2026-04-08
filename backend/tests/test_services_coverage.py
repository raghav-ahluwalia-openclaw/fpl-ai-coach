import pytest
from unittest.mock import MagicMock, patch
from app.services.captaincy_service import explainability_breakdown, build_captaincy_lab, build_explainability_top
from app.services.planner_service import build_chip_planner, build_rival_intelligence
from app.db.models import Player, Fixture

@pytest.fixture
def mock_player():
    p = Player(
        id=1,
        web_name="Salah",
        element_type=3,  # Midfielder
        now_cost=125,
        form=8.5,
        minutes=2700,
        chance_of_playing_next_round=100,
        news="",
        selected_by_percent=45.0,
        team_id=1
    )
    return p

@pytest.fixture
def mock_fixture():
    f = Fixture(
        id=101,
        event=10,
        team_h=1,
        team_a=2,
        team_h_difficulty=2,
        team_a_difficulty=4
    )
    return f

def test_explainability_breakdown(mock_player, mock_fixture):
    # We need to mock the scoring factors from base
    with patch("app.services.captaincy_service._fixture_factor", return_value=1.0):
        with patch("app.services.captaincy_service._availability_factor", return_value=1.0):
            with patch("app.services.captaincy_service._minutes_factor", return_value=1.0):
                result = explainability_breakdown(mock_player, [mock_fixture], 10)
                assert "form_score" in result
                assert "fixture_score" in result
                assert "volatility" in result

def test_build_captaincy_lab(mock_player, mock_fixture):
    with patch("app.services.captaincy_service._expected_points", return_value=6.5):
        with patch("app.services.captaincy_service._expected_points_horizon", return_value=18.0):
            with patch("app.services.captaincy_service._fixture_count_for_gw", return_value=1):
                with patch("app.services.captaincy_service._fixture_factor", return_value=1.0):
                    with patch("app.services.captaincy_service._availability_factor", return_value=1.0):
                        with patch("app.services.captaincy_service._minutes_factor", return_value=1.0):
                            result = build_captaincy_lab([mock_player], [mock_fixture], 10, 5)
                            assert result["gameweek"] == 10
                            assert len(result["safe_captains"]) == 1
                            assert result["safe_captains"][0]["name"] == "Salah"

def test_build_explainability_top(mock_player, mock_fixture):
    with patch("app.services.captaincy_service._expected_points", return_value=6.5):
        with patch("app.services.captaincy_service._fixture_count_for_gw", return_value=1):
            with patch("app.services.captaincy_service._reason", return_value="Good form"):
                result = build_explainability_top([mock_player], [mock_fixture], 10, 5)
                assert result["gameweek"] == 10
                assert len(result["players"]) == 1
                assert result["players"][0]["name"] == "Salah"

def test_build_chip_planner(mock_player, mock_fixture):
    # Midfielders/Forwards are element_type 3 or 4
    # Playable bench check: p.now_cost / 10.0 <= 5.8 and p.minutes >= 450
    bench_player = Player(
        id=2, web_name="Bench", element_type=3, now_cost=45, minutes=1000, 
        form=2.0, chance_of_playing_next_round=100, team_id=2
    )
    players = [mock_player, bench_player]
    fixtures = [mock_fixture]
    
    with patch("app.services.planner_service._expected_points_horizon", return_value=5.0):
        result = build_chip_planner(players, fixtures, 10, 6)
        assert result["gameweek"] == 10
        assert "chip_scores" in result
        assert "recommendation" in result

def test_build_rival_intelligence(mock_player, mock_fixture):
    db = MagicMock()
    players = [mock_player]
    fixtures = [mock_fixture]
    
    my_picks = {"picks": [{"element": 1, "is_captain": True}]}
    rival_picks = {"picks": [{"element": 1, "is_captain": False}]}
    
    with patch("app.services.planner_service._fetch_entry_picks_with_fallback") as mock_fetch:
        mock_fetch.side_effect = [(my_picks, 10), (rival_picks, 10)]
        with patch("app.services.planner_service.fetch_json", return_value={"summary_overall_rank": 1000}):
            result = build_rival_intelligence(
                db=db, players=players, fixtures=fixtures, 
                entry_id=123, rival_entry_id=456, gameweek=10, current_gw=10
            )
            assert result["gameweek"] == 10
            assert result["overlap_count"] == 1
            assert result["captaincy"]["my_captain"] == "Salah"
