# tasks/todo.md

## Active Plan — P1.5 + What-if Simulator (2026-03-18)

- [x] Review `tasks/lessons.md` before implementation
- [x] P1.5.1 Add notification polish data in backend (`last_sent`, `next_run_eta`)
- [x] P1.5.2 Show last-sent + next-run ETA in `/brief`
- [x] P1.5.3 Add backend tests for notification endpoints
- [x] P1.5.4 Extend integration validation for `/api/fpl/weekly-brief` + `/api/fpl/notification-status`
- [x] P1.5.5 Add recommendation consistency guardrails + confidence fallback
- [x] P2.1 Add What-if transfer simulator endpoint
- [x] P2.2 Validate backend/frontend/integration end-to-end
- [x] P2.3 Update README + roadmap status
- [ ] P2.4 Auto-commit completed bundle

## Verification steps

- [x] `./scripts/validate_backend.py`
- [x] `./scripts/validate_frontend.sh` (via validate_all)
- [x] `./scripts/validate_integration.py` (via validate_all)
- [x] Manual/functional checks included in validation scripts:
  - `/api/fpl/notification-status`
  - `/api/fpl/weekly-brief`
  - `/api/fpl/team/{id}/what-if`

## Review (post-implementation)

- Outcome: P1.5 completed, and P2 What-if simulator shipped.
- What passed: full backend/frontend/integration validation suite.
- Follow-ups: implement Captaincy Lab and Explainability cards next.
