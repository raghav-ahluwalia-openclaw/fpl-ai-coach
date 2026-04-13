from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.api.routes import insights_research as r
from app.db.models import Fixture, Player, Team


class _QueryStub:
    def __init__(self, rows):
        self._rows = rows

    def options(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._rows


class _DBStub:
    def __init__(self, players, fixtures, teams=None):
        self._players = players
        self._fixtures = fixtures
        self._teams = teams or []

    def query(self, model):
        if model is Player:
            return _QueryStub(self._players)
        if model is Fixture:
            return _QueryStub(self._fixtures)
        if model is Team:
            return _QueryStub(self._teams)
        return _QueryStub([])

    def get(self, *_args, **_kwargs):
        return None

    def close(self):
        return None


def _mk_player(pid: int, name: str, et: int = 3):
    return Player(
        id=pid,
        web_name=name,
        element_type=et,
        now_cost=95,
        form=6.0,
        points_per_game=5.5,
        minutes=1800,
        goals_scored=8,
        assists=7,
        clean_sheets=4,
        selected_by_percent=12.5,
        news="",
        chance_of_playing_next_round=100,
        team_id=1,
    )


def test_helper_sentiment_and_mentions_and_dedupe():
    txt = "Saka is great. Great upside, but rotation risk exists."
    assert "Great upside" in r._summarize_text(txt)
    score = r._sentiment_score(txt)
    assert isinstance(score, int)
    assert r._sentiment_label(5) == "positive"
    assert r._sentiment_label(-5) == "negative"
    assert r._sentiment_label(0) == "neutral"

    mentions = r._extract_player_mentions(txt, ["Saka", "Haaland"])
    assert mentions[0]["name"] == "Saka"

    vids = [{"title": "A"}, {"title": "a"}, {"title": "B"}]
    deduped = r._dedupe_videos_by_exact_title(vids)
    assert len(deduped) == 2
    assert r._is_draft_centric_video({"title": "FPL Draft Waiver picks"}) is True


def test_official_news_payload_success_and_failure():
    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    bootstrap = {
        "teams": [{"id": 1, "short_name": "ARS"}, {"id": 2, "short_name": "MCI"}],
        "elements": [
            {
                "id": 10,
                "web_name": "Saka",
                "team": 1,
                "status": "d",
                "news": "Hamstring",
                "chance_of_playing_next_round": 25,
                "selected_by_percent": "24.0",
            }
        ],
    }
    fixtures = [
        {
            "event": 31,
            "team_h": 1,
            "team_a": 2,
            "provisional_start_time": True,
            "finished": False,
            "kickoff_time": "2026-03-03T15:00:00Z",
        }
    ]

    with patch.object(r.requests, "get", side_effect=[_Resp(bootstrap), _Resp(fixtures)]):
        out = r._official_news_payload(limit=6)
    assert out["source"] == "Official FPL API"
    assert out["injuries"]
    assert out["fixture_updates"]

    with patch.object(r.requests, "get", side_effect=RuntimeError("boom")):
        bad = r._official_news_payload(limit=6)
    assert bad["injuries"] == []
    assert "error" in bad


def test_socials_refresh_branches():
    # missing scripts
    with patch.object(Path, "exists", return_value=False):
        try:
            r.fpl_socials_refresh(videos_per_creator=4)
            assert False, "expected HTTPException"
        except Exception as exc:  # noqa: BLE001
            assert "missing" in str(exc).lower()

    # digest timeout
    with patch.object(Path, "exists", return_value=True), patch.object(
        r.subprocess, "run", side_effect=r.subprocess.TimeoutExpired(cmd="x", timeout=1)
    ):
        out = r.fpl_socials_refresh(videos_per_creator=4)
        assert out["ok"] is False
        assert out["stage"] == "digest"


def test_top_captaincy_explainability_paths():
    players = [_mk_player(1, "Saka"), _mk_player(2, "Haaland", 4)]
    fixtures = [Fixture(id=1, event=31, team_h=1, team_a=2, team_h_difficulty=2, team_a_difficulty=4)]
    teams = [Team(id=1, short_name="ARS", name="Arsenal"), Team(id=2, short_name="MCI", name="Man City")]
    db = _DBStub(players, fixtures, teams)

    with patch.object(r, "SessionLocal", return_value=db), patch.object(
        r.api_ttl_cache, "get_or_set", side_effect=lambda _k, fn, ttl_seconds=0: fn()
    ), patch.object(r, "_resolve_gameweek", return_value=31), patch.object(
        r, "_expected_points", side_effect=[7.2, 8.1]
    ), patch.object(
        r, "_expected_points_horizon", return_value=20.0
    ), patch.object(
        r, "_reason", return_value="Good form"
    ):
        tp = r.top_players(limit=2, position=None, compact=False, include_reason=True)
        assert tp["count"] == 2
        assert tp["players"][0]["name"] == "Haaland"

    with patch.object(r, "SessionLocal", return_value=db), patch.object(
        r.api_ttl_cache, "get_or_set", side_effect=lambda _k, fn, ttl_seconds=0: fn()
    ), patch.object(r, "_resolve_gameweek", return_value=31), patch.object(
        r, "build_captaincy_lab", return_value={"gameweek": 31, "safe_captains": [], "upside_captains": []}
    ):
        c = r.captaincy_lab(gameweek=31, limit=5)
        assert c["gameweek"] == 31

    with patch.object(r, "SessionLocal", return_value=db), patch.object(
        r.api_ttl_cache, "get_or_set", side_effect=lambda _k, fn, ttl_seconds=0: fn()
    ), patch.object(r, "_resolve_gameweek", return_value=31), patch.object(
        r, "build_explainability_top", return_value={"gameweek": 31, "count": 1, "players": [{"name": "Saka"}]}
    ):
        e = r.explainability_top(gameweek=31, limit=5, position=None, include_next_5=False)
        assert e["gameweek"] == 31


def test_content_consensus_and_socials_fallback_without_digest(tmp_path):
    players = [_mk_player(1, "Saka")]
    db = _DBStub(players, [])

    digest_path = tmp_path / "creator_digest.json"
    digest_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-01T00:00:00Z",
                "top_topics": [{"topic": "wildcard"}],
                "creator_coverage": {"valid creator": 1, "fpl focal": 2},
                "videos": [{"creator": "valid creator", "title": "GW31 picks", "url": "https://x"}],
                "top_title_terms": ["gw31"],
                "top_player_mentions": ["Saka"],
            }
        ),
        encoding="utf-8",
    )

    with patch.object(r, "DIGEST_PATH", digest_path):
        cc = r.content_consensus(limit=5, include_videos=True)
    assert cc["generated_at"] == "2026-04-01T00:00:00Z"
    assert "fpl focal" not in cc["creator_coverage"]

    # force no digest; reddit call fails -> fallback thread
    with patch.object(r, "SessionLocal", return_value=db), patch.object(
        r, "DIGEST_PATH", tmp_path / "missing.json"
    ), patch.object(r.requests, "get", side_effect=RuntimeError("reddit down")):
        out = r.fpl_socials(limit=3, reddit_window="week")

    assert out["subreddit"] == "FantasyPL"
    assert out["reddit_threads"][0]["title"] == "Reddit fetch unavailable"
