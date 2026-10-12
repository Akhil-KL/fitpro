from datetime import date, timedelta

import pytest

from app.calculations import aggregation as agg
from app.calculations import profile as prof
from app.calculations.nutrition import (
    NutritionProfile,
    NutritionValues,
    UnitMismatch,
    default_count_unit,
    macro_distribution,
    normalize_unit,
    scale_nutrition,
)
from app.calculations.workout import SetRecord, best_set, estimated_1rm, exercise_volume


# ---------------------------------------------------------------- profile
def test_bmi():
    assert prof.bmi(70, 175) == 22.9
    assert prof.bmi_category(22.9) == "normal"
    assert prof.bmi_category(31) == "obese"


def test_bmr_mifflin_st_jeor():
    assert prof.bmr(70, 175, 21, "male") == 1693.8  # 700 + 1093.75 - 105 + 5
    assert prof.bmr(60, 165, 30, "female") == 1320.2  # 600 + 1031.25 - 150 - 161
    with pytest.raises(ValueError):
        prof.bmr(0, 175, 21, "male")


def test_tdee_and_calorie_targets():
    t = prof.tdee(1693.8, "moderate")
    assert t == pytest.approx(2625.4, abs=0.1)
    assert prof.calorie_target(t, "gain_muscle", "male") == 2925
    assert prof.calorie_target(t, "lose_fat", "male") == 2125
    assert prof.calorie_target(1500, "lose_fat", "female") == 1200  # safety floor
    with pytest.raises(ValueError):
        prof.tdee(1500, "couch")


def test_protein_and_macros_add_up():
    protein = prof.protein_target(70, "gain_muscle")
    assert protein == 126
    carbs, fat = prof.macro_targets(2925, protein)
    total = protein * 4 + carbs * 4 + fat * 9
    assert abs(total - 2925) < 10
    assert fat == round(2925 * 0.25 / 9)


def test_compute_targets_bundle():
    r = prof.compute_targets(weight_kg=70, height_cm=175, age=21, gender="male", activity_level="moderate", goal="maintain")
    assert r.calorie_target == round(r.tdee)
    assert r.water_target_ml == 2450


# ---------------------------------------------------------------- nutrition
CHICKEN = NutritionProfile(100, "g", 165, 31, 0, 3.6, 0)
EGG = NutritionProfile(1, "piece", 72, 6.3, 0.4, 4.8, 0, grams_per_piece=50)
BANANA = NutritionProfile(100, "g", 89, 1.1, 22.8, 0.3, 2.6, grams_per_piece=118)
MILK = NutritionProfile(100, "ml", 58, 3.1, 4.7, 3.0, 0)


def test_scale_per_100g_matches_spec_example():
    v = scale_nutrition(CHICKEN, 150, "g")
    assert v.calories == 247.5
    assert v.protein_g == 46.5


def test_scale_units():
    assert scale_nutrition(CHICKEN, 0.15, "kg").calories == 247.5
    assert scale_nutrition(EGG, 3, "piece").protein_g == pytest.approx(18.9)
    assert scale_nutrition(EGG, 100, "g").calories == 144  # 2 eggs by weight via grams_per_piece
    assert scale_nutrition(BANANA, 2, "piece").calories == pytest.approx(210.04)
    assert scale_nutrition(MILK, 1, "cup").calories == pytest.approx(139.2)


def test_scale_refuses_to_guess():
    with pytest.raises(UnitMismatch):
        scale_nutrition(CHICKEN, 2, "piece")
    with pytest.raises(UnitMismatch):
        scale_nutrition(CHICKEN, 200, "ml")
    with pytest.raises(ValueError):
        scale_nutrition(CHICKEN, 0, "g")


def test_default_count_unit_and_normalize():
    assert default_count_unit(EGG) == "piece"
    assert default_count_unit(BANANA) == "piece"
    assert default_count_unit(CHICKEN) is None
    assert normalize_unit("Grams") == "g"
    assert normalize_unit("bowl") == "vague"
    assert normalize_unit("scoops") == "serving"


def test_macro_distribution_uses_macro_calories():
    d = macro_distribution(100, 200, 50)  # 400 + 800 + 450 kcal
    assert d == {"protein": 24.2, "carbs": 48.5, "fat": 27.3}
    assert macro_distribution(0, 0, 0) == {"protein": 0.0, "carbs": 0.0, "fat": 0.0}


# ---------------------------------------------------------------- workout
def test_volume_and_records():
    sets = [SetRecord(8, 60)] * 4
    assert exercise_volume(sets) == 1920  # sets × reps × weight
    assert exercise_volume([SetRecord(20, None)]) == 0  # bodyweight
    assert estimated_1rm(100, 5) == 116.7
    assert estimated_1rm(100, 1) == 100
    assert best_set([SetRecord(10, 50), SetRecord(5, 60), SetRecord(8, 60)]) == SetRecord(8, 60)


# ---------------------------------------------------------------- aggregation
def test_daily_series_keeps_empty_days():
    start = date(2026, 10, 1)
    rows = [(start, NutritionValues(500, 30, 50, 10, 5)), (start, NutritionValues(300, 20, 30, 5, 2)),
            (start + timedelta(days=2), NutritionValues(1000, 50, 100, 30, 10))]
    series = agg.nutrition_series(rows, start, start + timedelta(days=3), "daily")
    assert [p.totals.calories for p in series] == [800, 0, 1000, 0]
    assert series[0].logged_days == 1


def test_weekly_series_averages_over_days_in_range():
    start, end = date(2026, 9, 28), date(2026, 10, 11)  # Monday .. Sunday (2 weeks)
    rows = [(start + timedelta(days=i), NutritionValues(2100, 100, 200, 70, 20)) for i in range(7)]
    series = agg.nutrition_series(rows, start, end, "weekly")
    assert len(series) == 2
    assert series[0].daily_average.calories == 2100
    assert series[1].totals.calories == 0


def test_monthly_buckets_and_granularity():
    buckets = agg.iter_buckets(date(2026, 1, 15), date(2026, 4, 2), "monthly")
    assert buckets == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    assert agg.auto_granularity(date(2026, 1, 1), date(2026, 1, 20)) == "daily"
    assert agg.auto_granularity(date(2026, 1, 1), date(2026, 3, 20)) == "weekly"
    assert agg.auto_granularity(date(2025, 1, 1), date(2026, 3, 20)) == "monthly"


def test_weight_progress():
    d = date(2026, 9, 1)
    pts = [(d, 80.0), (d + timedelta(days=14), 79.0), (d + timedelta(days=28), 78.0)]
    wp = agg.weight_progress(pts, target_weight=75)
    assert wp.change_kg == -2.0
    assert wp.avg_weekly_change_kg == -0.5
    assert wp.progress_pct == 40.0
    gain = agg.weight_progress([(d, 70.0), (d + timedelta(days=7), 71.0)], target_weight=75)
    assert gain.progress_pct == 20.0


def test_local_day_bounds_respect_timezone():
    tz = agg.get_zone("Asia/Kolkata")
    start, end = agg.local_day_bounds(date(2026, 10, 5), tz)
    assert start.isoformat() == "2026-10-04T18:30:00+00:00"
    assert (end - start).total_seconds() == 86400


def test_weekly_frequency():
    s = date(2026, 9, 28)
    days = [s, s, s + timedelta(days=2), s + timedelta(days=9)]
    assert agg.weekly_frequency(days, s, s + timedelta(days=13)) == 1.5
