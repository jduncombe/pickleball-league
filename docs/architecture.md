# Architecture

```
            ┌─ /*      ──▶ static site (Next.js export)
 Browser ───┤
            └─ /api/*  ──▶ FastAPI (prefix stripped) ──▶ PostgreSQL / SQLite
```

The same shape is used everywhere; only the router in front changes:

| Where | Serves the static site | Routes `/api/*` to the API | Database |
| --- | --- | --- | --- |
| AWS (ap-southeast-2) | S3 via CloudFront | CloudFront → internal ALB → ECS Fargate (Graviton) | RDS PostgreSQL (Graviton) |
| `docker compose` | nginx | nginx → `api` container | SQLite volume |
| `npm run dev` | Next.js dev server | dev-server rewrite → `API_URL` | SQLite file |

See [deployment.md](deployment.md) for the AWS details.

## Components

### `web/` — Next.js

- **App Router**, TypeScript, no UI framework (plain CSS in `src/app/globals.css`,
  light and dark themes via CSS variables).
- Pages are client components that fetch data through `src/lib/api.ts`, a small
  typed client. `src/lib/types.ts` mirrors the API's response schemas.
- **Static export** (`output: "export"` in `next.config.ts`): `npm run build`
  writes plain HTML/JS/CSS to `web/out/`, which is what gets uploaded to S3.
  There is no Node server in production. Consequences:
  - pages load data in the browser (client components);
  - league pages take the league as a query parameter (`/league/teams/?id=3`)
    instead of a dynamic path segment, because a static export can't
    pre-render unknown ids;
  - `trailingSlash: true` produces `league/teams/index.html`, and CloudFront
    maps directory URLs to `index.html` (`infra/app/functions/web-rewrite.js`).
- **Same-origin API:** the browser calls `/api/...` on the site's own origin
  and whatever sits in front routes it to the API. No CORS in any environment,
  and no API URL baked into the build (override with `NEXT_PUBLIC_API_URL` if
  you do want the browser to call the API directly).
- The live dashboard polls every 15 seconds so several devices (e.g. a desk
  laptop and a court-side tablet) stay in sync.

### `api/` — FastAPI

- `models.py` — SQLAlchemy 2.0 ORM models (`League`, `Team`, `Player`, `Match`).
- `schemas.py` — Pydantic models for validation and responses.
- `scheduling.py` — pure functions that build the round-robin schedule; no DB
  access, easy to unit test.
- `routers/` — endpoints grouped by resource.
- Tables are created on startup (`init_db`). Interactive docs at `/docs`,
  OpenAPI JSON at `/openapi.json`. Behind a proxy, `ROOT_PATH=/api` makes the
  docs page load the spec from `/api/openapi.json`.

### Storage

PostgreSQL in AWS (RDS), SQLite locally and in docker-compose. SQLAlchemy
hides the difference; the API test suite runs against both in CI.

## Configuration

| Variable | Service | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | api | `sqlite:///./data/pickleball.db` | SQLAlchemy database URL. Takes precedence over `DB_*`. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | api | – | Postgres connection parts, used when `DATABASE_URL` is unset (ECS injects the password from Secrets Manager) |
| `ROOT_PATH` | api | `""` | Prefix the API is served under by a proxy that strips it (`/api`) |
| `CORS_ORIGINS` | api | `http://localhost:3000` | Comma-separated origins allowed to call the API directly from a browser |
| `API_URL` | web (dev server, nginx image) | `http://localhost:8000` / `http://api:8000` | Where `/api/*` is forwarded |
| `NEXT_PUBLIC_API_URL` | web (build time) | `/api` | Base URL the browser uses for API calls |
| `TEST_DATABASE_URL` | api tests | in-memory SQLite | Run the tests against another database (CI uses Postgres) |

## Testing

`.github/workflows/ci.yml` runs on every pull request (and before every deploy):

- API: `cd api && pytest` against in-memory SQLite and a Postgres service container.
- Web: `cd web && npm run lint` (type check) and `npm run build` (static export).
- Docker: `docker compose build`.
- Terraform: `fmt -check`, `validate` for both stacks, `terraform test` for the
  app stack (mocked AWS provider, no credentials), and unit tests for the
  CloudFront Functions.

## Known gaps / next steps

This is a skeleton. Likely next steps, roughly in priority order:

1. **Authentication & roles** — organiser vs. read-only viewer, e.g. Amazon
   Cognito with tokens verified by the API.
2. **Migrations** — replace `create_all` with Alembic before the schema changes
   (and before running more than one API task, which would race on first start).
3. **Scheduling options** — balance courts across teams, respect team
   availability, handle late-added teams, re-generate only future weeks.
4. **Match detail** — multiple games per match (best of 3), which players played
   (needed for DUPR submission), rally/side-out scoring rules.
5. **Real-time updates** — replace polling with Server-Sent Events or WebSockets.
6. **DUPR integration** — see [dupr-integration.md](dupr-integration.md).
7. **Frontend tests** — Playwright smoke tests for the core flows.
