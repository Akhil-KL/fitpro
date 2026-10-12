from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel

Gender = Literal["male", "female", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
FitnessGoal = Literal["lose_fat", "maintain", "gain_muscle", "recomp"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str | None
    created_at: datetime
    has_profile: bool = False


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    age: int | None = Field(None, ge=13, le=110)
    gender: Gender | None = None
    ethnicity: str | None = Field(None, max_length=80)
    height_cm: float | None = Field(None, ge=100, le=250)
    current_weight_kg: float | None = Field(None, ge=25, le=350)
    activity_level: ActivityLevel | None = None
    fitness_goal: FitnessGoal | None = None
    target_weight_kg: float | None = Field(None, ge=25, le=350)
    timezone: str | None = Field(None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def valid_tz(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown timezone") from exc
        return v


class ProfileOut(ORMModel):
    name: str | None
    age: int | None
    gender: str | None
    ethnicity: str | None
    height_cm: float | None
    current_weight_kg: float | None
    activity_level: str | None
    fitness_goal: str | None
    target_weight_kg: float | None
    timezone: str
    is_complete: bool = False
    bmi: float | None = None
    bmi_category: str | None = None
    bmr: float | None = None
    tdee: float | None = None


class TargetsOut(ORMModel):
    calorie_target: int
    protein_target_g: int
    carbs_target_g: int
    fat_target_g: int
    water_target_ml: int
    effective_from: date
