"""Workout sessions, exercises/sets, plan lookups and corrections."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.calculations.aggregation import as_utc, get_zone, local_date, local_day_bounds
from app.calculations.workout import SetRecord, exercise_volume
from app.core.errors import NotFound
from app.models import User, WorkoutExercise, WorkoutPlan, WorkoutPlanDay, WorkoutSession, WorkoutSet
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.ai import Correction, ExerciseEntry
from app.schemas.workout import WorkoutCreate, WorkoutSessionOut, WorkoutSessionSummary

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_ABBREV = {"db": "dumbbell", "bb": "barbell", "ohp": "overhead press", "rdl": "romanian deadlift"}


def normalize_exercise(name: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    words = [_ABBREV.get(w, w) for w in words]
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words]
    return " ".join(words)


def same_exercise(a: str, b: str) -> bool:
    na, nb = normalize_exercise(a), normalize_exercise(b)
    return na == nb or na in nb or nb in na


def session_records(ex: WorkoutExercise) -> list[SetRecord]:
    return [SetRecord(s.reps, s.weight_kg, s.duration_seconds) for s in ex.sets]


def session_volume(session: WorkoutSession) -> float:
    return round(sum(exercise_volume(session_records(e)) for e in session.exercises), 2)


def describe_sets(ex: WorkoutExercise) -> str:
    sets = ex.sets
    if not sets:
        return ex.exercise_name
    first = sets[0]
    uniform = all((s.reps, s.weight_kg, s.duration_seconds) == (first.reps, first.weight_kg, first.duration_seconds) for s in sets)
    if uniform:
        parts = []
        if first.reps:
            parts.append(f"{len(sets)}×{first.reps}")
        elif first.duration_seconds:
            parts.append(f"{len(sets)}×{_fmt_duration(first.duration_seconds)}" if len(sets) > 1 else _fmt_duration(first.duration_seconds))
        if first.weight_kg:
            parts.append(f"@ {first.weight_kg:g} kg")
        return f"{ex.exercise_name} {' '.join(parts)}".strip()
    return f"{ex.exercise_name} ({len(sets)} sets)"


def _fmt_duration(sec: int) -> str:
    if sec >= 3600:
        return f"{sec / 3600:g} h"
    if sec >= 60:
        return f"{sec / 60:g} min"
    return f"{sec} s"


class WorkoutService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = WorkoutRepository(db)

    # ------------------------------------------------------------- sessions
    def _session_for_day(self, user: User, when: datetime, tz_name: str) -> WorkoutSession:
        tz = get_zone(tz_name)
        start, end = local_day_bounds(local_date(when, tz), tz)
        existing = [s for s in self.repo.sessions_between(user.id, start, end)]
        if existing:
            return existing[-1]
        session = WorkoutSession(user_id=user.id, started_at=when, completed_at=when)
        self.db.add(session)
        self.db.flush()
        return session

    @staticmethod
    def missing_fields(entry: ExerciseEntry) -> bool:
        """An entry needs reps or a duration to be recorded without guessing."""
        return entry.reps is None and entry.duration_seconds is None

    def log_entries(self, user: User, entries: list[ExerciseEntry], when: datetime, tz_name: str) -> WorkoutSession:
        session = self._session_for_day(user, when, tz_name)
        order = len(session.exercises)
        for entry in entries:
            ex = WorkoutExercise(exercise_name=entry.exercise_name.strip().lower(), order_index=order, created_at=datetime.now(timezone.utc))
            order += 1
            n_sets = entry.sets or 1
            ex.sets = [
                WorkoutSet(set_number=i + 1, reps=entry.reps, weight_kg=entry.weight_kg, duration_seconds=entry.duration_seconds)
                for i in range(n_sets)
            ]
            session.exercises.append(ex)
        self._link_plan_day(user, session, tz_name)
        session.completed_at = max(as_utc(session.completed_at) if session.completed_at else when, when)
        self.db.flush()
        return session

    def create_session(self, user: User, data: WorkoutCreate, tz_name: str) -> WorkoutSession:
        when = data.started_at or datetime.now(timezone.utc)
        session = WorkoutSession(user_id=user.id, started_at=when, completed_at=when if data.completed else None, notes=data.notes)
        for i, ex_in in enumerate(data.exercises):
            ex = WorkoutExercise(exercise_name=ex_in.exercise_name.strip().lower(), order_index=i, created_at=datetime.now(timezone.utc))
            ex.sets = [WorkoutSet(set_number=j + 1, **s.model_dump()) for j, s in enumerate(ex_in.sets)]
            session.exercises.append(ex)
        self.db.add(session)
        self.db.flush()
        self._link_plan_day(user, session, tz_name)
        self.db.flush()
        return session

    def _link_plan_day(self, user: User, session: WorkoutSession, tz_name: str) -> None:
        """Planned vs completed: tie the session to today's plan day when its exercises match."""
        if session.workout_plan_day_id is not None:
            return
        plan = self.repo.active_plan(user.id)
        if plan is None:
            return
        day = self.todays_plan_day(user, plan, tz_name, exclude_session=session.id)
        if day is None:
            return
        planned = [p.exercise_name for p in day.exercises]
        if any(same_exercise(e.exercise_name, p) for e in session.exercises for p in planned):
            session.workout_plan_day_id = day.id

    # ------------------------------------------------------------- corrections
    def find_recent_exercise(self, user: User, target: str | None) -> list[WorkoutExercise]:
        since = datetime.now(timezone.utc) - timedelta(hours=36)
        recent = self.repo.recent_exercises(user.id, since)
        if target:
            return [e for e in recent if same_exercise(e.exercise_name, target)]
        return recent[:1]

    def apply_correction(self, ex: WorkoutExercise, c: Correction) -> WorkoutExercise:
        if c.delete:
            self.db.delete(ex)
            self.db.flush()
            return ex
        current = ex.sets[0] if ex.sets else None
        reps = c.reps if c.reps is not None else (current.reps if current else None)
        weight = c.weight_kg if c.weight_kg is not None else (current.weight_kg if current else None)
        duration = current.duration_seconds if current else None
        n = c.sets if c.sets is not None else len(ex.sets) or 1
        ex.sets.clear()
        self.db.flush()
        ex.sets.extend(
            WorkoutSet(set_number=i + 1, reps=reps, weight_kg=weight, duration_seconds=duration) for i in range(n)
        )
        self.db.flush()
        return ex

    # ------------------------------------------------------------- plans
    def todays_plan_day(
        self, user: User, plan: WorkoutPlan, tz_name: str, exclude_session: uuid.UUID | None = None
    ) -> WorkoutPlanDay | None:
        if not plan.days:
            return None
        tz = get_zone(tz_name)
        today = datetime.now(tz).date()
        weekday = WEEKDAYS[today.weekday()]
        named = [d for d in plan.days if weekday in d.name.lower()]
        if named:
            return named[0]
        if any(any(w in d.name.lower() for w in WEEKDAYS) for d in plan.days):
            return None  # weekday-based plan with nothing scheduled today -> rest day

        last = self.repo.last_session_with_plan_day(user.id, plan.id)
        if last is not None and last.id != exclude_session:
            last_day = next((d for d in plan.days if d.id == last.workout_plan_day_id), None)
            if last_day is not None:
                if local_date(last.started_at, tz) == today:
                    return last_day  # already training today's day
                idx = plan.days.index(last_day)
                return plan.days[(idx + 1) % len(plan.days)]
        return plan.days[0]

    # ------------------------------------------------------------- output
    def session_out(self, session: WorkoutSession) -> WorkoutSessionOut:
        out = WorkoutSessionOut.model_validate(session)
        out.total_volume_kg = session_volume(session)
        if session.workout_plan_day_id:
            day = self.db.get(WorkoutPlanDay, session.workout_plan_day_id)
            out.plan_day_name = day.name if day else None
        return out

    def session_summary(self, session: WorkoutSession) -> WorkoutSessionSummary:
        day = self.db.get(WorkoutPlanDay, session.workout_plan_day_id) if session.workout_plan_day_id else None
        return WorkoutSessionSummary(
            id=session.id,
            started_at=session.started_at,
            completed_at=session.completed_at,
            exercise_count=len(session.exercises),
            set_count=sum(len(e.sets) for e in session.exercises),
            total_volume_kg=session_volume(session),
            exercise_names=[e.exercise_name for e in session.exercises],
            plan_day_name=day.name if day else None,
        )

    def get_session(self, user: User, session_id: uuid.UUID) -> WorkoutSession:
        s = self.repo.session_get(user.id, session_id)
        if s is None:
            raise NotFound("Workout not found.")
        return s
