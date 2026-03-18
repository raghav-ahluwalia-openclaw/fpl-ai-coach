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
   - `GET /api/fpl/content-consensus`

3. Weekly blended recommendation backend
   - `GET /api/fpl/weekly-brief`
   - Blends baseline + ML + creator consensus with safe/balanced/aggressive mode.

4. Weekly brief frontend UX
   - `frontend/src/app/brief/page.tsx`
   - Includes final action, model comparison, rationale, and creator consensus cards.

5. Deadline-aware notification system (in app)
   - `GET /api/fpl/deadline-next`
   - `GET /api/fpl/deadline-reminder`
   - `GET/POST /api/fpl/notification-settings`
   - `GET /api/fpl/notification-status`
   - Brief page notification settings UI (enable, lead time, mode, model).

6. Automatic pre-deadline reminder dispatch (runtime)
   - Cron job: **FPL Deadline Reminder Dispatcher**
   - 30-minute checks, deduped by GW using `memory/fpl-reminder-state.json`

---

## P1.5 (Next 1–3 days)

1. Frontend notification polish
   - Add “last sent” and “next run ETA” visibility in `/brief`.
   - Add one-click “send test reminder now”.

2. Reliability hardening
   - Add backend tests for notification endpoints.
   - Add integration assertion for `/api/fpl/weekly-brief` and `/api/fpl/notification-status`.

3. Recommendation consistency checks
   - Add guardrails for impossible transfers (e.g., player not in squad).
   - Add minimum confidence threshold fallback to baseline model.

## P2 (Next sprint)

1. What-if transfer simulator
   - Evaluate 1FT/2FT/-4/-8 scenarios over 1/3/5 GW.
   - Return best move, downside band, and EV delta vs hold.

2. Captaincy lab
   - Safe vs upside captain board.
   - Include volatility and effective ownership pressure.

3. Explainability cards
   - Per-player factor breakdown: form, fixture, minutes security, availability risk.

## P3 (Later)

1. Chip planner (WC/FH/BB/TC windows)
2. Rival/mini-league intelligence
3. Auto weekly Telegram digest card with visual summary

## Success metrics

- Prediction quality: captain hit-rate, transfer gain vs hold
- Product utility: weekly brief open rate before deadline
- Notification quality: on-time send rate, duplicate send rate
- Trust: % users opening explainability panels and following final recommendation
