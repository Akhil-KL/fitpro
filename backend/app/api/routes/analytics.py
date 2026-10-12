from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

FromQ = Annotated[date | None, Query(alias="from")]
ToQ = Annotated[date | None, Query(alias="to")]


@router.get("/daily")
def daily(user: CurrentUser, db: DbSession, day: Annotated[date | None, Query(alias="date")] = None) -> dict:
    return AnalyticsService(db).daily(user, day)


@router.get("/nutrition")
def nutrition(user: CurrentUser, db: DbSession, from_: FromQ = None, to: ToQ = None,
              granularity: Literal["daily", "weekly", "monthly", "auto"] = "auto") -> dict:
    return AnalyticsService(db).nutrition(user, from_, to, None if granularity == "auto" else granularity)


@router.get("/weight")
def weight(user: CurrentUser, db: DbSession, from_: FromQ = None, to: ToQ = None) -> dict:
    return AnalyticsService(db).weight(user, from_, to)


@router.get("/workouts")
def workouts(user: CurrentUser, db: DbSession, from_: FromQ = None, to: ToQ = None,
             exercise: Annotated[str | None, Query(max_length=160)] = None) -> dict:
    return AnalyticsService(db).workouts(user, from_, to, exercise.lower() if exercise else None)


@router.get("/summary")
def summary(user: CurrentUser, db: DbSession) -> dict:
    return AnalyticsService(db).summary(user)
