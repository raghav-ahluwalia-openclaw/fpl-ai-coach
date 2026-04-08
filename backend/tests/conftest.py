"""
Pytest configuration and shared fixtures for FPL AI Coach tests.
"""
import os
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.db.models import Player, Team, Fixture


# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///./test_fpl.db"
)


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}  # SQLite specific
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine) -> Generator:
    """Create a test database session with rollback after each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_team(db_session) -> Team:
    """Create a sample team for testing."""
    team = Team(
        name="Arsenal",
        short_name="ARS",
        strength=4,
    )
    db_session.add(team)
    db_session.commit()
    return team


@pytest.fixture
def sample_player(db_session, sample_team) -> Player:
    """Create a sample player for testing."""
    player = Player(
        web_name="Saka",
        first_name="Bukayo",
        second_name="Saka",
        team_id=sample_team.id,
        element_type=3,  # Midfielder
        now_cost=105,
        points_per_game=6.5,
        form=7.2,
        selected_by_percent=25.5,
        minutes=2000,
        goals_scored=15,
        assists=10,
        clean_sheets=8,
        chance_of_playing_next_round=100,
        news="",
    )
    db_session.add(player)
    db_session.commit()
    return player


@pytest.fixture
def sample_fixture(db_session, sample_team) -> Fixture:
    """Create a sample fixture for testing."""
    fixture = Fixture(
        event=10,
        kickoff_time="2026-03-28T15:00:00Z",
        team_h=sample_team.id,
        team_a=2,
        team_h_difficulty=3,
        team_a_difficulty=4,
    )
    db_session.add(fixture)
    db_session.commit()
    return fixture
