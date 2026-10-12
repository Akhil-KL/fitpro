from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk


class NutritionColumns:
    """Nutrition per `serving_size` `serving_unit` (e.g. per 100 g, per 1 piece)."""

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    serving_size: Mapped[float] = mapped_column(Float, nullable=False)
    serving_unit: Mapped[str] = mapped_column(String(20), nullable=False)  # g | ml | piece | serving
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fiber_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    # Optional: lets "2 bananas" resolve against a per-100 g entry without guessing.
    grams_per_piece: Mapped[float | None] = mapped_column(Float)


class Food(UUIDPk, Timestamps, NutritionColumns, Base):
    """Application-level food database."""

    __tablename__ = "foods"
    __table_args__ = (Index("ix_foods_name", "name"),)

    aliases: Mapped[str | None] = mapped_column(Text)  # comma-separated lowercase aliases
    source: Mapped[str] = mapped_column(String(80), default="seed", nullable=False)


class CustomFood(UUIDPk, Timestamps, NutritionColumns, Base):
    """User-specific foods."""

    __tablename__ = "custom_foods"
    __table_args__ = (Index("ix_custom_foods_user_id_name", "user_id", "name"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


class FoodLog(UUIDPk, Timestamps, Base):
    __tablename__ = "food_logs"
    __table_args__ = (
        Index("ix_food_logs_user_id_logged_at", "user_id", "logged_at"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    food_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("foods.id", ondelete="RESTRICT"))
    custom_food_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("custom_foods.id", ondelete="RESTRICT")
    )
    food_name: Mapped[str] = mapped_column(String(160), nullable=False)  # name as resolved at log time
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    meal_type: Mapped[str | None] = mapped_column(String(20))
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="chat", nullable=False)  # chat | manual
    notes: Mapped[str | None] = mapped_column(Text)

    nutrition: Mapped[FoodLogNutrition] = relationship(
        back_populates="food_log", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )


class FoodLogNutrition(UUIDPk, Base):
    """Snapshot of the nutrition actually used for the log (immune to later food DB edits)."""

    __tablename__ = "food_log_nutrition"

    food_log_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("food_logs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float] = mapped_column(Float, nullable=False)
    # e.g. "foods:per 100 g" | "custom_foods:per 1 piece" | "user_override"
    calculation_source: Mapped[str] = mapped_column(String(120), nullable=False)

    food_log: Mapped[FoodLog] = relationship(back_populates="nutrition")
