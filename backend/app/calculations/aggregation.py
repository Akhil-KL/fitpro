"""Pure aggregation helpers used by the analytics service (easy to unit test, DB-agnostic)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.calculations.nutrition import ZERO, NutritionValues

Granularity = Literal["daily", "weekly", "monthly"]


# ---------------------------------------------------------------- time helpers
def get_zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def local_date(dt: datetime, tz: ZoneInfo) -> date:
    return as_utc(dt).astimezone(tz).date()


def local_day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) of a local calendar day expressed in UTC."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def local_range_bounds(start: date, end: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """UTC bounds covering local dates start..end inclusive."""
    return local_day_bounds(start, tz)[0], local_day_bounds(end, tz)[1]


def auto_granularity(start: date, end: date) -> Granularity:
    days = (end - start).days + 1
    if days <= 31:
        return "daily"
    if days <= 180:
        return "weekly"
    return "monthly"


def bucket_start(d: date, granularity: Granularity) -> date:
    if granularity == "daily":
        return d
    if granularity == "weekly":
        return d - timedelta(days=d.weekday())  # ISO week, Monday start
    return d.replace(day=1)


def iter_buckets(start: date, end: date, granularity: Granularity) -> list[date]:
    out: list[date] = []
    cur = bucket_start(start, granularity)
    while cur <= end:
        out.append(cur)
        if granularity == "daily":
            cur += timedelta(days=1)
        elif granularity == "weekly":
            cur += timedelta(days=7)
        else:
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def days_in_bucket(bucket: date, granularity: Granularity, start: date, end: date) -> int:
    """Number of days of the bucket that fall inside the requested range."""
    if granularity == "daily":
        return 1
    if granularity == "weekly":
        last = bucket + timedelta(days=6)
    else:
        last = (bucket.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    lo, hi = max(bucket, start), min(last, end)
    return max((hi - lo).days + 1, 1)


# ------------------------------------------------------------------- nutrition
def sum_nutrition(values: Iterable[NutritionValues]) -> NutritionValues:
    total = ZERO
    for v in values:
        total = total + v
    return total


@dataclass(frozen=True)
class NutritionPoint:
    period_start: date
    totals: NutritionValues
    days: int
    logged_days: int

    @property
    def daily_average(self) -> NutritionValues:
        return self.totals.scaled(1 / self.days)


def nutrition_series(
    rows: Iterable[tuple[date, NutritionValues]], start: date, end: date, granularity: Granularity
) -> list[NutritionPoint]:
    """Group per-log nutrition by bucket. Empty buckets are kept (zeros), not dropped."""
    totals: dict[date, NutritionValues] = defaultdict(lambda: ZERO)
    logged: dict[date, set[date]] = defaultdict(set)
    for d, v in rows:
        if start <= d <= end:
            b = bucket_start(d, granularity)
            totals[b] = totals[b] + v
            logged[b].add(d)
    return [
        NutritionPoint(
            period_start=b,
            totals=totals.get(b, ZERO),
            days=days_in_bucket(b, granularity, start, end),
            logged_days=len(logged.get(b, ())),
        )
        for b in iter_buckets(start, end, granularity)
    ]


# ---------------------------------------------------------------------- weight
@dataclass(frozen=True)
class WeightProgress:
    starting_weight: float | None
    current_weight: float | None
    change_kg: float | None
    avg_weekly_change_kg: float | None
    target_weight: float | None
    progress_pct: float | None  # 0..100 toward target, None if not applicable


def weight_progress(
    points: list[tuple[date, float]], target_weight: float | None = None, baseline: float | None = None
) -> WeightProgress:
    """`points` sorted ascending. `baseline` overrides the start (e.g. profile weight at onboarding)."""
    if not points:
        return WeightProgress(baseline, baseline, None, None, target_weight, None)
    first_d, first_w = points[0]
    last_d, last_w = points[-1]
    start_w = baseline if baseline is not None else first_w
    change = round(last_w - start_w, 2)
    span_days = (last_d - first_d).days
    weekly = round((last_w - first_w) / span_days * 7, 2) if span_days >= 7 else None
    progress = None
    if target_weight is not None and target_weight != start_w:
        progress = (start_w - last_w) / (start_w - target_weight) * 100
        progress = round(min(max(progress, 0.0), 100.0), 1)
    return WeightProgress(start_w, last_w, change, weekly, target_weight, progress)


def daily_last_weight(rows: Iterable[tuple[date, datetime, float]]) -> list[tuple[date, float]]:
    """One weight per local day: the last reading of that day."""
    best: dict[date, tuple[datetime, float]] = {}
    for d, ts, w in rows:
        if d not in best or ts >= best[d][0]:
            best[d] = (ts, w)
    return [(d, best[d][1]) for d in sorted(best)]


# --------------------------------------------------------------------- workout
def count_by_bucket(days: Iterable[date], start: date, end: date, granularity: Granularity) -> list[tuple[date, int]]:
    counts: dict[date, int] = defaultdict(int)
    for d in days:
        if start <= d <= end:
            counts[bucket_start(d, granularity)] += 1
    return [(b, counts.get(b, 0)) for b in iter_buckets(start, end, granularity)]


def weekly_frequency(session_days: Iterable[date], start: date, end: date) -> float:
    """Average distinct training days per week in the range."""
    distinct = {d for d in session_days if start <= d <= end}
    weeks = ((end - start).days + 1) / 7
    return round(len(distinct) / weeks, 2) if weeks > 0 else 0.0
