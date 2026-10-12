from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WorkoutSetOut(ORMModel):
    set_number: int
    reps: int | None
    weight_kg: float | None
    duration_seconds: int | None


class WorkoutExerciseOut(ORMModel):
    id: uuid.UUID
    exercise_name: str
    order_index: int
    sets: list[WorkoutSetOut]


class WorkoutSessionOut(ORMModel):
    id: uuid.UUID
    workout_plan_day_id: uuid.UUID | None
    started_at: datetime
    completed_at: datetime | None
    notes: str | None
    exercises: list[WorkoutExerciseOut] = []
    plan_day_name: str | None = None
    total_volume_kg: float = 0


class WorkoutSessionSummary(BaseModel):
    id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    exercise_count: int
    set_count: int
    total_volume_kg: float
    exercise_names: list[str]
    plan_day_name: str | None = None


class SetIn(BaseModel):
    reps: int | None = Field(None, ge=1, le=1000)
    weight_kg: float | None = Field(None, ge=0, le=1000)
    duration_seconds: int | None = Field(None, ge=1, le=86400)


class ExerciseIn(BaseModel):
    exercise_name: str = Field(min_length=1, max_length=160)
    sets: list[SetIn] = Field(min_length=1, max_length=50)


class WorkoutCreate(BaseModel):
    started_at: datetime | None = None
    notes: str | None = Field(None, max_length=1000)
    exercises: list[ExerciseIn] = Field(default_factory=list, max_length=30)
    completed: bool = True


class PlannedExerciseOut(ORMModel):
    exercise_name: str
    sets: int | None
    target_reps: int | None
    rep_range: str | None
    target_weight: float | None
    duration_seconds: int | None
    order_index: int


class WorkoutPlanDayOut(ORMModel):
    id: uuid.UUID
    day_number: int
    name: str
    description: str | None
    exercises: list[PlannedExerciseOut]


class WorkoutPlanOut(ORMModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    source_document_id: uuid.UUID | None
    days: list[WorkoutPlanDayOut] = []


class WorkoutPlanSummary(ORMModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    day_count: int = 0


class DocumentOut(ORMModel):
    id: uuid.UUID
    file_name: str
    file_type: str
    processing_status: str
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None
    workout_plan_id: uuid.UUID | None = None


class WeightLogIn(BaseModel):
    weight_kg: float = Field(ge=20, le=400)
    logged_at: datetime | None = None


class WeightLogOut(ORMModel):
    id: uuid.UUID
    weight_kg: float
    logged_at: datetime


class WaterLogIn(BaseModel):
    amount_ml: int = Field(gt=0, le=10000)
    logged_at: datetime | None = None


class WaterLogOut(ORMModel):
    id: uuid.UUID
    amount_ml: int
    logged_at: datetime
