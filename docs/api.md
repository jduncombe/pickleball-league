# API reference

Base URL: `http://localhost:8000` when running the API directly, or `/api` on
the site's origin (CloudFront in AWS, nginx in docker-compose, the dev server
under `npm run dev`), which strips the prefix before forwarding.
Full interactive documentation, generated from the code, is served at
[`/docs`](http://localhost:8000/docs) — treat that as the source of truth.

Errors use FastAPI's format: `{"detail": "message"}` for 404/409, and
`{"detail": [{"loc": [...], "msg": "..."}]}` for 422 validation errors.

## Authentication

Everything except `/health` and `/auth/login`, `/auth/mfa/*` needs a signed-in
account: see [auth.md](auth.md) for roles, the sign-in flow and how
credentials are protected. In short:

- The web app's session is an HttpOnly cookie; requests that change data must
  also send `X-Requested-With: fetch`.
- Other clients (the scoring app, scripts) sign in with `"client": "app"` and
  send `Authorization: Bearer <token>`. In [`/docs`](http://localhost:8000/docs),
  use **Authorize** with such a token.
- **401**: not signed in, or the session expired or was revoked.
- **404**: doesn't exist, **or** your role or ownership doesn't let you see it
  (users see only their own leagues; umpires only `/scoring/*`).

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/auth/login` | `{"email", "password", "client": "web" \| "app"}` → `{"mfa_token", "mfa_setup_required"}`. 401 for a wrong email or password (same message for both), 429 when locked out or rate-limited. |
| `POST` | `/auth/mfa/setup` | `{"mfa_token"}` → `{"secret", "otpauth_uri", "qr_data_uri"}` (`qr_data_uri`: the QR code as an SVG `data:` URI), for accounts without an authenticator yet. 409 once one is set up. |
| `POST` | `/auth/mfa/verify` | `{"mfa_token", "code", "client"}` → `{"user", "expires_at", "access_token"}`. Starts the session: a cookie for `web` (and `access_token` is null), a bearer token for `app`. |
| `GET` | `/auth/me` | The signed-in account |
| `POST` | `/auth/logout` | Revoke the current token (and clear the cookie). 204. |
| `POST` | `/auth/password` | `{"current_password", "new_password", "code"}`. Signs you out everywhere. 204. |

### Accounts (admins only)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/users` | All accounts, by email |
| `POST` | `/users` | `{"email", "name", "role": "admin" \| "user" \| "umpire", "password"}`. 409 if the email is taken. |
| `PATCH` | `/users/{id}` | Any of `name`, `role`, `is_active`, `password`. Anything but the name signs them out everywhere. You can't change your own role or deactivate yourself (409). |
| `POST` | `/users/{id}/reset-mfa` | Remove their authenticator; they set up a new one at their next sign-in. |

Account object (passwords and TOTP secrets are never returned):

```json
{ "id": 3, "email": "sam@example.com", "name": "Sam", "role": "user",
  "is_active": true, "mfa_enabled": true,
  "created_at": "2026-11-08T09:00:00Z", "last_login_at": "2026-11-08T18:02:11Z" }
```

## Leagues

League, setup, team and match endpoints are for admins and users (league
organisers), not umpires. Users see and change only their own leagues; a
league belongs to whoever creates it (`POST /leagues`).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/leagues` | List leagues, newest first: all of them for admins, your own for users |
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
| `PUT` | `/leagues/{id}/setup` | Step 1 again: replace the basics. Adds or removes teams at the end to match `num_teams`. 409 if not in setup, or if changing `num_teams`/`num_weeks`/`matches_per_week`/`points_to_win` after matches have been played. |
| `PUT` | `/leagues/{id}/teams` | Step 2: names and players for every team (exactly `num_teams` entries, in order). Replaces players. 409 if not in setup. Drafts may be incomplete. |
| `POST` | `/leagues/{id}/finalize` | **Create the league.** 422 listing problems if a team has no players, or has no name when `use_team_names` is on. Builds the schedule if there isn't one, sets `status: "active"`. |
| `POST` | `/leagues/{id}/edit` | **Edit setup.** Back to `status: "setup"`. 409 while a match is on court. |
| `GET` | `/schedule-preview?num_teams=&num_weeks=&matches_per_week=` | What a schedule with these basics would look like, for the setup summary (no league needed). |

Preview response, for 9 teams, 8 weeks, 4 matches per week:

```json
{ "rounds_per_week": 5, "games_per_week": 18, "has_catch_up_round": true,
  "teams_short_per_week": 0, "min_meetings": 4, "max_meetings": 4 }
```

Basics (step 1):

```json
{
  "name": "Tuesday Night Doubles",
  "num_teams": 8,
  "num_weeks": 8,
  "matches_per_week": 3,
  "num_courts": 4,
  "points_to_win": 15,
  "use_team_names": false
}
```

Limits: teams 2–64, weeks 1–52, courts 1–50. `matches_per_week` (matches
each team plays per week) is 1–20 and at most `num_teams - 1`; rounds per week
follow from it (see [league-model.md](league-model.md#schedule-generation)).
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

## Scoring app

Endpoints for a scoring app, such as a tablet at the courts. The app signs
in as an **umpire** (or an organiser or admin) with `"client": "app"` and sends
`Authorization: Bearer <token>` (see [auth.md](auth.md#signing-in)). Umpires
can use only these endpoints, for any active league; organisers use them for
their own leagues, admins for any.

A scoring app at a court typically:

1. lists the leagues being played and the user picks one;
2. lists that league's **free** courts and claims one, so no other app can;
3. polls the court for its match (the organiser starts matches on courts
   from the live view) and sends the score when the game ends;
4. releases the court when it's done (e.g. at the end of the night).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/scoring/leagues` | Leagues being played (`status: "active"`), newest first: `id`, `name`, `num_courts`, `current_week`, `points_to_win` |
| `GET` | `/scoring/leagues/{id}/courts` | The league's courts that **no app has claimed**: `[{"court": 1, "in_use": false}, …]`. `in_use` means a match is on it now. 409 while the league is in setup. |
| `POST` | `/scoring/leagues/{id}/courts/{court}/claim` | Claim a court. Optional body `{"device_name": "Court 3 tablet"}` (up to 80 characters), shown to anyone else who tries it. **201** with the claim; **409** if it's already claimed (the message names the device); 404 for a court outside `1…num_courts`; 409 while the league is in setup. |
| `DELETE` | `/scoring/leagues/{id}/courts/{court}/claim` | Release a court, so it's offered again. 204, also if it wasn't claimed. Umpires can release only their own claims (409 otherwise); the organiser and admins any. |
| `GET` | `/scoring/leagues/{id}/courts/{court}/match` | The match on the court now, with the scoring rules and the claim (see below). `match` is `null` when nothing is being played. 404 for an unknown court. |
| `GET` | `/scoring/leagues/{id}/matches?week=&status=` | A week's matches (default: the league's `current_week`), in round order, with the scoring rules |
| `PUT` | `/scoring/matches/{id}/result` | Record a score: `{"score_a": 11, "score_b": 7}`. Same rules and errors as `PUT /matches/{id}/result` (422 for an invalid score, 409 once verified or while the league is in setup). Umpires can score only the in-progress match on a court they've claimed (409 otherwise). Returns the match object, and frees the court for its next match. |

Court claims stop two scoring apps using the same court, and decide which
umpire can score a court's match; they don't affect which matches can start
where. The organiser (or an admin) frees a court held by a lost or crashed
device by releasing its claim. Claims are kept when the league goes back into
setup; a claim on a court the league no longer has (after reducing
`num_courts`) is ignored.

A court and its match:

```json
{
  "league_id": 1, "league_name": "Autumn", "court": 2, "points_to_win": 11,
  "claim": { "league_id": 1, "court": 2, "device_name": "Court 2 tablet",
             "claimed_by": { "id": 7, "name": "Jo (umpire)" },
             "claimed_at": "2026-11-10T18:01:00Z" },
  "match": { /* match object, as above, or null */ }
}
```

A week's matches:

```json
{
  "league_id": 1, "league_name": "Autumn", "points_to_win": 11, "week": 2,
  "matches": [ /* match objects, as above */ ]
}
```

```bash
# TOKEN: from POST /auth/mfa/verify with "client": "app" (see auth.md)
curl -H "Authorization: Bearer $TOKEN" localhost:8000/scoring/leagues
curl -H "Authorization: Bearer $TOKEN" localhost:8000/scoring/leagues/1/courts
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"device_name": "Court 2 tablet"}' localhost:8000/scoring/leagues/1/courts/2/claim
curl -H "Authorization: Bearer $TOKEN" localhost:8000/scoring/leagues/1/courts/2/match
curl -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"score_a": 11, "score_b": 7}' localhost:8000/scoring/matches/12/result
```

## Meta

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | `{"status": "ok"}` — used by the Docker healthcheck |
