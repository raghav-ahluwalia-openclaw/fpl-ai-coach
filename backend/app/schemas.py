from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel

class Pick(BaseModel):
    id: int
    name: str
    position: str
    price: float
    expected_points: float
    reason: str


class Recommendation(BaseModel):
    gameweek: int
    formation: str
    lineup: List[Pick]
    captain: str
    vice_captain: str
    transfer_out: str
    transfer_in: str
    confidence: float
    last_ingested_at: Optional[str] = None
    summary: str


class TeamRecommendation(BaseModel):
    entry_id: int
    gameweek: int
    strategy_mode: str
    formation: str
    starting_xi: List[Pick]
    bench: List[Pick]
    captain: str
    vice_captain: str
    transfer_out: str
    transfer_in: str
    transfer_reason: str
    bank: float
    squad_value: float
    confidence: float
    last_ingested_at: Optional[str] = None
    summary: str


class TargetPlayer(BaseModel):
    id: int
    name: str
    position: str
    price: float
    ownership_pct: float
    expected_points_next_1: float
    expected_points_next_3: float
    expected_points_next_5: float
    minutes_risk: float
    availability_risk: float
    fixture_swing: float
    target_score: float
    tier: str
    reasons: List[str]


class TargetsResponse(BaseModel):
    gameweek: int
    strategy_mode: str
    horizon: int
    safe_targets: List[TargetPlayer]
    differential_targets: List[TargetPlayer]
    last_ingested_at: Optional[str] = None
    summary: str


class RankHistoryPoint(BaseModel):
    event: int
    overall_rank: int
    event_points: int
    total_points: int


class RankHistoryResponse(BaseModel):
    entry_id: int
    points: List[RankHistoryPoint]
    best_rank: Optional[int] = None
    worst_rank: Optional[int] = None
    summary: str


POSITION_MAP: Dict[int, str] = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
