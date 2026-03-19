from __future__ import annotations

from typing import Dict, List, Optional

from app.api.routes.base import (
    _expected_points_horizon,
    _fetch_entry_picks_with_fallback,
    _int,
)
from app.db.models import Fixture, Player
from app.services.http_client import fetch_json


def build_chip_planner(
    players: List[Player],
    fixtures: List[Fixture],
    gw: int,
    horizon: int,
    *,
    entry_id: Optional[int] = None,
) -> dict:
    team_ids = sorted({p.team_id for p in players})

    team_strength: Dict[int, float] = {}
    for team_id in team_ids:
        vals = []
        for f in fixtures:
            if f.event is None or f.event < gw or f.event >= gw + horizon:
                continue
            if f.team_h == team_id:
                vals.append(f.team_h_difficulty)
            elif f.team_a == team_id:
                vals.append(f.team_a_difficulty)
        team_strength[team_id] = (sum(vals) / len(vals)) if vals else 3.0

    easy_teams = sorted(team_strength.items(), key=lambda x: x[1])[:5]
    hard_teams = sorted(team_strength.items(), key=lambda x: x[1], reverse=True)[:5]

    gw_fixture_stats = []
    for ev in range(gw, gw + min(horizon, 6)):
        counts = {tid: 0 for tid in team_ids}
        for f in fixtures:
            if f.event != ev:
                continue
            counts[f.team_h] = counts.get(f.team_h, 0) + 1
            counts[f.team_a] = counts.get(f.team_a, 0) + 1

        blank_teams = sum(1 for _, c in counts.items() if c == 0)
        double_teams = sum(1 for _, c in counts.items() if c >= 2)
        gw_fixture_stats.append({"gameweek": ev, "blank_teams": blank_teams, "double_teams": double_teams})

    max_blank = max((x["blank_teams"] for x in gw_fixture_stats), default=0)
    max_double = max((x["double_teams"] for x in gw_fixture_stats), default=0)

    wildcard_score = max(0.0, min(10.0, (sum(v for _, v in hard_teams) / max(1, len(hard_teams))) * 1.2))
    free_hit_score = max(0.0, min(10.0, 2.0 + (max_blank * 0.45)))

    playable_bench = 0
    for p in players:
        if p.now_cost / 10.0 <= 5.8 and p.minutes >= 450:
            if _expected_points_horizon(p, fixtures, gw, horizon=3) >= 4.2:
                playable_bench += 1
    bench_boost_score = max(0.0, min(10.0, (playable_bench / 2.2) + (max_double * 0.35)))

    premiums = [p for p in players if p.now_cost / 10.0 >= 10.0]
    top_premium_xp = max((_expected_points_horizon(p, fixtures, gw, horizon=2) for p in premiums), default=0.0)
    triple_captain_score = max(0.0, min(10.0, (top_premium_xp * 1.0) + (max_double * 0.28)))

    chip_scores = {
        "wildcard": wildcard_score,
        "free_hit": free_hit_score,
        "bench_boost": bench_boost_score,
        "triple_captain": triple_captain_score,
    }

    chip_history = []
    chip_usage = {
        "wildcard": {"used_count": 0, "max_uses": 2, "remaining": 2, "available": True, "used_gws": []},
        "free_hit": {"used_count": 0, "max_uses": 2, "remaining": 2, "available": True, "used_gws": []},
        "bench_boost": {"used_count": 0, "max_uses": 1, "remaining": 1, "available": True, "used_gws": []},
        "triple_captain": {"used_count": 0, "max_uses": 1, "remaining": 1, "available": True, "used_gws": []},
    }

    if entry_id:
        try:
            hist = fetch_json(
                f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/",
                timeout=20,
                not_found_detail=f"FPL team {entry_id} not found",
                upstream_error_prefix="Could not fetch chip usage history",
            )
            chip_map = {
                "wildcard": "wildcard",
                "freehit": "free_hit",
                "bboost": "bench_boost",
                "3xc": "triple_captain",
            }
            label_map = {
                "wildcard": "Wildcard",
                "free_hit": "Free Hit",
                "bench_boost": "Bench Boost",
                "triple_captain": "Triple Captain",
            }
            for c in hist.get("chips", []) or []:
                raw = str(c.get("name") or "").lower().strip()
                key = chip_map.get(raw)
                if not key:
                    continue
                gw_used = _int(c.get("event"), 0)
                item = chip_usage[key]
                item["used_count"] += 1
                if gw_used > 0:
                    item["used_gws"].append(gw_used)
                chip_history.append(
                    {
                        "chip": key,
                        "label": label_map.get(key, key),
                        "gameweek": gw_used if gw_used > 0 else None,
                        "time": c.get("time"),
                    }
                )

            for key, item in chip_usage.items():
                item["used_gws"] = sorted(item["used_gws"])
                # Some FPL histories can report multi-use chip events (e.g., season-over-season/history behavior).
                # Keep display coherent by never showing used_count above max_uses.
                item["max_uses"] = max(int(item["max_uses"]), int(item["used_count"]))
                item["remaining"] = max(0, int(item["max_uses"]) - int(item["used_count"]))
                item["available"] = item["remaining"] > 0

            chip_history.sort(key=lambda x: (_int(x.get("gameweek"), 0), str(x.get("time") or "")))
        except Exception:  # noqa: BLE001
            pass

    # Exclude fully used chips from recommendations.
    available_scores = {
        k: v for k, v in chip_scores.items()
        if bool((chip_usage.get(k) or {}).get("available", True))
    }

    sorted_available = sorted(available_scores.items(), key=lambda kv: kv[1], reverse=True)
    best_chip = sorted_available[0] if sorted_available else None
    alt_chip = sorted_available[1] if len(sorted_available) > 1 else None

    recommendation = "hold"
    confidence = 0.45
    if best_chip and best_chip[1] >= 7.4:
        recommendation = f"play_{best_chip[0]}"
        alt_score = alt_chip[1] if alt_chip else 0.0
        confidence = min(0.9, 0.55 + ((best_chip[1] - alt_score) / 10.0))

    return {
        "gameweek": gw,
        "horizon": horizon,
        "chip_scores": {
            "wildcard": round(wildcard_score, 2),
            "free_hit": round(free_hit_score, 2),
            "bench_boost": round(bench_boost_score, 2),
            "triple_captain": round(triple_captain_score, 2),
        },
        "chip_usage": chip_usage,
        "chip_history": chip_history,
        "fixture_windows": gw_fixture_stats,
        "easy_fixture_teams": [{"team_id": t, "avg_difficulty": round(s, 2)} for t, s in easy_teams],
        "hard_fixture_teams": [{"team_id": t, "avg_difficulty": round(s, 2)} for t, s in hard_teams],
        "recommendation": recommendation,
        "alternative": (f"play_{alt_chip[0]}" if alt_chip and alt_chip[1] >= 6.8 else "hold"),
        "confidence": round(confidence, 2),
        "summary": "Chip planner scores chip timing using fixture swings plus blank/double GW pressure.",
    }


