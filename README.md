# FPL AI Coach

AI-powered Fantasy Premier League assistant with a Next.js frontend and FastAPI backend.

It helps with:
- weekly transfer planning (A/B/C plans)
- captaincy decisions (safe vs upside)
- team optimization (XI + bench)
- rival/league intelligence
- live gameweek tracking
- explainability + confidence signals

---

## Repo contents

- `frontend/` - Next.js app (App Router)
- `backend/` - FastAPI API + scoring/model logic
- `scripts/` - local run, validation, hooks, utility scripts
- `.github/workflows/ci.yml` - backend/frontend/integration CI

---

## Feature summary (current)

### Core decision features
- **Gameweek Hub** (`/weekly`): team health, transfer plans, confidence, and performance snapshot.
- **Planner** (`/planner`): chip planning + rival intelligence views.
- **Captaincy Lab** (`/captaincy`): captain option ranking with risk/upside framing.
- **Team recommendation engine**: mode-aware (`safe|balanced|aggressive`) suggestions.
- **What-if simulator**: 1FT/2FT scenario ranking by projected net gain.

### Intelligence + explainability
- **Weekly brief** blending baseline + ML + creator consensus.
- **Explainability cards** (player-level factor breakdowns).
- **Projection horizons** across key outputs (1/3/5 GW where available).
- **Calibration metadata** for confidence quality.

### Live + reliability
- **Live Team View** (`/live`): live total, starters/bench split, captain impact, player-level live points.
- **Diagnostics endpoint** (`/api/fpl/diagnostics`) for data freshness and troubleshooting.
- **Deadline notification plumbing** + status visibility.
- **Request tracing** with request-id/timing logging.

---

## Quick start (recommended)

From repo root:

```bash
# 1) Start app stack (backend + frontend)
./scripts/start_app.sh

# 2) Check status and URLs
./scripts/status_app.sh

# 3) Stop when done
./scripts/stop_app.sh
```

---

## Manual run (dev mode)

### 1) Start Postgres

```bash
docker compose up -d
```

### 2) Run backend

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3) Bootstrap ingest

In a new terminal:

```bash
curl -X POST http://127.0.0.1:8000/api/fpl/ingest/bootstrap
```

### 4) Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open: `http://localhost:3000`

---

## Useful routes

Frontend pages:
- `/weekly` (Gameweek Hub)
- `/live`
- `/planner`
- `/leagues`
- `/captaincy`
- `/brief`
- `/socials`

Key API routes:
- `GET /health`
- `POST /api/fpl/ingest/bootstrap`
- `GET /api/fpl/team/{entry_id}/gameweek-hub` (alias: `/weekly-cockpit`)
- `GET /api/fpl/team/{entry_id}/live`
- `GET /api/fpl/team/{entry_id}/what-if`
- `GET /api/fpl/captaincy-lab`
- `GET /api/fpl/chip-planner`
- `GET /api/fpl/rival-intelligence`
- `GET /api/fpl/weekly-brief`
- `GET /api/fpl/explainability/top`
- `GET /api/fpl/diagnostics`

---

## Validation and quality

Run full local validation:

```bash
./scripts/validate_all.sh
```

Or individually:

```bash
./scripts/validate_backend.py
./scripts/validate_frontend.sh
./scripts/validate_integration.py
```

Install git workflow hooks:

```bash
./scripts/install_hooks.sh
```

This enforces PR-first workflow locally:
- blocks direct commit on `main`/`master`
- blocks direct push on `main`/`master`
- use helper to create a branch:

```bash
./scripts/new_pr_branch.sh my-change-name
```

---

## Notes

- If you do not want Docker/Postgres, you can use sqlite by setting:
  `DATABASE_URL=sqlite:///./fpl.db` in `backend/.env`.
- `frontend` calls backend via `/api/*` rewrites for same-origin compatibility.
- Some planning views may use the latest published FPL squad snapshot when current GW picks are not yet available from FPL.
