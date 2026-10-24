from collections import Counter, defaultdict

import pytest

from app.scheduling import build_schedule, summarize


def _by_week(schedule):
    weeks = defaultdict(lambda: defaultdict(list))
    for week, rnd, pairing in schedule:
        weeks[week][rnd].append(pairing)
    return weeks


def test_nine_teams_four_matches_per_week():
    """4 rounds of 4 games (a different team sits out each), then a catch-up
    round of 2 games between the 4 teams that sat out."""
    teams = list(range(1, 10))
    week = _by_week(build_schedule(teams, num_weeks=1, matches_per_week=4))[1]

    assert [len(week[r]) for r in sorted(week)] == [4, 4, 4, 4, 2]
    sat_out = [set(teams) - {t for p in week[r] for t in p} for r in (1, 2, 3, 4)]
    assert all(len(s) == 1 for s in sat_out)
    sitters = set().union(*sat_out)
    assert len(sitters) == 4
    assert {t for p in week[5] for t in p} == sitters

    played = Counter(t for r in week for p in week[r] for t in p)
    assert set(played.values()) == {4}
    assert max(Counter(frozenset(p) for r in week for p in week[r]).values()) == 1


@pytest.mark.parametrize(
    ("n", "weeks", "m"),
    [(4, 3, 3), (6, 8, 2), (8, 10, 3), (9, 8, 4), (10, 6, 5), (11, 10, 4), (12, 8, 6), (13, 12, 4), (15, 6, 7)],
)
def test_every_team_plays_its_matches_each_week_without_repeats(n, weeks, m):
    teams = list(range(1, n + 1))
    schedule = build_schedule(teams, weeks, m)
    for week, rounds in _by_week(schedule).items():
        played = Counter(t for r in rounds.values() for p in r for t in p)
        short = [t for t in teams if played[t] < m]
        assert len(short) == (n * m) % 2, (week, short)  # only when teams x matches is odd
        assert max(played.values()) == m
        for pairings in rounds.values():  # at most once per round
            in_round = [t for p in pairings for t in p]
            assert len(in_round) == len(set(in_round))
        meetings = Counter(frozenset(p) for r in rounds.values() for p in r)
        assert max(meetings.values()) == 1, week


@pytest.mark.parametrize(("n", "weeks", "m"), [(9, 8, 4), (11, 10, 4), (13, 12, 4), (8, 7, 3)])
def test_pairs_meet_equally_when_the_season_allows(n, weeks, m):
    teams = list(range(1, n + 1))
    summary = summarize(build_schedule(teams, weeks, m), teams, weeks, m)
    assert summary.min_meetings == summary.max_meetings


@pytest.mark.parametrize(("n", "weeks", "m"), [(7, 16, 3), (5, 8, 3), (12, 10, 3), (16, 16, 8), (17, 12, 5)])
def test_meetings_and_shortfalls_stay_balanced(n, weeks, m):
    teams = list(range(1, n + 1))
    schedule = build_schedule(teams, weeks, m)
    summary = summarize(schedule, teams, weeks, m)
    assert summary.max_meetings - summary.min_meetings <= 2
    totals = Counter(t for _, _, p in schedule for t in p)
    assert max(totals.values()) - min(totals[t] for t in teams) <= 1  # shortfalls rotate


def test_schedule_is_repeatable():
    teams = list(range(1, 12))
    assert build_schedule(teams, 6, 4) == build_schedule(teams, 6, 4)
