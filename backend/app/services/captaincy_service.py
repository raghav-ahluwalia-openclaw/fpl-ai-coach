from __future__ import annotations

from typing import List, Optional

from app.api.routes.base import (
    POSITION_MAP,
    _availability_factor,
    _expected_points,
    _expected_points_horizon,
    _fixture_count_for_gw,
    _fixture_factor,
    _minutes_factor,
    _reason,
)
from app.db.models import Fixture, Player


def explainability_breakdown(player: Player, fixtures: List[Fixture], gw: Optional[int]) -> dict:
    fixture_factor = _fixture_factor(player, fixtures, gw)
    availability = _availability_factor(player.chance_of_playing_next_round, player.news)
    minutes_factor = _minutes_factor(player.minutes)

    form_score = round(min(10.0, player.form * 1.6), 2)
    fixture_score = round(min(10.0, fixture_factor * 8.5), 2)
    minutes_security = round(min(10.0, minutes_factor * 8.3), 2)
    availability_score = round(min(10.0, availability * 10.0), 2)

    ownership = max(0.0, min(player.selected_by_percent, 100.0))
    ownership_risk = round(max(0.0, min(10.0, ownership / 10.0)), 2)
    volatility = round(max(0.0, min(10.0, (8.0 - player.form) + (2.0 * (1.0 - availability)))), 2)

    return {
        "form_score": form_score,
        "fixture_score": fixture_score,
        "minutes_security": minutes_security,
        "availability_score": availability_score,
        "ownership_risk": ownership_risk,
        "volatility": volatility,
    }


def build_captaincy_lab(players: List[Player], fixtures: List[Fixture], gw: int, limit: int) -> dict:
    pool = [p for p in players if p.element_type in {3, 4}]
    safe_board = []
    upside_board = []

    for p in pool:
        xp1 = _expected_points(p, fixtures, gw)
        xp3 = _expected_points_horizon(p, fixtures, gw, horizon=3)
        availability = _availability_factor(p.chance_of_playing_next_round, p.news)
        minutes_security = _minutes_factor(p.minutes)
        ownership = max(0.0, min(p.selected_by_percent, 100.0))

        fixture_count = _fixture_count_for_gw(p, fixtures, gw)
        fixture_factor = _fixture_factor(p, fixtures, gw)
        fixture_volatility = max(0.0, min(1.0, abs(1.0 - fixture_factor)))

        role_uncertainty = 0.0
        if p.element_type in {1, 2}:
            role_uncertainty += 0.06
        if p.form < 2.5:
            role_uncertainty += 0.08

        rotation_proxy = max(0.0, min(1.0, 1.0 - min(minutes_security, 1.0)))
        availability_risk = max(0.0, min(1.0, 1.0 - availability))

        risk = (
            availability_risk * 0.38
            + rotation_proxy * 0.30
            + fixture_volatility * 0.20
            + role_uncertainty * 0.12
        )

        if fixture_count >= 2:
            risk *= 0.82
        if fixture_count == 0:
            risk = min(1.0, risk + 0.55)

        safe_score = xp3 * (1 - risk * 0.78) + (ownership * 0.01)
        upside_score = xp3 * (1 - risk * 0.22) + (max(0.0, 25.0 - ownership) / 25.0) * 1.8 + (p.form * 0.12)

        fixture_badge = "DGW" if fixture_count >= 2 else ("BLANK" if fixture_count == 0 else "SGW")
        if risk < 0.26:
            risk_band = "green"
            risk_label = "low"
        elif risk < 0.5:
            risk_band = "yellow"
            risk_label = "medium"
        else:
            risk_band = "red"
            risk_label = "high"

        common = {
            "id": p.id,
            "name": p.web_name,
            "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
            "price": round(p.now_cost / 10.0, 1),
            "xP_next_1": xp1,
            "xP_next_3": xp3,
            "ownership_pct": round(ownership, 1),
            "risk": round(risk, 2),
            "risk_band": risk_band,
            "risk_label": risk_label,
            "form": round(p.form, 2),
            "fixture_count": fixture_count,
            "fixture_badge": fixture_badge,
        }

        safe_board.append({**common, "captain_score": round(safe_score, 2)})
        upside_board.append({**common, "captain_score": round(upside_score, 2)})

    safe_board.sort(key=lambda x: x["captain_score"], reverse=True)
    upside_board.sort(key=lambda x: x["captain_score"], reverse=True)

    return {
        "gameweek": gw,
        "safe_captains": safe_board[:limit],
        "upside_captains": upside_board[:limit],
        "summary": "Captaincy lab ranks stable vs upside captain options using xP horizon, risk, and ownership pressure.",
    }


def build_explainability_top(players: List[Player], fixtures: List[Fixture], gw: int, limit: int) -> dict:
    scored = []
    for p in players:
        xp = _expected_points(p, fixtures, gw)
        breakdown = explainability_breakdown(p, fixtures, gw)
        scored.append((xp, p, breakdown))

    scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    for xp, p, breakdown in scored[:limit]:
        fixture_count = _fixture_count_for_gw(p, fixtures, gw)
        fixture_badge = "DGW" if fixture_count >= 2 else ("BLANK" if fixture_count == 0 else "SGW")
        out.append(
            {
                "id": p.id,
                "name": p.web_name,
                "position": POSITION_MAP.get(p.element_type, str(p.element_type)),
                "price": round(p.now_cost / 10.0, 1),
                "xP": round(xp, 2),
                "fixture_count": fixture_count,
                "fixture_badge": fixture_badge,
                "breakdown": breakdown,
                "reason": _reason(p, xp),
            }
        )

    return {
        "gameweek": gw,
        "count": len(out),
        "players": out,
        "summary": "Top players with explainability factors (form, fixture, minutes, availability, risk, volatility).",
    }
