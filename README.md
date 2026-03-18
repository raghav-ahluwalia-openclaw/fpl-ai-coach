# FPL AI Coach

Monorepo with:
- `frontend/` Next.js app
- `backend/` FastAPI app
- `docker-compose.yml` Postgres for persistent data

## 1) Start Postgres

```bash
docker compose up -d
```

## 2) Run backend

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 3) Ingest FPL data

In a new terminal:

```bash
curl -X POST http://127.0.0.1:8000/api/fpl/ingest/bootstrap
```

## 4) Run frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`

---

## API endpoints

- `GET /health`
- `POST /api/fpl/ingest/bootstrap` (supports `?force=true` to bypass ingest TTL)
- `GET /api/fpl/top?limit=20`
- `GET /api/fpl/recommendation`
- `POST /api/fpl/team/{entry_id}/import`
- `GET /api/fpl/team/{entry_id}/recommendation?mode=safe|balanced|aggressive`
- `GET /api/fpl/targets?mode=safe|balanced|aggressive&horizon=3&limit=10`

## CI (GitHub Actions)

This repo includes `.github/workflows/ci.yml` with parallel jobs for backend, frontend, and integration validation on every push and pull request.

## Repository hygiene

A root `.gitignore` is included to keep local/runtime artifacts out of git (for example: `backend/.env`, `backend/.venv/`, `backend/fpl.db`, `frontend/node_modules/`, `frontend/.next/`).

Optional cleanup helper:

```bash
./scripts/cleanup_repo_artifacts.sh
# or also remove local sqlite DB
./scripts/cleanup_repo_artifacts.sh --delete-db
```

## Git pre-commit hook (best practice)

This project includes a pre-commit hook that runs the full validation suite.

If this repo is not initialized yet:

```bash
git init
```

Install hook:

```bash
./scripts/install_hooks.sh
```

The hook runs:

```bash
./scripts/validate_all.sh
```

## Validation scripts (best-practice checks)

From project root:

```bash
./scripts/validate_all.sh
```

Or run individually:

```bash
./scripts/validate_backend.py
./scripts/validate_frontend.sh
./scripts/validate_integration.py
```

Optional:
- Override validation team ID: `FPL_TEAM_ID=538572 ./scripts/validate_backend.py`
- Override backend validation port: `VALIDATION_PORT=8092 ./scripts/validate_backend.py`
- Override integration ports:
  - `INTEGRATION_BACKEND_PORT=8093`
  - `INTEGRATION_FRONTEND_PORT=3091`

What gets validated:
- backend startup + health
- ingest endpoint
- top players endpoint
- global recommendation endpoint
- target radar endpoint
- team import + team recommendation (balanced/safe/aggressive)
- team rank history endpoint
- frontend lint + production build
- frontend↔backend rewrite integration (`/api/*` through Next.js)
- feature page routes (`/global`, `/targets`, `/team`, `/team-rank`, `/top`)

## Notes

- Recommendation model v1 uses: points-per-game, recent form, minutes proxy, fixture difficulty, and availability/news flags.
- If you do not want Docker, set `DATABASE_URL=sqlite:///./fpl.db` in `backend/.env`.
