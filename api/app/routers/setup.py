"""League setup: the phase in which basics, teams and players are entered.

A league starts in setup. "Create the league" (finalize) validates the setup,
builds the schedule and makes the league active; teams and players are then
fixed. "Edit setup" (edit) puts an active league back into setup. Once any
match has been played, the season's shape (number of teams, weeks, rounds per
week) and the points to win can no longer change, since that would invalidate
results; names, players and courts can.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from .. import schemas
from ..deps import DB, get_or_404
from ..models import League, LeagueStatus, Match, MatchStatus, Player, Team
from ..scheduling import build_schedule

router = APIRouter(prefix="/leagues", tags=["league setup"])

# Changing any of these means a different schedule.
SCHEDULE_FIELDS = ("num_teams", "num_weeks", "rounds_per_week")
# Fixed once a match has been played: the schedule, and the scoring rules
# that existing results were validated against.
LOCKED_AFTER_PLAY = (*SCHEDULE_FIELDS, "points_to_win")


def _require_setup(league: League) -> None:
    if league.status != LeagueStatus.SETUP:
        raise HTTPException(409, "League setup is finalised; use 'Edit setup' to change it")


def _resize_teams(league: League) -> None:
    """Add or drop teams at the end so there are exactly num_teams."""
    count = len(league.teams)
    if league.num_teams > count:
        league.teams.extend(Team(position=p) for p in range(count + 1, league.num_teams + 1))
    elif league.num_teams < count:
        del league.teams[league.num_teams :]


def _generate_matches(league: League) -> list[Match]:
    team_ids = [team.id for team in league.teams]
    return [
        Match(league_id=league.id, week=week, round=rnd, team_a_id=a, team_b_id=b)
        for week, rnd, (a, b) in build_schedule(team_ids, league.num_weeks, league.rounds_per_week)
    ]


@router.post("", response_model=schemas.LeagueRead, status_code=201)
def create_league(payload: schemas.LeagueBasics, db: DB):
    """Setup step 1 for a new league: creates it in setup with empty teams."""
    league = League(**payload.model_dump(), status=LeagueStatus.SETUP)
    league.teams = [Team(position=p) for p in range(1, payload.num_teams + 1)]
    db.add(league)
    db.commit()
    return league


@router.put("/{league_id}/setup", response_model=schemas.LeagueRead)
def update_basics(league_id: int, payload: schemas.LeagueBasics, db: DB):
    """Setup step 1 for an existing league in setup."""
    league = get_or_404(db, League, league_id)
    _require_setup(league)

    if league.has_played_matches:
        locked = [f for f in LOCKED_AFTER_PLAY if getattr(payload, f) != getattr(league, f)]
        if locked:
            raise HTTPException(
                409, "Matches have been played, so these can't change: " + ", ".join(locked)
            )
    if any(getattr(payload, f) != getattr(league, f) for f in SCHEDULE_FIELDS):
        # The schedule no longer fits; it is rebuilt when the league is created.
        league.matches.clear()
        db.flush()

    for field, value in payload.model_dump().items():
        setattr(league, field, value)
    league.current_week = min(league.current_week, league.num_weeks)
    _resize_teams(league)
    db.commit()
    return league


@router.put("/{league_id}/teams", response_model=list[schemas.TeamRead])
def update_teams(league_id: int, payload: schemas.TeamsSetup, db: DB):
    """Setup step 2: names and players for every team, in position order.

    Team names are stored even when the league doesn't use them, so switching
    team names off and on again doesn't lose them.
    """
    league = get_or_404(db, League, league_id)
    _require_setup(league)
    if len(payload.teams) != league.num_teams:
        raise HTTPException(422, f"Expected {league.num_teams} teams, got {len(payload.teams)}")

    for team, setup in zip(league.teams, payload.teams, strict=True):
        team.name = setup.name
        team.players = [Player(**p.model_dump()) for p in setup.players]
    db.commit()
    return league.teams


@router.post("/{league_id}/finalize", response_model=schemas.LeagueRead)
def create_the_league(league_id: int, db: DB):
    """"Create the league": check setup is complete, build the schedule if
    needed, and make the league active. Teams and players are then fixed."""
    league = get_or_404(db, League, league_id)
    _require_setup(league)

    problems = []
    for team in league.teams:
        if league.use_team_names and not team.name:
            problems.append(f"Team {team.position} needs a name")
        if not team.players:
            problems.append(f"Team {team.position} needs at least one player")
    if problems:
        raise HTTPException(422, "; ".join(problems))

    if not league.matches:
        db.add_all(_generate_matches(league))
    league.status = LeagueStatus.ACTIVE
    league.created_league_at = league.created_league_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(league)
    return league


@router.post("/{league_id}/edit", response_model=schemas.LeagueRead)
def edit_setup(league_id: int, db: DB):
    """"Edit setup": put an active league back into setup. Play is paused
    until the league is created again."""
    league = get_or_404(db, League, league_id)
    if league.status == LeagueStatus.SETUP:
        return league
    if any(m.status == MatchStatus.IN_PROGRESS for m in league.matches):
        raise HTTPException(409, "Finish the matches on court (or return them to the schedule) first")
    league.status = LeagueStatus.SETUP
    db.commit()
    return league
