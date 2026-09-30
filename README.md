# Pickleball League

A skeleton for running a pickleball league: create a league, enter teams and
players (with DUPR IDs), generate a round-robin schedule, run matches across a
limited number of courts, and record results.

| Part | Stack | Folder |
| --- | --- | --- |
| Web interface | Next.js (App Router, TypeScript) | [`web/`](web/) |
| API | Python · FastAPI · SQLAlchemy · SQLite | [`api/`](api/) |

## Quick start (Docker)

```bash
docker compose up --build
```

- Web UI: http://localhost:3000
- API + interactive docs (Swagger): http://localhost:8000/docs

League data is stored in SQLite on the `api-data` Docker volume.
`docker compose down -v` wipes it.

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
npm run dev                             # http://localhost:3000
```

## Screens

| Screen | Route | What it does |
| --- | --- | --- |
| **Live dashboard** (default) | `/` and `/leagues/[id]` | Teams on court right now, and this week's match-ups that can start because neither team is playing. Start a match on a free court, enter its score, or return it to the schedule. |
| League creation | `/leagues/new` | Name, number of teams, weeks, rounds per week and courts. Creates placeholder teams and the full season schedule. |
| Teams & players | `/leagues/[id]/teams` | Rename teams; add players with optional email and **DUPR ID**. |
| Schedule & results | `/leagues/[id]/matches` | Week-by-week schedule grouped by round, score entry/correction, standings. |
| Leagues | `/leagues` | All leagues. |

## Documentation

- [Architecture](docs/architecture.md) — components, request flow, configuration, next steps
- [League model & scheduling](docs/league-model.md) — weeks, rounds, courts, and how the dashboard decides what's playable
- [API reference](docs/api.md) — endpoints and payloads
- [DUPR integration plan](docs/dupr-integration.md) — what's stored today and how the integration will plug in

## Repository layout

```
.
├── docker-compose.yml
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
│   ├── src/app/            # routes (pages + /api proxy)
│   ├── src/components/     # dashboard, forms, nav
│   ├── src/lib/            # typed API client, types, hooks
│   └── Dockerfile
└── docs/
```
