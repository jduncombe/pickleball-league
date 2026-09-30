# API reference

Base URL: `http://localhost:8000` (or `/api` via the web app's proxy).
Full interactive documentation, generated from the code, is served at
[`/docs`](http://localhost:8000/docs) — treat that as the source of truth.

Errors use FastAPI's format: `{"detail": "message"}` for 404/409, and
`{"detail": [{"loc": [...], "msg": "..."}]}` for 422 validation errors.

## Leagues

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/leagues` | List leagues, newest first |
| `POST` | `/leagues` | Create a league + placeholder teams + schedule |
| `GET` | `/leagues/{id}` | Get a league |
| `PATCH` | `/leagues/{id}` | Update `name`, `num_courts`, `current_week` |
| `DELETE` | `/leagues/{id}` | Delete a league and everything in it |
| `POST` | `/leagues/{id}/schedule` | Regenerate the schedule (409 once any match has started) |
| `GET` | `/leagues/{id}/teams` | Teams with their players |
| `GET` | `/leagues/{id}/matches?week=&status=` | Matches, optionally filtered |
| `GET` | `/leagues/{id}/dashboard?week=` | Live view (defaults to `current_week`) |
| `GET` | `/leagues/{id}/standings` | Standings table |

Create a league:

```http
POST /leagues
{
  "name": "Tuesday Night Doubles",
  "num_teams": 8,          // 2–64
  "num_weeks": 8,          // 1–52
  "rounds_per_week": 3,    // 1–20
  "num_courts": 4          // 1–50
}
```

Dashboard response:

```jsonc
{
  "league": { ...League },
  "week": 1,
  "free_courts": [3, 4],
  "in_progress": [ ...Match ],   // on court now (any week)
  "available":   [ ...Match ],   // this week, both teams idle
  "waiting":     [ ...Match ],   // this week, a team is on court
  "completed_count": 2,
  "total_count": 12
}
```

## Teams & players

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/teams/{id}` | Team with players |
| `PATCH` | `/teams/{id}` | Rename: `{"name": "Dink Dynasty"}` |
| `POST` | `/teams/{id}/players` | Add a player |
| `PATCH` | `/players/{id}` | Update a player |
| `DELETE` | `/players/{id}` | Remove a player |

Player payload:

```json
{ "name": "Sam Rivera", "email": "sam@example.com", "dupr_id": "4KX92L" }
```

`email` and `dupr_id` are optional; blank strings are stored as `null`.
`dupr_id` must be 4–12 letters/digits and is upper-cased. `dupr_rating` is
read-only and reserved for the DUPR integration.

## Matches

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/matches/{id}` | Get a match |
| `POST` | `/matches/{id}/start` | Put on court: `{"court": 2}` or `{}` for the lowest free court. 409 if a team or the court is busy. |
| `POST` | `/matches/{id}/cancel` | Take an in-progress match off court, back to `scheduled` |
| `PUT` | `/matches/{id}/result` | Record/correct a score: `{"score_a": 11, "score_b": 7}`. Ties rejected. |

Match object:

```json
{
  "id": 12, "league_id": 1, "week": 2, "round": 1,
  "status": "in_progress",
  "court": 3,
  "team_a": { "id": 1, "name": "Dink Dynasty" },
  "team_b": { "id": 4, "name": "Kitchen Crew" },
  "score_a": null, "score_b": null,
  "started_at": "2026-09-30T18:05:00Z", "completed_at": null
}
```

## Meta

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | `{"status": "ok"}` — used by the Docker healthcheck |
