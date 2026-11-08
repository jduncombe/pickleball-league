"""Who is calling, and what they may see.

Requests authenticate with a PASETO access token (security.py), either
``Authorization: Bearer <token>`` (the scoring app) or the web app's HttpOnly
session cookie. Cookie-authenticated requests that change something must also
send ``X-Requested-With: fetch``: a cross-site form can't, and a cross-site
script can't without a CORS preflight the API refuses (CSRF protection on top
of the cookie's SameSite=Strict).

Roles (models.UserRole):
- admin: everything, every league, user management;
- user: their own leagues (League.owner_id);
- umpire: the scoring endpoints only.

What a caller may not see is answered with 404, the same as what doesn't
exist: it doesn't reveal what's there, and CloudFront turns 403s into the
site's 404 page anyway (infra/app/web.tf).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config, security
from .deps import DB, get_or_404, not_found_error
from .models import League, LeagueStatus, Match, RevokedToken, Team, User, UserRole

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-Requested-With"


def unauthorized(detail: str = "Not signed in") -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def not_found() -> HTTPException:
    return HTTPException(404, "Not found")


# Declared so the API docs offer "Authorize"; a missing header falls back to the cookie.
_bearer = HTTPBearer(auto_error=False, description="Access token from POST /auth/mfa/verify (client: app)")


def token_from_request(request: Request) -> tuple[str | None, bool]:
    """The access token, and whether it came from the session cookie."""
    header = request.headers.get("Authorization", "")
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip(), False
    return request.cookies.get(config.SESSION_COOKIE), True


def is_revoked(db: Session, jti: str) -> bool:
    return db.get(RevokedToken, jti) is not None


def revoke(db: Session, claims: dict) -> None:
    """Sign a token out before it expires (and forget expired revocations)."""
    now = datetime.now(UTC)
    db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete()
    if not is_revoked(db, claims["jti"]):
        db.add(RevokedToken(jti=claims["jti"], expires_at=datetime.fromisoformat(claims["exp"])))


def user_for_token(db: Session, purpose: str, token: str | None) -> tuple[User, dict]:
    """The active user a valid token of this purpose belongs to, and its claims; 401 otherwise."""
    if not token:
        raise unauthorized()
    try:
        claims = security.decode_token(purpose, token)
    except security.InvalidToken:
        raise unauthorized("Session expired or invalid; sign in again") from None
    user = db.get(User, int(claims["sub"]))
    if (
        user is None
        or not user.is_active
        or claims["ver"] != user.token_version
        or is_revoked(db, claims["jti"])
    ):
        raise unauthorized("Session expired or invalid; sign in again")
    return user, claims


def get_session(
    request: Request, db: DB, _: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None
) -> tuple[User, dict]:
    token, from_cookie = token_from_request(request)
    needs_csrf_header = from_cookie and token and request.method not in SAFE_METHODS
    if needs_csrf_header and request.headers.get(CSRF_HEADER) != "fetch":
        raise unauthorized(f"Missing {CSRF_HEADER} header")
    user, claims = user_for_token(db, security.ACCESS, token)
    if not user.mfa_enabled:  # can't happen for a token from the sign-in flow
        raise unauthorized()
    return user, claims


def get_current_user(session: Annotated[tuple[User, dict], Depends(get_session)]) -> User:
    return session[0]


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise not_found()
        return user

    return check


# League management (setup, schedule, results): admins and league organisers.
require_manager = require_roles(UserRole.ADMIN, UserRole.USER)
Manager = Annotated[User, Depends(require_manager)]
# The scoring app.
Scorer = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.USER, UserRole.UMPIRE))]
Admin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


def can_manage(user: User, league: League) -> bool:
    return user.role == UserRole.ADMIN or (user.role == UserRole.USER and league.owner_id == user.id)


def can_score(user: User, league: League) -> bool:
    """Umpires score any active league; organisers their own; admins any."""
    if user.role == UserRole.UMPIRE:
        return league.status == LeagueStatus.ACTIVE
    return can_manage(user, league)


def managed_league(db: Session, user: User, league_id: int) -> League:
    league = get_or_404(db, League, league_id)
    if not can_manage(user, league):
        raise not_found_error(League, league_id)
    return league


def managed(db: Session, user: User, model: type[Team] | type[Match], obj_id: int):
    """A team or match in a league this user manages; 404 otherwise."""
    obj = get_or_404(db, model, obj_id)
    if not can_manage(user, obj.league):
        raise not_found_error(model, obj_id)
    return obj
