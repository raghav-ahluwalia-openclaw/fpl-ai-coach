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

---

## Next Up (P3)

1. Chip planner (WC/FH/BB/TC windows)
2. Rival/mini-league intelligence
3. Auto weekly Telegram digest card with visual summary

## Success metrics

- Prediction quality: captain hit-rate, transfer gain vs hold
- Product utility: weekly brief open rate before deadline
- Notification quality: on-time send rate, duplicate send rate
- Trust: % users opening explainability panels and following final recommendation
