import pytest
from pydantic import ValidationError

from app.schemas.ai import ParsedMessage
from app.services.plan_parser import parse_plan_text
from app.services.rule_parser import parse_message


def items(p):
    return [(i.food_name, i.quantity, i.unit) for i in p.items]


def test_single_and_multiple_food_logs():
    p = parse_message("I ate 3 eggs.")
    assert p.intent == "food_log" and items(p) == [("egg", 3, None)]
    p = parse_message("I ate 3 eggs, 200g rice and 150g chicken for lunch.")
    assert items(p) == [("egg", 3, None), ("rice", 200, "g"), ("chicken", 150, "g")]
    assert p.meal == "lunch"


def test_missing_quantity_is_not_invented():
    p = parse_message("I ate some chicken.")
    assert items(p) == [("chicken", None, None)]
    p = parse_message("had a bowl of dal and 2 rotis for dinner")
    assert items(p) == [("dal", None, None), ("roti", 2, None)]


def test_follow_ups():
    assert items(parse_message("Add another egg.")) == [("egg", 1, None)]
    assert items(parse_message("Add 100g chicken.")) == [("chicken", 100, "g")]


@pytest.mark.parametrize("text", ["I did bench press 60kg for 4 sets of 8.", "Bench press 60kg, 4 sets of 8.",
                                  "bench press 4x8 @ 60kg"])
def test_workout(text):
    p = parse_message(text)
    assert p.intent == "workout_log"
    e = p.exercises[0]
    assert (e.exercise_name, e.sets, e.reps, e.weight_kg) == ("bench press", 4, 8, 60)


def test_multiple_and_timed_exercises():
    p = parse_message("Squats 100kg 5x5; then plank 3x60s")
    assert [(e.exercise_name, e.sets, e.reps, e.duration_seconds) for e in p.exercises] == [
        ("squats", 5, 5, None), ("plank", 3, None, 60)]
    assert parse_message("ran 30 minutes").exercises[0].duration_seconds == 1800
    assert parse_message("did 20 pushups").exercises[0].reps == 20


def test_weight_and_water():
    assert parse_message("My weight today is 66.8kg.").weight_kg == 66.8
    assert parse_message("I weigh 150 lbs").weight_kg == pytest.approx(68.04)
    assert parse_message("I drank 750ml water.").amount_ml == 750
    assert parse_message("drank 2 litres of water yesterday").day_offset == -1
    vague = parse_message("had 2 glasses of water")
    assert vague.amount_ml is None and vague.clarification_question


def test_corrections():
    p = parse_message("Actually, the rice was 250g.")
    assert p.intent == "food_correction"
    assert (p.correction.target_name, p.correction.quantity, p.correction.unit) == ("rice", 250, "g")
    assert parse_message("make that 300g").correction.target_name is None
    assert parse_message("delete the last entry").correction.delete
    assert parse_message("the chicken was actually 300 kcal").correction.nutrition_override.calories == 300
    w = parse_message("actually bench was 65kg")
    assert w.intent == "workout_correction" and w.correction.weight_kg == 65


def test_queries():
    assert parse_message("How much protein have I eaten today?").query_metric == "protein"
    assert parse_message("What is today's workout?").intent == "workout_query"
    assert parse_message("how am I doing today?").intent == "daily_summary"
    assert parse_message("what is my calorie target?").intent == "goal_query"
    assert parse_message("how much weight have I lost?").intent == "progress_query"


def test_nutrition_facts_and_custom_food():
    p = parse_message("100g contains 350 kcal, 25g protein, 50g carbs and 8g fat.")
    n = p.nutrition
    assert (n.basis_quantity, n.basis_unit, n.calories, n.protein_g, n.carbs_g, n.fat_g) == (100, "g", 350, 25, 50, 8)
    p = parse_message("create custom food protein atta: per 100g 350 kcal, 25g protein")
    assert p.intent == "custom_food_create" and p.custom_food_name == "protein atta"
    assert parse_message("1 scoop has 120 kcal and 24g protein").nutrition.basis_unit == "serving"


def test_parsed_message_validation_rejects_bad_values():
    with pytest.raises(ValidationError):
        ParsedMessage(intent="weight_log", weight_kg=5000)
    with pytest.raises(ValidationError):
        ParsedMessage(intent="food_log", items=[{"food_name": "egg", "quantity": -1}])
    with pytest.raises(ValidationError):
        ParsedMessage(intent="drop_tables")


PLAN = """PPL Split
Day 1 - Push
Bench Press 4x8
Incline DB Press 3x10
- Tricep pushdown: 3 sets of 10-12 reps
Day 2 - Pull
1. Deadlift 3x5 @ 100kg
Day 3: Legs
Plank 3x60s
Treadmill 20 min
Day 4 Rest
"""


def test_plan_parser_spec_example():
    plan = parse_plan_text(PLAN)
    assert plan.name == "PPL Split"
    assert [d.name for d in plan.days] == ["Push", "Pull", "Legs", "Rest"]
    push = plan.days[0].exercises
    assert [(e.exercise_name, e.sets, e.target_reps) for e in push[:2]] == [("Bench Press", 4, 8), ("Incline DB Press", 3, 10)]
    assert push[2].rep_range == "10-12"
    assert plan.days[1].exercises[0].target_weight == 100
    assert plan.days[2].exercises[0].duration_seconds == 60
    assert plan.days[2].exercises[1].duration_seconds == 1200
    assert plan.days[3].exercises == [] and plan.days[3].description == "Rest day"


def test_plan_parser_weekdays():
    plan = parse_plan_text("Monday: Chest\nBench press 4x10\nWednesday - Back\nLat pulldown 3x12")
    assert [d.name for d in plan.days] == ["Monday - Chest", "Wednesday - Back"]
    assert plan.exercise_count == 2
