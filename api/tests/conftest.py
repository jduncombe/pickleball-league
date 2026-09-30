import os

# Keep app startup (init_db) off the real database file.
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402, F401
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


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
def client():
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
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def league(client):
    resp = client.post(
        "/leagues",
        json={"name": "Autumn", "num_teams": 4, "num_weeks": 2,
              "rounds_per_week": 3, "num_courts": 1},
    )
    assert resp.status_code == 201
    return resp.json()
