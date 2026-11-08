import os

# Keep app startup (init_db) off the real database file.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("AUTH_SECRET_KEY", "test-only-secret-key-0123456789abcdef")
# TestClient talks plain http://testserver, where browsers wouldn't keep a Secure cookie.
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import config, security  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402

from .helpers import set_up_league  # noqa: E402

# Set TEST_DATABASE_URL (e.g. a throwaway Postgres) to run against a real server;
# defaults to in-memory SQLite.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def _make_engine():
    if TEST_DATABASE_URL:
        return create_engine(TEST_DATABASE_URL)
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def session_factory():
    engine = _make_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestSession
    app.dependency_overrides.clear()
    engine.dispose()


PASSWORD = "correct horse battery staple"


@pytest.fixture()
def make_user(session_factory):
    """Create an account with MFA enrolled: returns (user, TOTP secret)."""

    def make(role: UserRole = UserRole.USER, email: str | None = None, mfa: bool = True):
        with session_factory() as db:
            user = User(
                email=email or f"{role.value}{db.query(User).count() + 1}@example.com",
                name=f"{role.value.title()} {db.query(User).count() + 1}",
                role=role,
                password_hash=security.hash_password(PASSWORD),
            )
            db.add(user)
            db.flush()
            secret = security.new_totp_secret()
            if mfa:
                user.totp_secret = security.encrypt_totp_secret(secret, user.id)
                user.mfa_enabled = True
            db.commit()
            return user, secret

    return make


@pytest.fixture()
def client_for(make_user):
    """A TestClient signed in (bearer token) as a new account with this role."""

    def make(role: UserRole = UserRole.USER, email: str | None = None) -> TestClient:
        user, _ = make_user(role, email)
        token, _ = security.issue_token(security.ACCESS, user.id, 0, config.ACCESS_TOKEN_TTL_SECONDS)
        test_client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
        test_client.user = user
        return test_client

    return make


@pytest.fixture()
def anon(session_factory):
    """A TestClient that isn't signed in."""
    return TestClient(app)


@pytest.fixture()
def client(client_for):
    """Signed in as an admin, who can do everything."""
    return client_for(UserRole.ADMIN)


@pytest.fixture()
def league(client):
    """An active (created) league: 4 teams, 2 weeks x 3 rounds, 1 court."""
    return set_up_league(client)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from app.routers import auth

    auth._attempts.clear()
