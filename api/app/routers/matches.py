from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from .. import schemas
from ..deps import DB, get_or_404
from ..models import Match, MatchStatus

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/{match_id}", response_model=schemas.MatchRead)
def get_match(match_id: int, db: DB):
    return get_or_404(db, Match, match_id)


@router.post("/{match_id}/start", response_model=schemas.MatchRead)
def start_match(match_id: int, payload: schemas.MatchStart, db: DB):
    """Put a scheduled match on court. Both teams and the court must be free."""
    match = get_or_404(db, Match, match_id)
    if match.status != MatchStatus.SCHEDULED:
        raise HTTPException(409, f"Match is already {match.status.value}")

    in_progress = db.scalars(
        select(Match).where(
            Match.league_id == match.league_id,
            Match.status == MatchStatus.IN_PROGRESS,
        )
    ).all()
    busy_teams = {t for m in in_progress for t in (m.team_a_id, m.team_b_id)}
    if {match.team_a_id, match.team_b_id} & busy_teams:
        raise HTTPException(409, "One of the teams is already playing")

    busy_courts = {m.court for m in in_progress}
    free_courts = [c for c in range(1, match.league.num_courts + 1) if c not in busy_courts]
    court = payload.court or (free_courts[0] if free_courts else None)
    if court is None:
        raise HTTPException(409, "No free courts")
    if court not in free_courts:
        raise HTTPException(409, f"Court {court} is not available")

    match.status = MatchStatus.IN_PROGRESS
    match.court = court
    match.started_at = datetime.now(timezone.utc)
    db.commit()
    return match


@router.post("/{match_id}/cancel", response_model=schemas.MatchRead)
def cancel_match(match_id: int, db: DB):
    """Take an in-progress match off court and return it to the schedule."""
    match = get_or_404(db, Match, match_id)
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(409, "Only in-progress matches can be cancelled")
    match.status = MatchStatus.SCHEDULED
    match.court = None
    match.started_at = None
    db.commit()
    return match


@router.put("/{match_id}/result", response_model=schemas.MatchRead)
def record_result(match_id: int, payload: schemas.MatchResult, db: DB):
    """Record (or correct) a final score. Frees the court if the match was on one."""
    match = get_or_404(db, Match, match_id)
    match.score_a = payload.score_a
    match.score_b = payload.score_b
    match.status = MatchStatus.COMPLETED
    match.completed_at = datetime.now(timezone.utc)
    db.commit()
    return match
