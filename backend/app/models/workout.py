from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, utcnow


class WorkoutPlan(UUIDPk, Timestamps, Base):
    __tablename__ = "workout_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    days: Mapped[list[WorkoutPlanDay]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="WorkoutPlanDay.day_number"
    )


class WorkoutPlanDay(UUIDPk, Base):
    __tablename__ = "workout_plan_days"

    workout_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workout_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[WorkoutPlan] = relationship(back_populates="days")
    exercises: Mapped[list[PlannedExercise]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="PlannedExercise.order_index"
    )


class PlannedExercise(UUIDPk, Base):
    __tablename__ = "planned_exercises"

    workout_plan_day_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workout_plan_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_name: Mapped[str] = mapped_column(String(160), nullable=False)
    sets: Mapped[int | None] = mapped_column(Integer)
    target_reps: Mapped[int | None] = mapped_column(Integer)
    rep_range: Mapped[str | None] = mapped_column(String(20))  # e.g. "8-12" when a range is given
    target_weight: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    day: Mapped[WorkoutPlanDay] = relationship(back_populates="exercises")


class WorkoutSession(UUIDPk, Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (Index("ix_workout_sessions_user_id_started_at", "user_id", "started_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workout_plan_day_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workout_plan_days.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="WorkoutExercise.order_index"
    )


class WorkoutExercise(UUIDPk, Base):
    __tablename__ = "workout_exercises"

    workout_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_name: Mapped[str] = mapped_column(String(160), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped[WorkoutSession] = relationship(back_populates="exercises")
    sets: Mapped[list[WorkoutSet]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan", order_by="WorkoutSet.set_number"
    )


class WorkoutSet(UUIDPk, Base):
    __tablename__ = "workout_sets"

    workout_exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workout_exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")
