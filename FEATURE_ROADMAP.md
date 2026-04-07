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

1. (Completed) Weekly digest card v3
   - Optional image renderer payload shipped for richer Telegram card visuals

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
   - Status: ✅ Completed.
   - Delivered value urgency scoring (`price_rise_pressure_in`, `price_fall_pressure_out`, `value_urgency_score`) and ranking bonus in transfer simulation + Gameweek Hub plans.

6. Calibration + reliability
   - Goal: confidence calibration + bucketed confidence reporting.
   - Status: ✅ Completed (v1 rule calibration).
   - Delivered calibrated plan confidence with bucket + calibration metadata (`confidence_raw`, `confidence`, `confidence_bucket`, `confidence_calibration`).

### Phase 3 — measurement loop

7. Weekly evaluation module
   - Goal: recommendation hit-rate, no-transfer baseline, calibration report, performance API/card.
   - Status: ✅ MVP completed.
   - Delivered endpoints: `/api/fpl/performance/weekly` and `/api/fpl/team/{entry_id}/performance/weekly`.
   - Delivered UI card: Performance Snapshot on Gameweek Hub (`/weekly`).

### Completed since this plan was drafted

- ✅ Backend modularization phase 2 completed (DB models package, schemas package, scoring service extraction).
- ✅ Leagues feature MVP shipped (`/leagues`) with classic + H2H standings, rank/gap insights, and embedded overall rank trend.
- ✅ "Weekly Cockpit" terminology migrated to **Gameweek Hub** across frontend and backend API aliasing.
- ✅ Target Radar removed from frontend and backend (`/targets`, `/api/fpl/targets`) to simplify product surface.

---

## Phase 4 — Uplevel to market leader (started 2026-03-25)

### ✅ Started / shipped now

1. Live Team View MVP
   - Backend: `GET /api/fpl/team/{entry_id}/live`
   - Frontend: new `/live` page + home navigation card
   - Includes: live total, starters vs bench split, captain impact, player-level live points.

2. Better logging + troubleshooting baseline
   - Request middleware adds timing + request id (`x-request-id`) and structured log line per request.
   - New diagnostics endpoint: `GET /api/fpl/diagnostics` with data freshness + quick fix hints.

3. Live rank + mini-league delta tracker
   - Extended `GET /api/fpl/team/{entry_id}/live` with:
     - `rank_context` (current rank, reference rank, delta, direction)
     - `mini_league_context` (league rank movement + direction)
   - Frontend `/live` now shows rank movement cards with clear up/down/flat indicators.

### Next high-ROI items

4. Smart alerting engine v2 (**Backlog**)
   - Goal alerts (captain haul, rival swing, bench haul risk, injury/sub confirmations).
   - Status: deferred to backlog by product decision (2026-04-01).

5. Explainability v2 (decision confidence provenance)
   - Show why plan changed since previous run with factor deltas + confidence drift.

6. Simulation lab
   - Monte Carlo outcome bands for captain and transfer choices.

7. Retention loop
   - Personalized push digest (morning/evening) with one recommended action.

### Phase 4 execution plan (captured from chat)

- **P4.1 (done):** Live Team View MVP (`/api/fpl/team/{entry_id}/live`, `/live` page).
- **P4.2 (done):** Logging + diagnostics baseline (`x-request-id`, request timing logs, `/api/fpl/diagnostics`).
- **P4.3 (done):** Live rank + mini-league delta tracker (`rank_context`, `mini_league_context`, `/live` movement cards).
- **P4.4:** Smart alerting engine v2 (captain haul, rival swing, bench haul risk, injury/sub confirmations).
- **P4.5:** Explainability v2 (why recommendation changed + confidence drift).
- **P4.6:** Simulation lab (Monte Carlo outcome bands for captain + transfer decisions).
- **P4.7:** Retention loop (personalized AM/PM digest with one suggested action).

### Suggested implementation order (highest ROI first)

1. P4.5 Explainability v2
2. P4.6 Simulation lab
3. P4.7 Retention loop
4. P4.4 Smart alerting engine v2 (Backlog)

---

## Phase 4.8 — Visual + Motion Uplevel Plan (added 2026-03-25)

### Goal
Move FPL AI Coach from "functional" to "premium" with polished motion, clearer hierarchy, and richer visual analytics while preserving speed.

### Principles
- Motion should clarify state change, not distract.
- Keep performance first (GPU-friendly transforms, avoid layout thrash).
- Respect accessibility (`prefers-reduced-motion`, keyboard focus visibility, contrast).

### Foundation work (Sprint V1)
1. Design token baseline
   - Color tokens: `bg/surface/surface-elevated/text/muted/success/warn/danger/info/accent`.
   - Spacing scale: 4/8/12/16/24/32.
   - Radius + shadow tokens for consistent card depth.

2. Motion token baseline
   - Durations: 120ms / 200ms / 320ms.
   - Easing presets: `ease-out`, `ease-in-out`, `spring-soft`.
   - Global reduced-motion guard + fallback transitions.

3. Core reusable UI components
   - `MetricCard`, `DeltaChip`, `ConfidenceMeter`, `RiskPill`, `SkeletonBlock`, `EmptyState`.

### Screen-level upgrades (Sprint V2)
4. Gameweek Hub (`/weekly`)
   - Animated card entrance (staggered).
   - Delta highlight animations for rank/EV changes.
   - Confidence meter for A/B/C transfer plans.

5. Live (`/live`) + Leagues (`/leagues`)
   - Live score tick animation + captain impact pulse.
   - Mini-league position movement indicators.
   - Trend sparklines for rank and points movement.

6. Captaincy + Planner
   - Captain comparison visuals (probability/confidence bands).
   - Chip planner status visualization with clearer state coding.

### Data viz upgrades (Sprint V3)
7. Visualization layer
   - Add chart system for: trend lines, confidence bands, EV vs risk scatter, movement ladders.
   - Standardize chart color semantics + tooltip patterns.

8. Loading/error/empty state polish
   - Skeletons for all major data cards.
   - Uniform retry/error cards with diagnostics links.

### Performance + QA gates
9. Performance budgets
   - LCP < 2.5s on core pages (p75), animation FPS target 50+.
   - Limit heavy animations to above-the-fold key moments only.

10. Accessibility gates
   - WCAG AA contrast checks.
   - Keyboard focus states on interactive controls.
   - Reduced-motion mode parity checks.

### Skills installed to support this plan
- `ui-ux-pro-max`
- `frontend-ui-animator`
- `lottie-animations`
- `storybook-story-writing`
- `storybook-args-controls`
- `data-visualization`
- `dashboard-builder`

### IA simplification follow-up
- Added page consolidation map and naming standards doc: `docs/IA_CONSOLIDATION_PLAN.md`.
- Objective: simpler nav + fewer overlapping pages while preserving all decision workflows.
