# tasks/todo.md

## Active Plan — Product upgrade phases (saved 2026-03-19)

### Phase 1 (completed)
- [x] Transfer Planner Engine v2 (Top 1FT/2FT Plan A/B/C with EV/risk/confidence)
- [x] Gameweek Hub single-screen page (Team Health + Plans + Captain Matrix + changes)
- [x] XI + Bench optimizer UX with alternate-lineup gain

### Phase 2 (active)
- [x] Standardize explicit 1/3/5 GW projections across APIs
- [ ] Add price-change aware transfer scoring
- [ ] Add confidence calibration + bucketed reliability outputs

### Phase 3
- [x] Weekly evaluation module MVP (captain hit-rate, transfer baseline comparison, heuristic calibration)
- [x] `/api/fpl/performance/weekly` + dashboard card (Gameweek Hub Performance Snapshot)

## Recently completed (2026-03-19)

- [x] Backend modularization phase 2
  - [x] Move models into `app/db/models.py`
  - [x] Move schemas into `app/schemas/`
  - [x] Extract scoring helpers into `app/services/scoring.py`
  - [x] Re-run full validation suite
- [x] Leagues feature MVP shipped (`/leagues`) with standings, gaps, and insights
- [x] Overall rank trend moved into Leagues page; standalone Rank Trend page removed
- [x] Target Radar removed from frontend/backend (`/targets`, `/api/fpl/targets`)
- [x] Gameweek Hub naming migration completed across UI/API aliasing
- [x] Chip planner usage visibility improved (used chips state + recommendation excludes used-up chips)

## Verification

- [x] Backend validation
- [x] Frontend lint/build
- [x] Integration validation
