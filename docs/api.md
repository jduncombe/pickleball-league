# API reference

Base URL: `http://localhost:8000` when running the API directly, or `/api` on
the site's origin (CloudFront in AWS, nginx in docker-compose, the dev server
under `npm run dev`), which strips the prefix before forwarding.
Full interactive documentation, generated from the code, is served at
[`/docs`](http://localhost:8000/docs) — treat that as the source of truth.

Errors use FastAPI's format: `{"detail": "message"}` for 404/409, and
`{"detail": [{"loc": [...], "msg": "..."}]}` for 422 validation errors.

## Leagues

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/leagues` | List leagues, newest first |
| `GET` | `/leagues/{id}` | Get a league |
| `PATCH` | `/leagues/{id}` | Set `current_week` |
| `DELETE` | `/leagues/{id}` | Delete a league and everything in it |
| `GET` | `/leagues/{id}/teams` | Teams with their players, in position order |
| `GET` | `/leagues/{id}/matches?week=&status=` | Matches, optionally filtered |
| `GET` | `/leagues/{id}/dashboard?week=` | Live view (defaults to `current_week`) |
| `GET` | `/leagues/{id}/standings` | Standings table |

League objects include `status` (`"setup"` or `"active"`), `use_team_names`,
`created_league_at` (when setup was first finalised, else `null`) and
`has_played_matches`.

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

## League setup

A league is created **in setup**. Basics, teams and players can only be
changed while it is in setup; "create the league" makes it **active**
(schedule built, play allowed, teams and players fixed). "Edit setup" puts it
back into setup, pausing play until it is finalised again. See
[league-model.md](league-model.md#setup) for the rules.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/leagues` | Step 1 for a new league: basics. Creates the league in setup with `num_teams` empty teams. |
| `PUT` | `/leagues/{id}/setup` | Step 1 again: replace the basics. Adds or removes teams at the end to match `num_teams`. 409 if not in setup, or if changing `num_teams`/`num_weeks`/`rounds_per_week` after matches have been played. |
| `PUT` | `/leagues/{id}/teams` | Step 2: names and players for every team (exactly `num_teams` entries, in order). Replaces players. 409 if not in setup. Drafts may be incomplete. |
| `POST` | `/leagues/{id}/finalize` | **Create the league.** 422 listing problems if a team has no players, or has no name when `use_team_names` is on. Builds the schedule if there isn't one, sets `status: "active"`. |
| `POST` | `/leagues/{id}/edit` | **Edit setup.** Back to `status: "setup"`. 409 while a match is on court. |

Basics (step 1):

```json
{
  "name": "Tuesday Night Doubles",
  "num_teams": 8,
  "num_weeks": 8,
  "rounds_per_week": 3,
  "num_courts": 4,
  "points_to_win": 15,
  "use_team_names": false
}
```

Limits: teams 2–64, weeks 1–52, rounds per week 1–20, courts 1–50.
`points_to_win` is 11, 15 or 21 (default 11); like the number of teams, weeks
and rounds, it can't change once a match has been played.

Teams (step 2):

```json
{
  "teams": [
    { "name": "Dink Dynasty",
      "players": [{ "name": "Alex" }, { "name": "Sam", "dupr_id": "4KX92L", "email": "sam@example.com" }] },
    { "name": null, "players": [{ "name": "Jo" }, { "name": "Kim" }] }
  ]
}
```

Player `email` and `dupr_id` are optional; blank strings are stored as
`null`. `dupr_id` must be 4–12 letters/digits and is upper-cased.
`dupr_rating` is read-only and reserved for the DUPR integration. Team names
are stored even when `use_team_names` is off, so switching it off and on
again doesn't lose them.

## Teams

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/teams/{id}` | Team with players |

Teams and players have no write endpoints of their own; they change only
through league setup.

Team objects, and the `team_a`/`team_b`/`team` references in matches and
standings, carry `name` and **`display_name`**. Clients should show
`display_name`:

1. the team name, if the league uses team names and it is set;
2. otherwise the players' names (`"Alex & Sam"`, or `"Ann, Bo & Cy"` for three);
3. otherwise `"Team <position>"`.

Team references also carry **`dupr_ready`**: true when the team has players
and every one of them has a DUPR ID. Full team objects also have `position`
(1-based).

## Matches

Match actions (start, cancel, result) return 409 while the league is in setup.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/matches/{id}` | Get a match |
| `POST` | `/matches/{id}/start` | Put on court: `{"court": 2}` or `{}` for the lowest free court. 409 if a team or the court is busy. |
| `POST` | `/matches/{id}/cancel` | Take an in-progress match off court, back to `scheduled` |
| `PUT` | `/matches/{id}/result` | Record/correct a score: `{"score_a": 11, "score_b": 7}`. Must follow the league's rules (first to `points_to_win`, win by 2). 409 once verified. |
| `POST` | `/matches/{id}/verify` | Verify a completed match's result, locking it. 409 if the match isn't completed. |

An invalid score is a 422 in FastAPI's validation-error shape, with `loc`
naming the score field(s) most likely wrong (see
[league-model.md](league-model.md#results--standings)):

```json
{ "detail": [{ "loc": ["body", "score_b"], "type": "score_rules",
  "msg": "15-14 isn't finished: a game must be won by 2, so play continues (e.g. 16-14)" }] }
```

Match object:

```json
{
  "id": 12, "league_id": 1, "week": 2, "round": 1,
  "status": "in_progress",
  "court": 3,
  "team_a": { "id": 1, "name": "Dink Dynasty", "display_name": "Dink Dynasty" },
  "team_b": { "id": 4, "name": null, "display_name": "Jo & Kim" },
  "score_a": null, "score_b": null,
  "started_at": "2026-09-30T18:05:00Z", "completed_at": null, "verified_at": null
}
```

## Meta

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | `{"status": "ok"}` — used by the Docker healthcheck |
