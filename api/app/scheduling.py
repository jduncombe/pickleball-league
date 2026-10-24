"""Season schedule generation.

Goals, in priority order:

1. Every team plays ``matches_per_week`` matches each week, at most one per
   round. (If teams x matches is odd, one team per week has to be a match
   short; that rotates.)
2. No team plays the same opponent twice in a week.
3. Over the season, every pair of teams meets a similar number of times.

**Even number of teams:** each week is ``matches_per_week`` rounds in which
every team plays, each round pairing the teams that have met least.

**Odd number of teams:** one team sits out each regular round, so a week is
``matches_per_week`` regular rounds, each with a different team sitting out,
plus a **catch-up round** in which those teams play each other. The sitters
and their catch-up pairs are chosen first (fair byes, least-met pairs) and
kept apart in the regular rounds, so nobody meets twice in the week.

Example: 9 teams, 4 matches per week -> 4 rounds of 4 games, then a catch-up
round of 2 games between the 4 teams that sat out: 18 games, everyone plays 4.

Each week is built a few times with different (seeded) tie-breaks and the
most balanced result kept. Courts aren't assigned here; matches are put on
free courts live.
"""

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache

Pairing = tuple[int, int]
CostFn = Callable[[int, int], int]

# Stand-in "opponent" for the team that sits out when the count is odd.
_SIT_OUT = -1
# Up to this many teams in a round, find the cheapest pairing exactly
# (bitmask DP); above it, use a greedy pairing improved by local search.
_EXACT_LIMIT = 12

# A second meeting in the same week outweighs any season imbalance.
_SAME_WEEK_PENALTY = 1_000_000

# Attempts per week (see build_schedule): up to this many while a same-week
# repeat remains, and this many even when the first attempt is clean, to
# improve balance.
_ATTEMPTS_PER_WEEK = 12
_ATTEMPTS_PER_WEEK_IF_CLEAN = 3


def _cheapest_pairing(teams: list[int], cost: CostFn) -> list[Pairing]:
    """Perfect pairing of an even-sized list with (near-)minimum total cost."""
    if len(teams) <= _EXACT_LIMIT:
        n = len(teams)

        @lru_cache(maxsize=None)
        def best(mask: int) -> tuple[int, tuple[Pairing, ...]]:
            if mask == (1 << n) - 1:
                return 0, ()
            i = next(k for k in range(n) if not mask >> k & 1)
            options = []
            for j in range(i + 1, n):
                if mask >> j & 1:
                    continue
                sub_cost, sub = best(mask | 1 << i | 1 << j)
                options.append((sub_cost + cost(teams[i], teams[j]), ((teams[i], teams[j]), *sub)))
            return min(options)

        return list(best(0)[1])

    # Greedy: cheapest pairs first...
    candidates = sorted(
        (cost(a, b), a, b) for i, a in enumerate(teams) for b in teams[i + 1 :]
    )
    used: set[int] = set()
    pairs: list[list[int]] = []
    for _, a, b in candidates:
        if a not in used and b not in used:
            used.update((a, b))
            pairs.append([a, b])
    # ...then swap partners between two pairs while that lowers the cost.
    improved = True
    while improved:
        improved = False
        for x in range(len(pairs)):
            for y in range(x + 1, len(pairs)):
                (a, b), (c, d) = pairs[x], pairs[y]
                current = cost(a, b) + cost(c, d)
                for p, q in (([a, c], [b, d]), ([a, d], [b, c])):
                    if cost(*p) + cost(*q) < current:
                        pairs[x], pairs[y] = p, q
                        improved = True
                        break
    return [tuple(p) for p in pairs]


@dataclass
class _Season:
    """Running totals that later weeks are balanced against."""

    met: Counter[frozenset[int]]  # meetings so far
    sat_out: Counter[int]  # rounds sat out so far
    listed_first: Counter[int]  # times shown as team A
    short: Counter[int]  # weeks finished a match short (odd teams x matches)

    def copy(self) -> "_Season":
        return _Season(*(Counter(c) for c in (self.met, self.sat_out, self.listed_first, self.short)))


