# Pickleball League Web

Next.js (App Router) interface for the league API. See the
[root README](../README.md) for setup and [docs/architecture.md](../docs/architecture.md)
for how it talks to the API.

```bash
npm install
cp .env.example .env.local   # API_URL=http://localhost:8000
npm run dev                  # http://localhost:3000
npm run lint                 # type check
```

| Path | Purpose |
| --- | --- |
| `src/app/page.tsx` | Default screen: live dashboard for the last-viewed league |
| `src/app/leagues/new/` | League creation |
| `src/app/leagues/[id]/` | Live dashboard for one league |
| `src/app/leagues/[id]/teams/` | Teams & players (DUPR IDs) |
| `src/app/leagues/[id]/matches/` | Schedule, result entry, standings |
| `src/app/api/[...path]/route.ts` | Proxy to the Python API (`API_URL`) |
| `src/lib/api.ts` | Typed API client |
