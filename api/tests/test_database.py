"""Startup schema upkeep and the account CLI."""

from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app import cli, security
from app.database import Base, add_missing_columns
from app.models import League, User, UserRole


def test_new_columns_are_added_to_existing_tables():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    # leagues as it was before accounts: no owner_id.
    old = MetaData()
    Table("leagues", old, *[c._copy() for c in League.__table__.columns if c.name != "owner_id"])
    old.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO leagues (id, name, num_teams, num_weeks, matches_per_week, num_courts,"
                " points_to_win, use_team_names, status, current_week, created_at)"
                " VALUES (1, 'Old', 4, 1, 1, 1, 11, 0, 'active', 1, '2026-01-01')"
            )
        )
    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    assert "owner_id" in {c["name"] for c in inspect(engine).get_columns("leagues")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name, owner_id FROM leagues")).one() == ("Old", None)
    add_missing_columns(engine)  # idempotent


def test_cli_creates_an_admin(monkeypatch, session_factory):
    monkeypatch.setattr(cli, "SessionLocal", session_factory)
    monkeypatch.setattr(cli, "init_db", lambda: None)
    monkeypatch.setattr(cli, "_read_password", lambda: "a long admin password")
    cli.main(["create-user", "--email", "Root@Example.com", "--name", "Root"])
    with session_factory() as db:
        user = db.query(User).one()
    assert user.email == "root@example.com"
    assert user.role == UserRole.ADMIN
    assert not user.mfa_enabled
    assert security.verify_password(user.password_hash, "a long admin password")


def test_cli_can_generate_a_password(monkeypatch, session_factory, capsys):
    monkeypatch.setattr(cli, "SessionLocal", session_factory)
    monkeypatch.setattr(cli, "init_db", lambda: None)
    cli.main(["create-user", "--email", "ops@example.com", "--name", "Ops", "--generate-password"])
    password = capsys.readouterr().out.split("Temporary password: ")[1].split()[0]
    with session_factory() as db:
        user = db.query(User).one()
    assert len(password) >= 20
    assert security.verify_password(user.password_hash, password)
