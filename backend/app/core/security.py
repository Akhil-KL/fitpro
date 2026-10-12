"""Authentication primitives. Uses established libraries only (pwdlib/Argon2, PyJWT)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt

from app.config import Settings, get_settings
from app.core.errors import Unauthorized


@lru_cache
def _password_hasher():
    from pwdlib import PasswordHash

    return PasswordHash.recommended()  # Argon2id


def hash_password(password: str) -> str:
    return _password_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher().verify(password, password_hash)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, settings: Settings | None = None) -> tuple[str, int]:
    s = settings or get_settings()
    expires = s.access_token_minutes * 60
    payload = {"sub": subject, "typ": "access", "iat": _now(), "exp": _now() + timedelta(seconds=expires)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), expires


def password_fingerprint(password_hash: str | None) -> str:
    """Binds a reset token to the current hash, so it stops working once the password changes."""
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def create_reset_token(subject: str, password_hash: str | None, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    payload = {
        "sub": subject,
        "typ": "reset",
        "pwf": password_fingerprint(password_hash),
        "iat": _now(),
        "exp": _now() + timedelta(minutes=s.password_reset_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_local_token(token: str, expected_type: str = "access", settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    try:
        claims = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Session expired. Please log in again.") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid authentication token.") from exc
    if claims.get("typ") != expected_type:
        raise Unauthorized("Invalid authentication token.")
    return claims


@lru_cache
def _jwks_client(url: str):
    return jwt.PyJWKClient(url)


def decode_supabase_token(token: str, settings: Settings | None = None) -> dict:
    """Validate a Supabase Auth access token (HS256 project secret, or asymmetric keys via JWKS)."""
    s = settings or get_settings()
    try:
        if s.supabase_jwt_secret:
            return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience=s.supabase_jwt_audience)
        if s.supabase_url:
            key = _jwks_client(f"{s.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json").get_signing_key_from_jwt(token)
            return jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience=s.supabase_jwt_audience)
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Session expired. Please log in again.") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid authentication token.") from exc
    raise Unauthorized("Supabase auth is not configured on the server.")
