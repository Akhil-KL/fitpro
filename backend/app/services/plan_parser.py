"""Turn extracted workout-plan text into a structured plan (deterministic)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SPLIT_WORDS = (
    "push", "pull", "legs", "leg day", "upper", "lower", "full body", "fullbody", "chest", "back", "shoulders",
    "arms", "core", "cardio", "glutes", "posterior", "anterior", "rest", "active recovery",
)

_BULLET = re.compile(r"^\s*(?:[-•*·▪●◦>]+|\d+[.)]\s+|[a-z][.)]\s+)\s*")
_DAY = re.compile(r"^(?:week\s*\d+\s*[,/-]?\s*)?day\s*(\d+)\s*(?:[:\-–—|.)]\s*|\s+|$)(.*)$", re.I)
_WEEKDAY = re.compile(rf"^({'|'.join(WEEKDAYS)}|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b\s*(?:[:\-–—|]\s*)?(.*)$", re.I)
_SETS_X = re.compile(r"(\d+)\s*[x×*]\s*(\d+)(?:\s*[-–to]+\s*(\d+))?\s*(s|sec|secs|seconds|min|mins|minutes)?\b", re.I)
_SETS_OF = re.compile(r"(\d+)\s*sets?\s*(?:of|x|×)?\s*(\d+)(?:\s*[-–to]+\s*(\d+))?\s*(?:reps?)?", re.I)
_REPS_ONLY = re.compile(r"(\d+)(?:\s*[-–]\s*(\d+))?\s*reps?", re.I)
_SETS_ONLY = re.compile(r"(\d+)\s*sets?", re.I)
_DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?|min|seconds?|secs?|sec)\b", re.I)
_WEIGHT = re.compile(r"(?:@|at)?\s*(\d+(?:\.\d+)?)\s*(kg|kgs|lb|lbs)\b", re.I)
_ABBR = {"mon": "Monday", "tue": "Tuesday", "tues": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
         "thur": "Thursday", "thurs": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}


class PlanExerciseDraft(BaseModel):
    exercise_name: str
    sets: int | None = Field(None, ge=1, le=50)
    target_reps: int | None = Field(None, ge=1, le=1000)
    rep_range: str | None = None
    target_weight: float | None = Field(None, ge=0, le=1000)
    duration_seconds: int | None = Field(None, ge=1, le=86400)


class PlanDayDraft(BaseModel):
    day_number: int
    name: str
    description: str | None = None
    exercises: list[PlanExerciseDraft] = Field(default_factory=list)


class PlanDraft(BaseModel):
    name: str = "My Workout Plan"
    days: list[PlanDayDraft] = Field(default_factory=list)

    @property
    def exercise_count(self) -> int:
        return sum(len(d.exercises) for d in self.days)


def _secs(value: float, unit: str) -> int:
    u = unit.lower()
    if u.startswith(("hour", "hr")):
        return int(value * 3600)
    if u.startswith("min"):
        return int(value * 60)
    return int(value)


def parse_exercise_line(line: str) -> PlanExerciseDraft | None:
    sets = reps = duration = None
    rep_range = None
    weight = None
    span: tuple[int, int] | None = None

    if m := _SETS_X.search(line):
        sets = int(m.group(1))
        if m.group(4):
            duration = _secs(float(m.group(2)), m.group(4))
        else:
            reps = int(m.group(2))
            if m.group(3):
                rep_range = f"{m.group(2)}-{m.group(3)}"
        span = m.span()
    elif m := _SETS_OF.search(line):
        sets, reps = int(m.group(1)), int(m.group(2))
        if m.group(3):
            rep_range = f"{m.group(2)}-{m.group(3)}"
        span = m.span()
    else:
        ms, mr = _SETS_ONLY.search(line), _REPS_ONLY.search(line)
        if ms:
            sets = int(ms.group(1))
            span = ms.span()
        if mr:
            reps = int(mr.group(1))
            if mr.group(2):
                rep_range = f"{mr.group(1)}-{mr.group(2)}"
            span = span or mr.span()
            span = (min(span[0], mr.start()), span[1])
    if duration is None and (m := _DURATION.search(line)):
        duration = _secs(float(m.group(1)), m.group(2))
        span = span or m.span()
    if m := _WEIGHT.search(line):
        w = float(m.group(1))
        weight = round(w * 0.453592, 1) if m.group(2).lower().startswith("lb") else w

    if span is None:
        return None
    wm = _WEIGHT.search(line)
    first_num = min(span[0], wm.start()) if wm else span[0]
    name = line[:first_num].strip(" :-–—,.|@\t")
    if not re.search(r"[A-Za-z]{2,}", name):
        # Name after the numbers: "3x10 Lateral raise"
        tail = _WEIGHT.sub(" ", line[span[1]:])
        name = re.sub(r"^\s*(reps?|sets?)\b", "", tail, flags=re.I).strip(" :-–—,.|@\t")
    name = re.sub(r"\s+", " ", name)
    if not re.search(r"[A-Za-z]{2,}", name):
        return None
    return PlanExerciseDraft(exercise_name=name[:160], sets=sets, target_reps=reps, rep_range=rep_range,
                             target_weight=weight, duration_seconds=duration)


def _day_header(line: str) -> tuple[int | None, str] | None:
    if m := _DAY.match(line):
        rest = m.group(2).strip(" :-–—|")
        return int(m.group(1)), rest
    if m := _WEEKDAY.match(line):
        if _SETS_X.search(line) or _SETS_OF.search(line):
            return None
        day = m.group(1).lower()
        label = _ABBR.get(day, day.capitalize())
        rest = m.group(2).strip(" :-–—|")
        return None, f"{label} - {rest}" if rest else label
    low = line.lower().rstrip(":").strip()
    if (not re.search(r"\d", low) and len(low.split()) <= 5
            and any(low == w or low.startswith(w + " ") or low.startswith(w + "/") or low.endswith(" " + w) for w in SPLIT_WORDS)):
        return None, line.rstrip(":").strip()
    return None


def parse_plan_text(text: str, default_name: str = "My Workout Plan") -> PlanDraft:
    lines = [_BULLET.sub("", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    plan = PlanDraft(name=default_name)
    current: PlanDayDraft | None = None

    for idx, line in enumerate(lines):
        header = _day_header(line)
        if header is not None:
            num, label = header
            day_number = num or (len(plan.days) + 1)
            name = label or f"Day {day_number}"
            is_rest = bool(re.search(r"\b(rest|off|recovery)\b", name, re.I))
            current = PlanDayDraft(day_number=day_number, name=name[:160], description="Rest day" if is_rest else None)
            plan.days.append(current)
            continue
        ex = parse_exercise_line(line)
        if ex is not None:
            if current is None:
                current = PlanDayDraft(day_number=1, name="Day 1")
                plan.days.append(current)
            current.exercises.append(ex)
        elif idx == 0 and not plan.days and len(line) <= 80:
            plan.name = line.strip(" :")[:160]
        elif current is not None and current.exercises == [] and len(line) <= 200 and not current.description:
            current.description = line[:500]

    # Renumber sequentially when headers were weekdays/labels or numbers repeated.
    nums = [d.day_number for d in plan.days]
    if len(set(nums)) != len(nums):
        for i, d in enumerate(plan.days, start=1):
            d.day_number = i
    plan.days.sort(key=lambda d: d.day_number)
    return plan
