from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from .. import schemas
from ..auth import Manager, managed, require_manager
from ..deps import DB
from ..models import LeagueStatus, Match, MatchStatus
from ..scoring import check_score
from ..terms import Term, term

router = APIRouter(prefix="/matches", tags=["matches"], dependencies=[Depends(require_manager)])


def require_playable(match: Match) -> Match:
    """The match, if its league is active (no play while a league is in setup)."""
    if match.league.status != LeagueStatus.ACTIVE:
        raise HTTPException(409, f"{Term('league')} is in setup; create the {term('league')} to resume play")
    return match


@router.get("/{match_id}", response_model=schemas.MatchRead)
def get_match(match_id: int, user: Manager, db: DB):
    return managed(db, user, Match, match_id)


@router.post("/{match_id}/start", response_model=schemas.MatchRead)
def start_match(match_id: int, payload: schemas.MatchStart, user: Manager, db: DB):
    """Put a scheduled match on court. Both teams and the court must be free."""
    match = require_playable(managed(db, user, Match, match_id))
    if match.status != MatchStatus.SCHEDULED:
        raise HTTPException(409, f"{Term('match')} is already {match.status.value.replace('_', ' ')}")

    in_progress = db.scalars(
        select(Match).where(
            Match.league_id == match.league_id,
            Match.status == MatchStatus.IN_PROGRESS,
        )
    ).all()
    busy_teams = {t for m in in_progress for t in (m.team_a_id, m.team_b_id)}
    if {match.team_a_id, match.team_b_id} & busy_teams:
        raise HTTPException(409, f"One of the {term('team', 2)} is already playing")

    busy_courts = {m.court for m in in_progress}
    free_courts = [c for c in range(1, match.league.num_courts + 1) if c not in busy_courts]
    court = payload.court or (free_courts[0] if free_courts else None)
    if court is None:
        raise HTTPException(409, f"No free {term('court', 2)}")
    if court not in free_courts:
        raise HTTPException(409, f"{Term('court')} {court} is not available")

    match.status = MatchStatus.IN_PROGRESS
    match.court = court
    match.started_at = datetime.now(UTC)
    db.commit()
    return match


@router.post("/{match_id}/cancel", response_model=schemas.MatchRead)
def cancel_match(match_id: int, user: Manager, db: DB):
    """Take an in-progress match off court and return it to the schedule."""
    match = require_playable(managed(db, user, Match, match_id))
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(409, f"Only in-progress {term('match', 2)} can be returned to the schedule")
    match.status = MatchStatus.SCHEDULED
    match.court = None
    match.started_at = None
    db.commit()
    return match


@router.put("/{match_id}/result", response_model=schemas.MatchRead)
def record_result(match_id: int, payload: schemas.MatchResult, user: Manager, db: DB):
    """Record (or correct) a final score. Frees the court if the match was on one.

    Scores must follow the league's rules (first to points_to_win, win by 2);
    an invalid score is a 422 naming the score field(s) at fault. Verified
    results are locked (409).
    """
    return apply_result(require_playable(managed(db, user, Match, match_id)), payload, db)


def apply_result(match: Match, payload: schemas.MatchResult, db) -> Match:
    """Record a score on a playable match (shared with routers/scoring.py)."""
    if match.verified_at is not None:
        raise HTTPException(409, "This result has been verified and can't be changed")

    problem = check_score(payload.score_a, payload.score_b, match.league.points_to_win)
    if problem:
        # Same shape as FastAPI's own validation errors, so clients can
        # highlight the offending field(s) from `loc`.
        raise HTTPException(
            422,
            [
                {"loc": ["body", field], "msg": problem.message, "type": "score_rules"}
                for field in problem.fields
            ],
        )

    match.score_a = payload.score_a
    match.score_b = payload.score_b
    match.status = MatchStatus.COMPLETED
    match.completed_at = datetime.now(UTC)
    db.commit()
    return match


@router.post("/{match_id}/verify", response_model=schemas.MatchRead)
def verify_result(match_id: int, user: Manager, db: DB):
    """Verify a completed match's result. The score is then locked for good."""
    match = require_playable(managed(db, user, Match, match_id))
    if match.status != MatchStatus.COMPLETED:
        raise HTTPException(409, f"Only completed {term('match', 2)} can be verified")
    if match.verified_at is None:
        match.verified_at = datetime.now(UTC)
        db.commit()
    return match
