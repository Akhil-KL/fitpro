from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, utcnow


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    # Subject from the auth provider (Supabase user id) or "local:<uuid>" for local auth.
    auth_provider_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    # Only populated in local auth mode; Argon2 hash produced by pwdlib, never plaintext.
    password_hash: Mapped[str | None] = mapped_column(String(255))

    profile: Mapped[UserProfile | None] = relationship(back_populates="user", uselist=False)


class UserProfile(UUIDPk, Timestamps, Base):
    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120))
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(20))  # male | female | other
    ethnicity: Mapped[str | None] = mapped_column(String(80))  # optional, not used in calculations
    height_cm: Mapped[float | None] = mapped_column(Float)
    current_weight_kg: Mapped[float | None] = mapped_column(Float)
    activity_level: Mapped[str | None] = mapped_column(String(20))
    fitness_goal: Mapped[str | None] = mapped_column(String(20))
    target_weight_kg: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")


class NutritionTarget(UUIDPk, Base):
    """Target history: a new row per change, never overwritten across days."""

    __tablename__ = "nutrition_targets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calorie_target: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_target_g: Mapped[int] = mapped_column(Integer, nullable=False)
    carbs_target_g: Mapped[int] = mapped_column(Integer, nullable=False)
    fat_target_g: Mapped[int] = mapped_column(Integer, nullable=False)
    water_target_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
