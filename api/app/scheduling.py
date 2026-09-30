"""Round-robin schedule generation.

The league calendar is ``num_weeks`` weeks x ``rounds_per_week`` rounds. Each
round every team plays at most one match (one team sits out when the team
count is odd). Rounds are taken from a round-robin cycle generated with the
circle method, so every pairing is played once before any pairing repeats.

Courts are *not* assigned here: they are a live constraint resolved when a
match is started (see ``routers/matches.py``), so a round with more matches
than courts simply plays in waves.
"""

from collections.abc import Sequence

Pairing = tuple[int, int]


def round_robin(team_ids: Sequence[int]) -> list[list[Pairing]]:
    """Return one full round-robin cycle as a list of rounds of pairings."""
    teams: list[int | None] = list(team_ids)
    if len(teams) < 2:
        return []
    if len(teams) % 2:
        teams.append(None)  # bye

    n = len(teams)
    rounds: list[list[Pairing]] = []
    for r in range(n - 1):
        pairings: list[Pairing] = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a is None or b is None:
                continue
            # Alternate the listed order so neither side is always "team A".
            pairings.append((a, b) if r % 2 == 0 else (b, a))
        rounds.append(pairings)
        # Keep the first team fixed and rotate the rest one step clockwise.
        teams = [teams[0], teams[-1], *teams[1:-1]]
    return rounds


def build_schedule(
    team_ids: Sequence[int], num_weeks: int, rounds_per_week: int
) -> list[tuple[int, int, Pairing]]:
    """Return ``(week, round, pairing)`` tuples covering the whole season.

    Weeks and rounds are 1-indexed. The round-robin cycle repeats if the season
    has more rounds than the cycle.
    """
    cycle = round_robin(team_ids)
    if not cycle:
        return []

    schedule: list[tuple[int, int, Pairing]] = []
    slot = 0
    for week in range(1, num_weeks + 1):
        for rnd in range(1, rounds_per_week + 1):
            for pairing in cycle[slot % len(cycle)]:
                schedule.append((week, rnd, pairing))
            slot += 1
    return schedule
