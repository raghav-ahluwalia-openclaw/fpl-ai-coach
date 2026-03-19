from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.db.models import Fixture, Player
from app.schemas import POSITION_MAP, Pick, TargetPlayer


def _float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _int(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _minutes_factor(minutes: int) -> float:
    return min(max(minutes / 900.0, 0.0), 1.2)


def _availability_factor(chance: Optional[int], news: str) -> float:
    if chance is not None:
        return max(0.0, min(chance / 100.0, 1.0))
    if news and news.strip():
        return 0.85
    return 1.0


def _fixture_rows_for_gw(player: Player, fixture_rows: List[Fixture], target_gw: Optional[int]) -> List[Fixture]:
    if target_gw is None:
        return []
    out: List[Fixture] = []
    for row in fixture_rows:
        if row.event != target_gw:
            continue
        if row.team_h == player.team_id or row.team_a == player.team_id:
            out.append(row)
    return out


def _fixture_count_for_gw(player: Player, fixture_rows: List[Fixture], target_gw: Optional[int]) -> int:
    return len(_fixture_rows_for_gw(player, fixture_rows, target_gw))


def _fixture_factor(player: Player, fixture_rows: List[Fixture], target_gw: Optional[int]) -> float:
    if target_gw is None:
        return 1.0

    rows = _fixture_rows_for_gw(player, fixture_rows, target_gw)
    if not rows:
        return 0.03

    diffs = []
    for f in rows:
        diff = f.team_h_difficulty if f.team_h == player.team_id else f.team_a_difficulty
        diffs.append(diff)

    avg_diff = sum(diffs) / max(1, len(diffs))
    base = {1: 1.12, 2: 1.06, 3: 1.0, 4: 0.94, 5: 0.88}.get(round(avg_diff), 1.0)

    count = len(rows)
    dgw_boost = min(1.45, 1.0 + max(0, count - 1) * 0.28)
    return base * dgw_boost


def _position_base(player: Player) -> float:
    return {1: 0.92, 2: 0.97, 3: 1.03, 4: 1.05}.get(player.element_type, 1.0)


def _expected_points(player: Player, fixtures: List[Fixture], target_gw: Optional[int]) -> float:
    ppg = player.points_per_game
    form = player.form
    minutes_factor = _minutes_factor(player.minutes)
    availability = _availability_factor(player.chance_of_playing_next_round, player.news)
    fixture = _fixture_factor(player, fixtures, target_gw)
    role = _position_base(player)

    base = (ppg * 0.55) + (form * 0.30) + (minutes_factor * 2.2)
    score = base * availability * fixture * role
    return round(max(score, 0.0), 2)


def _expected_points_horizon(
    player: Player,
    fixtures: List[Fixture],
    start_gw: Optional[int],
    horizon: int = 3,
    weights: Optional[List[float]] = None,
) -> float:
    if start_gw is None:
        return _expected_points(player, fixtures, None)

    use_horizon = max(1, min(horizon, 5))
    default_weights = [1.0, 0.85, 0.7, 0.55, 0.45]
    base_weights = weights or default_weights

    use_weights = list(base_weights[:use_horizon])
    while len(use_weights) < use_horizon:
        use_weights.append(use_weights[-1] * 0.85)

    total = 0.0
    total_w = 0.0
    for i, w in enumerate(use_weights):
        gw = start_gw + i
        total += _expected_points(player, fixtures, gw) * w
        total_w += w

    return round(total / total_w, 2) if total_w else _expected_points(player, fixtures, start_gw)


def _strategy_config(mode: str) -> Tuple[List[float], float]:
    mode = (mode or "balanced").lower()
    if mode == "safe":
        return [0.9, 0.9, 0.9], 0.45
    if mode == "aggressive":
        return [1.2, 0.8, 0.4], 0.05
    return [1.0, 0.8, 0.6], 0.25


def _target_tier(score: float) -> str:
    if score >= 7.5:
        return "Strong Buy"
    if score >= 6.0:
        return "Watchlist"
    return "Hold"


def _build_target_player(
    player: Player,
    fixtures: List[Fixture],
    start_gw: int,
    mode: str,
    mode_weights: List[float],
) -> TargetPlayer:
    xp1 = _expected_points(player, fixtures, start_gw)
    xp3 = _expected_points_horizon(player, fixtures, start_gw, horizon=3, weights=mode_weights)
    xp5 = _expected_points_horizon(player, fixtures, start_gw, horizon=5)

    ownership = max(0.0, min(player.selected_by_percent, 100.0))
    minutes_risk = round(max(0.0, 1.0 - min(player.minutes / 900.0, 1.0)), 2)
    availability_risk = round(max(0.0, 1.0 - _availability_factor(player.chance_of_playing_next_round, player.news)), 2)

    fixture_lookahead = _expected_points_horizon(player, fixtures, start_gw, horizon=3, weights=[1.0, 1.0, 1.0])
    fixture_swing = round((fixture_lookahead - xp1) / max(1.0, xp1), 2)

    risk_penalty = (minutes_risk * 0.35) + (availability_risk * 0.65)
    score = xp3 * (1.0 - min(0.5, risk_penalty))

    if mode == "safe":
        score += min(0.4, ownership / 100.0)
    elif mode == "aggressive":
        score += max(0.0, 0.4 - (ownership / 100.0))

    reasons = []
    if xp3 >= 6.0:
        reasons.append("strong 3-GW projected output")
    if fixture_swing > 0.08:
        reasons.append("fixtures improving")
    if availability_risk > 0:
        reasons.append("monitor availability")
    if minutes_risk > 0.25:
        reasons.append("minutes risk")
    if not reasons:
        reasons.append("stable profile across upcoming fixtures")

    return TargetPlayer(
        id=player.id,
        name=player.web_name,
        position=POSITION_MAP.get(player.element_type, str(player.element_type)),
        price=round(player.now_cost / 10.0, 1),
        ownership_pct=round(ownership, 1),
        expected_points_next_1=round(xp1, 2),
        expected_points_next_3=round(xp3, 2),
        expected_points_next_5=round(xp5, 2),
        minutes_risk=minutes_risk,
        availability_risk=availability_risk,
        fixture_swing=fixture_swing,
        target_score=round(score, 2),
        tier=_target_tier(score),
        reasons=reasons,
    )


def _reason(player: Player, xpts: float) -> str:
    bits = []
    if player.form >= 4.0:
        bits.append("strong recent form")
    if player.points_per_game >= 5.0:
        bits.append("solid points-per-game")
    if player.chance_of_playing_next_round is not None and player.chance_of_playing_next_round < 100:
        bits.append(f"availability risk ({player.chance_of_playing_next_round}%)")
    if player.news:
        bits.append("flagged news")
    if not bits:
        bits.append("balanced underlying profile")
    return f"{', '.join(bits)}; projected {xpts} xP"


def _build_lineup_from_squad(scored: List[Tuple[float, Player]]) -> Tuple[List[Tuple[float, Player]], List[Tuple[float, Player]], str]:
    by_pos: Dict[int, List[Tuple[float, Player]]] = {1: [], 2: [], 3: [], 4: []}
    for xpts, p in scored:
        by_pos.setdefault(p.element_type, []).append((xpts, p))

    for pos in by_pos:
        by_pos[pos].sort(key=lambda x: x[0], reverse=True)

    min_pos = {1: 1, 2: 3, 3: 2, 4: 1}
    max_pos = {1: 1, 2: 5, 3: 5, 4: 3}

    selected: List[Tuple[float, Player]] = []
    selected_ids = set()
    counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for pos, need in min_pos.items():
        choices = by_pos.get(pos, [])[:need]
        if len(choices) < need:
            raise HTTPException(status_code=500, detail="Invalid squad composition; cannot build legal XI")
        for item in choices:
            selected.append(item)
            selected_ids.add(item[1].id)
            counts[pos] += 1

    remaining = sorted(scored, key=lambda x: x[0], reverse=True)
    for item in remaining:
        if len(selected) >= 11:
            break
        xpts, p = item
        if p.id in selected_ids:
            continue
        if counts[p.element_type] >= max_pos.get(p.element_type, 5):
            continue
        selected.append((xpts, p))
        selected_ids.add(p.id)
        counts[p.element_type] += 1

    if len(selected) < 11:
        raise HTTPException(status_code=500, detail="Could not compose full XI from squad")

    bench = [item for item in scored if item[1].id not in selected_ids]
    bench.sort(key=lambda x: x[0], reverse=True)

    formation = f"{counts[2]}-{counts[3]}-{counts[4]}"
    return selected, bench, formation


def _fixture_badge_for_gw(player: Player, fixtures: List[Fixture], gw: Optional[int]) -> tuple[int, str]:
    count = _fixture_count_for_gw(player, fixtures, gw)
    if count >= 2:
        return count, "DGW"
    if count == 0:
        return count, "BLANK"
    return count, "SGW"


def _pick_to_response(
    player: Player,
    xpts: float,
    *,
    expected_points_3: Optional[float] = None,
    fixture_count: Optional[int] = None,
    fixture_badge: Optional[str] = None,
) -> Pick:
    return Pick(
        id=player.id,
        name=player.web_name,
        position=POSITION_MAP.get(player.element_type, str(player.element_type)),
        price=round(player.now_cost / 10.0, 1),
        expected_points=xpts,
        expected_points_3=expected_points_3,
        reason=_reason(player, xpts),
        fixture_count=fixture_count,
        fixture_badge=fixture_badge,
    )


def _captain_weight(player: Player) -> float:
    pos_weight = {1: 0.78, 2: 0.9, 3: 1.05, 4: 1.1}.get(player.element_type, 1.0)
    availability = _availability_factor(player.chance_of_playing_next_round, player.news)
    return pos_weight * availability


def _choose_captains(lineup_pairs: List[Tuple[float, Player]]) -> Tuple[str, str]:
    ranked = sorted(lineup_pairs, key=lambda item: (item[0] * _captain_weight(item[1])), reverse=True)
    if len(ranked) < 2:
        raise HTTPException(status_code=500, detail="Not enough players to select captain and vice")
    return ranked[0][1].web_name, ranked[1][1].web_name


__all__ = [name for name in globals() if name.startswith("_") and name not in {"__builtins__", "__cached__", "__doc__", "__file__", "__loader__", "__name__", "__package__", "__spec__"}]
