"""Pickleball game-score rules: first to N points, win by 2.

A game to N ends as soon as one side has at least N points and leads by 2.
So a valid final score is either N to at most N-2 (e.g. 15-13 or 15-0), or,
if the game went past N, a two-point win (e.g. 16-14, 21-19).

Mirrored for instant feedback in web/src/lib/scoring.ts; keep them in sync.
"""

from dataclasses import dataclass

from .terms import a, term


@dataclass(frozen=True)
class ScoreProblem:
    message: str
    # Which score(s) are most likely wrong: subset of {"score_a", "score_b"}.
    fields: tuple[str, ...]


def _example_win(n: int, loser: int) -> str:
    """A valid final score in which the losing side has `loser` points."""
    return f"{n}-{loser}" if loser <= n - 2 else f"{loser + 2}-{loser}"


def check_score(score_a: int, score_b: int, points_to_win: int) -> ScoreProblem | None:
    """Return why a final score is impossible, or None if it is valid."""
    n = points_to_win
    high, low = max(score_a, score_b), min(score_a, score_b)
    entered = f"{score_a}-{score_b}"

    if score_a == score_b:
        return ScoreProblem(
            f"{entered} is a tie: there are no ties, play continues until one side leads by 2 "
            f"(e.g. {_example_win(n, low)})",
            ("score_a", "score_b"),
        )

    winner, loser = ("score_a", "score_b") if score_a > score_b else ("score_b", "score_a")

    if high < n:
        return ScoreProblem(
            f"{entered} isn't finished: the winner needs at least {n} points (e.g. {_example_win(n, low)})",
            (winner,),
        )
    if high - low < 2:
        return ScoreProblem(
            f"{entered} isn't finished: {a('game')} must be won by 2, so play continues "
            f"(e.g. {_example_win(n, low)})",
            (loser,),
        )
    if high > n and high - low > 2:
        return ScoreProblem(
            f"{entered} isn't possible: the {term('game')} ends as soon as one side has {n}+ points and "
            f"leads by 2 (e.g. {_example_win(n, low)})",
            (winner,),
        )
    return None
