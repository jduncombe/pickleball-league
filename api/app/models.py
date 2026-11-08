"""ORM models: League -> Teams -> Players, League -> Matches, League -> CourtClaims; Users."""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .terms import Term


def _now() -> datetime:
    return datetime.now(UTC)


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class LeagueStatus(str, enum.Enum):
    # Basics, teams and players are being entered or edited; no play.
    SETUP = "setup"
    # Setup finalised ("Create the league"): schedule exists, teams and
    # players are fixed, matches can be played.
    ACTIVE = "active"


class UserRole(str, enum.Enum):
    # Everything, every league, and user management.
    ADMIN = "admin"
    # Creates and runs their own leagues.
    USER = "user"
    # Scoring app only: claims courts and records scores (routers/scoring.py).
    UMPIRE = "umpire"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lower-cased; the sign-in name.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, values_callable=lambda e: [m.value for m in e]))
    # Argon2id (see security.py).
    password_hash: Mapped[str] = mapped_column(String(255))
    # TOTP secret, AES-GCM encrypted (security.py). Null until enrolment starts;
    # MFA is required, so an account can't sign in until mfa_enabled.
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Last TOTP time step accepted, so a code can't be used twice.
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # In every token; bumping it signs the user out everywhere (password,
    # role or MFA change, deactivation).
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RevokedToken(Base):
    """Tokens signed out before they expire. Kept until their expiry."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    num_teams: Mapped[int] = mapped_column(Integer)
    num_weeks: Mapped[int] = mapped_column(Integer)
    # Matches each team plays per week; rounds per week follow from it
    # (see scheduling.py).
    matches_per_week: Mapped[int] = mapped_column(Integer)
    num_courts: Mapped[int] = mapped_column(Integer)
    # Games are first to this many points, win by 2 (see scoring.py).
    points_to_win: Mapped[int] = mapped_column(Integer, default=11)
    # When false, teams are known by their players' names (see Team.display_name).
    use_team_names: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[LeagueStatus] = mapped_column(
        Enum(LeagueStatus, values_callable=lambda e: [m.value for m in e]),
        default=LeagueStatus.SETUP,
    )
    # First time setup was finalised; stays set while the league is re-edited.
    created_league_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # The user who runs the league. Null for leagues made before accounts
    # existed, which only admins see.
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    owner: Mapped[User | None] = relationship()
    # Other users the owner has shared the league with (co-organisers).
    members: Mapped[list["LeagueMember"]] = relationship(
        back_populates="league", cascade="all, delete-orphan", order_by="LeagueMember.added_at"
    )
    teams: Mapped[list["Team"]] = relationship(
        back_populates="league", cascade="all, delete-orphan", order_by="Team.position"
    )
    matches: Mapped[list["Match"]] = relationship(back_populates="league", cascade="all, delete-orphan")
    court_claims: Mapped[list["CourtClaim"]] = relationship(
        back_populates="league", cascade="all, delete-orphan", order_by="CourtClaim.court"
    )

    @property
    def has_played_matches(self) -> bool:
        """True once any match has started; the season's shape is then fixed."""
        return any(m.status != MatchStatus.SCHEDULED for m in self.matches)


class LeagueMember(Base):
    """A user the league's owner (or an admin) has shared the league with.

    Members manage the league like its owner, except deleting it and
    changing who it's shared with (see auth.py)."""

    __tablename__ = "league_members"
    __table_args__ = (UniqueConstraint("league_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    added_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    league: Mapped[League] = relationship(back_populates="members")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    added_by: Mapped[User | None] = relationship(foreign_keys=[added_by_id])


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    # 1-based order within the league, fixed at setup.
    position: Mapped[int] = mapped_column(Integer)
    # Only used when the league uses team names; see display_name.
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    league: Mapped[League] = relationship(back_populates="teams")
    players: Mapped[list["Player"]] = relationship(
        back_populates="team", cascade="all, delete-orphan", order_by="Player.id"
    )

    @property
    def dupr_ready(self) -> bool:
        """Every player has a DUPR ID, so the team's matches could be DUPR-rated."""
        return bool(self.players) and all(p.dupr_id for p in self.players)

    @property
    def display_name(self) -> str:
        """The team name (if the league uses them), else its players' names
        ("Alex & Sam"), else "Team N"."""
        if self.league.use_team_names and self.name:
            return self.name
        names = [p.name for p in self.players]
        if not names:
            return f"{Term('team')} {self.position}"
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} & {names[-1]}"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    # Stored now so a future DUPR integration can look players up / sync ratings.
    dupr_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    dupr_rating: Mapped[float | None] = mapped_column(nullable=True)

    team: Mapped[Team] = relationship(back_populates="players")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    week: Mapped[int] = mapped_column(Integer)
    round: Mapped[int] = mapped_column(Integer)
    team_a_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    team_b_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, values_callable=lambda e: [m.value for m in e]),
        default=MatchStatus.SCHEDULED,
    )
    court: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when an organiser verifies the result; the score is then locked.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    league: Mapped[League] = relationship(back_populates="matches")
    team_a: Mapped[Team] = relationship(foreign_keys=[team_a_id])
    team_b: Mapped[Team] = relationship(foreign_keys=[team_b_id])


class CourtClaim(Base):
    """A scoring app (e.g. a tablet) has taken a court, so no other app can."""

    __tablename__ = "court_claims"
    # One claim per court: the database enforces it, so two apps claiming at
    # the same moment can't both win.
    __table_args__ = (UniqueConstraint("league_id", "court"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    court: Mapped[int] = mapped_column(Integer)
    # Optional label from the app ("Court 3 tablet"), shown when it's taken.
    device_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # The account that claimed it (an umpire, or the league's organiser).
    claimed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    league: Mapped[League] = relationship(back_populates="court_claims")
    claimed_by: Mapped[User | None] = relationship()
