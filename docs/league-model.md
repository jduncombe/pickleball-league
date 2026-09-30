# League model & scheduling

## Concepts

| Concept | Meaning |
| --- | --- |
| **League** | A season with a fixed set of teams. Configured with number of teams, weeks, rounds per week, and courts. |
| **Week** | One league session (e.g. "Tuesday night"). The league tracks a `current_week`, which the dashboard shows by default. |
| **Round** | A slot within a week in which every team plays **at most one** match. With an odd number of teams, one team sits out (a bye) each round. |
| **Court** | A physical court. Courts limit how many matches run *simultaneously*; they don't change the schedule. |
| **Match** | Team A vs Team B in a given week and round. Status: `scheduled` → `in_progress` (on a court) → `completed` (score recorded). |

Creating a league creates `num_teams` placeholder teams ("Team 1", "Team 2", …)
to be renamed on the Teams screen, and generates the full season schedule
immediately.

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

The schedule can be regenerated (`POST /leagues/{id}/schedule`) until the first
match starts.

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
other moves to "waiting". Organisers generally start the earliest round first.

Matches from a week other than the selected week can still be on court (e.g.
make-up games); they appear under "On court" and block their teams.

## Results & standings

- A result can be entered for a match in any status: from the court card when
  it finishes, or later from the Schedule & results screen (e.g. paper score
  sheets). Entering a result frees the court.
- Ties are rejected (pickleball games are played to a win).
- Standings order: wins, then point differential, then points scored.
