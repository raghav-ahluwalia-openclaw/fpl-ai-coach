# FPL AI Coach - Frontend IA Consolidation Plan

Date: 2026-03-26

## Goal
Reduce navigation clutter while preserving all decision-critical workflows.

## Target navigation
1. Gameweek Hub (`/weekly`)
2. Live (`/live`)
3. Planner (`/planner`)
4. Leagues (`/leagues`)
5. Research Hub (`/top`)
6. Social Intel (`/socials`)
7. Settings (`/settings`)

## Route consolidation map

- `/weekly` -> Keep as primary weekly decision page.
- `/live` -> Keep as dedicated real-time monitoring page.
- `/planner` -> Keep for multi-GW strategy + rival/chip planning.
- `/leagues` -> Keep for standing/rank context.
- `/top` -> Rename UI to **Research Hub** and keep top picks + explainability.
- `/socials` -> Rename nav label to **Social Intel** (same route).
- `/brief` -> Consolidate into Gameweek Hub and redirect to `/weekly`.
- `/captaincy` -> Consolidate into Research Hub and redirect to `/top`.
- `/team` -> Legacy route, keep redirect to `/weekly`.
- `/global` -> Legacy route, keep redirect to `/top`.

## Naming consistency standards

- UI term: "Gameweek Hub" (not "Weekly Cockpit").
- Use "entryId" in frontend state for user team id.
- API response type names should end in `Response`.
- Prefer feature-specific data state names over generic `data` in new code.

## Implementation status

- [x] Nav label `FPL Socials` -> `Social Intel`
- [x] Home card title updated to `Social Intel`
- [x] `/top` H1 changed to `Research Hub`
- [x] `/captaincy` now redirects to `/top`
- [x] `/brief` now redirects to `/weekly`
- [ ] Optional follow-up: rename internal TS types and state variables for full naming consistency
