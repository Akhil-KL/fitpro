"""Deterministic nutrition scaling and unit handling.

Canonical units: g, ml, piece, serving. A food's nutrition is stored per
`serving_size` `serving_unit`; a log of `quantity` `unit` is scaled against it.
Units that cannot be converted without guessing raise `UnitMismatch` so the
caller can ask the user instead of inventing a quantity.
"""

from __future__ import annotations

from dataclasses import dataclass

MASS_TO_G = {"g": 1.0, "kg": 1000.0, "mg": 0.001, "oz": 28.3495, "lb": 453.592}
VOLUME_TO_ML = {"ml": 1.0, "l": 1000.0, "cup": 240.0, "tbsp": 15.0, "tsp": 5.0}
COUNT_UNITS = {"piece", "serving"}

UNIT_ALIASES = {
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g", "gr": "g",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
    "mg": "mg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l", "ltr": "l",
    "cup": "cup", "cups": "cup",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "piece": "piece", "pieces": "piece", "pc": "piece", "pcs": "piece", "whole": "piece",
    "slice": "piece", "slices": "piece", "scoop": "serving", "scoops": "serving",
    "serving": "serving", "servings": "serving", "packet": "serving", "packets": "serving",
    "package": "serving", "pack": "serving",
}

# Containers whose size is unknown: never guessed.
VAGUE_UNITS = {"bowl", "bowls", "plate", "plates", "handful", "handfuls", "glass", "glasses", "katori"}


class UnitMismatch(ValueError):
    """The logged unit cannot be converted to the food's serving basis without guessing."""


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    u = unit.strip().lower().rstrip(".")
    if u in VAGUE_UNITS:
        return "vague"
    return UNIT_ALIASES.get(u, u)


def to_base(quantity: float, unit: str) -> tuple[float, str]:
    """Convert to the base unit of its dimension: g, ml, or the count unit itself."""
    if unit in MASS_TO_G:
        return quantity * MASS_TO_G[unit], "g"
    if unit in VOLUME_TO_ML:
        return quantity * VOLUME_TO_ML[unit], "ml"
    if unit in COUNT_UNITS:
        return quantity, unit
    raise UnitMismatch(f"unsupported unit: {unit}")


@dataclass(frozen=True)
class NutritionProfile:
    serving_size: float
    serving_unit: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    grams_per_piece: float | None = None


@dataclass(frozen=True)
class NutritionValues:
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float

    def scaled(self, factor: float) -> NutritionValues:
        return NutritionValues(
            calories=round(self.calories * factor, 2),
            protein_g=round(self.protein_g * factor, 2),
            carbs_g=round(self.carbs_g * factor, 2),
            fat_g=round(self.fat_g * factor, 2),
            fiber_g=round(self.fiber_g * factor, 2),
        )

    def __add__(self, other: NutritionValues) -> NutritionValues:
        return NutritionValues(
            calories=round(self.calories + other.calories, 2),
            protein_g=round(self.protein_g + other.protein_g, 2),
            carbs_g=round(self.carbs_g + other.carbs_g, 2),
            fat_g=round(self.fat_g + other.fat_g, 2),
            fiber_g=round(self.fiber_g + other.fiber_g, 2),
        )


ZERO = NutritionValues(0, 0, 0, 0, 0)


def scale_factor(profile: NutritionProfile, quantity: float, unit: str) -> float:
    """How many 'servings' of the profile the logged amount represents."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if profile.serving_size <= 0:
        raise ValueError("serving size must be positive")
    log_q, log_dim = to_base(quantity, unit)
    srv_q, srv_dim = to_base(profile.serving_size, profile.serving_unit)

    if log_dim == srv_dim:
        return log_q / srv_q
    # piece <-> grams only when the food explicitly defines a piece weight
    if profile.grams_per_piece:
        if log_dim == "piece" and srv_dim == "g":
            return (log_q * profile.grams_per_piece) / srv_q
        if log_dim == "g" and srv_dim == "piece":
            return (log_q / profile.grams_per_piece) / srv_q
    raise UnitMismatch(f"cannot convert {unit} to {profile.serving_unit}")


def scale_nutrition(profile: NutritionProfile, quantity: float, unit: str) -> NutritionValues:
    """scaled_value = nutrition_per_serving × logged_amount / serving_size"""
    factor = scale_factor(profile, quantity, unit)
    base = NutritionValues(profile.calories, profile.protein_g, profile.carbs_g, profile.fat_g, profile.fiber_g)
    return base.scaled(factor)


def default_count_unit(profile: NutritionProfile) -> str | None:
    """Unit to use when the user gave a bare count ('3 eggs'), or None if a count is meaningless."""
    if profile.serving_unit in COUNT_UNITS:
        return profile.serving_unit
    if profile.grams_per_piece:
        return "piece"
    return None


def macro_distribution(protein_g: float, carbs_g: float, fat_g: float) -> dict[str, float]:
    """Share of macro *calories* (4/4/9 kcal per g), in percent. Sums to 100 when any macro > 0."""
    p, c, f = protein_g * 4, carbs_g * 4, fat_g * 9
    total = p + c + f
    if total <= 0:
        return {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
    return {
        "protein": round(p / total * 100, 1),
        "carbs": round(c / total * 100, 1),
        "fat": round(f / total * 100, 1),
    }
