from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.repositories.tracking_repository import TrackingRepository
from app.schemas.common import Page
from app.schemas.workout import WaterLogIn, WaterLogOut, WeightLogIn, WeightLogOut
from app.services.tracking_service import TrackingService

router = APIRouter(tags=["tracking"])

PageQ = Annotated[int, Query(ge=1)]
SizeQ = Annotated[int, Query(ge=1, le=100)]


@router.get("/weight-logs", response_model=Page[WeightLogOut])
def list_weight(user: CurrentUser, db: DbSession, page: PageQ = 1, page_size: SizeQ = 50) -> Page[WeightLogOut]:
    rows, total = TrackingRepository(db).weight_page(user.id, page_size, (page - 1) * page_size)
    return Page(items=[WeightLogOut.model_validate(r) for r in rows], page=page, page_size=page_size, total=total)


@router.post("/weight-logs", response_model=WeightLogOut, status_code=201)
def create_weight(body: WeightLogIn, user: CurrentUser, db: DbSession) -> WeightLogOut:
    entry = TrackingService(db).log_weight(user, body.weight_kg, body.logged_at or datetime.now(timezone.utc))
    db.commit()
    return WeightLogOut.model_validate(entry)


@router.get("/water-logs", response_model=Page[WaterLogOut])
def list_water(user: CurrentUser, db: DbSession, page: PageQ = 1, page_size: SizeQ = 50) -> Page[WaterLogOut]:
    rows, total = TrackingRepository(db).water_page(user.id, page_size, (page - 1) * page_size)
    return Page(items=[WaterLogOut.model_validate(r) for r in rows], page=page, page_size=page_size, total=total)


@router.post("/water-logs", response_model=WaterLogOut, status_code=201)
def create_water(body: WaterLogIn, user: CurrentUser, db: DbSession) -> WaterLogOut:
    entry = TrackingService(db).log_water(user, body.amount_ml, body.logged_at or datetime.now(timezone.utc))
    db.commit()
    return WaterLogOut.model_validate(entry)
