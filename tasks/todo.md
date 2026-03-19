# tasks/todo.md

## Active Plan — Product upgrade phases (saved 2026-03-19)

### Phase 1 (next execution target)
- [ ] Transfer Planner Engine v2 (Top 1FT/2FT Plan A/B/C with EV/risk/confidence)
- [ ] Weekly Cockpit single-screen page (Team Health + Plans + Captain Matrix + changes)
- [ ] XI + Bench optimizer UX with alternate-lineup gain

### Phase 2
- [ ] Standardize explicit 1/3/5 GW projections across APIs
- [ ] Add price-change aware transfer scoring
- [ ] Add confidence calibration + bucketed reliability outputs

### Phase 3
- [ ] Weekly evaluation module (hit-rate, no-transfer baseline, calibration report)
- [ ] `/api/fpl/performance/weekly` + dashboard card

## Recently completed (2026-03-19)

- [x] Backend modularization phase 2
  - [x] Move models into `app/db/models.py`
  - [x] Move schemas into `app/schemas/`
  - [x] Extract scoring helpers into `app/services/scoring.py`
  - [x] Re-run full validation suite

## Verification

- [x] Backend validation
- [x] Frontend lint/build
- [x] Integration validation
