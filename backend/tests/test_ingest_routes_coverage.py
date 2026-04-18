from unittest.mock import MagicMock, patch

from app.api.routes import ingest


def _query_mock_for(model_counts: dict):
    def _query(model):
        q = MagicMock()
        if model in model_counts:
            q.count.return_value = model_counts[model]
        if model is ingest.Fixture:
            q.delete.return_value = None
        return q

    return _query


def test_ingest_bootstrap_skip_when_recent():
    db = MagicMock()
    with patch.object(
        ingest, "_is_recently_ingested", return_value=True
    ), patch.object(
        ingest, "_get_meta", side_effect=lambda _db, k: {"last_ingested_at": "now", "next_gw": "31", "current_gw": "30", "next_deadline_utc": "2026-01-01"}.get(k, "")
    ):
        out = ingest.ingest_bootstrap(force=False, db=db)

    assert out["ok"] is True
    assert out["skipped"] is True
    assert out["next_gw"] == 31


def test_ingest_bootstrap_success_force():
    db = MagicMock()
    db.get.return_value = None
    db.query.side_effect = _query_mock_for({})

    bootstrap_payload = {
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS", "strength": 4}],
        "elements": [
            {
                "id": 10,
                "first_name": "Bukayo",
                "second_name": "Saka",
                "web_name": "Saka",
                "team": 1,
                "element_type": 3,
                "now_cost": 105,
                "minutes": 2200,
                "goals_scored": 12,
                "assists": 10,
                "clean_sheets": 8,
                "form": "7.2",
                "points_per_game": "6.5",
                "selected_by_percent": "35.2",
                "news": "",
                "chance_of_playing_next_round": 100,
            }
        ],
        "events": [
            {"id": 30, "is_current": True, "is_next": False},
            {"id": 31, "is_current": False, "is_next": True, "deadline_time": "2026-03-01T11:00:00Z"},
        ],
    }
    fixtures_payload = [
        {
            "id": 1001,
            "event": 31,
            "team_h": 1,
            "team_a": 2,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
            "kickoff_time": "2026-03-02T15:00:00Z",
        }
    ]

    with patch.object(
        ingest, "_is_recently_ingested", return_value=False
    ), patch.object(
        ingest, "fetch_json", side_effect=[bootstrap_payload, fixtures_payload]
    ), patch.object(ingest, "_set_meta") as set_meta, patch.object(
        ingest.api_ttl_cache, "clear"
    ) as clear_cache:
        out = ingest.ingest_bootstrap(force=True, db=db)

    assert out["ok"] is True
    assert out["players"] == 1
    assert out["fixtures"] == 1
    assert out["current_gw"] == 30
    assert out["next_gw"] == 31
    assert set_meta.call_count >= 4
    clear_cache.assert_called_once()
    db.commit.assert_called_once()


def test_diagnostics_success():
    db = MagicMock()
    db.query.side_effect = _query_mock_for({ingest.Player: 200, ingest.Team: 20, ingest.Fixture: 380})

    fake_conn = MagicMock()
    fake_ctx = MagicMock()
    fake_ctx.__enter__.return_value = fake_conn
    fake_ctx.__exit__.return_value = False

    with patch.object(
        ingest, "diagnostics_access_check", return_value=None
    ), patch.object(ingest.engine, "connect", return_value=fake_ctx), patch.object(
        ingest, "_get_meta", side_effect=lambda _db, k: {"current_gw": "30", "next_gw": "31"}.get(k, "")
    ):
        out = ingest.diagnostics(MagicMock(), db=db)

    assert out["ok"] is True
    assert out["counts"]["players"] == 200
    assert out["meta"]["next_gw"] == 31
