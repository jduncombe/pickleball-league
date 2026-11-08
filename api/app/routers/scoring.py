"""Endpoints for a scoring app (e.g. a tablet at the courts).

Callers sign in with ``client: "app"`` (routers/auth.py) and send the access
token as ``Authorization: Bearer <token>``. Umpires can use only these
endpoints, for any active league; organisers can use them for their own
leagues and admins for any.

A typical app: pick a league (``GET /scoring/leagues``), pick one of its free
courts (``GET .../courts``) and claim it (``POST .../courts/{court}/claim``),
then poll the court's match (``GET .../courts/{court}/match``) and send the
score (``PUT /scoring/matches/{id}/result``). Releasing the claim
(``DELETE .../courts/{court}/claim``) frees the court for another app.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import Scorer, can_manage, can_score, visible_to
from ..deps import DB, get_or_404, not_found_error
from ..models import CourtClaim, League, LeagueStatus, Match, MatchStatus, User, UserRole
from ..terms import Term, term
from . import matches

router = APIRouter(
    prefix="/scoring",
    tags=["scoring"],
    responses={401: {"description": "Not signed in, or the session has expired"}},
)


def _get_league(db: Session, user: User, league_id: int) -> League:
    league = get_or_404(db, League, league_id)
    if not can_score(user, league):
        raise not_found_error(League, league_id)
    return league


def _get_active_league(db: Session, user: User, league_id: int) -> League:
    league = _get_league(db, user, league_id)
    if league.status != LeagueStatus.ACTIVE:
        raise HTTPException(409, f"{Term('league')} is in setup; create the {term('league')} to play")
    return league


def _check_court(league: League, court: int) -> None:
    if not 1 <= court <= league.num_courts:
        raise HTTPException(404, f"{Term('court')} {court} not found (1-{league.num_courts})")


def _claim(db: Session, league_id: int, court: int) -> CourtClaim | None:
    return db.scalar(select(CourtClaim).where(CourtClaim.league_id == league_id, CourtClaim.court == court))


def _claimed_message(claim: CourtClaim) -> str:
    holder = claim.device_name or (claim.claimed_by.name if claim.claimed_by else None)
    by = f" by {holder}" if holder else ""
    return f"{Term('court')} {claim.court} is already claimed{by}"


@router.get("/leagues", response_model=list[schemas.ScoringLeague])
def list_leagues(user: Scorer, db: DB):
    """Leagues you can score that are being played (active), newest first."""
    query = select(League).where(League.status == LeagueStatus.ACTIVE).order_by(League.created_at.desc())
    if user.role == UserRole.USER:
        query = query.where(visible_to(user))
    return db.scalars(query).all()


@router.get("/leagues/{league_id}/courts", response_model=list[schemas.ScoringCourt])
def list_free_courts(league_id: int, user: Scorer, db: DB):
    """The league's courts that no scoring app has claimed."""
    league = _get_active_league(db, user, league_id)
    claimed = {c.court for c in league.court_claims}
    in_use = set(
        db.scalars(
            select(Match.court).where(Match.league_id == league_id, Match.status == MatchStatus.IN_PROGRESS)
        )
    )
    return [
        schemas.ScoringCourt(court=court, in_use=court in in_use)
        for court in range(1, league.num_courts + 1)
        if court not in claimed
    ]


@router.post(
    "/leagues/{league_id}/courts/{court}/claim", status_code=201, response_model=schemas.CourtClaimRead
)
def claim_court(
    league_id: int, court: int, user: Scorer, db: DB, payload: schemas.CourtClaimCreate | None = None
):
    """Claim a court for this app. 409 if another app has it."""
    league = _get_active_league(db, user, league_id)
    _check_court(league, court)
    if existing := _claim(db, league_id, court):
        raise HTTPException(409, _claimed_message(existing))
    claim = CourtClaim(
        league_id=league_id, court=court, device_name=payload and payload.device_name, claimed_by_id=user.id
    )
    db.add(claim)
    try:
        db.commit()
    except IntegrityError:
        # Another app claimed it between the check and the insert.
        db.rollback()
        raise HTTPException(409, _claimed_message(_claim(db, league_id, court))) from None
    return claim


@router.delete("/leagues/{league_id}/courts/{court}/claim", status_code=204)
def release_court(league_id: int, court: int, user: Scorer, db: DB):
    """Release a claimed court, so it's offered to other apps again. Releasing a free court is a no-op.

    Umpires can release only their own claims; the league's organiser and
    admins can release any (e.g. one held by a lost device).
    """
    league = _get_league(db, user, league_id)
    if claim := _claim(db, league_id, court):
        if claim.claimed_by_id != user.id and not can_manage(user, league):
            raise HTTPException(409, f"{_claimed_message(claim)}; only they or the organiser can release it")
        db.delete(claim)
        db.commit()
    return Response(status_code=204)


@router.get("/leagues/{league_id}/courts/{court}/match", response_model=schemas.CourtMatch)
def court_match(league_id: int, court: int, user: Scorer, db: DB):
    """The match being played on a court now, with the scoring rules; ``match`` is null if none."""
    league = _get_league(db, user, league_id)
    _check_court(league, court)
    match = db.scalar(
        select(Match).where(
            Match.league_id == league_id, Match.court == court, Match.status == MatchStatus.IN_PROGRESS
        )
    )
    return schemas.CourtMatch(
        league_id=league.id,
        league_name=league.name,
        court=court,
        points_to_win=league.points_to_win,
        claim=_claim(db, league_id, court),
        match=match,
    )


@router.get("/leagues/{league_id}/matches", response_model=schemas.ScoringMatches)
def list_matches(
    league_id: int,
    user: Scorer,
    db: DB,
    week: int | None = Query(default=None, ge=1),
    status: MatchStatus | None = None,
):
    """A week's matches (default: the league's current week), with the scoring rules."""
    league = _get_league(db, user, league_id)
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
def record_result(match_id: int, payload: schemas.MatchResult, user: Scorer, db: DB):
    """Record a final score, with the same rules and errors as ``PUT /matches/{id}/result``.

    Umpires can score only the match on a court they've claimed; organisers
    and admins any match in their leagues.
    """
    match = get_or_404(db, Match, match_id)
    if not can_score(user, match.league):
        raise not_found_error(Match, match_id)
    if user.role == UserRole.UMPIRE:
        claim = match.court and _claim(db, match.league_id, match.court)
        if match.status != MatchStatus.IN_PROGRESS or not claim or claim.claimed_by_id != user.id:
            raise HTTPException(409, f"Claim this {term('match')}'s {term('court')} to score it")
    return matches.apply_result(matches.require_playable(match), payload, db)
