"""Account management: admins only.

There's no self sign-up. An admin creates each account with a temporary
password; the person enrols an authenticator at their first sign-in.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import schemas, security
from ..auth import Admin
from ..deps import DB, get_or_404
from ..models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[schemas.UserRead])
def list_users(_: Admin, db: DB):
    return db.scalars(select(User).order_by(User.email)).all()


@router.post("", response_model=schemas.UserRead, status_code=201)
def create_user(payload: schemas.UserCreate, _: Admin, db: DB):
    user = User(
        email=payload.email,
        name=payload.name,
        role=payload.role,
        password_hash=security.hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"An account for {payload.email} already exists") from None
    return user


@router.patch("/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: int, payload: schemas.UserUpdate, admin: Admin, db: DB):
    """Change name, role, active or password. Anything but the name signs them out everywhere."""
    user = get_or_404(db, User, user_id)
    changes = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and ("role" in changes or changes.get("is_active") is False):
        raise HTTPException(409, "You can't change your own role or deactivate yourself")
    if "password" in changes:
        user.password_hash = security.hash_password(changes.pop("password"))
        user.failed_logins = 0
        user.locked_until = None
        user.token_version += 1
    if changes.keys() & {"role", "is_active"}:
        user.token_version += 1
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    return user


@router.post("/{user_id}/reset-mfa", response_model=schemas.UserRead)
def reset_mfa(user_id: int, _: Admin, db: DB):
    """Remove the account's authenticator (e.g. a lost phone). They enrol a new
    one at their next sign-in, and are signed out everywhere now."""
    user = get_or_404(db, User, user_id)
    user.totp_secret = None
    user.totp_last_step = None
    user.mfa_enabled = False
    user.token_version += 1
    db.commit()
    return user