def _choose_sitters(teams: list[int], week: int, count: int, season: _Season) -> list[int]:
    """Pick `count` teams to sit out one regular round each this week.

    - Byes stay fair: teams with the fewest sit-outs so far go first.
    - With an odd `count`, one sitter gets no catch-up game and ends the week a
      match short, so the team with the fewest short weeks is included.
    - Sitters play each other in the catch-up round, so the remaining places
      go to least-met pairs.
    """
    position = {t: i for i, t in enumerate(sorted(teams))}
    order = sorted(teams, key=lambda t: (season.sat_out[t], (position[t] - week * count) % len(teams)))
    rank = {t: i for i, t in enumerate(order)}

    sitters: list[int] = []
    if count % 2:
        due = min(order, key=lambda t: (season.short[t], rank[t]))
        sitters.append(due)
        order.remove(due)
    paired = len(sitters)  # sitters before this index are settled
    need = count - paired  # even
    if not need:
        return sitters

    cutoff = season.sat_out[order[need - 1]]
    sitters += [t for t in order if season.sat_out[t] < cutoff]  # behind on byes
    pool = [t for t in order if season.sat_out[t] == cutoff]
    while len(sitters) < count:
        if (len(sitters) - paired) % 2:
            # Give the last unpartnered sitter their least-met candidate.
            last = sitters[-1]
            pick = [min(pool, key=lambda t: (season.met[frozenset((t, last))], rank[t]))]
        else:
            # Add the least-met pair of candidates.
            *_, a, b = min(
                (season.met[frozenset((a, b))], rank[a], rank[b], a, b)
                for i, a in enumerate(pool)
                for b in pool[i + 1 :]
            )
            pick = [a, b]
        sitters += pick
        pool = [t for t in pool if t not in pick]
    return sitters


def _build_week(
    teams: list[int], week: int, matches_per_week: int, season: _Season, rng: random.Random | None
) -> tuple[list[list[Pairing]], int]:
    """One week's rounds, updating `season`. Returns (rounds, same-week repeats).

    `rng`, if given, shuffles team order to vary tie-breaks between attempts.
    """
    if rng:
        teams = teams[:]
        rng.shuffle(teams)
    played: Counter[int] = Counter()
    met_this_week: Counter[frozenset[int]] = Counter()
    sat_out_this_week: Counter[int] = Counter()
    rounds: list[list[Pairing]] = []
    repeats = 0

    def pair_cost(a: int, b: int) -> int:
        pair = frozenset((a, b))
        return met_this_week[pair] * _SAME_WEEK_PENALTY + season.met[pair]

    def play(pairings: list[Pairing]) -> None:
        nonlocal repeats
        ordered = []
        for a, b in pairings:
            # Show whichever team has been listed first less often as team A.
            if season.listed_first[b] < season.listed_first[a]:
                a, b = b, a
            season.listed_first[a] += 1
            played[a] += 1
            played[b] += 1
            pair = frozenset((a, b))
            repeats += met_this_week[pair]
            season.met[pair] += 1
            met_this_week[pair] += 1
            ordered.append((a, b))
        rounds.append(ordered)

    def sit(team: int) -> None:
        season.sat_out[team] += 1
        sat_out_this_week[team] += 1

    if len(teams) % 2 and matches_per_week < len(teams):
        # Odd number of teams: one team sits out each regular round. Pick this
        # week's sitters (fewest sit-outs so far, rotating) and pair them for
        # the catch-up round now, so those pairs aren't used earlier in the week.
        sitters = _choose_sitters(teams, week, matches_per_week, season)
        if rng:
            rng.shuffle(sitters)
        pool = sitters + ([_SIT_OUT] if len(sitters) % 2 else [])

        def catch_up_cost(a: int, b: int) -> int:
            if _SIT_OUT in (a, b):
                # Odd number of sitters: one goes without; rotate who.
                return season.short[b if a == _SIT_OUT else a] * _SAME_WEEK_PENALTY
            return season.met[frozenset((a, b))]

        catch_up = [p for p in _cheapest_pairing(pool, catch_up_cost) if _SIT_OUT not in p]
        for a, b in catch_up:  # reserve: keep these pairs apart until then
            met_this_week[frozenset((a, b))] += 1
        for sitter in sitters:
            sit(sitter)
            play(_cheapest_pairing([t for t in teams if t != sitter], pair_cost))
        for a, b in catch_up:
            met_this_week[frozenset((a, b))] -= 1
        if catch_up:
            play(catch_up)

    # Even number of teams (and a safety net for anything still owed): rounds
    # of everyone who still needs a match. If that's an odd number, whoever
    # has sat out least this week, then this season, sits out.
    def cost(a: int, b: int) -> int:
        if _SIT_OUT in (a, b):
            t = b if a == _SIT_OUT else a
            return sat_out_this_week[t] * _SAME_WEEK_PENALTY + season.sat_out[t]
        return pair_cost(a, b)

    while True:
        needing = [t for t in teams if played[t] < matches_per_week]
        if len(needing) < 2:
            break
        if len(needing) % 2:
            needing.append(_SIT_OUT)
        pairing = _cheapest_pairing(needing, cost)
        for a, b in pairing:
            if _SIT_OUT in (a, b):
                sit(b if a == _SIT_OUT else a)
        play([p for p in pairing if _SIT_OUT not in p])

    for t in teams:
        if played[t] < matches_per_week:
            season.short[t] += 1
    return rounds, repeats


