# DUPR integration plan

[DUPR](https://www.dupr.com) (Dynamic Universal Pickleball Rating) is the
rating system most leagues and clubs use. This skeleton stores what an
integration will need, but does not call DUPR yet.

## What exists today

- `Player.dupr_id` — optional, entered on the Teams & players screen.
  Validated loosely (4–12 alphanumeric characters, upper-cased) in
  `api/app/schemas.py` (`DUPR_ID_PATTERN`) and mirrored in the web form. Tighten
  once the exact format is confirmed against the API.
- `Player.dupr_rating` — nullable float, shown in the players table as "—".
  Read-only in the API; intended to be written only by the integration.
- `dupr_id` is indexed, for lookups when syncing.

## Planned integration

DUPR offers API access to approved partners (clubs, leagues, tournament
software); credentials and exact endpoints come with that approval, so the
details below are intentionally generic.

1. **Client module** — `api/app/integrations/dupr.py` wrapping authentication and
   the handful of calls needed. Credentials via environment variables
   (`DUPR_CLIENT_ID`, `DUPR_CLIENT_SECRET`, `DUPR_BASE_URL`), never committed.
2. **Verify players** — when a DUPR ID is entered, look it up and confirm the
   name matches; flag mismatches in the UI instead of rejecting outright.
3. **Sync ratings** — `POST /leagues/{id}/dupr/sync` (and/or a scheduled job)
   refreshes `dupr_rating` (and a `dupr_synced_at` timestamp to add) for every
   player with a DUPR ID. Useful for seeding teams or balancing divisions.
4. **Submit results** — DUPR rates *players*, not teams, and needs the
   individual game scores. That requires model changes first:
   - record which two players from each team played a match (a
     `MatchPlayer` join table);
   - record per-game scores (a `Game` table: match, game number, score A/B)
     instead of only the match total;
   - track submission state per match (`dupr_match_id`, `dupr_submitted_at`,
     submission error) so failures can be retried.
5. **Consent** — players should agree to their results being submitted; add a
   per-player flag before enabling submission.

## Open questions

- Singles vs. doubles leagues (the model currently assumes team play).
- Whether ratings should be shown publicly on the dashboard or only to organisers.
- Handling players without a DUPR ID (skip their matches, or submit what's possible).
