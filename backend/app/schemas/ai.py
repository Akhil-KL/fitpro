"""Structured output of the AI parsing layer.

Every parser (OpenAI or rule-based) must produce a `ParsedMessage`; it is
validated here before any business logic runs. The parser only extracts what
the user said: quantities and nutrition values are null when not stated.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intent = Literal[
    "food_log",
    "food_correction",
    "custom_food_create",
    "custom_food_update",
    "workout_log",
    "workout_correction",
    "weight_log",
    "water_log",
    "daily_summary",
    "nutrition_query",
    "workout_query",
    "progress_query",
    "goal_query",
    "general_fitness_query",
    "clarification",
    "unknown",
]
INTENTS: tuple[str, ...] = Intent.__args__  # type: ignore[attr-defined]

Meal = Literal["breakfast", "lunch", "dinner", "snack"]
Metric = Literal["calories", "protein", "carbs", "fat", "fiber", "water", "weight", "workout"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class FoodItem(_Strict):
    food_name: str = Field(min_length=1, max_length=160)
    quantity: float | None = Field(default=None, gt=0, le=100000)
    unit: str | None = Field(default=None, max_length=20)

    @field_validator("food_name")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class ExerciseEntry(_Strict):
    exercise_name: str = Field(min_length=1, max_length=160)
    sets: int | None = Field(default=None, ge=1, le=50)
    reps: int | None = Field(default=None, ge=1, le=1000)
    weight_kg: float | None = Field(default=None, ge=0, le=1000)
    duration_seconds: int | None = Field(default=None, ge=1, le=86400)


class NutritionFacts(_Strict):
    """Nutrition the user supplied, per `basis_quantity` `basis_unit`."""

    basis_quantity: float | None = Field(default=None, gt=0, le=100000)
    basis_unit: str | None = None
    calories: float | None = Field(default=None, ge=0, le=20000)
    protein_g: float | None = Field(default=None, ge=0, le=2000)
    carbs_g: float | None = Field(default=None, ge=0, le=2000)
    fat_g: float | None = Field(default=None, ge=0, le=2000)
    fiber_g: float | None = Field(default=None, ge=0, le=2000)

    def has_values(self) -> bool:
        return self.calories is not None


class Correction(_Strict):
    target_name: str | None = None  # "rice", "bench press"; None = most recent entry
    quantity: float | None = Field(default=None, gt=0, le=100000)
    unit: str | None = None
    nutrition_override: NutritionFacts | None = None
    sets: int | None = Field(default=None, ge=1, le=50)
    reps: int | None = Field(default=None, ge=1, le=1000)
    weight_kg: float | None = Field(default=None, ge=0, le=1000)
    delete: bool = False


class ParsedMessage(_Strict):
    intent: Intent
    items: list[FoodItem] = Field(default_factory=list, max_length=25)
    meal: Meal | None = None
    exercises: list[ExerciseEntry] = Field(default_factory=list, max_length=25)
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    amount_ml: float | None = Field(default=None, gt=0, le=10000)
    custom_food_name: str | None = Field(default=None, max_length=160)
    nutrition: NutritionFacts | None = None
    correction: Correction | None = None
    query_metric: Metric | None = None
    day_offset: int = Field(default=0, ge=-7, le=0)  # 0 = today, -1 = yesterday
    selection: int | None = Field(default=None, ge=1, le=20)  # reply picking option N
    clarification_question: str | None = None
    reply: str | None = None  # free text answer, only for general_fitness_query


# --- schema used for OpenAI Structured Outputs (strict mode: every key required, nullable) ---
class LLMFoodItem(BaseModel):
    food_name: str
    quantity: float | None
    unit: str | None


class LLMExercise(BaseModel):
    exercise_name: str
    sets: int | None
    reps: int | None
    weight_kg: float | None
    duration_seconds: int | None


class LLMNutrition(BaseModel):
    basis_quantity: float | None
    basis_unit: str | None
    calories: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    fiber_g: float | None


class LLMCorrection(BaseModel):
    target_name: str | None
    quantity: float | None
    unit: str | None
    nutrition_override: LLMNutrition | None
    sets: int | None
    reps: int | None
    weight_kg: float | None
    delete: bool


class LLMParsedMessage(BaseModel):
    intent: Intent
    items: list[LLMFoodItem]
    meal: Meal | None
    exercises: list[LLMExercise]
    weight_kg: float | None
    amount_ml: float | None
    custom_food_name: str | None
    nutrition: LLMNutrition | None
    correction: LLMCorrection | None
    query_metric: Metric | None
    day_offset: int
    selection: int | None
    clarification_question: str | None
    reply: str | None
