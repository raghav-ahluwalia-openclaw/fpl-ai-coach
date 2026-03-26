# FPL AI Coach Frontend

Next.js (App Router) frontend for FPL AI Coach.

## Main pages

- `/` Home dashboard
- `/weekly` Gameweek Hub
- `/live` Live Team View
- `/planner` Planner
- `/leagues` League insights
- `/captaincy` Captaincy Lab
- `/brief` Weekly brief
- `/socials` FPL socials insights

## Run locally

From `frontend/`:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Build + lint

```bash
npm run lint
npm run build
```

## Backend connectivity

The app uses same-origin `/api/*` routes (Next rewrites) to proxy to backend.
For full-stack setup and backend instructions, see the repo root `README.md`.
