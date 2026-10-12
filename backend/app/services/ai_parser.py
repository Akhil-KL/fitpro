"""AI parsing layer.

The LLM classifies intent and extracts entities into `ParsedMessage` via
OpenAI or Gemini structured JSON output is validated with Pydantic; anything
invalid falls back to the deterministic rule parser. The LLM never computes
nutrition, never writes SQL and never touches the database.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date

from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas.ai import LLMParsedMessage, ParsedMessage
from app.services import rule_parser

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the parsing layer of a chat-first fitness logger. Convert the user's latest message
into the JSON schema. You ONLY extract what the user said; the backend does every calculation.

Rules:
- Never invent quantities, units, weights, reps or nutrition values. If a value is not stated, use null.
  "some chicken" -> quantity null. "a bowl of dal" -> quantity null, unit null. "3 eggs" -> quantity 3, unit null.
- Units: use g, kg, ml, l, cup, tbsp, tsp, oz, lb, piece, serving. A bare count ("2 rotis") has unit null.
- food_name: the singular, lowercase food name as the user said it (e.g. "egg", "rice", "chicken breast").
- "Add another egg" / "one more roti" -> food_log with quantity 1.
- Use conversation state to resolve follow-ups. If state.pending exists and the message answers it
  (a quantity like "200g", an option number, or nutrition facts), use intent "clarification" and fill
  items[0].quantity/unit (food_name "_"), selection, or nutrition accordingly.
- Corrections ("actually the rice was 250g", "make that 300g", "the chicken was 300 kcal", "delete the last one")
  -> food_correction / workout_correction with correction.target_name (null = most recent entry).
- Nutrition facts ("100g contains 350 kcal, 25g protein") -> nutrition with basis_quantity/basis_unit as stated.
  If the user asks to create/save a custom food, intent custom_food_create with custom_food_name.
- Workouts: one entry per exercise; weight in kg (convert lb x 0.4536); duration in seconds.
  "4x8" means 4 sets of 8 reps. "20 pushups" means sets 1, reps 20.
- Questions about the user's own logged data -> nutrition_query / daily_summary / progress_query / goal_query /
  workout_query ("what is today's workout?"). Do not answer them; the backend will.
- general_fitness_query: general questions (technique, nutrition concepts). Put a short helpful answer in
  `reply`; never state numbers about the user's own intake.
- day_offset: -1 if the user says "yesterday", else 0.
- If the message is unrelated or unintelligible, intent "unknown".
"""


@dataclass
class ParseContext:
    recent_messages: list[dict] = field(default_factory=list)  # [{"role":..., "content":...}]
    state: dict | None = None
    today: date | None = None


@dataclass
class ParseResult:
    parsed: ParsedMessage
    source: str  # "openai" | "gemini" | "rules"
    raw: dict | None = None


class AIParser:
    def __init__(self, settings: Settings | None = None, client: object | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # imported lazily so tests run without the SDK

            self._client = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.ai_timeout_seconds)
        return self._client

    def _parse_gemini(self, message: str, ctx: ParseContext) -> tuple[ParsedMessage, dict]:
        import httpx

        context = {
            "today": (ctx.today or date.today()).isoformat(),
            "state": ctx.state or {},
        }
        prompt = SYSTEM_PROMPT + "\nReturn only valid JSON matching this schema:\n" + json.dumps(
            LLMParsedMessage.model_json_schema()
        )
        prompt += "\nConversation state: " + json.dumps(context, default=str)
        for item in ctx.recent_messages[-self.settings.chat_context_messages:]:
            prompt += f"\n{item['role']}: {item['content'][:1000]}"
        prompt += "\nuser: " + message
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": LLMParsedMessage.model_json_schema(),
            },
        }
        response = httpx.post(
            url,
            params={"key": self.settings.gemini_api_key},
            json=payload,
            timeout=self.settings.ai_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        raw = json.loads(text)
        return ParsedMessage.model_validate(_drop_nulls(raw)), raw

    def parse(self, message: str, ctx: ParseContext | None = None) -> ParseResult:
        ctx = ctx or ParseContext()
        if self.settings.ai_enabled:
            for attempt in range(2):  # one retry on invalid output
                try:
                    if self.settings.ai_provider == "gemini":
                        parsed, raw = self._parse_gemini(message, ctx)
                        source = "gemini"
                    else:
                        parsed, raw = self._parse_llm(message, ctx)
                        source = "openai"
                    return ParseResult(parsed=parsed, source=source, raw=raw)
                except ValidationError as exc:
                    log.warning("LLM output failed validation (attempt %s): %s", attempt + 1, exc.errors()[:3])
                except Exception as exc:  # network/API errors: degrade gracefully
                    log.warning("LLM parse failed, using rule parser: %s", type(exc).__name__)
                    break
        return ParseResult(parsed=rule_parser.parse_message(message), source="rules")

    def _parse_llm(self, message: str, ctx: ParseContext) -> tuple[ParsedMessage, dict]:
        client = self._get_client()
        context = {
            "today": (ctx.today or date.today()).isoformat(),
            "state": ctx.state or {},
        }
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append({"role": "system", "content": "Conversation state: " + json.dumps(context, default=str)})
        for m in ctx.recent_messages[-self.settings.chat_context_messages:]:
            messages.append({"role": m["role"], "content": m["content"][:1000]})
        messages.append({"role": "user", "content": message})

        completion = client.chat.completions.parse(
            model=self.settings.openai_model,
            messages=messages,
            response_format=LLMParsedMessage,
            temperature=0,
        )
        choice = completion.choices[0].message
        if getattr(choice, "refusal", None) or choice.parsed is None:
            raise ValueError("model refused or returned no parsed output")
        raw = choice.parsed.model_dump()
        # Re-validate against the strict internal schema (range checks etc.).
        return ParsedMessage.model_validate(_drop_nulls(raw)), raw


def _drop_nulls(obj):
    if isinstance(obj, dict):
        return {k: _drop_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_drop_nulls(v) for v in obj]
    return obj
