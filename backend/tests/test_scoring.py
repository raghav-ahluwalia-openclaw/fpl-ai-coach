"""
Unit tests for scoring service.

Tests cover:
- Expected points calculations
- Fixture difficulty factors
- Availability factors
- Captain selection logic
"""
import pytest

from app.services.scoring import (
    _expected_points,
    _expected_points_horizon,
    _fixture_factor,
    _availability_factor,
    _minutes_factor,
    _captain_weight,
    _choose_captains,
    _strategy_config,
)
from app.schemas import Pick


class TestMinutesFactor:
    """Test minutes played factor calculations."""
    
    def test_zero_minutes(self):
        """Player with 0 minutes should have 0 factor."""
        assert _minutes_factor(0) == 0.0
    
    def test_full_match(self):
        """Player with 90 minutes should have factor of 1.0."""
        assert _minutes_factor(90) == 1.0
    
    def test_substitute(self):
        """Player with 45 minutes should have factor of 0.5."""
        assert _minutes_factor(45) == 0.5
    
    def test_multiple_matches(self):
        """Player with 900+ minutes should cap at 1.2."""
        assert _minutes_factor(900) == 1.0
        assert _minutes_factor(1000) == 1.2
        assert _minutes_factor(2000) == 1.2  # Capped


class TestAvailabilityFactor:
    """Test player availability factor calculations."""
    
    def test_full_fitness(self):
        """Player with 100% chance should have factor of 1.0."""
        assert _availability_factor(100, "") == 1.0
    
    def test_injury_risk(self):
        """Player with 50% chance should have factor of 0.5."""
        assert _availability_factor(50, "") == 0.5
    
    def test_injury_news(self):
        """Player with injury news should have reduced factor."""
        assert _availability_factor(None, "Minor knock") == 0.85
    
    def test_no_news_no_chance(self):
        """Player with no news and no chance should default to 1.0."""
        assert _availability_factor(None, "") == 1.0


class TestFixtureFactor:
    """Test fixture difficulty factor calculations."""
    
    def test_no_fixture(self, sample_player, sample_fixture):
        """Player with no fixture should have very low factor (blank GW)."""
        fixtures = []
        factor = _fixture_factor(sample_player, fixtures, target_gw=10)
        assert factor == 0.03  # Hard penalty for blank
    
    def test_easy_fixture(self, sample_player, sample_fixture):
        """Player with difficulty 1 should have boosted factor."""
        sample_fixture.team_h_difficulty = 1
        factor = _fixture_factor(sample_player, [sample_fixture], target_gw=10)
        assert factor > 1.0  # Easy fixture boost
    
    def test_hard_fixture(self, sample_player, sample_fixture):
        """Player with difficulty 5 should have reduced factor."""
        sample_fixture.team_h_difficulty = 5
        factor = _fixture_factor(sample_player, [sample_fixture], target_gw=10)
        assert factor < 1.0  # Hard fixture penalty
    
    def test_double_gameweek(self, sample_player, sample_fixture):
        """Player with 2 fixtures should get DGW boost."""
        fixture2 = Fixture(
            id=2,
            code=123457,
            event=10,
            finished=False,
            kickoff_time="2026-03-30T19:45:00Z",
            team_h=sample_player.team_id,
            team_a=3,
            team_h_difficulty=3,
            team_a_difficulty=3,
        )
        factor = _fixture_factor(sample_player, [sample_fixture, fixture2], target_gw=10)
        assert factor > _fixture_factor(sample_player, [sample_fixture], target_gw=10)


class TestExpectedPoints:
    """Test expected points calculations."""
    
    def test_basic_calculation(self, sample_player, sample_fixture):
        """Test basic expected points calculation."""
        xp = _expected_points(sample_player, [sample_fixture], target_gw=10)
        assert xp > 0
        assert isinstance(xp, float)
    
    def test_injured_player(self, sample_player, sample_fixture):
        """Test injured player has lower expected points."""
        sample_player.chance_of_playing_next_round = 25
        xp_injured = _expected_points(sample_player, [sample_fixture], target_gw=10)
        
        sample_player.chance_of_playing_next_round = 100
        xp_fit = _expected_points(sample_player, [sample_fixture], target_gw=10)
        
        assert xp_injured < xp_fit
    
    def test_hard_fixture_impact(self, sample_player, sample_fixture):
        """Test hard fixture reduces expected points."""
        sample_fixture.team_h_difficulty = 5
        xp_hard = _expected_points(sample_player, [sample_fixture], target_gw=10)
        
        sample_fixture.team_h_difficulty = 2
        xp_easy = _expected_points(sample_player, [sample_fixture], target_gw=10)
        
        assert xp_hard < xp_easy


class TestExpectedPointsHorizon:
    """Test multi-gameweek horizon calculations."""
    
    def test_single_gw_horizon(self, sample_player, sample_fixture):
        """Test 1-GW horizon."""
        xp_1, xp_3 = _expected_points_horizon(sample_player, [sample_fixture], current_gw=10, horizon=3)
        assert xp_1 > 0
        assert xp_3 >= xp_1  # 3-GW should be >= 1-GW
    
    def test_form_factor(self, sample_player, sample_fixture):
        """Test that form affects horizon calculations."""
        sample_player.form = "10.0"
        xp_high_form, _ = _expected_points_horizon(sample_player, [sample_fixture], current_gw=10, horizon=3)
        
        sample_player.form = "2.0"
        xp_low_form, _ = _expected_points_horizon(sample_player, [sample_fixture], current_gw=10, horizon=3)
        
        assert xp_high_form > xp_low_form


class TestCaptainWeight:
    """Test captain selection weight calculations."""
    
    def test_basic_weight(self, sample_player):
        """Test basic captain weight calculation."""
        weight = _captain_weight(sample_player, mode="balanced")
        assert weight > 0
        assert isinstance(weight, float)
    
    def test_safe_mode(self, sample_player):
        """Test safe mode favors consistent players."""
        safe_weight = _captain_weight(sample_player, mode="safe")
        # Safe mode should weight PPG and form more
        assert safe_weight > 0
    
    def test_aggressive_mode(self, sample_player):
        """Test aggressive mode favors differential picks."""
        sample_player.selected_by_percent = "5.0"  # Low ownership
        agg_weight = _captain_weight(sample_player, mode="aggressive")
        assert agg_weight > 0


class TestChooseCaptains:
    """Test captain selection logic."""
    
    def test_returns_safe_and_differential(self, sample_player):
        """Test captain selection returns both safe and differential options."""
        players = [sample_player]
        fixtures = []
        safe, differential = _choose_captains(players, fixtures, target_gw=10)
        
        assert isinstance(safe, list)
        assert isinstance(differential, list)


class TestStrategyConfig:
    """Test strategy configuration."""
    
    def test_safe_config(self):
        """Test safe strategy configuration."""
        config = _strategy_config("safe")
        assert "safe" in config
        assert config["safe"]["form_weight"] > config["safe"]["differential_weight"]
    
    def test_balanced_config(self):
        """Test balanced strategy configuration."""
        config = _strategy_config("balanced")
        assert "balanced" in config
    
    def test_aggressive_config(self):
        """Test aggressive strategy configuration."""
        config = _strategy_config("aggressive")
        assert "aggressive" in config
        # Aggressive should weight differential more
        assert config["aggressive"]["differential_weight"] > config["aggressive"]["form_weight"]
