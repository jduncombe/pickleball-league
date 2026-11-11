"""Sharing a league with other users (co-organisers).

The owner (or an admin) shares a league with other user accounts by email.
They then manage it like the owner: setup, schedule, results, the scoring
app. Only the owner and admins can delete the league or change who it's
shared with; someone it's shared with can remove themselves.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import schemas
from ..auth import Manager, can_own, managed_league, require_manager
from ..deps import DB
from ..models import League, LeagueMember, User, UserRole
from ..terms import Term, term

router = APIRouter(prefix="/leagues", tags=["league sharing"], dependencies=[Depends(require_manager)])


def _sharing(league: League) -> schemas.LeagueSharing:
    return schemas.LeagueSharing(owner=league.owner, members=league.members)


@router.get("/{league_id}/members", response_model=schemas.LeagueSharing)
def list_members(league_id: int, user: Manager, db: DB):
    """Who owns the league and who it's shared with."""
    return _sharing(managed_league(db, user, league_id))


@router.post("/{league_id}/members", response_model=schemas.LeagueSharing, status_code=201)
def add_member(league_id: int, payload: schemas.LeagueShare, user: Manager, db: DB):
    """Share the league with a user, by their account's email. Owner and admins only."""
    league = managed_league(db, user, league_id)
    if not can_own(user, league):
        raise HTTPException(409, f"Only the {term('league')}'s owner can share it")
    member = db.scalar(select(User).where(User.email == payload.email))
    if member is None or not member.is_active:
        raise HTTPException(404, f"No active account for {payload.email}")
    if member.role != UserRole.USER:
        # Admins see every league already; umpires can't manage leagues.
        raise HTTPException(422, f"{Term('league', 2)} can only be shared with user accounts")
    if member.id == league.owner_id:
        raise HTTPException(409, f"{member.name} owns this {term('league')}")
    if any(m.user_id == member.id for m in league.members):
        raise HTTPException(409, f"Already shared with {member.name}")
    league.members.append(LeagueMember(user_id=member.id, added_by_id=user.id))
    try:
        db.commit()
    except IntegrityError:  # shared with them at the same moment by someone else
        db.rollback()
        raise HTTPException(409, f"Already shared with {member.name}") from None
    db.refresh(league)
    return _sharing(league)


@router.delete("/{league_id}/members/{member_user_id}", status_code=204)
def remove_member(league_id: int, member_user_id: int, user: Manager, db: DB):
    """Stop sharing with someone. The owner and admins can remove anyone;
    people it's shared with can remove themselves (leave)."""
    league = managed_league(db, user, league_id)
    if not can_own(user, league) and member_user_id != user.id:
        raise HTTPException(409, f"Only the {term('league')}'s owner can change who it's shared with")
    for member in league.members:
        if member.user_id == member_user_id:
            league.members.remove(member)
            db.commit()
            break
    return Response(status_code=204)
