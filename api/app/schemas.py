"""Pydantic request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import MatchStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Leagues -----------------------------------------------------------------


class LeagueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    num_teams: int = Field(ge=2, le=64)
    num_weeks: int = Field(ge=1, le=52)
    rounds_per_week: int = Field(ge=1, le=20)
    num_courts: int = Field(ge=1, le=50)


class LeagueUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    num_courts: int | None = Field(default=None, ge=1, le=50)
    current_week: int | None = Field(default=None, ge=1)


class LeagueRead(ORMModel):
    id: int
    name: str
    num_teams: int
    num_weeks: int
    rounds_per_week: int
    num_courts: int
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


class PlayerUpdate(PlayerFields):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class PlayerRead(ORMModel):
    id: int
    team_id: int
    name: str
    email: str | None
    dupr_id: str | None
    dupr_rating: float | None


# --- Teams -------------------------------------------------------------------


class TeamUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TeamRead(ORMModel):
    id: int
    league_id: int
    name: str
    players: list[PlayerRead] = []


class TeamRef(ORMModel):
    id: int
    name: str


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


class MatchStart(BaseModel):
    court: int | None = Field(
        default=None, ge=1, description="Court number; the lowest free court if omitted."
    )


class MatchResult(BaseModel):
    score_a: int = Field(ge=0, le=99)
    score_b: int = Field(ge=0, le=99)

    @field_validator("score_b")
    @classmethod
    def no_ties(cls, score_b, info):
        if info.data.get("score_a") == score_b:
            raise ValueError("pickleball matches cannot end in a tie")
        return score_b


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
