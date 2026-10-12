from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.calculations.nutrition import normalize_unit
from app.schemas.common import ORMModel

ServingUnit = Literal["g", "ml", "piece", "serving"]
Meal = Literal["breakfast", "lunch", "dinner", "snack"]


class FoodOut(BaseModel):
    id: uuid.UUID
    name: str
    serving_size: float
    serving_unit: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    grams_per_piece: float | None = None
    is_custom: bool


class CustomFoodIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    serving_size: float = Field(gt=0, le=10000)
    serving_unit: ServingUnit
    calories: float = Field(ge=0, le=20000)
    protein_g: float = Field(0, ge=0, le=2000)
    carbs_g: float = Field(0, ge=0, le=2000)
    fat_g: float = Field(0, ge=0, le=2000)
    fiber_g: float = Field(0, ge=0, le=2000)
    grams_per_piece: float | None = Field(None, gt=0, le=5000)

    @field_validator("name")
    @classmethod
    def norm_name(cls, v: str) -> str:
        return " ".join(v.strip().lower().split())


class NutritionOut(ORMModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    calculation_source: str


class FoodLogOut(ORMModel):
    id: uuid.UUID
    food_name: str
    food_id: uuid.UUID | None
    custom_food_id: uuid.UUID | None
    quantity: float
    unit: str
    meal_type: str | None
    logged_at: datetime
    source: str
    notes: str | None
    nutrition: NutritionOut | None


class NutritionOverride(BaseModel):
    calories: float = Field(ge=0, le=20000)
    protein_g: float = Field(0, ge=0, le=2000)
    carbs_g: float = Field(0, ge=0, le=2000)
    fat_g: float = Field(0, ge=0, le=2000)
    fiber_g: float = Field(0, ge=0, le=2000)


class FoodLogUpdate(BaseModel):
    quantity: float | None = Field(None, gt=0, le=100000)
    unit: str | None = None
    meal_type: Meal | None = None
    notes: str | None = Field(None, max_length=500)
    nutrition_override: NutritionOverride | None = None

    @field_validator("unit")
    @classmethod
    def norm_unit(cls, v: str | None) -> str | None:
        return normalize_unit(v) if v else v
