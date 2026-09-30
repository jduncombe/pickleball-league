"""Runtime configuration, read from environment variables."""

import os
from urllib.parse import quote_plus


def _database_url() -> str:
    """``DATABASE_URL`` if set, else a Postgres URL assembled from ``DB_*`` parts.

    The parts form exists for ECS, where the password is injected separately
    from Secrets Manager (see infra/app/api.tf).
    """
    if url := os.getenv("DATABASE_URL"):
        return url
    if host := os.getenv("DB_HOST"):
        user = quote_plus(os.environ["DB_USER"])
        password = quote_plus(os.environ["DB_PASSWORD"])
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "pickleball")
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
    return "sqlite:///./data/pickleball.db"


DATABASE_URL = _database_url()

# Path prefix the API is served under when behind a proxy that strips it
# (e.g. "/api" behind CloudFront or nginx). Only affects generated docs URLs.
ROOT_PATH = os.getenv("ROOT_PATH", "")

# Comma-separated list of origins allowed to call the API from a browser.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
