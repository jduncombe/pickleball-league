from itertools import combinations

from app.scheduling import build_schedule, round_robin


def test_round_robin_even_covers_every_pairing_once():
    rounds = round_robin([1, 2, 3, 4, 5, 6])
    assert len(rounds) == 5
    pairs = [frozenset(p) for rnd in rounds for p in rnd]
    assert sorted(pairs, key=sorted) == sorted(
        (frozenset(c) for c in combinations(range(1, 7), 2)), key=sorted
    )
    for rnd in rounds:
        teams = [t for p in rnd for t in p]
        assert len(teams) == len(set(teams)) == 6


def test_round_robin_odd_gives_one_bye_per_round():
    rounds = round_robin([1, 2, 3, 4, 5])
    assert len(rounds) == 5
    for rnd in rounds:
        assert len(rnd) == 2


def test_build_schedule_repeats_cycle():
    schedule = build_schedule([1, 2, 3, 4], num_weeks=2, rounds_per_week=2)
    # 4 rounds x 2 matches; cycle length is 3, so round 4 repeats round 1.
    assert len(schedule) == 8
    assert [(w, r) for w, r, _ in schedule[::2]] == [(1, 1), (1, 2), (2, 1), (2, 2)]
    assert schedule[6][2] == schedule[0][2]
