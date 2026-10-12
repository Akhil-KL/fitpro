from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import CustomFood, Food, FoodLog


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class FoodRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- application foods
    def all_foods(self) -> list[Food]:
        return list(self.db.scalars(select(Food)))

    def count_foods(self) -> int:
        return self.db.scalar(select(func.count()).select_from(Food)) or 0

    def search_foods(self, term: str, limit: int, offset: int = 0) -> tuple[list[Food], int]:
        like = f"%{_escape_like(term.lower())}%"
        cond = or_(func.lower(Food.name).like(like, escape="\\"), func.lower(Food.aliases).like(like, escape="\\"))
        total = self.db.scalar(select(func.count()).select_from(Food).where(cond)) or 0
        rows = self.db.scalars(select(Food).where(cond).order_by(func.length(Food.name), Food.name).offset(offset).limit(limit))
        return list(rows), total

    # ---- custom foods (always user-scoped)
    def custom_foods(self, user_id: uuid.UUID) -> list[CustomFood]:
        return list(self.db.scalars(select(CustomFood).where(CustomFood.user_id == user_id)))

    def custom_by_name(self, user_id: uuid.UUID, name: str) -> CustomFood | None:
        return self.db.scalar(
            select(CustomFood).where(CustomFood.user_id == user_id, func.lower(CustomFood.name) == name.lower())
        )

    def custom_get(self, user_id: uuid.UUID, food_id: uuid.UUID) -> CustomFood | None:
        return self.db.scalar(select(CustomFood).where(CustomFood.id == food_id, CustomFood.user_id == user_id))

    def search_custom(self, user_id: uuid.UUID, term: str, limit: int, offset: int = 0) -> tuple[list[CustomFood], int]:
        like = f"%{_escape_like(term.lower())}%"
        cond = (CustomFood.user_id == user_id) & func.lower(CustomFood.name).like(like, escape="\\")
        total = self.db.scalar(select(func.count()).select_from(CustomFood).where(cond)) or 0
        rows = self.db.scalars(select(CustomFood).where(cond).order_by(CustomFood.name).offset(offset).limit(limit))
        return list(rows), total

    def custom_is_referenced(self, custom_food_id: uuid.UUID) -> bool:
        return bool(self.db.scalar(select(func.count()).select_from(FoodLog).where(FoodLog.custom_food_id == custom_food_id)))

    # ---- food logs (always user-scoped)
    def log_get(self, user_id: uuid.UUID, log_id: uuid.UUID) -> FoodLog | None:
        return self.db.scalar(select(FoodLog).where(FoodLog.id == log_id, FoodLog.user_id == user_id))

    def logs_between(self, user_id: uuid.UUID, start: datetime, end: datetime) -> list[FoodLog]:
        return list(
            self.db.scalars(
                select(FoodLog)
                .where(FoodLog.user_id == user_id, FoodLog.logged_at >= start, FoodLog.logged_at < end)
                .order_by(FoodLog.logged_at)
            ).unique()
        )

    def logs_page(
        self, user_id: uuid.UUID, start: datetime | None, end: datetime | None, limit: int, offset: int
    ) -> tuple[list[FoodLog], int]:
        conds = [FoodLog.user_id == user_id]
        if start is not None:
            conds.append(FoodLog.logged_at >= start)
        if end is not None:
            conds.append(FoodLog.logged_at < end)
        total = self.db.scalar(select(func.count()).select_from(FoodLog).where(*conds)) or 0
        rows = self.db.scalars(
            select(FoodLog).where(*conds).order_by(FoodLog.logged_at.desc()).offset(offset).limit(limit)
        ).unique()
        return list(rows), total

    def recent_logs(self, user_id: uuid.UUID, since: datetime, limit: int = 20) -> list[FoodLog]:
        return list(
            self.db.scalars(
                select(FoodLog)
                .where(FoodLog.user_id == user_id, FoodLog.logged_at >= since)
                .order_by(FoodLog.created_at.desc())
                .limit(limit)
            ).unique()
        )
