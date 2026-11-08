"""Cryptography for authentication: passwords, PASETO tokens and TOTP.

- Passwords: Argon2id (argon2-cffi's RFC 9106 defaults), rehashed on sign-in
  when the parameters change.
- Tokens: PASETO v4.local (XChaCha20 encryption + BLAKE2b MAC), so claims are
  both tamper-proof and unreadable to clients. Each token's purpose is bound in
  as the implicit assertion, so an MFA-step token can't be used as a session.
- TOTP secrets: encrypted at rest with AES-256-GCM, bound to the user id.

The token key and the TOTP key are both derived from AUTH_SECRET_KEY with HKDF.
"""

import base64
import json
import logging
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

import pyotp
import segno
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pyseto import Key, Paseto
from pyseto.exceptions import PysetoError

from . import config

log = logging.getLogger(__name__)


def _master_secret() -> bytes:
    if config.AUTH_SECRET_KEY:
        secret = config.AUTH_SECRET_KEY.encode()
        if len(secret) < 32:
            raise RuntimeError("AUTH_SECRET_KEY must be at least 32 characters")
        return secret
    path = Path(config.AUTH_SECRET_FILE)
    if not path.exists():
        log.warning("AUTH_SECRET_KEY is not set: generating a key in %s", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL: if two processes start at once, one creates it and the other reads it.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_urlsafe(48))
    secret = path.read_text().strip().encode()
    if len(secret) < 32:
        raise RuntimeError(f"{path} must hold at least 32 characters")
    return secret


def _derive(master: bytes, purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"pickleball-league " + purpose).derive(
        master
    )


_MASTER = _master_secret()
_TOKEN_KEY = Key.new(version=4, purpose="local", key=_derive(_MASTER, b"paseto v4.local"))
_TOTP_KEY = AESGCM(_derive(_MASTER, b"totp aes-256-gcm"))
del _MASTER


# --- Passwords ------------------------------------------------------------------

_hasher = PasswordHasher()
# Verified against when the account doesn't exist, so a wrong email takes as
# long as a wrong password (no account enumeration by timing).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# --- Tokens -----------------------------------------------------------------------

ACCESS = "access"
MFA = "mfa"


class InvalidToken(Exception):
    pass


def issue_token(purpose: str, user_id: int, token_version: int, ttl: int) -> tuple[str, dict[str, Any]]:
    """A PASETO v4.local token for this purpose. Returns (token, claims)."""
    claims = {"sub": str(user_id), "ver": token_version, "jti": uuid.uuid4().hex}
    token = Paseto.new(exp=ttl, include_iat=True).encode(
        _TOKEN_KEY, claims, implicit_assertion=purpose.encode(), serializer=json
    )
    decoded = Paseto.new().decode(_TOKEN_KEY, token, implicit_assertion=purpose.encode(), deserializer=json)
    return token.decode(), decoded.payload


def decode_token(purpose: str, token: str) -> dict[str, Any]:
    """Claims of a valid, unexpired token for this purpose; InvalidToken otherwise."""
    try:
        decoded = Paseto.new().decode(
            _TOKEN_KEY, token, implicit_assertion=purpose.encode(), deserializer=json
        )
    except (PysetoError, ValueError):
        raise InvalidToken from None
    payload = decoded.payload
    if not isinstance(payload, dict) or not {"sub", "ver", "jti", "exp"} <= payload.keys():
        raise InvalidToken
    return payload


# --- TOTP (RFC 6238: 6 digits, 30 s, SHA-1, as authenticator apps expect) --------


def new_totp_secret() -> str:
    return pyotp.random_base32(length=32)  # 160 bits


def encrypt_totp_secret(secret: str, user_id: int) -> str:
    nonce = os.urandom(12)
    sealed = _TOTP_KEY.encrypt(nonce, secret.encode(), f"user:{user_id}".encode())
    return base64.b64encode(nonce + sealed).decode()


def decrypt_totp_secret(stored: str, user_id: int) -> str:
    raw = base64.b64decode(stored)
    return _TOTP_KEY.decrypt(raw[:12], raw[12:], f"user:{user_id}".encode()).decode()


def totp_provisioning(secret: str, account: str) -> tuple[str, str]:
    """The otpauth:// URI for authenticator apps, and the same as a QR code
    (an SVG data: URI, for an <img>)."""
    uri = pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=config.APP_NAME)
    qr = segno.make(uri, error="m").svg_data_uri(scale=5, dark="#000", light="#fff")
    return uri, qr


class ReusedCode(Exception):
    """A correct code that has already been used (TOTP codes are single-use)."""


def verify_totp(secret: str, code: str, last_step: int | None) -> int | None:
    """The time step the code is valid for (allowing one step of clock drift),
    or None if it's wrong. A correct code at or before ``last_step`` has been
    used already: ReusedCode."""
    code = code.strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return None
    totp = pyotp.TOTP(secret)
    now = int(time.time()) // totp.interval
    for step in (now - 1, now, now + 1):
        if secrets.compare_digest(totp.generate_otp(step), code):
            if last_step is not None and step <= last_step:
                raise ReusedCode
            return step
    return None
