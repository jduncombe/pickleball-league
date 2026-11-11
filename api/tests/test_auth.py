"""Sign-in (password + TOTP), sessions and token security."""

import time

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import config, security
from app.main import app
from app.models import User, UserRole
from app.routers import auth as auth_router

from .conftest import PASSWORD

CSRF = {"X-Requested-With": "fetch"}


def code(secret: str, offset: int = 0) -> str:
    return pyotp.TOTP(secret).at(time.time() + offset * 30)


def login(c: TestClient, email: str, password: str = PASSWORD, client: str = "web"):
    return c.post("/auth/login", json={"email": email, "password": password, "client": client})


def sign_in(c: TestClient, user: User, secret: str, client: str = "web"):
    mfa_token = login(c, user.email, client=client).json()["mfa_token"]
    return c.post("/auth/mfa/verify", json={"mfa_token": mfa_token, "code": code(secret), "client": client})


# --- The sign-in flow -------------------------------------------------------------


def test_first_sign_in_enrols_an_authenticator(anon, make_user, session_factory):
    user, _ = make_user(UserRole.USER, "new@example.com", mfa=False)

    step = login(anon, "New@Example.com ")  # email is normalised
    assert step.status_code == 200, step.text
    assert step.headers["Cache-Control"] == "no-store"
    assert step.json()["mfa_setup_required"] is True
    mfa_token = step.json()["mfa_token"]
    assert mfa_token.startswith("v4.local.")

    setup = anon.post("/auth/mfa/setup", json={"mfa_token": mfa_token}).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert "new%40example.com" in setup["otpauth_uri"]
    assert setup["qr_data_uri"].startswith("data:image/svg+xml")
    secret = setup["secret"]

    # The secret is stored encrypted, not as given.
    with session_factory() as db:
        stored = db.get(User, user.id).totp_secret
    assert secret not in stored
    assert security.decrypt_totp_secret(stored, user.id) == secret

    wrong = anon.post("/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"})
    assert wrong.status_code == 401
    resp = anon.post("/auth/mfa/verify", json={"mfa_token": mfa_token, "code": code(secret)})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["mfa_enabled"] is True
    assert resp.json()["access_token"] is None  # the web app gets a cookie instead

    # Enrolled: setup is refused from now on.
    again = login(anon, user.email).json()
    assert again["mfa_setup_required"] is False
    assert anon.post("/auth/mfa/setup", json={"mfa_token": again["mfa_token"]}).status_code == 409


def test_web_session_cookie(anon, make_user):
    user, secret = make_user(UserRole.USER)
    resp = sign_in(anon, user, secret)
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{config.SESSION_COOKIE}=v4.local.")
    for attribute in ("HttpOnly", "SameSite=strict", "Path=/", f"Max-Age={config.ACCESS_TOKEN_TTL_SECONDS}"):
        assert attribute.lower() in cookie.lower()

    assert anon.get("/auth/me").json()["email"] == user.email
    # Changes need the CSRF header when the session is a cookie.
    assert anon.post("/leagues", json={"name": "x"}).status_code == 401
    assert anon.post("/leagues", json={"name": "x"}, headers=CSRF).status_code == 422  # authenticated


def test_secure_cookie_name_in_production(monkeypatch, anon, make_user):
    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    monkeypatch.setattr(config, "SESSION_COOKIE", "__Host-session")
    user, secret = make_user(UserRole.USER)
    cookie = sign_in(anon, user, secret).headers["set-cookie"]
    assert cookie.startswith("__Host-session=") and "secure" in cookie.lower()


def test_app_client_gets_a_bearer_token(anon, make_user):
    user, secret = make_user(UserRole.UMPIRE)
    resp = sign_in(anon, user, secret, client="app")
    assert resp.status_code == 200, resp.text
    assert "set-cookie" not in resp.headers
    token = resp.json()["access_token"]
    me = anon.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "umpire"


def test_umpires_cant_sign_in_to_the_web_app(anon, make_user):
    user, _ = make_user(UserRole.UMPIRE)
    resp = login(anon, user.email)
    assert resp.status_code == 401
    assert "scoring app" in resp.json()["detail"]


def test_logout_revokes_the_token(anon, make_user):
    user, secret = make_user(UserRole.UMPIRE)
    token = sign_in(anon, user, secret, client="app").json()["access_token"]
    bearer = {"Authorization": f"Bearer {token}"}
    assert anon.post("/auth/logout", headers=bearer).status_code == 204
    assert anon.get("/auth/me", headers=bearer).status_code == 401


def test_logout_clears_the_cookie(anon, make_user):
    user, secret = make_user(UserRole.USER)
    sign_in(anon, user, secret)
    token = anon.cookies[config.SESSION_COOKIE]
    resp = anon.post("/auth/logout", headers=CSRF)
    assert resp.status_code == 204
    assert 'session=""' in resp.headers["set-cookie"] or "Max-Age=0" in resp.headers["set-cookie"]
    # Replaying the old cookie value doesn't work either.
    replay = TestClient(app, cookies={config.SESSION_COOKIE: token})
    assert replay.get("/auth/me").status_code == 401


# --- Failures -----------------------------------------------------------------


def test_wrong_password_and_unknown_email_look_the_same(anon, make_user):
    user, _ = make_user(UserRole.USER)
    wrong = login(anon, user.email, "not the password")
    unknown = login(anon, "nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Incorrect email or password"}


