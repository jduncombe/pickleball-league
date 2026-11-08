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

# Product name shown in the API docs; match the web brand (white-labelling).
APP_NAME = os.getenv("APP_NAME", "Pickleball League")

# Comma-separated list of origins allowed to call the API from a browser.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]


# --- Authentication (see app/security.py and docs/auth.md) ---------------------

# Master secret for auth: the PASETO token key and the key that encrypts TOTP
# secrets at rest are both derived from it (HKDF). At least 32 characters of
# randomness, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
# If it changes, everyone is signed out and every authenticator must be reset.
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "")
# Without AUTH_SECRET_KEY, a key is generated once and kept in this file
# (readable by the API's user only), next to the SQLite database by default.
AUTH_SECRET_FILE = os.getenv("AUTH_SECRET_FILE", "./data/auth_secret")

# How long a sign-in lasts. There are no refresh tokens: after this, sign in
# again (password + TOTP code).
ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", str(8 * 3600)))
# Between the password step and the TOTP step of a sign-in.
MFA_TOKEN_TTL_SECONDS = 300

# The web app's session cookie. Secure (HTTPS-only, also allowed on
# http://localhost by browsers) unless COOKIE_SECURE=false.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"
SESSION_COOKIE = "__Host-session" if COOKIE_SECURE else "session"

# Account lockout: this many failed passwords or TOTP codes in a row lock the
# account for LOCKOUT_SECONDS.
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 15 * 60
# Per client IP, across accounts (password spraying): attempts per minute.
LOGIN_ATTEMPTS_PER_MINUTE = int(os.getenv("LOGIN_ATTEMPTS_PER_MINUTE", "20"))
# Proxies in front of the API that append to X-Forwarded-For, so the client's
# IP (for the sign-in rate limit) can be told from one it made up: 0 when the
# API is reached directly, 1 behind nginx (docker-compose), 2 behind
# CloudFront + the ALB (AWS).
TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
