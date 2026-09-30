# Architecture

```
 Browser ──HTTP──▶ Next.js server (web, :3000) ──HTTP──▶ FastAPI (api, :8000) ──▶ SQLite (/data)
            pages + /api/* proxy                         REST + OpenAPI docs
```

## Components

### `web/` — Next.js

- **App Router**, TypeScript, no UI framework (plain CSS in `src/app/globals.css`,
  light and dark themes via CSS variables).
- Pages are client components that fetch data through `src/lib/api.ts`, a small
  typed client. `src/lib/types.ts` mirrors the API's response schemas.
- **API proxy:** the browser never talks to the Python API directly. It calls
  `/api/...` on the Next.js server, and the route handler in
  `src/app/api/[...path]/route.ts` forwards the request to `API_URL`. This means:
  - the API address is a *runtime* setting (no rebuild per environment);
  - no CORS setup is needed in the Docker deployment;
  - auth (see below) can later be added in one place.
- The live dashboard polls every 15 seconds so several devices (e.g. a desk
  laptop and a court-side tablet) stay in sync.

### `api/` — FastAPI

- `models.py` — SQLAlchemy 2.0 ORM models (`League`, `Team`, `Player`, `Match`).
- `schemas.py` — Pydantic models for validation and responses.
- `scheduling.py` — pure functions that build the round-robin schedule; no DB
  access, easy to unit test.
- `routers/` — endpoints grouped by resource.
- Tables are created on startup (`init_db`). Interactive docs at `/docs`,
  OpenAPI JSON at `/openapi.json`.

### Storage

SQLite, stored at `DATABASE_URL` (defaults to `./data/pickleball.db`; `/data`
volume in Docker). SQLAlchemy keeps the move to Postgres to a connection-string
change plus a `psycopg` dependency.

## Configuration

| Variable | Service | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | api | `sqlite:///./data/pickleball.db` | SQLAlchemy database URL |
| `CORS_ORIGINS` | api | `http://localhost:3000` | Comma-separated origins allowed to call the API directly |
| `API_URL` | web | `http://localhost:8000` | Where the Next.js server proxies `/api/*` |

## Testing

- API: `cd api && pytest` — scheduler unit tests plus API flow tests against an
  in-memory database.
- Web: `cd web && npm run lint` (type check) and `npm run build`.

## Known gaps / next steps

This is a skeleton. Likely next steps, roughly in priority order:

1. **Authentication & roles** — organiser vs. read-only viewer. Add at the Next.js
   proxy (session) and pass a token to the API.
2. **Migrations** — replace `create_all` with Alembic before the schema changes.
3. **Scheduling options** — balance courts across teams, respect team
   availability, handle late-added teams, re-generate only future weeks.
4. **Match detail** — multiple games per match (best of 3), which players played
   (needed for DUPR submission), rally/side-out scoring rules.
5. **Real-time updates** — replace polling with Server-Sent Events or WebSockets.
6. **DUPR integration** — see [dupr-integration.md](dupr-integration.md).
7. **Frontend tests** — Playwright smoke tests for the core flows.
