"""End-to-end API tests through FastAPI's TestClient (SQLite in-memory, rule-based parser)."""

from conftest import register

API = "/api/v1"


def chat(client, headers, message, conv=None):
    body = {"message": message}
    if conv:
        body["conversation_id"] = conv
    r = client.post(f"{API}/chat/messages", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def food_logs(client, headers):
    r = client.get(f"{API}/food-logs", headers=headers)
    assert r.status_code == 200
    return r.json()


# ----------------------------------------------------------------- auth & profile
def test_auth_flow_and_protection(client):
    assert client.get(f"{API}/profile").status_code == 401
    headers = register(client)
    assert client.post(f"{API}/auth/register", json={"email": "vikas@example.com", "password": "supersecret1"}).status_code == 409
    bad = client.post(f"{API}/auth/login", json={"email": "vikas@example.com", "password": "wrong-password"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "unauthorized"
    ok = client.post(f"{API}/auth/login", json={"email": "VIKAS@example.com", "password": "supersecret1"})
    assert ok.status_code == 200
    me = client.get(f"{API}/auth/me", headers=headers).json()
    assert me["email"] == "vikas@example.com" and me["has_profile"] is False
    assert client.get(f"{API}/profile", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_password_reset(client):
    register(client, "reset@example.com", "oldpassword1")
    r = client.post(f"{API}/auth/password-reset/request", json={"email": "reset@example.com"})
    token = r.json()["dev_reset_token"]
    assert client.post(f"{API}/auth/password-reset/confirm", json={"token": token, "new_password": "newpassword1"}).status_code == 200
    # single use: the token is bound to the old password hash
    assert client.post(f"{API}/auth/password-reset/confirm", json={"token": token, "new_password": "another123"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "reset@example.com", "password": "newpassword1"}).status_code == 200
    unknown = client.post(f"{API}/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert unknown.status_code == 200 and "dev_reset_token" not in unknown.json()


def test_profile_targets_and_history(client, auth):
    p = client.get(f"{API}/profile", headers=auth).json()
    assert p["is_complete"] and p["bmi"] == 22.9 and p["bmr"] == 1693.8
    t = client.get(f"{API}/targets", headers=auth).json()
    assert t["calorie_target"] == 2925 and t["protein_target_g"] == 126
    client.put(f"{API}/profile", headers=auth, json={"fitness_goal": "lose_fat"})
    assert client.get(f"{API}/targets", headers=auth).json()["calorie_target"] == 2125
    bad = client.put(f"{API}/profile", headers=auth, json={"age": 5})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"


# ----------------------------------------------------------------- chat: food
def test_chat_multi_food_log_and_query(client, auth):
    r = chat(client, auth, "I ate 3 eggs, 200g rice and 150g chicken for lunch.")
    assert r["status"] == "completed" and r["intent"] == "food_log"
    assert len(r["updated_entities"]) == 3
    # 216 + 260 + 247.5
    assert r["result"]["totals"]["calories"] == 723.5
    assert "723.5" not in r["message"] and "724 kcal" in r["message"]
    logs = food_logs(client, auth)
    assert logs["total"] == 3 and all(lg["meal_type"] == "lunch" for lg in logs["items"])

    q = chat(client, auth, "How much protein have I eaten today?", r["conversation_id"])
    assert q["intent"] == "nutrition_query"
    assert q["result"]["consumed"] == round(18.9 + 5.4 + 46.5, 1)
    assert "126 g target" in q["message"]


def test_chat_correction_updates_instead_of_duplicating(client, auth):
    r = chat(client, auth, "I ate 3 eggs and 200g rice")
    conv = r["conversation_id"]
    c = chat(client, auth, "Actually, the rice was 250g.", conv)
    assert c["intent"] == "food_correction" and c["status"] == "completed"
    logs = food_logs(client, auth)["items"]
    assert len(logs) == 2
    rice = next(lg for lg in logs if "rice" in lg["food_name"])
    assert rice["quantity"] == 250 and rice["nutrition"]["calories"] == 325

    chat(client, auth, "Add another egg.", conv)
    logs = food_logs(client, auth)["items"]
    assert len(logs) == 3

    d = chat(client, auth, "delete the last entry", conv)
    assert d["updated_entities"][0]["action"] == "deleted"
    assert food_logs(client, auth)["total"] == 2


def test_chat_override_nutrition(client, auth):
    conv = chat(client, auth, "150g chicken")["conversation_id"]
    r = chat(client, auth, "the chicken was actually 300 kcal", conv)
    assert r["status"] == "completed"
    log = food_logs(client, auth)["items"][0]
    assert log["nutrition"]["calories"] == 300 and log["nutrition"]["calculation_source"] == "user_override"
    assert log["nutrition"]["protein_g"] == 46.5  # untouched macros kept


def test_chat_ambiguous_quantity_asks_then_logs(client, auth):
    r = chat(client, auth, "I ate some chicken.")
    assert r["status"] == "needs_clarification" and "How much chicken" in r["message"]
    assert food_logs(client, auth)["total"] == 0
    r2 = chat(client, auth, "150", r["conversation_id"])  # bare number = grams, as asked
    assert r2["status"] == "completed"
    assert food_logs(client, auth)["items"][0]["nutrition"]["calories"] == 247.5


def test_chat_unknown_food_custom_nutrition_flow(client, auth):
    r = chat(client, auth, "I ate 100g of homemade protein atta")
    assert r["status"] == "needs_clarification" and r["clarification"]["kind"] == "food_unknown"
    conv = r["conversation_id"]
    r2 = chat(client, auth, "100g contains 350 kcal, 25g protein, 50g carbs and 8g fat.", conv)
    assert r2["status"] == "completed", r2
    assert {e["type"] for e in r2["updated_entities"]} == {"custom_food", "food_log"}
    custom = client.get(f"{API}/foods/custom", headers=auth).json()
    assert custom[0]["name"] == "homemade protein atta" and custom[0]["calories"] == 350

    # Saved for future use: next time it resolves directly.
    r3 = chat(client, auth, "had 50g homemade protein atta", conv)
    assert r3["status"] == "completed" and r3["result"]["totals"]["calories"] == 175

    # Editing the custom food does not change historical snapshots.
    cid = custom[0]["id"]
    upd = client.put(f"{API}/foods/custom/{cid}", headers=auth, json={**{k: custom[0][k] for k in (
        "name", "serving_size", "serving_unit", "protein_g", "carbs_g", "fat_g", "fiber_g")}, "calories": 400})
    assert upd.status_code == 200
    cals = sorted(lg["nutrition"]["calories"] for lg in food_logs(client, auth)["items"])
    assert cals == [175, 350]
    # protected from deletion while referenced
    assert client.delete(f"{API}/foods/custom/{cid}", headers=auth).status_code == 409


def test_chat_cancel_pending(client, auth):
    r = chat(client, auth, "I ate some chicken")
    r2 = chat(client, auth, "never mind", r["conversation_id"])
    assert r2["message"] == "Okay, cancelled."


# ----------------------------------------------------------------- chat: other logs
def test_chat_workout_weight_water(client, auth):
    w = chat(client, auth, "I did bench press 60kg for 4 sets of 8.")
    assert w["intent"] == "workout_log" and w["result"]["volume_kg"] == 1920
    conv = w["conversation_id"]
    chat(client, auth, "squats 100kg 5x5", conv)
    hist = client.get(f"{API}/workouts", headers=auth).json()
    assert hist["total"] == 1 and hist["items"][0]["exercise_count"] == 2  # same-day session reused
    fix = chat(client, auth, "actually bench was 65kg", conv)
    assert fix["intent"] == "workout_correction"
    detail = client.get(f"{API}/workouts/{hist['items'][0]['id']}", headers=auth).json()
    bench = next(e for e in detail["exercises"] if e["exercise_name"] == "bench press")
    assert all(s["weight_kg"] == 65 for s in bench["sets"]) and len(bench["sets"]) == 4

    incomplete = chat(client, auth, "bench press 70kg", conv)
    assert incomplete["status"] == "needs_clarification"
    done = chat(client, auth, "3x5", conv)
    assert done["status"] == "completed"

    weight = chat(client, auth, "My weight today is 66.8kg.", conv)
    assert weight["result"]["weight_kg"] == 66.8
    assert client.get(f"{API}/profile", headers=auth).json()["current_weight_kg"] == 66.8
    water = chat(client, auth, "I drank 750ml water.", conv)
    assert water["result"]["day_total_ml"] == 750
    vague = chat(client, auth, "had 2 glasses of water", conv)
    assert vague["status"] == "needs_clarification"
    assert chat(client, auth, "500 ml", conv)["result"]["day_total_ml"] == 1250


# ----------------------------------------------------------------- documents & plans
def test_workout_plan_upload_and_todays_workout(client, auth):
    txt = b"My PPL\nDay 1 - Push\nBench Press 4x8\nIncline DB Press 3x10\nLateral Raise 3x15\nDay 2 - Pull\nDeadlift 3x5\n"
    r = client.post(f"{API}/workout-plans/upload", headers=auth, files={"file": ("ppl.txt", txt, "text/plain")})
    assert r.status_code == 202
    doc = client.get(f"{API}/documents/{r.json()['id']}", headers=auth).json()
    assert doc["processing_status"] == "completed" and doc["workout_plan_id"]
    assert "storage_path" not in doc
    plan = client.get(f"{API}/workout-plans/{doc['workout_plan_id']}", headers=auth).json()
    assert plan["name"] == "My PPL" and len(plan["days"]) == 2

    q = chat(client, auth, "What is today's workout?")
    assert q["intent"] == "workout_query" and q["result"]["day"] == "Push"
    assert [e["exercise_name"] for e in q["result"]["exercises"]][:1] == ["Bench Press"]

    chat(client, auth, "bench press 60kg 4x8", q["conversation_id"])
    q2 = chat(client, auth, "What is today's workout?", q["conversation_id"])
    assert q2["result"]["completed_exercises"] == ["Bench Press"]  # planned vs completed

    bad = client.post(f"{API}/workout-plans/upload", headers=auth, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 422
    fake_pdf = client.post(f"{API}/workout-plans/upload", headers=auth, files={"file": ("x.pdf", b"hello", "application/pdf")})
    assert fake_pdf.status_code == 422
    empty = client.post(f"{API}/workout-plans/upload", headers=auth, files={"file": ("e.txt", b"nothing useful here at all", "text/plain")})
    status = client.get(f"{API}/documents/{empty.json()['id']}", headers=auth).json()
    assert status["processing_status"] == "failed" and status["error_message"]


# ----------------------------------------------------------------- isolation & analytics
def test_user_isolation(client, auth):
    chat(client, auth, "I ate 3 eggs")
    log_id = food_logs(client, auth)["items"][0]["id"]
    other = register(client, "other@example.com", "password123")
    assert food_logs(client, other)["total"] == 0
    assert client.put(f"{API}/food-logs/{log_id}", headers=other, json={"quantity": 9}).status_code == 404
    assert client.delete(f"{API}/food-logs/{log_id}", headers=other).status_code == 404
    convs = client.get(f"{API}/chat/conversations", headers=auth).json()["items"]
    assert client.get(f"{API}/chat/conversations/{convs[0]['id']}/messages", headers=other).status_code == 404
    assert chat(client, other, "actually it was 4 eggs")["status"] == "failed"
    assert food_logs(client, auth)["items"][0]["quantity"] == 3


def test_manual_endpoints_and_analytics(client, auth):
    chat(client, auth, "I ate 3 eggs and 200g rice for breakfast")
    client.post(f"{API}/weight-logs", headers=auth, json={"weight_kg": 70.4})
    client.post(f"{API}/water-logs", headers=auth, json={"amount_ml": 500})
    client.post(f"{API}/workouts", headers=auth, json={"exercises": [
        {"exercise_name": "Deadlift", "sets": [{"reps": 5, "weight_kg": 120}, {"reps": 5, "weight_kg": 130}]}]})

    daily = client.get(f"{API}/analytics/daily", headers=auth).json()
    target = client.get(f"{API}/targets", headers=auth).json()["calorie_target"]
    assert target == 2932  # logging 70.4 kg recalculated today's targets
    assert daily["calories"]["consumed"] == 476 and daily["calories"]["target"] == target
    assert daily["calories"]["remaining"] == target - 476
    assert daily["water_ml"]["consumed"] == 500 and daily["workout"]["completed"]
    assert abs(sum(daily["macro_distribution"].values()) - 100) < 0.2

    n = client.get(f"{API}/analytics/nutrition?granularity=daily", headers=auth).json()
    assert len(n["points"]) == 7 and n["points"][-1]["calories"] == 476
    wk = client.get(f"{API}/analytics/workouts", headers=auth).json()
    assert wk["workout_count"] == 1 and wk["total_volume_kg"] == 1250
    assert wk["personal_records"][0]["best_weight_kg"] == 130
    wt = client.get(f"{API}/analytics/weight", headers=auth).json()
    assert wt["current_weight_kg"] == 70.4 and wt["points"][0]["weight_kg"] == 70.4
    s = client.get(f"{API}/analytics/summary", headers=auth).json()
    assert s["today"]["food_log_count"] == 2 and s["recent_activity"]
    bad = client.get(f"{API}/analytics/nutrition?from=2026-10-10&to=2026-10-01", headers=auth)
    assert bad.status_code == 422

    search = client.get(f"{API}/foods/search?q=rice&page_size=1", headers=auth).json()
    assert search["total"] >= 2 and len(search["items"]) == 1
    page2 = client.get(f"{API}/foods/search?q=rice&page=2&page_size=1", headers=auth).json()
    assert page2["items"][0]["id"] != search["items"][0]["id"]

    log = food_logs(client, auth)["items"][0]
    upd = client.put(f"{API}/food-logs/{log['id']}", headers=auth, json={"quantity": log["quantity"] * 2})
    assert upd.json()["nutrition"]["calories"] == round(log["nutrition"]["calories"] * 2, 2)
