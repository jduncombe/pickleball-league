import pytest

from app.scoring import check_score


@pytest.mark.parametrize(
    ("a", "b", "points"),
    [
        (15, 13, 15),  # won at the target, by 2
        (16, 14, 15),  # went past the target, won by 2
        (13, 15, 15),  # either side can win
        (15, 0, 15),
        (11, 9, 11),
        (12, 10, 11),
        (25, 23, 21),
        (30, 28, 15),  # long deuce games are fine
    ],
)
def test_valid_scores(a, b, points):
    assert check_score(a, b, points) is None


@pytest.mark.parametrize(
    ("a", "b", "points", "fields"),
    [
        (15, 14, 15, ("score_b",)),  # not won by 2: loser's score is wrong
        (14, 15, 15, ("score_a",)),
        (16, 13, 15, ("score_a",)),  # game would have ended at 15-13: winner's score is wrong
        (16, 15, 15, ("score_b",)),  # past the target but only by 1
        (13, 10, 15, ("score_a",)),  # nobody reached 15
        (15, 15, 15, ("score_a", "score_b")),  # tie
        (11, 10, 11, ("score_b",)),
        (18, 14, 15, ("score_a",)),  # past 15 must finish 2 apart
    ],
)
def test_invalid_scores_name_the_likely_wrong_box(a, b, points, fields):
    problem = check_score(a, b, points)
    assert problem is not None
    assert problem.fields == fields


@pytest.mark.parametrize(
    ("a", "b", "example"),
    [(15, 14, "16-14"), (14, 14, "16-14"), (16, 13, "15-13"), (18, 14, "16-14"), (12, 9, "15-9")],
)
def test_messages_suggest_a_valid_score(a, b, example):
    problem = check_score(a, b, 15)
    assert f"(e.g. {example})" in problem.message
    winner, loser = map(int, example.split("-"))
    assert check_score(winner, loser, 15) is None
