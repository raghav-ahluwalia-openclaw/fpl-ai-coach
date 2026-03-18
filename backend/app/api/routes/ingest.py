from __future__ import annotations

from .base import *  # noqa: F403

@router.get("/health")
def health():
    ok = True
    err = None
    try:
        with engine.connect() as c:
            c.exec_driver_sql("SELECT 1")
    except Exception as e:  # noqa: BLE001
        ok = False
        err = str(e)
    return {"ok": ok, "db": "up" if ok else "down", "db_error": err}


@router.post("/api/fpl/ingest/bootstrap")
def ingest_bootstrap(force: bool = Query(default=False)):
    db = SessionLocal()
    try:
        if not force and _is_recently_ingested(db, INGEST_TTL_MINUTES):
            logger.info("ingest skipped: within TTL", extra={"ttl_minutes": INGEST_TTL_MINUTES})
            return {
                "ok": True,
                "skipped": True,
                "reason": f"Recent ingest found (within {INGEST_TTL_MINUTES} minutes)",
                "last_ingested_at": _get_meta(db, "last_ingested_at"),
                "next_gw": _int(_get_meta(db, "next_gw"), 0) or None,
                "current_gw": _int(_get_meta(db, "current_gw"), 0) or None,
                "next_deadline_utc": _get_meta(db, "next_deadline_utc"),
            }

        bootstrap = fetch_json(
            FPL_BOOTSTRAP_URL,
            timeout=25,
            upstream_error_prefix="FPL bootstrap source unavailable",
        )
        fixtures = fetch_json(
            FPL_FIXTURES_URL,
            timeout=25,
            upstream_error_prefix="FPL fixtures source unavailable",
        )

        teams = bootstrap.get("teams", [])
        players = bootstrap.get("elements", [])
        events = bootstrap.get("events", [])

        if not players:
            raise HTTPException(status_code=502, detail="No players returned by bootstrap-static")

        for t in teams:
            row = db.get(Team, _int(t.get("id")))
            if row is None:
                row = Team(id=_int(t.get("id")))
                db.add(row)
            row.name = t.get("name", "")
            row.short_name = t.get("short_name", "")
            row.strength = _int(t.get("strength"), 3)

        for p in players:
            pid = _int(p.get("id"))
            row = db.get(Player, pid)
            if row is None:
                row = Player(id=pid)
                db.add(row)

            row.first_name = p.get("first_name", "")
            row.second_name = p.get("second_name", "")
            row.web_name = p.get("web_name", "")
            row.team_id = _int(p.get("team"))
            row.element_type = _int(p.get("element_type"))
            row.now_cost = _int(p.get("now_cost"))
            row.minutes = _int(p.get("minutes"))
            row.goals_scored = _int(p.get("goals_scored"))
            row.assists = _int(p.get("assists"))
            row.clean_sheets = _int(p.get("clean_sheets"))
            row.form = _float(p.get("form"))
            row.points_per_game = _float(p.get("points_per_game"))
            row.selected_by_percent = _float(p.get("selected_by_percent"))
            row.news = p.get("news", "") or ""
            row.chance_of_playing_next_round = p.get("chance_of_playing_next_round")

        db.query(Fixture).delete()
        for f in fixtures:
            row = Fixture(
                id=_int(f.get("id")),
                event=f.get("event"),
                team_h=_int(f.get("team_h")),
                team_a=_int(f.get("team_a")),
                team_h_difficulty=_int(f.get("team_h_difficulty"), 3),
                team_a_difficulty=_int(f.get("team_a_difficulty"), 3),
                kickoff_time=f.get("kickoff_time"),
            )
            db.add(row)

        next_gw = None
        current_gw = None
        next_deadline_utc = None
        for e in events:
            if e.get("is_current"):
                current_gw = e.get("id")
            if e.get("is_next"):
                next_gw = e.get("id")
                next_deadline_utc = e.get("deadline_time")

        now_iso = datetime.now(timezone.utc).isoformat()
        _set_meta(db, "last_ingested_at", now_iso)
        _set_meta(db, "next_gw", str(next_gw) if next_gw is not None else "")
        _set_meta(db, "current_gw", str(current_gw) if current_gw is not None else "")
        _set_meta(db, "next_deadline_utc", str(next_deadline_utc) if next_deadline_utc else "")

        db.commit()
        logger.info(
            "ingest completed",
            extra={"teams": len(teams), "players": len(players), "fixtures": len(fixtures), "next_gw": next_gw},
        )
        return {
            "ok": True,
            "teams": len(teams),
            "players": len(players),
            "fixtures": len(fixtures),
            "current_gw": current_gw,
            "next_gw": next_gw,
            "next_deadline_utc": next_deadline_utc,
            "last_ingested_at": now_iso,
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during ingest: {e}")
    finally:
        db.close()
