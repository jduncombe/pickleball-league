"""Endpoints for a scoring app (e.g. a tablet at the courts).

Every route needs ``Authorization: Bearer <SCORING_API_TOKEN>``; see app/auth.py.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from .. import schemas
from ..auth import require_scoring_token
from ..deps import DB, get_or_404
from ..models import League, Match, MatchStatus
from . import matches

router = APIRouter(
    prefix="/scoring",
    tags=["scoring"],
    dependencies=[Depends(require_scoring_token)],
    responses={401: {"description": "Missing or invalid scoring token"}},
)


@router.get("/leagues/{league_id}/matches", response_model=schemas.ScoringMatches)
def list_matches(
    league_id: int,
    db: DB,
    week: int | None = Query(default=None, ge=1),
    status: MatchStatus | None = None,
):
    """A week's matches (default: the league's current week), with the scoring rules."""
    league = get_or_404(db, League, league_id)
    week = week or league.current_week
    query = select(Match).where(Match.league_id == league_id, Match.week == week)
    if status is not None:
        query = query.where(Match.status == status)
    return schemas.ScoringMatches(
        league_id=league.id,
        league_name=league.name,
        points_to_win=league.points_to_win,
        week=week,
        matches=db.scalars(query.order_by(Match.round, Match.id)).all(),
    )


@router.put("/matches/{match_id}/result", response_model=schemas.MatchRead)
def record_result(match_id: int, payload: schemas.MatchResult, db: DB):
    """Record a final score, with the same rules and errors as ``PUT /matches/{id}/result``."""
    return matches.record_result(match_id, payload, db)
