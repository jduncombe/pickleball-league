# League model & scheduling

## Concepts

| Concept | Meaning |
| --- | --- |
| **League** | A season with a fixed set of teams. Configured with number of teams, weeks, rounds per week, and courts. |
| **Week** | One league session (e.g. "Tuesday night"). The league tracks a `current_week`, which the dashboard shows by default. |
| **Round** | A slot within a week in which every team plays **at most one** match. With an odd number of teams, one team sits out (a bye) each round. |
| **Court** | A physical court. Courts limit how many matches run *simultaneously*; they don't change the schedule. |
| **Match** | Team A vs Team B in a given week and round. Status: `scheduled` → `in_progress` (on a court) → `completed` (score recorded). |

## Setup

A league moves between two phases:

```
 New league ──▶ SETUP ──"Create the league"──▶ ACTIVE
                  ▲                               │
                  └────────── "Edit setup" ◀──────┘
```

**Setup** is two steps:

1. **League basics:** name, number of teams, weeks, rounds per week, courts,
   and whether the league **uses team names**.
2. **Teams & players:** each team's players (name, optional DUPR ID and
   email), plus a name for each team if the league uses team names. Drafts
   can be saved incomplete and resumed later.

**Create the league** checks the setup is complete: every team needs at least
one player, and a name if team names are on. It then builds the schedule and
makes the league **active**. While active, teams and players are **fixed**
(the Teams page is read-only). Player substitutes are planned for later.

**Edit setup** puts an active league back into setup. Play is paused until
it is finalised again ("Save & resume league"), and it can't be entered while
a match is on court.

- **Before any match has been played,** everything can change. Changing the
  number of teams, weeks or rounds per week discards the schedule, which is
  rebuilt when the league is created again.
- **Once a match has been played,** those three are locked, because changing
  them would invalidate results. The league name, courts, team names, players
  and DUPR IDs can still change, and the schedule and results are kept.

### Team names

Every screen shows a team by its display name:

1. its team name, if the league **uses team names** (the setting from step 1);
2. otherwise its players' names: "Alex & Sam", or "Ann, Bo & Cy" for three;
3. otherwise "Team N", where N is its position.

Team names are kept even while the setting is off, so switching it back on
restores them.

## Schedule generation

`api/app/scheduling.py` uses the **circle method** round robin:

1. One cycle has `n − 1` rounds for `n` teams (`n` rounds if `n` is odd, using a
   bye). Every pair of teams meets exactly once per cycle, and each team plays
   at most once per round.
2. The season has `num_weeks × rounds_per_week` round slots. Slots are filled
   from the cycle in order; if the season is longer than one cycle, the cycle
   repeats (so teams meet more than once).
3. Team A/B order alternates each round, so no team is always listed first.

Example: 8 teams, 3 rounds/week, 8 weeks → 24 slots, cycle of 7 rounds, 4
matches per round, 96 matches total; each pairing is played 3–4 times.

With an odd number of teams, a different team sits out each round. The
Schedule & results screen shows it on the round card ("Bye: …"). Byes aren't
stored; a round's bye is simply whichever team has no match in it.

The schedule is built when the league is created. It is rebuilt only if
setup is edited to change the number of teams, weeks or rounds, which is
possible only before any match has been played (see [Setup](#setup)).

## Courts and the live dashboard

Court assignment happens *live*, not in the schedule. That keeps the schedule
simple and copes with real-world variation (a long match, a late team).

The dashboard (`GET /leagues/{id}/dashboard`) splits the selected week into:

- **On court** — every match currently `in_progress`, with its court.
- **Ready to play** — this week's `scheduled` matches where **neither team is
  currently on court**. Listed in round order, so earlier rounds come first.
- **Waiting** — this week's `scheduled` matches blocked because at least one
  team is on court.

Plus the list of **free courts**. Starting a match (`POST /matches/{id}/start`)
checks that both teams and the chosen court are free; without a court number
the lowest free court is used.

Note that "ready to play" matches can overlap — e.g. *A vs B* (round 2) and
*A vs C* (round 3) can both be listed while A is idle. Once one starts, the
other moves to "waiting".

To keep the week on track, the live view **highlights the ready-to-play
matches from the earliest round** that still has one ("Earliest round"). Those
are the suggested next games.

Teams whose players **all** have DUPR IDs are shown in a different colour on
the live view (court cards, ready to play, waiting), with a legend. A match
between two such teams is one that could be submitted to DUPR. The API
exposes this as `dupr_ready` on each team.

Matches from a week other than the selected week can still be on court (e.g.
make-up games); they appear under "On court" and block their teams.

## Results & standings

- A result can be entered for a match in any status: from the court card when
  it finishes, or later from the Schedule & results screen (e.g. paper score
  sheets). Entering a result frees the court.
- **Scoring rules.** Each league sets **points to win** at setup: 11, 15 or 21
  (default 11). A game is first to that many points and must be **won by 2**;
  there are no ties. If the score reaches one below the target each (14-14
  in a game to 15), play continues until one side leads by 2. So, for games
  to 15:
  - valid: 15-13, 15-0, 16-14, 22-20;
  - invalid: 15-14 (not won by 2, play continues), 16-13 (the game would
    have ended at 15-13), 14-12 (nobody reached 15), and any tie.

  Scores are checked as they're saved, in the browser and again by the API
  (`api/app/scoring.py`, mirrored in `web/src/lib/scoring.ts`). The box that
  is most likely wrong is highlighted, with a message suggesting a valid
  score. Points to win can't change once a match has been played.
- **Verifying results.** On Schedule & results, a completed match has a
  **Verify** button. A verified result is locked: it shows "verified" with a
  lock, and the API refuses any change to it. There is no un-verify.
- Standings order: wins, then point differential, then points scored.
