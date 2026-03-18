from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, UniqueConstraint

from app.db import Base

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    short_name = Column(String, nullable=False)
    strength = Column(Integer, default=3)


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        Index("ix_players_team_id", "team_id"),
        Index("ix_players_element_type", "element_type"),
    )

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    second_name = Column(String, nullable=False)
    web_name = Column(String, nullable=False)
    team_id = Column(Integer, nullable=False)
    element_type = Column(Integer, nullable=False)  # 1 GK 2 DEF 3 MID 4 FWD

    now_cost = Column(Integer, nullable=False, default=0)  # 10x
    minutes = Column(Integer, nullable=False, default=0)
    goals_scored = Column(Integer, nullable=False, default=0)
    assists = Column(Integer, nullable=False, default=0)
    clean_sheets = Column(Integer, nullable=False, default=0)
    form = Column(Float, nullable=False, default=0.0)
    points_per_game = Column(Float, nullable=False, default=0.0)
    selected_by_percent = Column(Float, nullable=False, default=0.0)
    news = Column(String, nullable=False, default="")
    chance_of_playing_next_round = Column(Integer, nullable=True)


class Fixture(Base):
    __tablename__ = "fixtures"
    __table_args__ = (
        Index("ix_fixtures_event", "event"),
        Index("ix_fixtures_team_h", "team_h"),
        Index("ix_fixtures_team_a", "team_a"),
    )

    id = Column(Integer, primary_key=True)
    event = Column(Integer, nullable=True)
    team_h = Column(Integer, nullable=False)
    team_a = Column(Integer, nullable=False)
    team_h_difficulty = Column(Integer, nullable=False)
    team_a_difficulty = Column(Integer, nullable=False)
    kickoff_time = Column(String, nullable=True)


class Meta(Base):
    __tablename__ = "meta"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class UserSquadPick(Base):
    __tablename__ = "user_squad_picks"
    __table_args__ = (
        UniqueConstraint("entry_id", "event", "player_id", name="uq_user_squad_entry_event_player"),
        Index("ix_user_squad_entry_event", "entry_id", "event"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, nullable=False, index=True)
    event = Column(Integer, nullable=False)
    player_id = Column(Integer, nullable=False)
    list_position = Column(Integer, nullable=False, default=0)
    multiplier = Column(Integer, nullable=False, default=1)
    is_captain = Column(Boolean, nullable=False, default=False)
    is_vice_captain = Column(Boolean, nullable=False, default=False)
    purchase_price = Column(Integer, nullable=True)
    selling_price = Column(Integer, nullable=True)
    imported_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
