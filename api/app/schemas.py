"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import LeagueStatus, MatchStatus, UserRole
from .security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from .terms import count, term


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
            raise ValueError(
                f"With {count(self.num_teams, 'team')}, each {term('team')} can play at most "
                f"{count(self.num_teams - 1, 'match')} per {term('week')} "
                f"(one against each other {term('team')})"
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


class ScoringLeague(ORMModel):
    id: int
    name: str
    num_courts: int
    current_week: int
    points_to_win: int


class ScoringCourt(BaseModel):
    court: int
    # A match is on this court now (it can still be claimed).
    in_use: bool


class CourtClaimCreate(BaseModel):
    device_name: str | None = Field(default=None, max_length=80)

    @field_validator("device_name", mode="before")
    @classmethod
    def _blank_is_none(cls, value):
        return _clean_optional(value)


class ClaimHolder(ORMModel):
    id: int
    name: str


class CourtClaimRead(ORMModel):
    league_id: int
    court: int
    device_name: str | None
    claimed_by: ClaimHolder | None
    claimed_at: datetime


class CourtMatch(BaseModel):
    """What's being played on a court; ``match`` is null when it's free."""

    league_id: int
    league_name: str
    court: int
    points_to_win: int
    claim: CourtClaimRead | None
    match: MatchRead | None


class ScoringMatches(BaseModel):
    league_id: int
    league_name: str
    points_to_win: int
    week: int
    matches: list[MatchRead]


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


# --- Accounts and sign-in ------------------------------------------------------

Password = Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)]
TotpCode = Annotated[str, Field(min_length=6, max_length=8)]
# "web": the session goes in an HttpOnly cookie and never reaches script.
# "app" (the scoring app): the access token is returned in the body.
Client = Literal["web", "app"]


def _normalise_email(value):
    return value.strip().lower() if isinstance(value, str) else value


class UserRead(ORMModel):
    id: int
    email: str
    name: str
    role: UserRole
    is_active: bool
    mfa_enabled: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+$")
    name: str = Field(min_length=1, max_length=120)
    role: UserRole
    password: Password

    _email = field_validator("email", mode="before")(_normalise_email)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None
    password: Password | None = None


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    client: Client = "web"

    _email = field_validator("email", mode="before")(_normalise_email)


class LoginStep(BaseModel):
    """Password accepted; send a TOTP code with this token (after enrolling, if needed)."""

    mfa_token: str
    mfa_setup_required: bool


class MfaSetupRequest(BaseModel):
    mfa_token: str


class MfaSetup(BaseModel):
    secret: str
    otpauth_uri: str
    # The otpauth URI as a QR code: an SVG data: URI, for an <img>.
    qr_data_uri: str


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: TotpCode
    client: Client = "web"


class Session(BaseModel):
    user: UserRead
    expires_at: datetime
    # Only for client "app"; the web app gets an HttpOnly cookie instead.
    access_token: str | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password: Password
    code: TotpCode