def build_rival_intelligence(
    *,
    db,
    players: List[Player],
    fixtures: List[Fixture],
    entry_id: int,
    rival_entry_id: int,
    gameweek: int,
    current_gw: int,
) -> dict:
    my_payload, my_gw = _fetch_entry_picks_with_fallback(entry_id, gameweek, [current_gw, gameweek - 1])
    rival_payload, _ = _fetch_entry_picks_with_fallback(rival_entry_id, my_gw, [current_gw, my_gw - 1])

    my_picks = my_payload.get("picks", [])
    rival_picks = rival_payload.get("picks", [])

    my_ids = {_int(p.get("element")) for p in my_picks}
    rival_ids = {_int(p.get("element")) for p in rival_picks}

    overlap = sorted(my_ids.intersection(rival_ids))
    my_only = sorted(my_ids - rival_ids)
    rival_only = sorted(rival_ids - my_ids)

    by_id = {p.id: p for p in players}

    my_captain_id = next((_int(p.get("element")) for p in my_picks if bool(p.get("is_captain", False))), None)
    rival_captain_id = next((_int(p.get("element")) for p in rival_picks if bool(p.get("is_captain", False))), None)

    def names(ids: List[int]) -> List[str]:
        return [by_id[pid].web_name for pid in ids if pid in by_id]

    my_diff_scored = []
    for pid in my_only:
        p = by_id.get(pid)
        if not p:
            continue
        xp = _expected_points_horizon(p, fixtures, my_gw, horizon=3)
        eo_pressure = min(1.0, max(0.0, p.selected_by_percent / 100.0))
        impact = xp * (1.0 - eo_pressure)
        my_diff_scored.append({
            "id": p.id,
            "name": p.web_name,
            "xP_3": round(xp, 2),
            "ownership_pct": round(p.selected_by_percent, 1),
            "impact_score": round(impact, 2),
        })

    rival_diff_scored = []
    for pid in rival_only:
        p = by_id.get(pid)
        if not p:
            continue
        xp = _expected_points_horizon(p, fixtures, my_gw, horizon=3)
        eo_pressure = min(1.0, max(0.0, p.selected_by_percent / 100.0))
        impact = xp * (1.0 - eo_pressure)
        rival_diff_scored.append({
            "id": p.id,
            "name": p.web_name,
            "xP_3": round(xp, 2),
            "ownership_pct": round(p.selected_by_percent, 1),
            "impact_score": round(impact, 2),
        })

    my_diff_scored.sort(key=lambda x: x["impact_score"], reverse=True)
    rival_diff_scored.sort(key=lambda x: x["impact_score"], reverse=True)

    my_captain_name = by_id.get(my_captain_id).web_name if my_captain_id in by_id else None
    rival_captain_name = by_id.get(rival_captain_id).web_name if rival_captain_id in by_id else None
    captain_overlap = my_captain_id is not None and my_captain_id == rival_captain_id

    captain_risk = "high_if_diff" if not captain_overlap else "hedged"

    def _overall_rank_for_entry(team_entry_id: int):
        try:
            entry = fetch_json(
                f"https://fantasy.premierleague.com/api/entry/{team_entry_id}/",
                timeout=20,
                not_found_detail=f"FPL team {team_entry_id} not found",
                upstream_error_prefix="Could not fetch FPL entry profile",
            )
            return _int(entry.get("summary_overall_rank"), 0) or None
        except Exception:  # noqa: BLE001
            return None

    my_overall_rank = _overall_rank_for_entry(entry_id)
    rival_overall_rank = _overall_rank_for_entry(rival_entry_id)

    return {
        "gameweek": my_gw,
        "entry_id": entry_id,
        "rival_entry_id": rival_entry_id,
        "entry_overall_rank": my_overall_rank,
        "rival_overall_rank": rival_overall_rank,
        "overlap_count": len(overlap),
        "my_only_count": len(my_only),
        "rival_only_count": len(rival_only),
        "overlap_players": names(overlap),
        "my_differentials": names(my_only),
        "rival_differentials": names(rival_only),
        "captaincy": {
            "my_captain": my_captain_name,
            "rival_captain": rival_captain_name,
            "overlap": captain_overlap,
            "risk": captain_risk,
        },
        "differential_impact": {
            "my_top": my_diff_scored[:8],
            "rival_top": rival_diff_scored[:8],
        },
        "summary": "Rival intelligence compares overlap, captaincy exposure, and differential impact scores.",
    }
