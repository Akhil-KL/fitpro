import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.calculations.aggregation import get_zone, local_day_bounds, local_range_bounds
from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotFound, ValidationFailed
from app.repositories.food_repository import FoodRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import Page
from app.schemas.food import CustomFoodIn, FoodLogOut, FoodLogUpdate, FoodOut
from app.services.nutrition_service import NutritionService, food_out

router = APIRouter(tags=["foods"])

PageQ = Annotated[int, Query(ge=1)]
SizeQ = Annotated[int, Query(ge=1, le=100)]


@router.get("/foods/search", response_model=Page[FoodOut])
def search_foods(user: CurrentUser, db: DbSession, q: Annotated[str, Query(min_length=1, max_length=80)],
                 page: PageQ = 1, page_size: SizeQ = 20) -> Page[FoodOut]:
    items, total = NutritionService(db).search(user.id, q.strip(), page, page_size)
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/foods/custom", response_model=list[FoodOut])
def list_custom_foods(user: CurrentUser, db: DbSession) -> list[FoodOut]:
    return [food_out(f) for f in sorted(FoodRepository(db).custom_foods(user.id), key=lambda f: f.name)]


@router.post("/foods/custom", response_model=FoodOut, status_code=201)
def create_custom_food(body: CustomFoodIn, user: CurrentUser, db: DbSession) -> FoodOut:
    cf = NutritionService(db).create_custom(user, body)
    db.commit()
    return food_out(cf)


@router.put("/foods/custom/{food_id}", response_model=FoodOut)
def update_custom_food(food_id: uuid.UUID, body: CustomFoodIn, user: CurrentUser, db: DbSession) -> FoodOut:
    cf = NutritionService(db).update_custom(user, food_id, body)
    db.commit()
    return food_out(cf)


@router.delete("/foods/custom/{food_id}", status_code=204)
def delete_custom_food(food_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    NutritionService(db).delete_custom(user, food_id)
    db.commit()
    return Response(status_code=204)


@router.get("/food-logs", response_model=Page[FoodLogOut])
def list_food_logs(
    user: CurrentUser, db: DbSession,
    day: Annotated[date | None, Query(alias="date")] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    page: PageQ = 1, page_size: SizeQ = 50,
) -> Page[FoodLogOut]:
    profile = UserRepository(db).profile(user.id)
    tz = get_zone(profile.timezone if profile else None)
    start = end = None
    if day is not None:
        start, end = local_day_bounds(day, tz)
    elif from_ or to:
        if from_ and to and from_ > to:
            raise ValidationFailed("'from' must be on or before 'to'.")
        lo, hi = local_range_bounds(from_ or date(1970, 1, 1), to or date(2999, 12, 31), tz)
        start, end = (lo if from_ else None), (hi if to else None)
    rows, total = FoodRepository(db).logs_page(user.id, start, end, page_size, (page - 1) * page_size)
    return Page(items=[FoodLogOut.model_validate(r) for r in rows], page=page, page_size=page_size, total=total)


@router.put("/food-logs/{log_id}", response_model=FoodLogOut)
def update_food_log(log_id: uuid.UUID, body: FoodLogUpdate, user: CurrentUser, db: DbSession) -> FoodLogOut:
    repo = FoodRepository(db)
    entry = repo.log_get(user.id, log_id)
    if entry is None:
        raise NotFound("Food log not found.")
    NutritionService(db).update_log(user, entry, body)
    db.commit()
    return FoodLogOut.model_validate(entry)


@router.delete("/food-logs/{log_id}", status_code=204)
def delete_food_log(log_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    entry = FoodRepository(db).log_get(user.id, log_id)
    if entry is None:
        raise NotFound("Food log not found.")
    NutritionService(db).delete_log(user, entry)
    db.commit()
    return Response(status_code=204)
