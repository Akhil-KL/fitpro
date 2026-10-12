"""Deterministic workout calculations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class SetRecord:
    reps: int | None
    weight_kg: float | None
    duration_seconds: int | None = None


def set_volume(s: SetRecord) -> float:
    """Weighted set: reps × weight. Bodyweight sets count reps; timed sets contribute 0 load volume."""
    if s.reps and s.weight_kg:
        return s.reps * s.weight_kg
    return 0.0


def exercise_volume(sets: Iterable[SetRecord]) -> float:
    """volume = Σ reps × weight  (equals sets × reps × weight for uniform sets)."""
    return round(sum(set_volume(s) for s in sets), 2)


def total_reps(sets: Iterable[SetRecord]) -> int:
    return sum(s.reps or 0 for s in sets)


def total_duration(sets: Iterable[SetRecord]) -> int:
    return sum(s.duration_seconds or 0 for s in sets)


def estimated_1rm(weight_kg: float, reps: int) -> float:
    """Epley formula; a single rep returns the lifted weight."""
    if weight_kg <= 0 or reps <= 0:
        return 0.0
    if reps == 1:
        return round(weight_kg, 1)
    return round(weight_kg * (1 + reps / 30), 1)


def best_set(sets: Iterable[SetRecord]) -> SetRecord | None:
    """Heaviest set; ties broken by reps."""
    candidates = [s for s in sets if s.weight_kg]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.weight_kg or 0, s.reps or 0))
