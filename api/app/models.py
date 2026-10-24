"""ORM models: League -> Teams -> Players, League -> Matches."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    num_teams: Mapped[int] = mapped_column(Integer)
    num_weeks: Mapped[int] = mapped_column(Integer)
    rounds_per_week: Mapped[int] = mapped_column(Integer)
    num_courts: Mapped[int] = mapped_column(Integer)
    # When false, teams are known by their players' names (see Team.display_name).
    use_team_names: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[LeagueStatus] = mapped_column(
        Enum(LeagueStatus, values_callable=lambda e: [m.value for m in e]),
        default=LeagueStatus.SETUP,
    )
    # First time setup was finalised; stays set while the league is re-edited.
    created_league_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    teams: Mapped[list["Team"]] = relationship(
        back_populates="league", cascade="all, delete-orphan", order_by="Team.position"
    )
    matches: Mapped[list["Match"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )

    @property
    def has_played_matches(self) -> bool:
        """True once any match has started; the season's shape is then fixed."""
        return any(m.status != MatchStatus.SCHEDULED for m in self.matches)


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
    def display_name(self) -> str:
        """The team name (if the league uses them), else its players' names
        ("Alex & Sam"), else "Team N"."""
        if self.league.use_team_names and self.name:
            return self.name
        names = [p.name for p in self.players]
        if not names:
            return f"Team {self.position}"
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

    league: Mapped[League] = relationship(back_populates="matches")
    team_a: Mapped[Team] = relationship(foreign_keys=[team_a_id])
    team_b: Mapped[Team] = relationship(foreign_keys=[team_b_id])
