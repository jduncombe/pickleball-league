# Pickleball League

[![CI](https://github.com/jduncombe/pickleball-league/actions/workflows/ci.yml/badge.svg)](https://github.com/jduncombe/pickleball-league/actions/workflows/ci.yml)
[![Deploy](https://github.com/jduncombe/pickleball-league/actions/workflows/deploy.yml/badge.svg)](https://github.com/jduncombe/pickleball-league/actions/workflows/deploy.yml)

A skeleton for running a pickleball league: create a league, enter teams and
players (with DUPR IDs), generate a round-robin schedule, run matches across a
limited number of courts, and record results.

| Part | Stack | Folder |
| --- | --- | --- |
| Web interface | Next.js (App Router, TypeScript), exported as a static site | [`web/`](web/) |
| API | Python · FastAPI · SQLAlchemy · PostgreSQL (SQLite locally) | [`api/`](api/) |
| Infrastructure | Terraform: S3 + CloudFront, ECS Fargate, RDS, in an existing VPC | [`infra/`](infra/) |
| CI/CD | GitHub Actions | [`.github/workflows/`](.github/workflows/) |

## Quick start (Docker)

```bash
docker compose up --build
```

- Web UI: http://localhost:3000 (nginx serving the static export, with `/api/*` proxied to the API as CloudFront does in AWS)
- API + interactive docs (Swagger): http://localhost:8000/docs, or http://localhost:3000/api/docs

League data is stored in SQLite on the `api-data` Docker volume.
`docker compose down -v` wipes it.

## Deploying to AWS

The Terraform and deploy workflow put the static site in S3 behind CloudFront,
and the API on Graviton ECS Fargate with RDS PostgreSQL, in an existing VPC in
ap-southeast-2. **The deploy job is currently disabled**, so pushes to `main`
run CI only. Setup and how to enable it are in
[docs/deployment.md](docs/deployment.md).

## Local development (without Docker)

API (Python 3.11+):

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload          # http://localhost:8000
pytest                                  # run the tests
```

Web (Node 20+):

```bash
cd web
npm install
cp .env.example .env.local              # API_URL=http://localhost:8000
npm run dev                             # http://localhost:3000 (/api/* forwarded to API_URL)
```

## Screens

| Screen | Route | What it does |
| --- | --- | --- |
| **Live dashboard** (default) | `/` and `/league/?id=…` | Teams on court right now, and this week's match-ups that can start because neither team is playing. Start a match on a free court, enter its score, or return it to the schedule. |
| League creation | `/leagues/new` | Name, number of teams, weeks, rounds per week and courts. Creates placeholder teams and the full season schedule. |
| Teams & players | `/league/teams/?id=…` | Rename teams; add players with optional email and **DUPR ID**. |
| Schedule & results | `/league/matches/?id=…` | Week-by-week schedule grouped by round, score entry/correction, standings. |
| Leagues | `/leagues` | All leagues. |

## Documentation

- [Architecture](docs/architecture.md) — components, request flow, configuration, next steps
- [Deployment](docs/deployment.md) — AWS architecture, one-time setup, CI/CD, operations, costs
- [League model & scheduling](docs/league-model.md) — weeks, rounds, courts, and how the dashboard decides what's playable
- [API reference](docs/api.md) — endpoints and payloads
- [DUPR integration plan](docs/dupr-integration.md) — what's stored today and how the integration will plug in

## Repository layout

```
.
├── docker-compose.yml
├── .github/workflows/      # ci.yml (tests), deploy.yml (AWS)
├── api/                    # FastAPI service
│   ├── app/
│   │   ├── main.py         # app, CORS, routers
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── schemas.py      # Pydantic request/response models
│   │   ├── scheduling.py   # round-robin generator
│   │   └── routers/        # leagues, teams/players, matches
│   ├── tests/
│   └── Dockerfile
├── web/                    # Next.js app
│   ├── src/app/            # pages (static export)
│   ├── src/components/     # dashboard, forms, nav
│   ├── src/lib/            # typed API client, types, hooks
│   ├── nginx.conf.template # local serving + /api proxy
│   └── Dockerfile
├── infra/
│   ├── bootstrap/          # one-time: state bucket, ECR, GitHub deploy role
│   └── app/                # RDS, ECS/ALB, S3/CloudFront in an existing VPC (+ offline tests)
└── docs/
```
