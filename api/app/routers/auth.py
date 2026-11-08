"""Sign-in with password + TOTP, and the session.

Sign-in is two steps, and TOTP is required for every account:

1. ``POST /auth/login`` with email and password returns a short-lived MFA
   token (and whether the account still has to enrol an authenticator).
2. If it has to, ``POST /auth/mfa/setup`` with that token returns a new TOTP
   secret and its QR code.
3. ``POST /auth/mfa/verify`` with the token and a current code finishes
   enrolment if needed and starts the session: an HttpOnly cookie for the
   web app, or a bearer token in the body for the scoring app.

Failed passwords and codes count towards a lockout; sign-in attempts are
also rate-limited per client IP. Errors don't say whether an account exists.
"""

import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, schemas, security
from ..auth import CurrentUser, get_session, revoke, unauthorized, user_for_token
from ..deps import DB
from ..models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

BAD_CREDENTIALS = "Incorrect email or password"
REUSED_CODE = "That code has been used already; wait for the next one from your app"


# --- Rate limiting --------------------------------------------------------------

_attempts: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    """The client's IP: the address TRUSTED_PROXY_HOPS proxies back in X-Forwarded-For."""
    hops = config.TRUSTED_PROXY_HOPS
    if hops:
        forwarded = [a.strip() for a in request.headers.get("X-Forwarded-For", "").split(",") if a.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """At most LOGIN_ATTEMPTS_PER_MINUTE sign-in attempts per IP (per API process)."""
    now = time.monotonic()
    window = _attempts[client_ip(request)]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= config.LOGIN_ATTEMPTS_PER_MINUTE:
        raise HTTPException(429, "Too many sign-in attempts; wait a minute", headers={"Retry-After": "60"})
    window.append(now)


# --- Lockout --------------------------------------------------------------------


def _is_locked(user: User) -> bool:
    locked_until = user.locked_until
    if locked_until is None:
        return False
    if locked_until.tzinfo is None:  # SQLite drops the timezone
        locked_until = locked_until.replace(tzinfo=UTC)
    return locked_until > datetime.now(UTC)


def _record_failure(db: Session, user: User) -> None:
    user.failed_logins += 1
    if user.failed_logins >= config.MAX_FAILED_LOGINS:
        user.locked_until = datetime.now(UTC) + timedelta(seconds=config.LOCKOUT_SECONDS)
        user.failed_logins = 0
    db.commit()


def _locked_error() -> HTTPException:
    minutes = config.LOCKOUT_SECONDS // 60
    return HTTPException(429, f"Too many failed attempts; this account is locked for up to {minutes} minutes")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


# --- Sign-in --------------------------------------------------------------------


@router.post("/login", response_model=schemas.LoginStep)
def login(payload: schemas.LoginRequest, request: Request, response: Response, db: DB):
    """Step 1: email and password. Returns a 5-minute token for the TOTP step."""
    _no_store(response)
    rate_limit(request)
    user = db.scalar(select(User).where(User.email == payload.email))
    # Always verify a hash, so unknown emails take as long as wrong passwords.
    password_ok = security.verify_password(user.password_hash if user else None, payload.password)
    if user is None or not user.is_active:
        raise unauthorized(BAD_CREDENTIALS)
    if _is_locked(user):
        # Only someone with the right password learns the account is locked.
        raise _locked_error() if password_ok else unauthorized(BAD_CREDENTIALS)
    if not password_ok:
        _record_failure(db, user)
        raise unauthorized(BAD_CREDENTIALS)
    if payload.client == "web" and user.role == UserRole.UMPIRE:
        raise unauthorized("Umpire accounts sign in on the scoring app")

    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(payload.password)
        db.commit()
    token, _ = security.issue_token(security.MFA, user.id, user.token_version, config.MFA_TOKEN_TTL_SECONDS)
    return schemas.LoginStep(mfa_token=token, mfa_setup_required=not user.mfa_enabled)


@router.post("/mfa/setup", response_model=schemas.MfaSetup)
def mfa_setup(payload: schemas.MfaSetupRequest, response: Response, db: DB):
    """Step 2, first sign-in only: a new TOTP secret to add to an authenticator app.

    Each call replaces the previous (unconfirmed) secret. 409 once enrolled:
    an admin has to reset MFA to enrol a new device.
    """
    _no_store(response)
    user, _ = user_for_token(db, security.MFA, payload.mfa_token)
    if user.mfa_enabled:
        raise HTTPException(409, "An authenticator is already set up for this account")
    secret = security.new_totp_secret()
    user.totp_secret = security.encrypt_totp_secret(secret, user.id)
    user.totp_last_step = None
    db.commit()
    uri, qr = security.totp_provisioning(secret, user.email)
    return schemas.MfaSetup(secret=secret, otpauth_uri=uri, qr_data_uri=qr)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        config.SESSION_COOKIE,
        token,
        max_age=config.ACCESS_TOKEN_TTL_SECONDS,
        path="/",
        secure=config.COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


@router.post("/mfa/verify", response_model=schemas.Session)
def mfa_verify(payload: schemas.MfaVerifyRequest, response: Response, db: DB):
    """Step 3: a current TOTP code. Starts the session."""
    _no_store(response)
    user, mfa_claims = user_for_token(db, security.MFA, payload.mfa_token)
    if _is_locked(user):
        raise _locked_error()
    if payload.client == "web" and user.role == UserRole.UMPIRE:
        raise unauthorized("Umpire accounts sign in on the scoring app")
    if user.totp_secret is None:
        raise HTTPException(409, "Set up an authenticator first")

    secret = security.decrypt_totp_secret(user.totp_secret, user.id)
    try:
        step = security.verify_totp(secret, payload.code, user.totp_last_step)
    except security.ReusedCode:
        # Right code, wrong moment: not a guess, so it doesn't count towards lockout.
        raise unauthorized(REUSED_CODE) from None
    if step is None:
        _record_failure(db, user)
        raise unauthorized("Incorrect code")

    user.totp_last_step = step
    user.mfa_enabled = True
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    revoke(db, mfa_claims)  # the MFA token is single-use
    token, claims = security.issue_token(
        security.ACCESS, user.id, user.token_version, config.ACCESS_TOKEN_TTL_SECONDS
    )
    db.commit()

    if payload.client == "web":
        _set_session_cookie(response, token)
        token = None
    return schemas.Session(user=user, expires_at=datetime.fromisoformat(claims["exp"]), access_token=token)


# --- The session ----------------------------------------------------------------


@router.get("/me", response_model=schemas.UserRead)
def me(user: CurrentUser, response: Response):
    _no_store(response)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, db: DB):
    """Sign out: the token stops working now, not when it expires."""
    response = Response(status_code=204)
    response.delete_cookie(config.SESSION_COOKIE, path="/", secure=config.COOKIE_SECURE, httponly=True)
    try:
        _, claims = get_session(request, db)
    except HTTPException:
        return response  # already signed out
    revoke(db, claims)
    db.commit()
    return response


@router.post("/password", status_code=204)
def change_password(payload: schemas.PasswordChange, user: CurrentUser, db: DB):
    """Change your password (with a TOTP code). Signs you out everywhere."""
    if _is_locked(user):
        raise _locked_error()
    secret = security.decrypt_totp_secret(user.totp_secret, user.id)
    try:
        step = security.verify_totp(secret, payload.code, user.totp_last_step)
    except security.ReusedCode:
        raise unauthorized(REUSED_CODE) from None
    if not security.verify_password(user.password_hash, payload.current_password) or step is None:
        _record_failure(db, user)
        raise unauthorized("Incorrect password or code")
    user.totp_last_step = step
    user.password_hash = security.hash_password(payload.new_password)
    user.token_version += 1
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie(config.SESSION_COOKIE, path="/", secure=config.COOKIE_SECURE, httponly=True)
    return response
