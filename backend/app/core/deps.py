"""FastAPI dependencies: DB session and the authenticated user (never taken from the client body)."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import RateLimited, Unauthorized
from app.core.security import decode_local_token, decode_supabase_token
from app.db.session import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User:
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise Unauthorized("Authentication required.")
    settings = get_settings()

    if settings.auth_mode == "supabase":
        claims = decode_supabase_token(creds.credentials)
        sub = str(claims.get("sub") or "")
        if not sub:
            raise Unauthorized("Invalid authentication token.")
        user = db.scalar(select(User).where(User.auth_provider_id == sub))
        if user is None:  # first request from a Supabase user: provision the local row
            user = User(auth_provider_id=sub, email=claims.get("email"))
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                user = db.scalar(select(User).where(User.auth_provider_id == sub))
        if user is None:
            raise Unauthorized("Account not found.")
        return user

    claims = decode_local_token(creds.credentials)
    try:
        user_id = uuid.UUID(claims["sub"])
    except (ValueError, KeyError) as exc:
        raise Unauthorized("Invalid authentication token.") from exc
    user = db.get(User, user_id)
    if user is None:
        raise Unauthorized("Account not found.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class SlidingWindowLimiter:
    """Small in-process limiter (per user). Swap for Redis when running multiple instances."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise RateLimited("Too many messages. Please wait a moment.")
        q.append(now)


chat_limiter = SlidingWindowLimiter()


def chat_rate_limit(user: CurrentUser, request: Request) -> None:
    chat_limiter.check(f"chat:{user.id}", get_settings().chat_rate_limit_per_minute)
