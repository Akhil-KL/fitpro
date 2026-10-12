"""Chat orchestration: parse -> validate -> business logic -> persist -> respond.

The parser only produces a validated `ParsedMessage`. This service decides what
is written, always scoped to the authenticated user, inside one transaction per
message. Replies are built from backend-calculated values only.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.calculations.aggregation import as_utc, get_zone, local_day_bounds
from app.calculations.nutrition import UnitMismatch, normalize_unit
from app.calculations.profile import bmi, bmr, tdee
from app.core.errors import AppError, NotFound
from app.models import ChatMessage, Conversation, FoodLog, User, UserProfile
from app.repositories.food_repository import FoodRepository
from app.repositories.tracking_repository import ChatRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.ai import Correction, ExerciseEntry, NutritionFacts, ParsedMessage
from app.schemas.chat import ChatRequest, ChatResponse, UpdatedEntity
from app.schemas.food import FoodLogUpdate, NutritionOverride
from app.services.ai_parser import AIParser, ParseContext
from app.services.analytics_service import AnalyticsService
from app.services.nutrition_service import FoodSource, NutritionService, snapshot_values
from app.services.profile_service import ProfileService
from app.services.rule_parser import extract_quantity, parse_exercise, parse_nutrition_facts, singularize
from app.services.tracking_service import TrackingService
from app.services.workout_service import WorkoutService, describe_sets, same_exercise, session_volume

log = logging.getLogger(__name__)

CANCEL_RE = re.compile(r"^\s*(cancel|never ?mind|nvm|skip|forget it|stop|no thanks|nope)\b", re.I)
CORRECTION_WINDOW = timedelta(hours=36)

HELP_TEXT = (
    "I can log things for you. Try:\n"
    "• \"I ate 3 eggs and 200g rice for breakfast\"\n"
    "• \"Bench press 60kg 4x8\"\n"
    "• \"My weight is 66.8kg\" or \"I drank 750ml water\"\n"
    "• \"Actually the rice was 250g\"\n"
    "• \"How much protein have I eaten today?\" or \"What's today's workout?\""
)


# ------------------------------------------------------------------ formatting
def fmt_num(v: float, digits: int = 1) -> str:
    v = round(v, digits)
    return f"{v:,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{v:,.0f}"


def fmt_amount(quantity: float, unit: str, name: str) -> str:
    q = fmt_num(quantity, 2)
    if unit == "piece":
        return f"{q} {name}" if quantity == 1 else f"{q} × {name}"
    if unit == "serving":
        return f"{q} serving{'s' if quantity != 1 else ''} of {name}"
    return f"{q} {unit} {name}"


def join_human(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


@dataclass
class Outcome:
    message: str
    intent: str
    status: str = "completed"
    result: dict[str, Any] | None = None
    entities: list[UpdatedEntity] = field(default_factory=list)
    clarification: dict[str, Any] | None = None


class ChatService:
    def __init__(self, db: Session, parser: AIParser | None = None) -> None:
        self.db = db
        self.parser = parser or AIParser()
        self.chats = ChatRepository(db)
        self.foods = FoodRepository(db)
        self.nutrition = NutritionService(db)
        self.workouts = WorkoutService(db)
        self.workout_repo = WorkoutRepository(db)
        self.tracking = TrackingService(db)
        self.analytics = AnalyticsService(db)
        self.profiles = ProfileService(db)

    # =============================================================== entry point
    def handle(self, user: User, req: ChatRequest) -> ChatResponse:
        conv = self._conversation(user, req.conversation_id)
        profile = self.profiles.get_or_create(user)
        self.db.commit()
        conv_id = conv.id
        state: dict = dict(conv.state or {})
        recent = [{"role": m.role, "content": m.content}
                  for m in self.chats.recent_messages(conv.id, self.parser.settings.chat_context_messages)]
        tz = get_zone(profile.timezone)
        ctx = ParseContext(recent_messages=recent, state=self._state_for_llm(state), today=datetime.now(tz).date())
        parse = self.parser.parse(req.message, ctx)
        parsed = parse.parsed

        try:
            outcome = self._dispatch(user, profile, state, parsed, req.message)
        except AppError as exc:
            self.db.rollback()
            outcome = Outcome(message=exc.message, intent=parsed.intent, status="failed")
            state = dict(conv.state or {})
        except Exception:
            log.exception("chat dispatch failed")
            self.db.rollback()
            outcome = Outcome(message="Sorry, something went wrong saving that. Nothing was changed — please try again.",
                              intent=parsed.intent, status="failed")
            state = dict(conv.state or {})

        conv = self.db.get(Conversation, conv_id)
        assert conv is not None
        user_msg = ChatMessage(conversation_id=conv.id, role="user", content=req.message, parsed_intent=parsed.intent,
                               parsed_payload={"parser": parse.source, "parsed": parsed.model_dump(mode="json", exclude_defaults=True)})
        now = datetime.now(timezone.utc)
        assistant = ChatMessage(conversation_id=conv.id, role="assistant", content=outcome.message,
                                parsed_intent=outcome.intent, created_at=now + timedelta(microseconds=1),
                                parsed_payload={"status": outcome.status, "result": outcome.result,
                                                "options": (outcome.clarification or {}).get("options")})
        user_msg.created_at = now
        self.db.add_all([user_msg, assistant])
        conv.state = state or None
        conv.updated_at = now
        if not conv.title:
            conv.title = req.message[:80]
        self.db.commit()
        return ChatResponse(
            conversation_id=conv.id, message_id=assistant.id, message=outcome.message, intent=outcome.intent,
            status=outcome.status, result=outcome.result, updated_entities=outcome.entities,
            clarification=outcome.clarification, parser=parse.source,
        )

    def _conversation(self, user: User, conv_id: uuid.UUID | None) -> Conversation:
        if conv_id is not None:
            conv = self.chats.conversation(user.id, conv_id)
            if conv is None:
                raise NotFound("Conversation not found.")
            return conv
        conv = Conversation(user_id=user.id)
        self.db.add(conv)
        self.db.flush()
        return conv

    @staticmethod
    def _state_for_llm(state: dict) -> dict:
        p = state.get("pending")
        if not p:
            return {}
        return {"pending": {k: p.get(k) for k in ("kind", "question", "item", "options") if p.get(k) is not None}}

    # =============================================================== dispatch
    def _dispatch(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage, text: str) -> Outcome:
        pending = state.get("pending")
        if pending:
            if CANCEL_RE.match(text):
                state.pop("pending", None)
                return Outcome("Okay, cancelled.", "clarification")
            resolved = self._resolve_pending(user, profile, state, pending, parsed, text)
            if resolved is not None:
                return resolved
            state.pop("pending", None)  # user moved on: drop the stale question

        handler = {
            "food_log": self._food_log,
            "food_correction": self._food_correction,
            "workout_correction": self._workout_correction,
            "custom_food_create": self._custom_food,
            "custom_food_update": self._custom_food,
            "workout_log": self._workout_log,
            "weight_log": self._weight_log,
            "water_log": self._water_log,
            "nutrition_query": self._nutrition_query,
            "daily_summary": self._daily_summary,
            "goal_query": self._goal_query,
            "progress_query": self._progress_query,
            "workout_query": self._workout_query,
            "general_fitness_query": self._general,
        }.get(parsed.intent)
        if handler is None:
            if parsed.intent == "clarification":
                return Outcome("I'm not sure what that refers to. " + HELP_TEXT, "clarification", status="answered")
            return Outcome("I didn't catch that. " + HELP_TEXT, "unknown", status="answered")
        return handler(user, profile, state, parsed)

    def _when(self, parsed_or_offset: ParsedMessage | int) -> datetime:
        offset = parsed_or_offset if isinstance(parsed_or_offset, int) else parsed_or_offset.day_offset
        return datetime.now(timezone.utc) + timedelta(days=offset)

    # =============================================================== food logging
    def _food_log(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        items = [i.model_dump() for i in parsed.items if i.food_name and i.food_name != "_"]
        if not items:
            return Outcome("What did you eat, and how much?", "food_log", status="needs_clarification")
        return self._process_food_queue(user, state, items, parsed.meal, parsed.day_offset, logged=[])

    def _process_food_queue(
        self, user: User, state: dict, queue: list[dict], meal: str | None, day_offset: int, logged: list[FoodLog]
    ) -> Outcome:
        when = self._when(day_offset)
        while queue:
            item = queue.pop(0)
            question = self._try_log_item(user, item, meal, when, logged, state, queue, day_offset)
            if question is not None:
                return self._food_reply(logged, question, state)
        state.pop("pending", None)
        return self._food_reply(logged, None, state)

    def _try_log_item(
        self, user: User, item: dict, meal: str | None, when: datetime, logged: list[FoodLog], state: dict,
        queue: list[dict], day_offset: int,
    ) -> Outcome | None:
        """Log one item, or set a pending question and return it."""
        food: FoodSource | None = self.nutrition.get_source(user.id, item.get("food_id"), item.get("custom_food_id"))
        if food is None:
            res = self.nutrition.resolve(user.id, item["food_name"])
            if res.kind == "unknown":
                q = (f"I don't have nutrition info for \"{item['food_name']}\". Tell me what it contains and I'll save it "
                     f"as a custom food — e.g. \"100g has 350 kcal, 25g protein, 50g carbs, 8g fat\".")
                return self._ask(state, "food_unknown", q, item=item, queue=queue, meal=meal, day_offset=day_offset)
            if res.kind == "ambiguous":
                options = [{"id": str(c.id), "name": c.name, "custom": c.__class__.__name__ == "CustomFood"} for c in res.candidates]
                lines = "\n".join(f"{i}. {o['name']}" for i, o in enumerate(options, 1))
                q = f"Which \"{item['food_name']}\" did you mean?\n{lines}"
                return self._ask(state, "food_choice", q, item=item, queue=queue, meal=meal, day_offset=day_offset,
                                 options=options)
            food = res.food
            assert food is not None
            item["food_id"] = None if food.__class__.__name__ == "CustomFood" else str(food.id)
            item["custom_food_id"] = str(food.id) if food.__class__.__name__ == "CustomFood" else None
            item["resolved_name"] = food.name

        if item.get("quantity") is None:
            if food.serving_unit in ("g", "ml") and not food.grams_per_piece:
                hint, expected = ("grams", "g") if food.serving_unit == "g" else ("ml", "ml")
            elif food.serving_unit == "serving":
                hint, expected = "servings", "serving"
            else:
                hint, expected = "pieces or grams", None
            q = f"How much {item['food_name']} did you have? (in {hint})"
            return self._ask(state, "food_quantity", q, item={**item, "expected_unit": expected}, queue=queue,
                             meal=meal, day_offset=day_offset)

        unit = self.nutrition.effective_unit(food, item["quantity"], item.get("unit"))
        if unit is None:
            q = f"How many grams of {item['food_name']} was that?"
            return self._ask(state, "food_quantity", q, item={**item, "quantity": None, "expected_unit": "g"},
                             queue=queue, meal=meal, day_offset=day_offset)
        try:
            entry = self.nutrition.create_log(user, food, item["quantity"], unit, logged_at=when, meal_type=meal)
        except UnitMismatch:
            basis = "grams" if food.serving_unit == "g" else food.serving_unit + "s"
            q = (f"I can't convert {item.get('unit') or unit} of {food.name} without guessing. "
                 f"How much was it in {basis}?")
            expected = "g" if food.serving_unit == "g" else food.serving_unit
            return self._ask(state, "food_quantity", q, item={**item, "quantity": None, "unit": None,
                                                              "expected_unit": expected}, queue=queue,
                             meal=meal, day_offset=day_offset)
        logged.append(entry)
        ids = state.setdefault("recent_food_log_ids", [])
        ids.append(str(entry.id))
        state["recent_food_log_ids"] = ids[-10:]
        return None

    def _ask(self, state: dict, kind: str, question: str, **data) -> Outcome:
        state["pending"] = {"kind": kind, "question": question, **data}
        return Outcome(question, "clarification", status="needs_clarification",
                       clarification={"kind": kind, "question": question,
                                      "options": data.get("options")})

    def _food_reply(self, logged: list[FoodLog], question: Outcome | None, state: dict) -> Outcome:
        entities = [UpdatedEntity(type="food_log", id=lg.id, action="created") for lg in logged]
        if not logged:
            assert question is not None
            return question
        total = sum((snapshot_values(lg) for lg in logged[1:]), snapshot_values(logged[0]))
        parts = [fmt_amount(lg.quantity, lg.unit, lg.food_name) for lg in logged]
        msg = (f"Logged {join_human(parts)} — {fmt_num(total.calories, 0)} kcal and "
               f"{fmt_num(total.protein_g)} g protein.")
        result = {
            "logged": [{"id": str(lg.id), "food_name": lg.food_name, "quantity": lg.quantity, "unit": lg.unit,
                        "meal_type": lg.meal_type, "calories": lg.nutrition.calories,
                        "protein_g": lg.nutrition.protein_g} for lg in logged],
            "totals": {"calories": total.calories, "protein_g": total.protein_g, "carbs_g": total.carbs_g,
                       "fat_g": total.fat_g},
        }
        if question is not None:
            return Outcome(f"{msg}\n\n{question.message}", "food_log", status="needs_clarification", result=result,
                           entities=entities, clarification=question.clarification)
        return Outcome(msg, "food_log", result=result, entities=entities)

    # =============================================================== pending answers
    def _resolve_pending(
        self, user: User, profile: UserProfile, state: dict, p: dict, parsed: ParsedMessage, text: str
    ) -> Outcome | None:
        kind = p.get("kind")
        queue: list[dict] = p.get("queue") or []
        meal, day_offset = p.get("meal"), p.get("day_offset", 0)

        if kind == "food_quantity":
            qty, unit = self._answer_quantity(parsed, text, p["item"]["food_name"])
            if qty is None:
                return None
            item = {**p["item"], "quantity": qty, "unit": unit or p["item"].get("expected_unit")}
            return self._process_food_queue(user, state, [item, *queue], meal, day_offset, logged=[])

        if kind == "food_choice":
            options = p.get("options") or []
            choice = self._answer_choice(parsed, text, [o["name"] for o in options])
            if choice is None:
                return None
            opt = options[choice]
            item = {**p["item"], "food_id": None if opt["custom"] else opt["id"],
                    "custom_food_id": opt["id"] if opt["custom"] else None}
            return self._process_food_queue(user, state, [item, *queue], meal, day_offset, logged=[])

        if kind in ("food_unknown", "nutrition_basis"):
            facts = parsed.nutrition or parse_nutrition_facts(text)
            if kind == "nutrition_basis":
                stored = NutritionFacts.model_validate(p["facts"])
                qty, unit = extract_quantity(text)
                if not unit or unit == "vague":
                    if re.search(r"\b(piece|each|one)\b", text, re.I):
                        qty, unit = 1, "piece"
                    elif re.search(r"\bserving|scoop\b", text, re.I):
                        qty, unit = 1, "serving"
                    else:
                        return None
                facts = stored.model_copy(update={"basis_quantity": qty or 1, "basis_unit": unit})
            if facts is None or facts.calories is None:
                return None
            if not facts.basis_unit:
                q = "Is that per 100 g, per piece, or per serving?"
                return self._ask(state, "nutrition_basis", q, item=p["item"], queue=queue, meal=meal,
                                 day_offset=day_offset, facts=facts.model_dump())
            name = p["item"]["food_name"]
            cf, created = self.nutrition.upsert_custom_from_facts(user, name, facts)
            entity = UpdatedEntity(type="custom_food", id=cf.id, action="created" if created else "updated")
            item = {**p["item"], "custom_food_id": str(cf.id), "food_id": None}
            out = self._process_food_queue(user, state, [item, *queue], meal, day_offset, logged=[])
            out.message = f"Saved \"{cf.name}\" as a custom food. " + out.message
            out.entities.insert(0, entity)
            return out

        if kind == "correction_choice":
            options = p.get("options") or []
            choice = self._answer_choice(parsed, text, [o["name"] for o in options])
            if choice is None:
                return None
            entry = self.foods.log_get(user.id, uuid.UUID(options[choice]["id"]))
            state.pop("pending", None)
            if entry is None:
                return Outcome("That entry no longer exists.", "food_correction", status="failed")
            return self._apply_food_correction(user, entry, Correction.model_validate(p["correction"]))

        if kind == "workout_details":
            entry = ExerciseEntry.model_validate(p["exercise"])
            ex = parse_exercise(f"{entry.exercise_name} {text}")
            if ex is None or (ex.reps is None and ex.duration_seconds is None):
                return None
            merged = entry.model_copy(update={k: v for k, v in ex.model_dump().items() if v is not None and k != "exercise_name"})
            rest = [ExerciseEntry.model_validate(e) for e in p.get("queue", [])]
            state.pop("pending", None)
            return self._log_exercises(user, profile, state, [merged, *rest], day_offset)

        if kind == "water_amount":
            qty, unit = extract_quantity(text)
            if qty is None or unit not in ("ml", "l", "cup"):
                return None
            amount = qty * {"ml": 1, "l": 1000, "cup": 240}[unit]
            state.pop("pending", None)
            return self._water_log(user, profile, state, ParsedMessage(intent="water_log", amount_ml=amount, day_offset=day_offset))

        if kind == "weight_amount":
            qty, unit = extract_quantity(text)
            if qty is None:
                return None
            kg = qty * 0.453592 if unit == "lb" else qty
            if not 20 <= kg <= 400:
                return None
            state.pop("pending", None)
            return self._weight_log(user, profile, state, ParsedMessage(intent="weight_log", weight_kg=kg, day_offset=day_offset))

        if kind == "custom_food_name":
            name = text.strip().strip("\"'.").lower()
            if not name or len(name) > 160 or parsed.intent not in ("unknown", "clarification", "food_log"):
                return None
            facts = NutritionFacts.model_validate(p["facts"])
            state.pop("pending", None)
            return self._custom_food(user, profile, state, ParsedMessage(intent="custom_food_create",
                                                                         custom_food_name=name, nutrition=facts))
        return None

    @staticmethod
    def _answer_quantity(parsed: ParsedMessage, text: str, food_name: str) -> tuple[float | None, str | None]:
        if parsed.intent == "clarification" and parsed.selection is not None:
            return float(parsed.selection), None
        if parsed.intent in ("clarification", "food_log", "unknown") and parsed.items:
            it = parsed.items[0]
            same = it.food_name == "_" or singularize(it.food_name) == singularize(food_name) or len(parsed.items) == 1 and \
                (food_name in it.food_name or it.food_name in food_name)
            if same and it.quantity is not None:
                return it.quantity, normalize_unit(it.unit) if it.unit else None
        if parsed.intent in ("clarification", "unknown"):
            qty, unit = extract_quantity(text)
            if qty is not None and unit != "vague":
                return qty, unit
        return None, None

    @staticmethod
    def _answer_choice(parsed: ParsedMessage, text: str, names: list[str]) -> int | None:
        if parsed.selection is not None and 1 <= parsed.selection <= len(names):
            return parsed.selection - 1
        t = text.strip().lower()
        hits = [i for i, n in enumerate(names) if t and (t in n.lower() or n.lower() in t)]
        return hits[0] if len(hits) == 1 else None

    # =============================================================== corrections
    def _recent_food_matches(self, user: User, state: dict, target: str | None) -> list[FoodLog]:
        since = datetime.now(timezone.utc) - CORRECTION_WINDOW
        recent = self.foods.recent_logs(user.id, since)
        if not target:
            ids = state.get("recent_food_log_ids") or []
            if ids:
                by_id = {str(lg.id): lg for lg in recent}
                for i in reversed(ids):
                    if i in by_id:
                        return [by_id[i]]
            return recent[:1]
        t = singularize(target.lower())
        matches = []
        for lg in recent:
            name = lg.food_name.lower()
            if t in name or singularize(name) in t or any(t == singularize(w) for w in re.split(r"[\s(),]+", name) if w):
                matches.append(lg)
        if not matches:
            res = self.nutrition.resolve(user.id, target)
            if res.kind == "found" and res.food is not None:
                matches = [lg for lg in recent if lg.food_id == res.food.id or lg.custom_food_id == res.food.id]
        return matches

    def _food_correction(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        c = parsed.correction
        if c is None:
            return Outcome("What should I change?", "food_correction", status="needs_clarification")
        matches = self._recent_food_matches(user, state, c.target_name)
        if not matches:
            if c.target_name and self.workouts.find_recent_exercise(user, c.target_name):
                return self._workout_correction(user, profile, state, parsed.model_copy(update={"intent": "workout_correction"}))
            what = f"a recent \"{c.target_name}\" entry" if c.target_name else "a recent food entry"
            return Outcome(f"I couldn't find {what} to change.", "food_correction", status="failed")
        if len(matches) > 1:
            recent_ids = set(state.get("recent_food_log_ids") or [])
            in_batch = [m for m in matches if str(m.id) in recent_ids]
            if len(in_batch) == 1:
                matches = in_batch
            else:
                tz = get_zone(profile.timezone)
                options = [{"id": str(m.id), "name": f"{fmt_amount(m.quantity, m.unit, m.food_name)} at "
                            f"{as_utc(m.logged_at).astimezone(tz).strftime('%H:%M')}"}
                           for m in matches[:5]]
                lines = "\n".join(f"{i}. {o['name']}" for i, o in enumerate(options, 1))
                return self._ask(state, "correction_choice", f"Which entry should I change?\n{lines}",
                                 options=options, correction=c.model_dump())
        return self._apply_food_correction(user, matches[0], c)

    def _apply_food_correction(self, user: User, entry: FoodLog, c: Correction) -> Outcome:
        before = fmt_amount(entry.quantity, entry.unit, entry.food_name)
        if c.delete:
            self.nutrition.delete_log(user, entry)
            return Outcome(f"Deleted {before}.", "food_correction",
                           entities=[UpdatedEntity(type="food_log", id=entry.id, action="deleted")])
        upd = FoodLogUpdate()
        if c.nutrition_override is not None and c.nutrition_override.calories is not None:
            cur = snapshot_values(entry)
            o = c.nutrition_override
            upd.nutrition_override = NutritionOverride(
                calories=o.calories, protein_g=o.protein_g if o.protein_g is not None else cur.protein_g,
                carbs_g=o.carbs_g if o.carbs_g is not None else cur.carbs_g,
                fat_g=o.fat_g if o.fat_g is not None else cur.fat_g,
                fiber_g=o.fiber_g if o.fiber_g is not None else cur.fiber_g,
            )
        if c.quantity is not None:
            upd.quantity = c.quantity
            unit = normalize_unit(c.unit) if c.unit else None
            upd.unit = unit if unit and unit != "vague" else None
        if upd.quantity is None and upd.nutrition_override is None:
            return Outcome("What's the correct amount?", "food_correction", status="needs_clarification")
        self.nutrition.update_log(user, entry, upd)
        n = entry.nutrition
        after = fmt_amount(entry.quantity, entry.unit, entry.food_name)
        msg = (f"Updated {before} → {after}: now {fmt_num(n.calories, 0)} kcal and {fmt_num(n.protein_g)} g protein."
               if before != after else
               f"Updated {after}: now {fmt_num(n.calories, 0)} kcal and {fmt_num(n.protein_g)} g protein.")
        return Outcome(msg, "food_correction", result={"id": str(entry.id), "calories": n.calories, "protein_g": n.protein_g},
                       entities=[UpdatedEntity(type="food_log", id=entry.id, action="updated")])

    def _workout_correction(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        c = parsed.correction
        if c is None:
            return Outcome("What should I change about the workout?", "workout_correction", status="needs_clarification")
        found = self.workouts.find_recent_exercise(user, c.target_name)
        if not found:
            if c.target_name and c.quantity is not None and self._recent_food_matches(user, state, c.target_name):
                return self._food_correction(user, profile, state, parsed.model_copy(update={"intent": "food_correction"}))
            what = f"\"{c.target_name}\"" if c.target_name else "an exercise"
            return Outcome(f"I couldn't find {what} in your recent workouts.", "workout_correction", status="failed")
        ex = found[0]
        if c.weight_kg is None and c.quantity is not None and (c.unit or "").lower() in ("kg", "lb"):
            c = c.model_copy(update={"weight_kg": c.quantity * (0.453592 if c.unit == "lb" else 1)})
        before = describe_sets(ex)
        self.workouts.apply_correction(ex, c)
        if c.delete:
            return Outcome(f"Removed {before}.", "workout_correction",
                           entities=[UpdatedEntity(type="workout_session", id=ex.workout_session_id, action="updated")])
        return Outcome(f"Updated {before} → {describe_sets(ex)}.", "workout_correction",
                       entities=[UpdatedEntity(type="workout_session", id=ex.workout_session_id, action="updated")])

    # =============================================================== custom foods
    def _custom_food(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        facts = parsed.nutrition
        if facts is None or facts.calories is None:
            return Outcome("Tell me the calories (and protein, carbs, fat if you know them) and the amount they're for — "
                           "e.g. \"per 100g: 350 kcal, 25g protein\".", parsed.intent, status="needs_clarification")
        if not parsed.custom_food_name:
            return self._ask(state, "custom_food_name", "What should I call this food?", facts=facts.model_dump())
        if not facts.basis_unit:
            return Outcome("Is that per 100 g, per piece or per serving? Please resend with the amount, e.g. "
                           "\"per 100g: 350 kcal...\".", parsed.intent, status="needs_clarification")
        cf, created = self.nutrition.upsert_custom_from_facts(user, parsed.custom_food_name, facts)
        verb = "Saved" if created else "Updated"
        msg = (f"{verb} custom food \"{cf.name}\": {fmt_num(cf.calories, 0)} kcal, {fmt_num(cf.protein_g)} g protein, "
               f"{fmt_num(cf.carbs_g)} g carbs, {fmt_num(cf.fat_g)} g fat per {fmt_num(cf.serving_size, 2)} {cf.serving_unit}.")
        return Outcome(msg, parsed.intent, entities=[UpdatedEntity(type="custom_food", id=cf.id,
                                                                   action="created" if created else "updated")])

    # =============================================================== workouts
    def _workout_log(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        if not parsed.exercises:
            return Outcome("Which exercise did you do, and how many sets and reps?", "workout_log", status="needs_clarification")
        return self._log_exercises(user, profile, state, list(parsed.exercises), parsed.day_offset)

    def _log_exercises(self, user: User, profile: UserProfile, state: dict, entries: list[ExerciseEntry], day_offset: int) -> Outcome:
        complete = [e for e in entries if not self.workouts.missing_fields(e)]
        incomplete = [e for e in entries if self.workouts.missing_fields(e)]
        parts: list[str] = []
        entities: list[UpdatedEntity] = []
        result = None
        if complete:
            session = self.workouts.log_entries(user, complete, self._when(day_offset), profile.timezone)
            new = session.exercises[-len(complete):]
            parts = [describe_sets(e) for e in new]
            vol = sum(sum((s.reps or 0) * (s.weight_kg or 0) for s in e.sets) for e in new)
            entities = [UpdatedEntity(type="workout_session", id=session.id, action="updated")]
            result = {"session_id": str(session.id), "exercises": parts, "volume_kg": vol,
                      "session_volume_kg": session_volume(session)}
        msg = ""
        if parts:
            vol = result["volume_kg"] if result else 0
            msg = f"Logged {join_human(parts)}." + (f" Volume: {fmt_num(vol, 0)} kg." if vol else "")
        if incomplete:
            first, rest = incomplete[0], incomplete[1:]
            q = f"How many sets and reps (or how long) for {first.exercise_name}?"
            ask = self._ask(state, "workout_details", q, exercise=first.model_dump(),
                            queue=[e.model_dump() for e in rest], day_offset=day_offset)
            return Outcome((msg + "\n\n" if msg else "") + q, "workout_log", status="needs_clarification",
                           result=result, entities=entities, clarification=ask.clarification)
        state.pop("pending", None)
        return Outcome(msg, "workout_log", result=result, entities=entities)

    # =============================================================== weight & water
    def _weight_log(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        if parsed.weight_kg is None:
            q = parsed.clarification_question or "What was your weight (in kg)?"
            return self._ask(state, "weight_amount", q, day_offset=parsed.day_offset)
        previous = self.analytics.tracking.latest_weight(user.id)
        entry = self.tracking.log_weight(user, parsed.weight_kg, self._when(parsed))
        msg = f"Logged your weight: {fmt_num(entry.weight_kg, 2)} kg."
        if previous is not None:
            diff = round(entry.weight_kg - previous.weight_kg, 2)
            if diff:
                msg += f" That's {fmt_num(abs(diff), 2)} kg {'up' if diff > 0 else 'down'} from your last entry."
        if profile.target_weight_kg:
            left = round(entry.weight_kg - profile.target_weight_kg, 1)
            if left:
                msg += f" {fmt_num(abs(left))} kg to go to your {fmt_num(profile.target_weight_kg)} kg target."
        return Outcome(msg, "weight_log", result={"weight_kg": entry.weight_kg},
                       entities=[UpdatedEntity(type="weight_log", id=entry.id, action="created")])

    def _water_log(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        if parsed.amount_ml is None:
            q = parsed.clarification_question or "How much water was that, in ml or litres?"
            return self._ask(state, "water_amount", q, day_offset=parsed.day_offset)
        entry = self.tracking.log_water(user, parsed.amount_ml, self._when(parsed))
        day = self.analytics.daily(user, (datetime.now(get_zone(profile.timezone)) + timedelta(days=parsed.day_offset)).date())
        w = day["water_ml"]
        msg = f"Logged {fmt_num(entry.amount_ml, 0)} ml of water."
        msg += f" {fmt_num(w['consumed'], 0)}" + (f" / {fmt_num(w['target'], 0)} ml" if w["target"] else " ml") + " so far."
        return Outcome(msg, "water_log", result={"amount_ml": entry.amount_ml, "day_total_ml": w["consumed"]},
                       entities=[UpdatedEntity(type="water_log", id=entry.id, action="created")])

    # =============================================================== queries
    def _day(self, profile: UserProfile, offset: int):
        return (datetime.now(get_zone(profile.timezone)) + timedelta(days=offset)).date()

    def _nutrition_query(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        d = self.analytics.daily(user, self._day(profile, parsed.day_offset))
        when = "today" if parsed.day_offset == 0 else "yesterday"
        metric = parsed.query_metric or "calories"
        key, unit, label = {
            "calories": ("calories", "kcal", "calories"), "protein": ("protein_g", "g", "protein"),
            "carbs": ("carbs_g", "g", "carbs"), "fat": ("fat_g", "g", "fat"), "fiber": ("fiber_g", "g", "fiber"),
            "water": ("water_ml", "ml", "water"),
        }.get(metric, ("calories", "kcal", "calories"))
        v = d[key]
        sp = "" if unit == "kcal" else " "
        msg = f"You've had {fmt_num(v['consumed'] or 0, 0 if unit != 'g' else 1)}{' ' if unit == 'kcal' else sp}{unit} of {label} {when}"
        if v.get("target"):
            rem = v["remaining"]
            msg += (f" — {fmt_num(rem, 0)} {unit} left of your {fmt_num(v['target'], 0)} {unit} target." if rem >= 0
                    else f" — {fmt_num(-rem, 0)} {unit} over your {fmt_num(v['target'], 0)} {unit} target.")
        else:
            msg += ". Complete your profile to get a target."
        return Outcome(msg, "nutrition_query", status="answered", result={"metric": metric, **v})

    def _daily_summary(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        d = self.analytics.daily(user, self._day(profile, parsed.day_offset))
        when = "Today" if parsed.day_offset == 0 else "Yesterday"
        c, p = d["calories"], d["protein_g"]
        lines = [f"{when}: {fmt_num(c['consumed'] or 0, 0)}" + (f" / {fmt_num(c['target'], 0)}" if c["target"] else "") + " kcal, "
                 f"{fmt_num(p['consumed'] or 0)}" + (f" / {fmt_num(p['target'], 0)}" if p["target"] else "") + " g protein, "
                 f"{fmt_num(d['carbs_g']['consumed'] or 0)} g carbs, {fmt_num(d['fat_g']['consumed'] or 0)} g fat."]
        w = d["water_ml"]
        lines.append(f"Water: {fmt_num(w['consumed'], 0)}" + (f" / {fmt_num(w['target'], 0)}" if w["target"] else "") + " ml.")
        wk = d["workout"]
        lines.append("Workout: " + (join_human(wk["exercises"]) + "." if wk["completed"] else "none logged yet."))
        if d["meals"]:
            foods = [f"{fmt_amount(i['quantity'], i['unit'], i['food_name'])}" for items in d["meals"].values() for i in items]
            lines.append("Food: " + join_human(foods[:12]) + ("…" if len(foods) > 12 else "") + ".")
        return Outcome("\n".join(lines), "daily_summary", status="answered", result=d)

    def _goal_query(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        t = UserRepository(self.db).active_targets(user.id)
        if t is None or not ProfileService.is_complete(profile):
            return Outcome("Complete your profile (age, sex, height, weight, activity level and goal) and I'll calculate "
                           "your targets.", "goal_query", status="answered")
        b = bmr(profile.current_weight_kg, profile.height_cm, profile.age, profile.gender)  # type: ignore[arg-type]
        msg = (f"Your daily targets: {fmt_num(t.calorie_target, 0)} kcal, {t.protein_target_g} g protein, "
               f"{t.carbs_target_g} g carbs, {t.fat_target_g} g fat and {fmt_num(t.water_target_ml, 0)} ml water. "
               f"(BMR {fmt_num(b, 0)} kcal, TDEE {fmt_num(tdee(b, profile.activity_level), 0)} kcal, "  # type: ignore[arg-type]
               f"BMI {bmi(profile.current_weight_kg, profile.height_cm)}.)")  # type: ignore[arg-type]
        return Outcome(msg, "goal_query", status="answered")

    def _progress_query(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        today = self._day(profile, 0)
        if parsed.query_metric == "workout":
            w = self.analytics.workouts(user, today - timedelta(days=29), today)
            n = w["workout_count"]
            msg = (f"Last 30 days: {n} workout{'s' if n != 1 else ''} ({fmt_num(w['weekly_frequency'])} per week), "
                   f"{w['total_sets']} sets, {fmt_num(w['total_volume_kg'], 0)} kg total volume.")
            prs = w["personal_records"][:3]
            if prs:
                msg += " Best lifts: " + join_human([f"{p['exercise']} {fmt_num(p['best_weight_kg'])} kg" for p in prs]) + "."
            return Outcome(msg, "progress_query", status="answered", result=w)
        w = self.analytics.weight(user, today - timedelta(days=89), today)
        if w["current_weight_kg"] is None:
            return Outcome("No weight entries yet. Tell me \"my weight is 70kg\" to start tracking.", "progress_query",
                           status="answered")
        msg = f"Current weight {fmt_num(w['current_weight_kg'], 2)} kg"
        ch = w["change_kg"]
        if ch and w["starting_weight_kg"] is not None:
            msg += f" — {'down' if ch < 0 else 'up'} {fmt_num(abs(ch), 2)} kg from your starting {fmt_num(w['starting_weight_kg'], 2)} kg"
        elif ch == 0:
            msg += " — no change from your starting weight yet"
        msg += "."
        if w["avg_weekly_change_kg"] is not None:
            msg += f" Average {fmt_num(w['avg_weekly_change_kg'], 2)} kg/week over the last 90 days."
        if w["progress_pct"] is not None:
            msg += f" {fmt_num(w['progress_pct'])}% of the way to {fmt_num(w['target_weight_kg'])} kg."
        return Outcome(msg, "progress_query", status="answered", result=w)

    def _workout_query(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        plan = self.workout_repo.active_plan(user.id)
        if plan is None:
            return Outcome("You don't have a workout plan yet. Upload your split (PDF or TXT) on the Workouts page and "
                           "I'll tell you what to train each day.", "workout_query", status="answered")
        day = self.workouts.todays_plan_day(user, plan, profile.timezone)
        if day is None or not day.exercises:
            name = day.name if day else "Rest"
            return Outcome(f"Today is a rest day on \"{plan.name}\" ({name}). Recover well!", "workout_query",
                           status="answered", result={"plan_id": str(plan.id), "day": name, "exercises": []})
        lines = []
        for e in day.exercises:
            spec = ""
            if e.sets and (e.rep_range or e.target_reps):
                spec = f"{e.sets}×{e.rep_range or e.target_reps}"
            elif e.sets and e.duration_seconds:
                spec = f"{e.sets}×{e.duration_seconds}s"
            elif e.duration_seconds:
                spec = f"{e.duration_seconds // 60} min" if e.duration_seconds >= 60 else f"{e.duration_seconds}s"
            if e.target_weight:
                spec += f" @ {fmt_num(e.target_weight)} kg"
            lines.append(f"• {e.exercise_name}" + (f" — {spec}" if spec else ""))
        tz = get_zone(profile.timezone)
        start, end = local_day_bounds(datetime.now(tz).date(), tz)
        done = {e.exercise_name for s in self.workout_repo.sessions_between(user.id, start, end) for e in s.exercises}
        done_planned = [p.exercise_name for p in day.exercises if any(same_exercise(p.exercise_name, d) for d in done)]
        msg = f"Today: Day {day.day_number} — {day.name} ({plan.name})\n" + "\n".join(lines)
        if done_planned:
            msg += f"\n\nAlready done: {join_human(done_planned)}."
        return Outcome(msg, "workout_query", status="answered", result={
            "plan_id": str(plan.id), "day_number": day.day_number, "day": day.name,
            "exercises": [{"exercise_name": e.exercise_name, "sets": e.sets, "target_reps": e.target_reps,
                           "rep_range": e.rep_range, "target_weight": e.target_weight,
                           "duration_seconds": e.duration_seconds} for e in day.exercises],
            "completed_exercises": done_planned,
        })

    def _general(self, user: User, profile: UserProfile, state: dict, parsed: ParsedMessage) -> Outcome:
        if parsed.reply:
            return Outcome(parsed.reply, "general_fitness_query", status="answered")
        return Outcome("I'm best at logging food, workouts, weight and water and answering questions about your own "
                       "data. General fitness Q&A needs an OpenAI key configured on the server.\n\n" + HELP_TEXT,
                       "general_fitness_query", status="answered")

