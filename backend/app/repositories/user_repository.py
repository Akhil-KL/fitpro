from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NutritionTarget, User, UserProfile


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def profile(self, user_id: uuid.UUID) -> UserProfile | None:
        return self.db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))

    def active_targets(self, user_id: uuid.UUID, on: date | None = None) -> NutritionTarget | None:
        stmt = select(NutritionTarget).where(NutritionTarget.user_id == user_id)
        if on is not None:
            stmt = stmt.where(NutritionTarget.effective_from <= on)
        stmt = stmt.order_by(NutritionTarget.effective_from.desc(), NutritionTarget.created_at.desc()).limit(1)
        return self.db.scalar(stmt)

    def target_on_exact(self, user_id: uuid.UUID, day: date) -> NutritionTarget | None:
        return self.db.scalar(
            select(NutritionTarget).where(NutritionTarget.user_id == user_id, NutritionTarget.effective_from == day)
        )

    def target_history(self, user_id: uuid.UUID) -> list[NutritionTarget]:
        return list(
            self.db.scalars(
                select(NutritionTarget).where(NutritionTarget.user_id == user_id).order_by(NutritionTarget.effective_from)
            )
        )
