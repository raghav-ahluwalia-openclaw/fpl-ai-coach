# tasks/todo.md

## Active Plan — P1.5 + P2 bundle (2026-03-18)

- [x] Review `tasks/lessons.md` before implementation
- [x] P1.5.1 Add notification polish data in backend (`last_sent`, `next_run_eta`)
- [x] P1.5.2 Show last-sent + next-run ETA in `/brief`
- [x] P1.5.3 Add backend tests for notification endpoints
- [x] P1.5.4 Extend integration validation for `/api/fpl/weekly-brief` + `/api/fpl/notification-status`
- [x] P1.5.5 Add recommendation consistency guardrails + confidence fallback
- [x] P2.1 Add What-if transfer simulator endpoint
- [x] P2.2 Add Captaincy Lab endpoint + frontend page
- [x] P2.3 Add Explainability endpoint + cards in Top page
- [x] P2.4 Validate backend/frontend/integration end-to-end
- [ ] P2.5 Auto-commit completed bundle

## Verification steps

- [x] `./scripts/validate_all.sh`
- [x] Manual route verification in build output (`/captaincy` present)

## Review (post-implementation)

- Outcome: P1.5 and full P2 scope delivered (what-if + captaincy + explainability).
- What passed: full backend/frontend/integration validation suite.
- Follow-ups: start P3 (chip planner, rival intelligence, weekly digest card).
