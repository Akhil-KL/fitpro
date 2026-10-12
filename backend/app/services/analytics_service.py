"""Analytics derived from raw events in PostgreSQL. Charts consume these values as-is.

Aggregation runs in Python over user-scoped, date-bounded rows (correct per the
user's local timezone and identical on PostgreSQL and SQLite). When volumes
grow, the pure functions in `calculations.aggregation` are the seam where a
DuckDB-backed extraction can be swapped in (Phase 10).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.calculations.aggregation import (
    Granularity,
    auto_granularity,
    bucket_start,
    count_by_bucket,
    daily_last_weight,
    get_zone,
    local_date,
    local_day_bounds,
    local_range_bounds,
    nutrition_series,
    sum_nutrition,
    weekly_frequency,
    weight_progress,
)
from app.calculations.nutrition import macro_distribution
from app.calculations.workout import best_set, estimated_1rm, exercise_volume, total_reps
from app.core.errors import ValidationFailed
from app.models import User, UserProfile
from app.repositories.food_repository import FoodRepository
from app.repositories.tracking_repository import TrackingRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_repository import WorkoutRepository
from app.services.nutrition_service import snapshot_values
from app.services.workout_service import describe_sets, session_records, session_volume

MAX_RANGE_DAYS = 3 * 366


def _r(v: float | None, n: int = 1) -> float | None:
    return None if v is None else round(v, n)


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.foods = FoodRepository(db)
        self.tracking = TrackingRepository(db)
        self.workout_repo = WorkoutRepository(db)

    def _profile(self, user: User) -> UserProfile | None:
        return self.users.profile(user.id)

    def _tz(self, user: User):
        p = self._profile(user)
        return get_zone(p.timezone if p else None)

    def today(self, user: User) -> date:
        return datetime.now(self._tz(user)).date()

    def resolve_range(self, user: User, start: date | None, end: date | None, default_days: int = 7) -> tuple[date, date]:
        end = end or self.today(user)
        start = start or end - timedelta(days=default_days - 1)
        if start > end:
            raise ValidationFailed("'from' must be on or before 'to'.")
        if (end - start).days > MAX_RANGE_DAYS:
            raise ValidationFailed("Date range too large (max 3 years).")
        return start, end

    # ------------------------------------------------------------------ daily
    def daily(self, user: User, day: date | None = None) -> dict:
        tz = self._tz(user)
        day = day or self.today(user)
        start, end = local_day_bounds(day, tz)
        logs = self.foods.logs_between(user.id, start, end)
        totals = sum_nutrition(snapshot_values(lg) for lg in logs)
        target = self.users.active_targets(user.id, day)
        water = sum(w.amount_ml for w in self.tracking.water_between(user.id, start, end))
        sessions = self.workout_repo.sessions_between(user.id, start, end)
        latest_w = self.tracking.latest_weight(user.id, before=end)
        profile = self._profile(user)

        def remaining(target_v: float | None, consumed: float) -> float | None:
            return None if target_v is None else round(target_v - consumed, 1)

        meals: dict[str, list[dict]] = defaultdict(list)
        for lg in logs:
            meals[lg.meal_type or "unspecified"].append(
                {"id": str(lg.id), "food_name": lg.food_name, "quantity": lg.quantity, "unit": lg.unit,
                 "calories": round(lg.nutrition.calories, 1), "protein_g": round(lg.nutrition.protein_g, 1),
                 "logged_at": lg.logged_at.isoformat()}
            )
        return {
            "date": day.isoformat(),
            "calories": {"consumed": _r(totals.calories, 0), "target": target.calorie_target if target else None,
                         "remaining": remaining(target.calorie_target if target else None, totals.calories)},
            "protein_g": {"consumed": _r(totals.protein_g), "target": target.protein_target_g if target else None,
                          "remaining": remaining(target.protein_target_g if target else None, totals.protein_g)},
            "carbs_g": {"consumed": _r(totals.carbs_g), "target": target.carbs_target_g if target else None,
                        "remaining": remaining(target.carbs_target_g if target else None, totals.carbs_g)},
            "fat_g": {"consumed": _r(totals.fat_g), "target": target.fat_target_g if target else None,
                      "remaining": remaining(target.fat_target_g if target else None, totals.fat_g)},
            "fiber_g": {"consumed": _r(totals.fiber_g)},
            "water_ml": {"consumed": water, "target": target.water_target_ml if target else None,
                         "remaining": remaining(target.water_target_ml if target else None, water)},
            "macro_distribution": macro_distribution(totals.protein_g, totals.carbs_g, totals.fat_g),
            "workout": {
                "completed": bool(sessions),
                "session_count": len(sessions),
                "exercises": [describe_sets(e) for s in sessions for e in s.exercises],
                "volume_kg": round(sum(session_volume(s) for s in sessions), 1),
            },
            "current_weight_kg": latest_w.weight_kg if latest_w else (profile.current_weight_kg if profile else None),
            "food_log_count": len(logs),
            "meals": meals,
        }

    # -------------------------------------------------------------- nutrition
    def nutrition(self, user: User, start: date | None, end: date | None, granularity: str | None) -> dict:
        start, end = self.resolve_range(user, start, end)
        gran: Granularity = granularity if granularity in ("daily", "weekly", "monthly") else auto_granularity(start, end)  # type: ignore[assignment]
        tz = self._tz(user)
        lo, hi = local_range_bounds(start, end, tz)
        rows = [(local_date(lg.logged_at, tz), snapshot_values(lg)) for lg in self.foods.logs_between(user.id, lo, hi)]
        series = nutrition_series(rows, start, end, gran)
        target = self.users.active_targets(user.id, end)
        totals = sum_nutrition(v for _, v in rows)
        logged_days = len({d for d, _ in rows})
        points = []
        for p in series:
            avg = p.daily_average
            points.append({
                "period_start": p.period_start.isoformat(),
                "calories": round(p.totals.calories if gran == "daily" else avg.calories, 0),
                "protein_g": round(p.totals.protein_g if gran == "daily" else avg.protein_g, 1),
                "carbs_g": round(p.totals.carbs_g if gran == "daily" else avg.carbs_g, 1),
                "fat_g": round(p.totals.fat_g if gran == "daily" else avg.fat_g, 1),
                "fiber_g": round(p.totals.fiber_g if gran == "daily" else avg.fiber_g, 1),
                "total_calories": round(p.totals.calories, 0),
                "logged_days": p.logged_days,
            })
        avg_cals = totals.calories / logged_days if logged_days else 0
        avg_protein = totals.protein_g / logged_days if logged_days else 0
        adherence = None
        if target and logged_days:
            within = sum(
                1 for p in series if gran == "daily" and p.logged_days and abs(p.totals.calories - target.calorie_target) <= 0.1 * target.calorie_target
            )
            adherence = round(within / logged_days * 100, 1) if gran == "daily" else None
        return {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "granularity": gran,
            "value_basis": "daily_total" if gran == "daily" else "daily_average",
            "points": points,
            "averages": {"calories": round(avg_cals, 0), "protein_g": round(avg_protein, 1), "logged_days": logged_days},
            "macro_distribution": macro_distribution(totals.protein_g, totals.carbs_g, totals.fat_g),
            "targets": {"calories": target.calorie_target, "protein_g": target.protein_target_g} if target else None,
            "calorie_adherence_pct": adherence,
        }

    # ----------------------------------------------------------------- weight
    def weight(self, user: User, start: date | None, end: date | None) -> dict:
        start, end = self.resolve_range(user, start, end, default_days=30)
        tz = self._tz(user)
        lo, hi = local_range_bounds(start, end, tz)
        logs = self.tracking.weights_between(user.id, lo, hi)
        points = daily_last_weight((local_date(w.logged_at, tz), w.logged_at, w.weight_kg) for w in logs)
        profile = self._profile(user)
        first = self.tracking.first_weight(user.id)
        latest = self.tracking.latest_weight(user.id)
        ends = [] if first is None or latest is None else [
            (local_date(first.logged_at, tz), first.weight_kg), (local_date(latest.logged_at, tz), latest.weight_kg)]
        all_time = weight_progress(ends, target_weight=profile.target_weight_kg if profile else None)
        in_range = weight_progress(points)
        return {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "points": [{"date": d.isoformat(), "weight_kg": w} for d, w in points],
            "current_weight_kg": in_range.current_weight or (profile.current_weight_kg if profile else None),
            "starting_weight_kg": all_time.starting_weight,
            "change_kg": all_time.change_kg,
            "range_change_kg": in_range.change_kg,
            "avg_weekly_change_kg": in_range.avg_weekly_change_kg,
            "target_weight_kg": all_time.target_weight,
            "progress_pct": all_time.progress_pct,
        }

    # ---------------------------------------------------------------- workouts
    def workouts(self, user: User, start: date | None, end: date | None, exercise: str | None = None) -> dict:
        start, end = self.resolve_range(user, start, end, default_days=30)
        tz = self._tz(user)
        lo, hi = local_range_bounds(start, end, tz)
        sessions = self.workout_repo.sessions_between(user.id, lo, hi)
        gran = "daily" if (end - start).days < 14 else "weekly" if (end - start).days <= 180 else "monthly"
        days = [local_date(s.started_at, tz) for s in sessions]

        volume_by_bucket: dict[str, float] = defaultdict(float)
        per_exercise: dict[str, dict] = {}
        progression: dict[str, list[dict]] = defaultdict(list)
        total_sets = total_rep_count = 0
        for s, d in zip(sessions, days):
            for e in s.exercises:
                recs = session_records(e)
                vol = exercise_volume(recs)
                total_sets += len(recs)
                total_rep_count += total_reps(recs)
                stats = per_exercise.setdefault(e.exercise_name, {"exercise": e.exercise_name, "sessions": 0, "sets": 0,
                                                                   "reps": 0, "volume_kg": 0.0, "best_weight_kg": None, "best_e1rm_kg": None})
                stats["sessions"] += 1
                stats["sets"] += len(recs)
                stats["reps"] += total_reps(recs)
                stats["volume_kg"] = round(stats["volume_kg"] + vol, 1)
                b = best_set(recs)
                if b and b.weight_kg:
                    e1 = estimated_1rm(b.weight_kg, b.reps or 1)
                    if stats["best_weight_kg"] is None or b.weight_kg > stats["best_weight_kg"]:
                        stats["best_weight_kg"] = b.weight_kg
                    if stats["best_e1rm_kg"] is None or e1 > stats["best_e1rm_kg"]:
                        stats["best_e1rm_kg"] = e1
                    progression[e.exercise_name].append({"date": d.isoformat(), "top_weight_kg": b.weight_kg,
                                                         "reps": b.reps, "e1rm_kg": e1, "volume_kg": round(vol, 1)})
        counts = count_by_bucket(days, start, end, gran)  # type: ignore[arg-type]
        for s, d in zip(sessions, days):
            volume_by_bucket[bucket_start(d, gran).isoformat()] += session_volume(s)  # type: ignore[arg-type]

        top = sorted(per_exercise.values(), key=lambda x: (-x["sessions"], x["exercise"]))
        selected = exercise or (top[0]["exercise"] if top else None)
        return {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "granularity": gran,
            "workout_count": len(sessions),
            "training_days": len(set(days)),
            "weekly_frequency": weekly_frequency(days, start, end),
            "total_sets": total_sets,
            "total_reps": total_rep_count,
            "total_volume_kg": round(sum(session_volume(s) for s in sessions), 1),
            "frequency": [{"period_start": b.isoformat(), "workouts": c,
                           "volume_kg": round(volume_by_bucket.get(b.isoformat(), 0.0), 1)} for b, c in counts],
            "exercises": top,
            "personal_records": [{"exercise": x["exercise"], "best_weight_kg": x["best_weight_kg"],
                                  "best_e1rm_kg": x["best_e1rm_kg"]} for x in top if x["best_weight_kg"]],
            "progression_exercise": selected,
            "progression": progression.get(selected, []) if selected else [],
        }

    # ----------------------------------------------------------------- summary
    def summary(self, user: User) -> dict:
        today = self.today(user)
        week_start = today - timedelta(days=6)
        nutrition = self.nutrition(user, week_start, today, "daily")
        recent_logs, _ = self.foods.logs_page(user.id, None, None, limit=8, offset=0)
        return {
            "today": self.daily(user, today),
            "week": {
                "nutrition": nutrition,
                "workouts": self.workouts(user, week_start, today),
            },
            "weight": self.weight(user, today - timedelta(days=29), today),
            "recent_activity": [
                {"type": "food", "id": str(lg.id), "label": f"{lg.quantity:g} {lg.unit} {lg.food_name}",
                 "calories": round(lg.nutrition.calories), "logged_at": lg.logged_at.isoformat()}
                for lg in recent_logs
            ],
        }
