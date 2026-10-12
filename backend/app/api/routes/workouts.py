import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile

from app.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotFound, ValidationFailed
from app.models import WorkoutPlan
from app.repositories.tracking_repository import DocumentRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.common import Page
from app.schemas.workout import (
    DocumentOut,
    WorkoutCreate,
    WorkoutPlanOut,
    WorkoutPlanSummary,
    WorkoutSessionOut,
    WorkoutSessionSummary,
)
from app.services.document_service import DocumentService, process_document_task
from app.services.workout_service import WorkoutService

router = APIRouter(tags=["workouts"])


def _tz(db, user) -> str:
    p = UserRepository(db).profile(user.id)
    return p.timezone if p else "UTC"


@router.get("/workouts", response_model=Page[WorkoutSessionSummary])
def list_workouts(user: CurrentUser, db: DbSession, page: Annotated[int, Query(ge=1)] = 1,
                  page_size: Annotated[int, Query(ge=1, le=100)] = 20) -> Page[WorkoutSessionSummary]:
    rows, total = WorkoutRepository(db).sessions_page(user.id, page_size, (page - 1) * page_size)
    svc = WorkoutService(db)
    return Page(items=[svc.session_summary(s) for s in rows], page=page, page_size=page_size, total=total)


@router.post("/workouts", response_model=WorkoutSessionOut, status_code=201)
def create_workout(body: WorkoutCreate, user: CurrentUser, db: DbSession) -> WorkoutSessionOut:
    svc = WorkoutService(db)
    session = svc.create_session(user, body, _tz(db, user))
    db.commit()
    return svc.session_out(svc.get_session(user, session.id))


@router.get("/workouts/{session_id}", response_model=WorkoutSessionOut)
def get_workout(session_id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkoutSessionOut:
    svc = WorkoutService(db)
    return svc.session_out(svc.get_session(user, session_id))


# ------------------------------------------------------------------ plans
@router.post("/workout-plans/upload", response_model=DocumentOut, status_code=202)
async def upload_plan(background: BackgroundTasks, user: CurrentUser, db: DbSession,
                      file: UploadFile = File(...)) -> DocumentOut:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ValidationFailed(f"File is larger than {get_settings().max_upload_mb} MB.")
    doc = DocumentService(db).create(user, file.filename or "plan.txt", data)
    db.commit()
    background.add_task(process_document_task, doc.id)  # async processing; UI polls the status
    return DocumentOut.model_validate(doc)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(user: CurrentUser, db: DbSession) -> list[DocumentOut]:
    return [_doc_out(db, d) for d in DocumentRepository(db).list(user.id)]


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DocumentOut:
    doc = DocumentRepository(db).get(user.id, doc_id)
    if doc is None:
        raise NotFound("Document not found.")
    return _doc_out(db, doc)


def _doc_out(db, doc) -> DocumentOut:
    out = DocumentOut.model_validate(doc)
    plan = db.query(WorkoutPlan).filter(WorkoutPlan.source_document_id == doc.id, WorkoutPlan.user_id == doc.user_id).first()
    out.workout_plan_id = plan.id if plan else None
    return out


@router.get("/workout-plans", response_model=list[WorkoutPlanSummary])
def list_plans(user: CurrentUser, db: DbSession) -> list[WorkoutPlanSummary]:
    out = []
    for p in WorkoutRepository(db).plans(user.id):
        s = WorkoutPlanSummary.model_validate(p)
        s.day_count = len(p.days)
        out.append(s)
    return out


@router.get("/workout-plans/today")
def todays_plan(user: CurrentUser, db: DbSession) -> dict:
    repo = WorkoutRepository(db)
    plan = repo.active_plan(user.id)
    if plan is None:
        return {"plan": None, "day": None}
    day = WorkoutService(db).todays_plan_day(user, plan, _tz(db, user))
    return {
        "plan": {"id": str(plan.id), "name": plan.name},
        "day": None if day is None else {
            "id": str(day.id), "day_number": day.day_number, "name": day.name, "description": day.description,
            "exercises": [{"exercise_name": e.exercise_name, "sets": e.sets, "target_reps": e.target_reps,
                           "rep_range": e.rep_range, "target_weight": e.target_weight,
                           "duration_seconds": e.duration_seconds} for e in day.exercises],
        },
    }


@router.get("/workout-plans/{plan_id}", response_model=WorkoutPlanOut)
def get_plan(plan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkoutPlanOut:
    plan = WorkoutRepository(db).plan_get(user.id, plan_id)
    if plan is None:
        raise NotFound("Workout plan not found.")
    return WorkoutPlanOut.model_validate(plan)


@router.post("/workout-plans/{plan_id}/activate", response_model=WorkoutPlanSummary)
def activate_plan(plan_id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkoutPlanSummary:
    repo = WorkoutRepository(db)
    plan = repo.plan_get(user.id, plan_id)
    if plan is None:
        raise NotFound("Workout plan not found.")
    for p in repo.plans(user.id):
        p.is_active = p.id == plan.id
    db.commit()
    s = WorkoutPlanSummary.model_validate(plan)
    s.day_count = len(plan.days)
    return s