def test_lockout_after_repeated_failures(anon, make_user):
    user, secret = make_user(UserRole.USER)
    for _ in range(config.MAX_FAILED_LOGINS):
        assert login(anon, user.email, "wrong password!").status_code == 401
    # Locked: the right password is refused (and only it learns why)...
    assert login(anon, user.email).status_code == 429
    assert login(anon, user.email, "wrong password!").status_code == 401


def test_wrong_codes_count_towards_lockout(anon, make_user):
    user, secret = make_user(UserRole.USER)
    for _ in range(config.MAX_FAILED_LOGINS):
        token = login(anon, user.email).json()["mfa_token"]
        assert anon.post("/auth/mfa/verify", json={"mfa_token": token, "code": "123456"}).status_code == 401
    assert login(anon, user.email).status_code == 429


def test_rate_limit_per_ip(anon, make_user, monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ATTEMPTS_PER_MINUTE", 3)
    for i in range(3):
        assert login(anon, f"x{i}@example.com").status_code == 401
    resp = login(anon, "x9@example.com")
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "60"


@pytest.mark.parametrize(
    ("hops", "forwarded", "expected"),
    [
        (0, "1.1.1.1", "testclient"),
        (1, "6.6.6.6, 2.2.2.2", "2.2.2.2"),  # behind nginx: the last entry
        (2, "6.6.6.6, 3.3.3.3, 10.0.0.9", "3.3.3.3"),  # behind CloudFront + ALB
        (2, "4.4.4.4", "testclient"),  # fewer entries than proxies: don't trust it
    ],
)
def test_client_ip(monkeypatch, hops, forwarded, expected):
    from starlette.requests import Request

    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", hops)
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", forwarded.encode())],
            "client": ("testclient", 50000),
        }
    )
    assert auth_router.client_ip(request) == expected


def test_totp_code_cant_be_reused(anon, make_user):
    user, secret = make_user(UserRole.USER)
    current = code(secret)
    first = login(anon, user.email).json()["mfa_token"]
    assert anon.post("/auth/mfa/verify", json={"mfa_token": first, "code": current}).status_code == 200
    second = login(anon, user.email).json()["mfa_token"]
    resp = anon.post("/auth/mfa/verify", json={"mfa_token": second, "code": current})
    assert resp.status_code == 401
    assert "used already" in resp.json()["detail"]


def test_mfa_token_is_single_use(anon, make_user):
    user, secret = make_user(UserRole.USER)
    token = login(anon, user.email).json()["mfa_token"]
    assert anon.post("/auth/mfa/verify", json={"mfa_token": token, "code": code(secret)}).status_code == 200
    resp = anon.post("/auth/mfa/verify", json={"mfa_token": token, "code": code(secret, 1)})
    assert resp.status_code == 401


def test_tokens_are_bound_to_their_purpose(anon, make_user):
    user, secret = make_user(UserRole.USER)
    mfa_token = login(anon, user.email).json()["mfa_token"]
    # An MFA-step token (password only) is not a session.
    assert anon.get("/auth/me", headers={"Authorization": f"Bearer {mfa_token}"}).status_code == 401
    # And a session token can't stand in for the MFA step.
    access, _ = security.issue_token(security.ACCESS, user.id, 0, 60)
    assert anon.post("/auth/mfa/setup", json={"mfa_token": access}).status_code == 401


def test_tampered_and_expired_tokens_are_refused(anon, make_user):
    user, _ = make_user(UserRole.ADMIN)
    token, _ = security.issue_token(security.ACCESS, user.id, 0, 60)
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert anon.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401
    expired, _ = security.issue_token(security.ACCESS, user.id, 0, -10)
    assert anon.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_inactive_accounts_cant_sign_in(anon, client, make_user):
    user, secret = make_user(UserRole.USER)
    token = sign_in(anon, user, secret, client="app").json()["access_token"]
    client.patch(f"/users/{user.id}", json={"is_active": False})
    assert anon.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert login(anon, user.email).status_code == 401


# --- Passwords ----------------------------------------------------------------


def test_passwords_are_argon2id_hashes(session_factory, make_user):
    user, _ = make_user(UserRole.USER)
    with session_factory() as db:
        stored = db.get(User, user.id).password_hash
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


def test_change_password_signs_out_everywhere(anon, make_user):
    user, secret = make_user(UserRole.USER)
    token = sign_in(anon, user, secret, client="app").json()["access_token"]
    bearer = {"Authorization": f"Bearer {token}"}
    body = {"current_password": PASSWORD, "new_password": "a brand new passphrase", "code": code(secret, 1)}
    assert (
        anon.post("/auth/password", json={**body, "current_password": "nope"}, headers=bearer).status_code
        == 401
    )
    assert anon.post("/auth/password", json=body, headers=bearer).status_code == 204
    assert anon.get("/auth/me", headers=bearer).status_code == 401
    assert login(anon, user.email).status_code == 401
    assert login(anon, user.email, "a brand new passphrase").status_code == 200


def test_short_passwords_are_refused(client):
    resp = client.post(
        "/users", json={"email": "a@example.com", "name": "A", "role": "user", "password": "short"}
    )
    assert resp.status_code == 422
