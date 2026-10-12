from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import WorkoutExercise, WorkoutPlan, WorkoutPlanDay, WorkoutSession


class WorkoutRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _sessions(self):
        return select(WorkoutSession).options(
            selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.sets)
        )

    def session_get(self, user_id: uuid.UUID, session_id: uuid.UUID) -> WorkoutSession | None:
        return self.db.scalar(self._sessions().where(WorkoutSession.id == session_id, WorkoutSession.user_id == user_id))

    def sessions_between(self, user_id: uuid.UUID, start: datetime, end: datetime) -> list[WorkoutSession]:
        return list(
            self.db.scalars(
                self._sessions()
                .where(WorkoutSession.user_id == user_id, WorkoutSession.started_at >= start, WorkoutSession.started_at < end)
                .order_by(WorkoutSession.started_at)
            )
        )

    def sessions_page(self, user_id: uuid.UUID, limit: int, offset: int) -> tuple[list[WorkoutSession], int]:
        total = self.db.scalar(select(func.count()).select_from(WorkoutSession).where(WorkoutSession.user_id == user_id)) or 0
        rows = self.db.scalars(
            self._sessions().where(WorkoutSession.user_id == user_id).order_by(WorkoutSession.started_at.desc())
            .offset(offset).limit(limit)
        )
        return list(rows), total

    def last_session_with_plan_day(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> WorkoutSession | None:
        return self.db.scalar(
            select(WorkoutSession)
            .join(WorkoutPlanDay, WorkoutPlanDay.id == WorkoutSession.workout_plan_day_id)
            .where(WorkoutSession.user_id == user_id, WorkoutPlanDay.workout_plan_id == plan_id)
            .order_by(WorkoutSession.started_at.desc())
            .limit(1)
        )

    def recent_exercises(self, user_id: uuid.UUID, since: datetime, limit: int = 20) -> list[WorkoutExercise]:
        return list(
            self.db.scalars(
                select(WorkoutExercise)
                .join(WorkoutSession)
                .options(selectinload(WorkoutExercise.sets))
                .where(WorkoutSession.user_id == user_id, WorkoutExercise.created_at >= since)
                .order_by(WorkoutExercise.created_at.desc())
                .limit(limit)
            )
        )

    # ---- plans
    def _plans(self):
        return select(WorkoutPlan).options(selectinload(WorkoutPlan.days).selectinload(WorkoutPlanDay.exercises))

    def active_plan(self, user_id: uuid.UUID) -> WorkoutPlan | None:
        return self.db.scalar(
            self._plans().where(WorkoutPlan.user_id == user_id, WorkoutPlan.is_active.is_(True))
            .order_by(WorkoutPlan.created_at.desc()).limit(1)
        )

    def plan_get(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> WorkoutPlan | None:
        return self.db.scalar(self._plans().where(WorkoutPlan.id == plan_id, WorkoutPlan.user_id == user_id))

    def plans(self, user_id: uuid.UUID) -> list[WorkoutPlan]:
        return list(self.db.scalars(self._plans().where(WorkoutPlan.user_id == user_id).order_by(WorkoutPlan.created_at.desc())))

    def plan_day_get(self, user_id: uuid.UUID, day_id: uuid.UUID) -> WorkoutPlanDay | None:
        return self.db.scalar(
            select(WorkoutPlanDay).join(WorkoutPlan)
            .where(WorkoutPlanDay.id == day_id, WorkoutPlan.user_id == user_id)
        )
