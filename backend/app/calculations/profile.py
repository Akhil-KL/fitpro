"""Deterministic profile calculations: BMI, BMR, TDEE and daily targets.

Formulas
--------
* BMI  = weight_kg / height_m^2
* BMR  = Mifflin-St Jeor: 10*kg + 6.25*cm - 5*age + s, s = +5 (male), -161 (female),
         -78 (other/unspecified: midpoint of the two constants)
* TDEE = BMR * activity multiplier
* Calories: TDEE adjusted by goal, never below a safety floor
* Protein: g per kg bodyweight by goal
* Fat: 25 % of calories; Carbs: the remaining calories
* Water: 35 ml per kg bodyweight
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Gender = Literal["male", "female", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
FitnessGoal = Literal["lose_fat", "maintain", "gain_muscle", "recomp"]

ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_CALORIE_ADJUSTMENT: dict[str, int] = {
    "lose_fat": -500,
    "maintain": 0,
    "gain_muscle": 300,
    "recomp": -200,
}

PROTEIN_G_PER_KG: dict[str, float] = {
    "lose_fat": 2.0,
    "maintain": 1.6,
    "gain_muscle": 1.8,
    "recomp": 2.0,
}

FAT_CALORIE_SHARE = 0.25
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9
WATER_ML_PER_KG = 35
CALORIE_FLOOR = {"male": 1500, "female": 1200, "other": 1350}


def bmi(weight_kg: float, height_cm: float) -> float:
    if weight_kg <= 0 or height_cm <= 0:
        raise ValueError("weight and height must be positive")
    h = height_cm / 100
    return round(weight_kg / (h * h), 1)


def bmi_category(value: float) -> str:
    if value < 18.5:
        return "underweight"
    if value < 25:
        return "normal"
    if value < 30:
        return "overweight"
    return "obese"


def bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError("weight, height and age must be positive")
    s = {"male": 5, "female": -161}.get(gender, -78)
    return round(10 * weight_kg + 6.25 * height_cm - 5 * age + s, 1)


def tdee(bmr_value: float, activity_level: str) -> float:
    try:
        return round(bmr_value * ACTIVITY_MULTIPLIERS[activity_level], 1)
    except KeyError as exc:
        raise ValueError(f"unknown activity level: {activity_level}") from exc


def calorie_target(tdee_value: float, goal: str, gender: str) -> int:
    if goal not in GOAL_CALORIE_ADJUSTMENT:
        raise ValueError(f"unknown goal: {goal}")
    floor = CALORIE_FLOOR.get(gender, CALORIE_FLOOR["other"])
    return int(round(max(tdee_value + GOAL_CALORIE_ADJUSTMENT[goal], floor)))


def protein_target(weight_kg: float, goal: str) -> int:
    if goal not in PROTEIN_G_PER_KG:
        raise ValueError(f"unknown goal: {goal}")
    return int(round(weight_kg * PROTEIN_G_PER_KG[goal]))


def macro_targets(calories: int, protein_g: int) -> tuple[int, int]:
    """Return (carbs_g, fat_g) given calorie and protein targets."""
    fat_g = calories * FAT_CALORIE_SHARE / KCAL_PER_G_FAT
    remaining = calories - protein_g * KCAL_PER_G_PROTEIN - fat_g * KCAL_PER_G_FAT
    carbs_g = max(remaining, 0) / KCAL_PER_G_CARB
    return int(round(carbs_g)), int(round(fat_g))


def water_target(weight_kg: float) -> int:
    return int(round(weight_kg * WATER_ML_PER_KG / 50) * 50)  # round to nearest 50 ml


@dataclass(frozen=True)
class TargetResult:
    bmi: float
    bmi_category: str
    bmr: float
    tdee: float
    calorie_target: int
    protein_target_g: int
    carbs_target_g: int
    fat_target_g: int
    water_target_ml: int


def compute_targets(
    *, weight_kg: float, height_cm: float, age: int, gender: str, activity_level: str, goal: str
) -> TargetResult:
    b = bmr(weight_kg, height_cm, age, gender)
    t = tdee(b, activity_level)
    cals = calorie_target(t, goal, gender)
    protein = protein_target(weight_kg, goal)
    carbs, fat = macro_targets(cals, protein)
    bmi_value = bmi(weight_kg, height_cm)
    return TargetResult(
        bmi=bmi_value,
        bmi_category=bmi_category(bmi_value),
        bmr=b,
        tdee=t,
        calorie_target=cals,
        protein_target_g=protein,
        carbs_target_g=carbs,
        fat_target_g=fat,
        water_target_ml=water_target(weight_kg),
    )
