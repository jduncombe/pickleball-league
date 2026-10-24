"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import LeagueStatus, MatchStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Leagues -----------------------------------------------------------------


class LeagueBasics(BaseModel):
    """Setup step 1. Used to create a league and to edit it during setup."""

    name: str = Field(min_length=1, max_length=120)
    num_teams: int = Field(ge=2, le=64)
    num_weeks: int = Field(ge=1, le=52)
    # Matches each team plays per week (each against a different opponent).
    matches_per_week: int = Field(ge=1, le=20)
    num_courts: int = Field(ge=1, le=50)
    points_to_win: Literal[11, 15, 21] = 11
    use_team_names: bool = False

    @model_validator(mode="after")
    def matches_fit_opponents(self):
        if self.matches_per_week > self.num_teams - 1:
            most = self.num_teams - 1
            raise ValueError(
                f"With {self.num_teams} teams, each team can play at most {most} "
                f"match{'es' if most != 1 else ''} per week (one against each other team)"
            )
        return self


class LeagueUpdate(BaseModel):
    """Changes allowed while a league is active (setup details go through setup)."""

    current_week: int | None = Field(default=None, ge=1)


class LeagueRead(ORMModel):
    id: int
    name: str
    num_teams: int
    num_weeks: int
    matches_per_week: int
    num_courts: int
    points_to_win: int
    use_team_names: bool
    status: LeagueStatus
    created_league_at: datetime | None
    # Once true, num_teams/num_weeks/matches_per_week/points_to_win can't change in setup.
    has_played_matches: bool
    current_week: int
    created_at: datetime


# --- Players -----------------------------------------------------------------

# DUPR ids are short alphanumeric strings (e.g. "ABC123"). Validation is kept
# deliberately loose until the DUPR integration defines the exact format.
DUPR_ID_PATTERN = r"^[A-Za-z0-9]{4,12}$"


def _clean_optional(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class PlayerFields(BaseModel):
    email: str | None = Field(default=None, max_length=254)
    dupr_id: str | None = Field(default=None, pattern=DUPR_ID_PATTERN)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value):
        return _clean_optional(value)

    @field_validator("dupr_id", mode="before")
    @classmethod
    def clean_dupr_id(cls, value):
        value = _clean_optional(value)
        return value.upper() if isinstance(value, str) else value


class PlayerCreate(PlayerFields):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class PlayerRead(ORMModel):
    id: int
    team_id: int
    name: str
    email: str | None
    dupr_id: str | None
    dupr_rating: float | None


# --- Teams -------------------------------------------------------------------


class TeamSetup(BaseModel):
    """One team in setup step 2. Ignored name if the league doesn't use team names."""

    name: str | None = Field(default=None, max_length=120)
    players: list[PlayerCreate] = Field(default_factory=list, max_length=20)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return _clean_optional(value)


class TeamsSetup(BaseModel):
    """Setup step 2: every team, in position order (exactly num_teams entries)."""

    teams: list[TeamSetup]


class TeamRef(ORMModel):
    id: int
    name: str | None
    display_name: str
    # True when the team has players and all of them have DUPR IDs.
    dupr_ready: bool


class TeamRead(TeamRef):
    league_id: int
    position: int
    players: list[PlayerRead] = []


# --- Matches -----------------------------------------------------------------


class MatchRead(ORMModel):
    id: int
    league_id: int
    week: int
    round: int
    status: MatchStatus
    court: int | None
    team_a: TeamRef
    team_b: TeamRef
    score_a: int | None
    score_b: int | None
    started_at: datetime | None
    completed_at: datetime | None
    verified_at: datetime | None


class MatchStart(BaseModel):
    court: int | None = Field(
        default=None, ge=1, description="Court number; the lowest free court if omitted."
    )


class MatchResult(BaseModel):
    # Checked against the league's points_to_win in routers/matches.py.
    score_a: int = Field(ge=0, le=99)
    score_b: int = Field(ge=0, le=99)


# --- Dashboard / standings -------------------------------------------------------


class Dashboard(BaseModel):
    league: LeagueRead
    week: int
    free_courts: list[int]
    in_progress: list[MatchRead]
    available: list[MatchRead]
    waiting: list[MatchRead]
    completed_count: int
    total_count: int


class StandingRow(BaseModel):
    team: TeamRef
    played: int
    wins: int
    losses: int
    points_for: int
    points_against: int
    point_diff: int


class SchedulePreview(BaseModel):
    """What a schedule with these settings looks like (setup summary)."""

    rounds_per_week: int  # most rounds in any week
    games_per_week: int  # most games in any week
    has_catch_up_round: bool  # odd team count: last round pairs the teams that sat out
    # Weeks in which one team plays a match fewer (teams x matches is odd).
    teams_short_per_week: int
    # Across the season, the fewest and most times any two teams meet.
    min_meetings: int
    max_meetings: int
