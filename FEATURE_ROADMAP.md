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

5. Explainability v2 (decision confidence provenance) (**Done**)
   - Shows why plan changed since previous run with factor deltas + confidence drift in Gameweek Hub payload + UI.

6. Simulation lab (**Done**)
   - Monte Carlo outcome bands for captain and transfer choices via `GET /api/fpl/team/{entry_id}/simulation-lab` and `/simulation` page.

7. Retention loop
   - Personalized push digest (morning/evening) with one recommended action.

### Phase 4 execution plan (captured from chat)

- **P4.1 (done):** Live Team View MVP (`/api/fpl/team/{entry_id}/live`, `/live` page).
- **P4.2 (done):** Logging + diagnostics baseline (`x-request-id`, request timing logs, `/api/fpl/diagnostics`).
- **P4.3 (done):** Live rank + mini-league delta tracker (`rank_context`, `mini_league_context`, `/live` movement cards).
- **P4.4:** Smart alerting engine v2 (captain haul, rival swing, bench haul risk, injury/sub confirmations).
- **P4.5 (done):** Explainability v2 (why recommendation changed + confidence drift).
- **P4.6 (done):** Simulation lab (Monte Carlo outcome bands for captain + transfer decisions).
- **P4.7:** Retention loop (personalized AM/PM digest with one suggested action).

### Suggested implementation order (highest ROI first)

1. P4.7 Retention loop
2. P4.4 Smart alerting engine v2 (Backlog)

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

---

## Phase 5 — Professional UX/Product Polish Plan (added 2026-04-13)

### Goal
Move from feature-rich dashboard to polished, decision-first product with stronger trust UX, faster workflows, and premium app feel.

### 1) Information architecture + consistency
1. Decision Rail (global)
   - Persistent rail/header showing: Entry, Mode, Horizon, Captain, Transfer, Confidence, Deadline.
   - Visible across `/weekly`, `/planner`, `/simulation`, `/live`.

2. Cross-page state consistency
   - Persist `entryId + mode + horizon + risk` across pages and sessions.
   - Eliminate duplicate mode/horizon setup friction.

3. Copy and interaction model standardization
   - Normalize all recommendation cards to: **Action / Why / Risk / Confidence / Fallback**.
   - Align labels and naming across nav and cards.

### 2) Trust UX (data confidence + freshness)
4. Card-level freshness/source badges
   - Add `FreshnessBadge` to major cards (updated time, source, cache/live).

5. Data health banner
   - Add top-level health state (green/yellow/red) with concise explanation.
   - Show fallback/degraded mode clearly.

6. Global "what changed since last run"
   - Page-level change summary (not only per-module) with key deltas.

### 3) Power-user workflow speed
7. Command palette
   - `Cmd/Ctrl+K` quick actions: open page, run sim, refresh import, jump to transfer/captain sections.

8. Saved presets
   - Presets like "Safe Deadline", "Balanced Default", "Aggressive Catch-up".
   - One-click preset apply.

9. Weekly checklist flow
   - Structured checklist: Import -> Review -> Simulate -> Decide -> Lock.
   - Progress persistence and completion state.

### 4) Comparative decision UX
10. Plan comparison drawer
    - Side-by-side Plan A/B/C + Hold with EV, downside, hit impact, confidence, value urgency.

11. Baseline always-visible benchmark
    - Keep "No transfer / Roll" comparator pinned as control option.

12. Multi-week impact visualization
    - Compact 1/3/5 GW mini-chart for P10/P50/P90 where simulation exists.

### 5) Notifications + retention UX
13. Notification center
    - In-app history of alerts and dispatch status.

14. Alert policy manager
    - Per-alert toggles, frequency, quiet hours, snooze/mute controls.

15. Alert explainability
    - "Why you received this alert" with trigger details and thresholds.

16. Retention digest loop (P4.7 expansion)
    - Morning/evening digest templates with one recommended action and confidence rationale.

### 6) Visual polish + mobile ergonomics
17. Card hierarchy system
    - Tiered visual hierarchy: primary decision cards vs supporting analytics vs diagnostics.

18. Mobile action ergonomics
    - Sticky bottom action bar for key actions on mobile.
    - Improve touch target consistency and section jump behavior.

19. Motion consistency pass
    - Reuse motion tokens consistently for deltas, confidence transitions, and state changes.

### 7) Accessibility + quality completeness
20. Keyboard and focus audit
    - Full keyboard traversal and visible focus state coverage on all critical routes.

21. Contrast and reduced-motion parity
    - WCAG AA validation for core UI states.
    - Ensure reduced-motion alternatives across animated flows.

22. UX regression guardrails
    - Add route-level UX QA checklist + snapshots for `/weekly`, `/live`, `/planner`, `/simulation`.

### Suggested implementation order (highest ROI)
1. Trust UX (items 4-6)
2. Comparative decision UX (items 10-12)
3. Workflow speed (items 7-9)
4. Notifications + retention UX (items 13-16)
5. Visual + mobile + accessibility passes (items 17-22)

### Implementation progress (2026-04-14, slice 1)
- Added initial **Decision Rail** component and surfaced it on `/weekly`, `/planner`, `/live`, and `/simulation` (entry + mode + GW window + deadline countdown).
- Introduced visual hierarchy utility classes in global styles: `card-primary`, `card-supporting`, `card-diagnostic`, plus reusable `pill` and `touch-target` helpers.
- Applied hierarchy styles to key Gameweek Hub sections (`summary`, `simulation preview`, `changes`).
- Added mobile sticky action bar on `/weekly` with fast actions: Refresh, Simulation Lab, Jump to Transfers.
- Increased touch target sizing/consistency for top controls in Weekly and updated CTA copy to action-oriented labels for consistency.

### Implementation progress (2026-04-14, slice 2)
- Added reusable **FreshnessBadge** component (recency + source + live/cached state).
- Added reusable **DataHealthBanner** component (good/warn/bad health state with concise detail).
- Wired trust UX into `/weekly`:
  - Global change summary strip at top of content section.
  - Data health banner after gameweek status.
  - Freshness badge in team overview and global change summary.
- Wired trust UX into `/live`:
  - Data health banner near top.
  - Freshness badge in live summary card header.
