from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from .. import schemas
from ..deps import DB, get_or_404
from ..models import League, Match, MatchStatus, Team
from ..scheduling import build_schedule

router = APIRouter(prefix="/leagues", tags=["leagues"])


def _generate_matches(league: League) -> list[Match]:
    team_ids = [team.id for team in league.teams]
    return [
        Match(league_id=league.id, week=week, round=rnd, team_a_id=a, team_b_id=b)
        for week, rnd, (a, b) in build_schedule(
            team_ids, league.num_weeks, league.rounds_per_week
        )
    ]


@router.get("", response_model=list[schemas.LeagueRead])
def list_leagues(db: DB):
    return db.scalars(select(League).order_by(League.created_at.desc())).all()


@router.post("", response_model=schemas.LeagueRead, status_code=201)
def create_league(payload: schemas.LeagueCreate, db: DB):
    """Create a league, its placeholder teams and a round-robin schedule."""
    league = League(**payload.model_dump())
    league.teams = [Team(name=f"Team {i}") for i in range(1, payload.num_teams + 1)]
    db.add(league)
    db.flush()  # assign team ids before building the schedule
    db.add_all(_generate_matches(league))
    db.commit()
    return league


@router.get("/{league_id}", response_model=schemas.LeagueRead)
def get_league(league_id: int, db: DB):
    return get_or_404(db, League, league_id)


@router.patch("/{league_id}", response_model=schemas.LeagueRead)
def update_league(league_id: int, payload: schemas.LeagueUpdate, db: DB):
    league = get_or_404(db, League, league_id)
    changes = payload.model_dump(exclude_unset=True)
    if "current_week" in changes and changes["current_week"] > league.num_weeks:
        raise HTTPException(422, f"current_week must be between 1 and {league.num_weeks}")
    for field, value in changes.items():
        setattr(league, field, value)
    db.commit()
    return league


@router.delete("/{league_id}", status_code=204)
def delete_league(league_id: int, db: DB):
    db.delete(get_or_404(db, League, league_id))
    db.commit()


@router.post("/{league_id}/schedule", response_model=list[schemas.MatchRead])
def regenerate_schedule(league_id: int, db: DB):
    """Throw away and rebuild the schedule. Refused once any match has started."""
    league = get_or_404(db, League, league_id)
    if any(m.status != MatchStatus.SCHEDULED for m in league.matches):
        raise HTTPException(409, "Cannot regenerate a schedule once matches have started")
    league.matches.clear()
    db.flush()
    league.matches.extend(_generate_matches(league))
    db.commit()
    return sorted(league.matches, key=lambda m: (m.week, m.round, m.id))


@router.get("/{league_id}/teams", response_model=list[schemas.TeamRead])
def list_teams(league_id: int, db: DB):
    return get_or_404(db, League, league_id).teams


@router.get("/{league_id}/matches", response_model=list[schemas.MatchRead])
def list_matches(
    league_id: int,
    db: DB,
    week: int | None = Query(default=None, ge=1),
    status: MatchStatus | None = None,
):
    get_or_404(db, League, league_id)
    query = select(Match).where(Match.league_id == league_id)
    if week is not None:
        query = query.where(Match.week == week)
    if status is not None:
        query = query.where(Match.status == status)
    return db.scalars(query.order_by(Match.week, Match.round, Match.id)).all()


@router.get("/{league_id}/dashboard", response_model=schemas.Dashboard)
def dashboard(league_id: int, db: DB, week: int | None = Query(default=None, ge=1)):
    """What's on court now, and which of this week's matches could start next.

    * ``in_progress`` – matches currently being played (any week).
    * ``available``   – this week's unplayed matches where neither team is on court.
    * ``waiting``     – this week's unplayed matches blocked by a team that is on court.
    """
    league = get_or_404(db, League, league_id)
    week = week or league.current_week

    in_progress = db.scalars(
        select(Match)
        .where(Match.league_id == league_id, Match.status == MatchStatus.IN_PROGRESS)
        .order_by(Match.court)
    ).all()
    week_matches = db.scalars(
        select(Match)
        .where(Match.league_id == league_id, Match.week == week)
        .order_by(Match.round, Match.id)
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
def standings(league_id: int, db: DB):
    league = get_or_404(db, League, league_id)
    rows = {
        team.id: {"team": team, "played": 0, "wins": 0, "losses": 0,
                  "points_for": 0, "points_against": 0}
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
    result.sort(key=lambda r: (-r.wins, -r.point_diff, -r.points_for, r.team.name))
    return result
