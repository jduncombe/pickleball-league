from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from .. import schemas
from ..auth import Manager, can_own, managed_league, require_manager, visible_to
from ..deps import DB
from ..models import League, Match, MatchStatus, UserRole
from ..terms import term

router = APIRouter(prefix="/leagues", tags=["leagues"], dependencies=[Depends(require_manager)])


@router.get("", response_model=list[schemas.LeagueRead])
def list_leagues(user: Manager, db: DB):
    """Every league for admins; your own and those shared with you for users."""
    query = select(League).order_by(League.created_at.desc())
    if user.role != UserRole.ADMIN:
        query = query.where(visible_to(user))
    return db.scalars(query).all()


@router.get("/{league_id}", response_model=schemas.LeagueRead)
def get_league(league_id: int, user: Manager, db: DB):
    return managed_league(db, user, league_id)


@router.patch("/{league_id}", response_model=schemas.LeagueRead)
def update_league(league_id: int, payload: schemas.LeagueUpdate, user: Manager, db: DB):
    league = managed_league(db, user, league_id)
    changes = payload.model_dump(exclude_unset=True)
    if "current_week" in changes and changes["current_week"] > league.num_weeks:
        raise HTTPException(422, f"Current {term('week')} must be between 1 and {league.num_weeks}")
    for field, value in changes.items():
        setattr(league, field, value)
    db.commit()
    return league


@router.delete("/{league_id}", status_code=204)
def delete_league(league_id: int, user: Manager, db: DB):
    """Only the owner (or an admin) can delete a league; 409 for people it's shared with."""
    league = managed_league(db, user, league_id)
    if not can_own(user, league):
        raise HTTPException(409, f"Only the {term('league')}'s owner can delete it")
    db.delete(league)
    db.commit()


@router.get("/{league_id}/teams", response_model=list[schemas.TeamRead])
def list_teams(league_id: int, user: Manager, db: DB):
    return managed_league(db, user, league_id).teams


@router.get("/{league_id}/matches", response_model=list[schemas.MatchRead])
def list_matches(
    league_id: int,
    user: Manager,
    db: DB,
    week: int | None = Query(default=None, ge=1),
    status: MatchStatus | None = None,
):
    managed_league(db, user, league_id)
    query = select(Match).where(Match.league_id == league_id)
    if week is not None:
        query = query.where(Match.week == week)
    if status is not None:
        query = query.where(Match.status == status)
    return db.scalars(query.order_by(Match.week, Match.round, Match.id)).all()


@router.get("/{league_id}/dashboard", response_model=schemas.Dashboard)
def dashboard(league_id: int, user: Manager, db: DB, week: int | None = Query(default=None, ge=1)):
    """What's on court now, and which of this week's matches could start next.

    * ``in_progress`` – matches currently being played (any week).
    * ``available``   – this week's unplayed matches where neither team is on court.
    * ``waiting``     – this week's unplayed matches blocked by a team that is on court.
    """
    league = managed_league(db, user, league_id)
    week = week or league.current_week

    in_progress = db.scalars(
        select(Match)
        .where(Match.league_id == league_id, Match.status == MatchStatus.IN_PROGRESS)
        .order_by(Match.court)
    ).all()
    week_matches = db.scalars(
        select(Match).where(Match.league_id == league_id, Match.week == week).order_by(Match.round, Match.id)
    ).all()

    busy_teams = {t for m in in_progress for t in (m.team_a_id, m.team_b_id)}
    busy_courts = {m.court for m in in_progress}
    available, waiting = [], []
    for match in week_matches:
        if match.status != MatchStatus.SCHEDULED:
            continue
        if match.team_a_id in busy_teams or match.team_b_id in busy_teams:
            waiting.append(match)
        else:
            available.append(match)

    return schemas.Dashboard(
        league=league,
        week=week,
        free_courts=[c for c in range(1, league.num_courts + 1) if c not in busy_courts],
        in_progress=in_progress,
        available=available,
        waiting=waiting,
        completed_count=sum(m.status == MatchStatus.COMPLETED for m in week_matches),
        total_count=len(week_matches),
    )


@router.get("/{league_id}/standings", response_model=list[schemas.StandingRow])
def standings(league_id: int, user: Manager, db: DB):
    league = managed_league(db, user, league_id)
    rows = {
        team.id: {"team": team, "played": 0, "wins": 0, "losses": 0, "points_for": 0, "points_against": 0}
        for team in league.teams
    }
    for match in league.matches:
        if match.status != MatchStatus.COMPLETED:
            continue
        for team_id, scored, conceded in (
            (match.team_a_id, match.score_a, match.score_b),
            (match.team_b_id, match.score_b, match.score_a),
        ):
            row = rows[team_id]
            row["played"] += 1
            row["points_for"] += scored
            row["points_against"] += conceded
            row["wins" if scored > conceded else "losses"] += 1

    result = [
        schemas.StandingRow(**row, point_diff=row["points_for"] - row["points_against"])
        for row in rows.values()
    ]
    result.sort(key=lambda r: (-r.wins, -r.point_diff, -r.points_for, r.team.display_name))
    return result
