# FPL AI Coach Feature Roadmap

## Current status snapshot (2026-03-18)

### ✅ Shipped

1. Historical-season ML pipeline
   - `backend/ml/build_historical_dataset.py`
   - `backend/ml/train_xgb_historical.py`
   - API model switch: `model_version=xgb_v1|xgb_hist_v1`

2. Creator consensus ingest pipeline
   - `scripts/fpl_creator_watchlist.json`
   - `scripts/fpl_creator_digest.py`
   - Transcript-based tags + summaries + player mention extraction
   - `GET /api/fpl/content-consensus`

3. Weekly blended recommendation
   - `GET /api/fpl/weekly-brief`
   - Blends baseline + ML + creator consensus by mode.

4. Weekly brief frontend UX (`/brief`)
   - Final action, model comparison, rationale, creator consensus
   - Notification controls + test reminder action

5. Deadline-aware notification system
   - `GET /api/fpl/deadline-next`
   - `GET /api/fpl/deadline-reminder`
   - `GET/POST /api/fpl/notification-settings`
   - `GET /api/fpl/notification-status` (includes last/next check + last sent metadata)

6. Automatic pre-deadline reminder dispatch (runtime)
   - Cron job: **FPL Deadline Reminder Dispatcher**
   - 30-minute checks, deduped by GW using `memory/fpl-reminder-state.json`

7. Recommendation consistency guardrails
   - Invalid/self/duplicate transfer guardrails in team recommendation
   - Weekly brief ML confidence threshold fallback to baseline

8. What-if transfer simulator
   - `GET /api/fpl/team/{entry_id}/what-if`
   - Supports 1FT/2FT scenarios, horizon, free transfers, hit cost
   - Returns ranked scenarios by projected net gain

9. Captaincy lab
   - `GET /api/fpl/captaincy-lab`
   - Safe vs upside captain boards with xP, risk, ownership pressure
   - Frontend page: `/captaincy`

10. Explainability cards
   - `GET /api/fpl/explainability/top`
   - Factor-level breakdown per player (form, fixture, minutes, availability, risk)
   - Rendered in Top Players page

11. Reliability hardening
   - Backend notification endpoint tests: `backend/tests/test_notification_endpoints.py`
   - Integration validation includes weekly-brief + notification-status + what-if

12. P3 starter — Planner + Rival + Digest payload
   - `GET /api/fpl/chip-planner`
   - `GET /api/fpl/rival-intelligence`
   - `GET /api/fpl/weekly-digest-card`
   - Frontend page: `/planner`

13. P3 v2 enhancements
   - Chip planner now includes blank/double GW window detection (`fixture_windows`)
   - Chip recommendation now returns confidence + alternative
   - Weekly digest card now provides rich emoji sections + `telegram_text`

14. P3 v2.5 Rival intelligence enhancements
   - Captaincy overlap risk surfaced in API + planner UI
   - Differential impact scoring added for both squads

---

## Remaining P3

1. Weekly digest card v3
   - Add optional image renderer payload for richer Telegram card visuals

## Success metrics

- Prediction quality: captain hit-rate, transfer gain vs hold
- Product utility: weekly brief open rate before deadline
- Notification quality: on-time send rate, duplicate send rate
- Trust: % users opening explainability panels and following final recommendation

---

## Product upgrade plan (saved from chat, 2026-03-19)

### Phase 1 — highest ROI

1. Transfer Planner Engine v2
   - Goal: Top 1FT + Top 2FT Plan A/B/C with EV, risk, confidence.
   - Status: ✅ Completed.
   - Delivered in `/api/fpl/team/{entry_id}/weekly-cockpit` as A/B/C plans for 1FT and 2FT with `ev`, `risk_score`, `confidence`, and `confidence_bucket`.

2. Gameweek Hub page (single screen)
   - Goal: Team Health + Transfer Plans A/B/C + Captain Matrix + What changed.
   - Status: ✅ Completed.
   - Delivered in frontend `/weekly` (renamed UI label: **Gameweek Hub**) as one-screen workflow for weekly decisions.

3. XI + Bench Optimizer in my-team context
   - Goal: optimize XI + bench order with expected gain deltas.
   - Status: ✅ Completed.
   - Delivered with optimizer output plus `expected_gain_vs_current_xi_1/3` and `bench_order_gain_1/3`.

### Phase 2 — engine quality

4. Projection horizon upgrade
   - Goal: explicit 1/3/5 GW projections consistently across outputs.
   - Status: ✅ Completed for core APIs.
   - Delivered in recommendation, recommendation-ml, team recommendation, top players, captaincy lab, and weekly cockpit payloads with explicit 1/3/5 fields (backward compatible).

5. Price-change aware transfer scoring
   - Goal: include rise/fall pressure in transfer ranking.
   - Status: ⛔ Not started.

6. Calibration + reliability
   - Goal: confidence calibration + bucketed confidence reporting.
   - Status: ⚠️ Partial (guardrails exist; no explicit calibration layer yet).

### Phase 3 — measurement loop

7. Weekly evaluation module
   - Goal: recommendation hit-rate, no-transfer baseline, calibration report, performance API/card.
   - Status: ⛔ Not started.

### Completed since this plan was drafted

- ✅ Backend modularization phase 2 completed (DB models package, schemas package, scoring service extraction).
- ✅ Leagues feature MVP shipped (`/leagues`) with classic + H2H standings, rank/gap insights, and embedded overall rank trend.
- ✅ "Weekly Cockpit" terminology migrated to **Gameweek Hub** across frontend and backend API aliasing.
- ✅ Target Radar removed from frontend and backend (`/targets`, `/api/fpl/targets`) to simplify product surface.