def build_schedule(
    team_ids: Sequence[int], num_weeks: int, matches_per_week: int
) -> list[tuple[int, int, Pairing]]:
    """Return ``(week, round, (team_a, team_b))`` for the whole season (1-indexed).

    Each week is built a few times with different tie-breaks (seeded, so the
    result is repeatable) and the best attempt kept: fewest same-week repeat
    meetings, then the most even season-long meeting counts.
    """
    teams = list(team_ids)
    if len(teams) < 2:
        return []

    season = _Season(Counter(), Counter(), Counter(), Counter())
    schedule: list[tuple[int, int, Pairing]] = []
    for week in range(1, num_weeks + 1):
        best = None
        for attempt in range(_ATTEMPTS_PER_WEEK):
            trial = season.copy()
            rng = random.Random(week * 1_000 + attempt) if attempt else None
            rounds, repeats = _build_week(teams, week, matches_per_week, trial, rng)
            # Sum of squared meeting counts is lowest when meetings are spread evenly.
            score = (repeats, sum(c * c for c in trial.met.values()))
            if best is None or score < best[0]:
                best = (score, rounds, trial)
            if repeats == 0 and _ATTEMPTS_PER_WEEK_IF_CLEAN <= attempt + 1:
                break
        _, rounds, season = best
        for rnd, pairings in enumerate(rounds, start=1):
            schedule.extend((week, rnd, p) for p in pairings)
    return schedule


@dataclass(frozen=True)
class ScheduleSummary:
    rounds_per_week: list[int]
    games_per_week: list[int]
    # Team-weeks in which a team played fewer than matches_per_week.
    short_team_weeks: int
    # How often pairs of teams meet over the season: fewest and most.
    min_meetings: int
    max_meetings: int


def summarize(
    schedule: list[tuple[int, int, Pairing]],
    team_ids: Sequence[int],
    num_weeks: int,
    matches_per_week: int,
) -> ScheduleSummary:
    teams = list(team_ids)
    rounds: Counter[int] = Counter()
    games: Counter[int] = Counter()
    played: Counter[tuple[int, int]] = Counter()
    meetings = Counter({frozenset((a, b)): 0 for i, a in enumerate(teams) for b in teams[i + 1 :]})
    for week, rnd, (a, b) in schedule:
        rounds[week] = max(rounds[week], rnd)
        games[week] += 1
        played[week, a] += 1
        played[week, b] += 1
        meetings[frozenset((a, b))] += 1
    weeks = range(1, num_weeks + 1)
    return ScheduleSummary(
        rounds_per_week=[rounds[w] for w in weeks],
        games_per_week=[games[w] for w in weeks],
        short_team_weeks=sum(
            1 for w in weeks for t in teams if played[w, t] < matches_per_week
        ),
        min_meetings=min(meetings.values(), default=0),
        max_meetings=max(meetings.values(), default=0),
    )
