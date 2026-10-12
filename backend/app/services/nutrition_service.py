"""Food resolution, nutrition snapshots, food logs and custom foods.

Services flush but never commit: the caller (route or chat service) owns the
transaction so multi-record writes are atomic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.calculations.nutrition import (
    NutritionProfile,
    NutritionValues,
    UnitMismatch,
    default_count_unit,
    normalize_unit,
    scale_nutrition,
    to_base,
)
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.data.seed_foods import SEED_FOODS
from app.models import CustomFood, Food, FoodLog, FoodLogNutrition, User
from app.repositories.food_repository import FoodRepository
from app.schemas.ai import NutritionFacts
from app.schemas.food import CustomFoodIn, FoodLogUpdate, FoodOut
from app.services.rule_parser import singularize

FoodSource = Food | CustomFood


@dataclass
class Resolution:
    kind: str  # found | ambiguous | unknown
    food: FoodSource | None = None
    candidates: list[FoodSource] = field(default_factory=list)


def profile_of(food: FoodSource) -> NutritionProfile:
    return NutritionProfile(
        serving_size=food.serving_size,
        serving_unit=food.serving_unit,
        calories=food.calories,
        protein_g=food.protein_g,
        carbs_g=food.carbs_g,
        fat_g=food.fat_g,
        fiber_g=food.fiber_g,
        grams_per_piece=food.grams_per_piece,
    )


def food_out(food: FoodSource) -> FoodOut:
    return FoodOut(
        id=food.id, name=food.name, serving_size=food.serving_size, serving_unit=food.serving_unit,
        calories=food.calories, protein_g=food.protein_g, carbs_g=food.carbs_g, fat_g=food.fat_g,
        fiber_g=food.fiber_g, grams_per_piece=food.grams_per_piece, is_custom=isinstance(food, CustomFood),
    )


def snapshot_values(log: FoodLog) -> NutritionValues:
    n = log.nutrition
    return NutritionValues(n.calories, n.protein_g, n.carbs_g, n.fat_g, n.fiber_g)


def describe_basis(food: FoodSource) -> str:
    size = int(food.serving_size) if float(food.serving_size).is_integer() else food.serving_size
    return f"per {size} {food.serving_unit}"


def _name_variants(name: str) -> list[str]:
    n = " ".join(name.lower().strip().split())
    variants = [n, singularize(n)]
    if not n.endswith("s"):
        variants.append(n + "s")
    return list(dict.fromkeys(v for v in variants if v))


def _aliases(food: Food) -> set[str]:
    return {a.strip() for a in (food.aliases or "").lower().split(",") if a.strip()}


class NutritionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FoodRepository(db)

    # ------------------------------------------------------------- seed
    def seed_foods(self) -> int:
        if self.repo.count_foods() > 0:
            return 0
        for row in SEED_FOODS:
            self.db.add(Food(source="seed", **row))
        self.db.flush()
        return len(SEED_FOODS)

    # ------------------------------------------------------------- resolution
    def resolve(self, user_id: uuid.UUID, name: str) -> Resolution:
        variants = _name_variants(name)
        for v in variants:  # 1) the user's own custom foods win
            if cf := self.repo.custom_by_name(user_id, v):
                return Resolution("found", cf)

        candidates: dict[uuid.UUID, FoodSource] = {}
        for v in variants:
            foods, _ = self.repo.search_foods(v, limit=25)
            for f in foods:
                if f.name.lower() == v or v in _aliases(f):  # 2) exact name / alias
                    return Resolution("found", f)
                candidates[f.id] = f
            customs, _ = self.repo.search_custom(user_id, v, limit=10)
            for c in customs:
                candidates[c.id] = c

        cands = list(candidates.values())
        if len(cands) == 1:
            return Resolution("found", cands[0])
        if cands:
            # Prefer candidates whose name starts with the query ("rice" -> "rice (cooked)").
            starts = [c for c in cands if any(c.name.lower().startswith(v) for v in variants)]
            if len(starts) == 1:
                return Resolution("found", starts[0])
            return Resolution("ambiguous", candidates=sorted(cands, key=lambda c: len(c.name))[:5])
        return Resolution("unknown")

    def get_source(self, user_id: uuid.UUID, food_id: str | None, custom_food_id: str | None) -> FoodSource | None:
        if custom_food_id:
            return self.repo.custom_get(user_id, uuid.UUID(custom_food_id))
        if food_id:
            return self.db.get(Food, uuid.UUID(food_id))
        return None

    @staticmethod
    def effective_unit(food: FoodSource, quantity: float | None, unit: str | None) -> str | None:
        """Canonical unit for the log, or None when a bare count can't apply to this food."""
        if unit:
            return normalize_unit(unit)
        return default_count_unit(profile_of(food))

    # ------------------------------------------------------------- logs
    def create_log(
        self,
        user: User,
        food: FoodSource,
        quantity: float,
        unit: str,
        *,
        logged_at: datetime,
        meal_type: str | None = None,
        source: str = "chat",
        notes: str | None = None,
    ) -> FoodLog:
        values = scale_nutrition(profile_of(food), quantity, unit)  # may raise UnitMismatch
        log = FoodLog(
            user_id=user.id,
            food_id=food.id if isinstance(food, Food) else None,
            custom_food_id=food.id if isinstance(food, CustomFood) else None,
            food_name=food.name,
            quantity=quantity,
            unit=unit,
            meal_type=meal_type,
            logged_at=logged_at,
            source=source,
            notes=notes,
        )
        log.nutrition = FoodLogNutrition(
            calories=values.calories, protein_g=values.protein_g, carbs_g=values.carbs_g,
            fat_g=values.fat_g, fiber_g=values.fiber_g,
            calculation_source=f"{'custom_foods' if isinstance(food, CustomFood) else 'foods'}:{describe_basis(food)}",
        )
        self.db.add(log)
        self.db.flush()
        return log

    def update_log(self, user: User, log: FoodLog, upd: FoodLogUpdate) -> FoodLog:
        if log.user_id != user.id:
            raise NotFound("Food log not found.")
        new_q = upd.quantity if upd.quantity is not None else log.quantity
        new_u = upd.unit or log.unit
        quantity_changed = new_q != log.quantity or new_u != log.unit

        if upd.nutrition_override is not None:
            o = upd.nutrition_override
            log.nutrition.calories, log.nutrition.protein_g = o.calories, o.protein_g
            log.nutrition.carbs_g, log.nutrition.fat_g, log.nutrition.fiber_g = o.carbs_g, o.fat_g, o.fiber_g
            log.nutrition.calculation_source = "user_override"
        elif quantity_changed:
            try:
                old_base, old_dim = to_base(log.quantity, log.unit)
                new_base, new_dim = to_base(new_q, new_u)
            except UnitMismatch as exc:
                raise ValidationFailed(f"Unsupported unit: {new_u}") from exc
            if old_dim == new_dim:
                # Scale the stored snapshot, so later food-database edits never leak into history.
                scaled = snapshot_values(log).scaled(new_base / old_base)
            else:
                food = self._log_source(log)
                if food is None:
                    raise ValidationFailed("The original food no longer exists; keep the same unit.")
                try:
                    scaled = scale_nutrition(profile_of(food), new_q, new_u)
                except UnitMismatch as exc:
                    raise ValidationFailed(f"Can't convert {new_u} for {log.food_name}.") from exc
                log.nutrition.calculation_source = f"recalculated:{describe_basis(food)}"
            n = log.nutrition
            n.calories, n.protein_g, n.carbs_g = scaled.calories, scaled.protein_g, scaled.carbs_g
            n.fat_g, n.fiber_g = scaled.fat_g, scaled.fiber_g

        log.quantity, log.unit = new_q, new_u
        if upd.meal_type is not None:
            log.meal_type = upd.meal_type
        if upd.notes is not None:
            log.notes = upd.notes
        self.db.flush()
        return log

    def delete_log(self, user: User, log: FoodLog) -> None:
        if log.user_id != user.id:
            raise NotFound("Food log not found.")
        self.db.delete(log)
        self.db.flush()

    def _log_source(self, log: FoodLog) -> FoodSource | None:
        if log.custom_food_id:
            return self.repo.custom_get(log.user_id, log.custom_food_id)
        if log.food_id:
            return self.db.get(Food, log.food_id)
        return None

    # ------------------------------------------------------------- custom foods
    def create_custom(self, user: User, data: CustomFoodIn) -> CustomFood:
        if self.repo.custom_by_name(user.id, data.name):
            raise Conflict(f"You already have a custom food called '{data.name}'.")
        cf = CustomFood(user_id=user.id, **data.model_dump())
        self.db.add(cf)
        self.db.flush()
        return cf

    def update_custom(self, user: User, food_id: uuid.UUID, data: CustomFoodIn) -> CustomFood:
        cf = self.repo.custom_get(user.id, food_id)
        if cf is None:
            raise NotFound("Custom food not found.")
        other = self.repo.custom_by_name(user.id, data.name)
        if other is not None and other.id != cf.id:
            raise Conflict(f"You already have a custom food called '{data.name}'.")
        for k, v in data.model_dump().items():
            setattr(cf, k, v)
        self.db.flush()  # historical logs keep their own snapshots
        return cf

    def delete_custom(self, user: User, food_id: uuid.UUID) -> None:
        cf = self.repo.custom_get(user.id, food_id)
        if cf is None:
            raise NotFound("Custom food not found.")
        if self.repo.custom_is_referenced(cf.id):
            raise Conflict("This food is used by past logs and can't be deleted. Edit it instead.")
        self.db.delete(cf)
        self.db.flush()

    @staticmethod
    def custom_from_facts(name: str, facts: NutritionFacts) -> CustomFoodIn:
        unit = normalize_unit(facts.basis_unit) if facts.basis_unit else None
        if unit not in ("g", "ml", "piece", "serving"):
            raise ValidationFailed("Nutrition must be given per g, ml, piece or serving.")
        if facts.calories is None:
            raise ValidationFailed("Calories are required.")
        return CustomFoodIn(
            name=name,
            serving_size=facts.basis_quantity or 1,
            serving_unit=unit,  # type: ignore[arg-type]
            calories=facts.calories,
            protein_g=facts.protein_g or 0,
            carbs_g=facts.carbs_g or 0,
            fat_g=facts.fat_g or 0,
            fiber_g=facts.fiber_g or 0,
        )

    def upsert_custom_from_facts(self, user: User, name: str, facts: NutritionFacts) -> tuple[CustomFood, bool]:
        data = self.custom_from_facts(name, facts)
        existing = self.repo.custom_by_name(user.id, data.name)
        if existing:
            return self.update_custom(user, existing.id, data), False
        return self.create_custom(user, data), True

    # ------------------------------------------------------------- search
    def search(self, user_id: uuid.UUID, q: str, page: int, page_size: int) -> tuple[list[FoodOut], int]:
        """Custom foods first, then the application database."""
        start = (page - 1) * page_size
        customs, c_total = self.repo.search_custom(user_id, q, limit=page_size, offset=start)
        remaining = page_size - len(customs)
        foods: list[Food] = []
        f_total = self.repo.search_foods(q, limit=1)[1]
        if remaining > 0:
            foods, _ = self.repo.search_foods(q, limit=remaining, offset=max(0, start - c_total))
        return [food_out(c) for c in customs] + [food_out(f) for f in foods], c_total + f_total
