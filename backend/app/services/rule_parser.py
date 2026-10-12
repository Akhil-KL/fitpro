"""Deterministic rule-based message parser.

Used when no OpenAI key is configured, when the LLM call fails, and as a
predictable baseline in tests. It never invents values: anything the user did
not state is left as None so business logic can ask for it.
"""

from __future__ import annotations

import re

from app.calculations.nutrition import UNIT_ALIASES, VAGUE_UNITS, normalize_unit
from app.schemas.ai import Correction, ExerciseEntry, FoodItem, NutritionFacts, ParsedMessage

NUM = r"\d+(?:\.\d+)?"
WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "half": 0.5, "half a": 0.5, "a couple of": 2, "couple of": 2, "a dozen": 12, "dozen": 12,
    "another": 1, "one more": 1, "a single": 1,
}
_UNIT_WORDS = sorted(set(UNIT_ALIASES) | VAGUE_UNITS, key=len, reverse=True)
_UNIT_RE = "|".join(re.escape(u) for u in _UNIT_WORDS)
_WORDNUM_RE = "|".join(re.escape(w) for w in sorted(WORD_NUMBERS, key=len, reverse=True))

MEALS = {"breakfast": "breakfast", "lunch": "lunch", "dinner": "dinner", "supper": "dinner",
         "snack": "snack", "snacks": "snack"}

EXERCISE_HINTS = (
    "bench", "squat", "deadlift", "press", "curl", "row", "pull up", "pullup", "pull-up", "chin",
    "push up", "pushup", "push-up", "dip", "lunge", "plank", "raise", "fly", "flye", "extension",
    "pulldown", "pull down", "shrug", "crunch", "sit up", "situp", "burpee", "run", "ran", "jog",
    "walk", "cycle", "cycling", "cycled", "bike", "swim", "swam", "rowing", "yoga", "hiit", "skipping",
    "jump rope", "kettlebell", "thrust", "rdl", "calf", "leg", "lat", "tricep", "bicep", "cardio",
    "treadmill", "elliptical", "stretch", "skull",
)
CARDIO_RENAME = {"ran": "running", "run": "running", "jogged": "jogging", "jog": "jogging",
                 "walked": "walking", "walk": "walking", "cycled": "cycling", "biked": "cycling",
                 "swam": "swimming", "swim": "swimming"}

FOOD_VERB_RE = re.compile(
    r"\b(ate|eaten|eat|had|have had|consumed|munched|snacked on|drank|drink|for (?:breakfast|lunch|dinner|snack))\b"
)
QUESTION_RE = re.compile(
    r"^(how|what|what's|whats|when|which|show|tell|am i|did i|do i|is my|are my|should i|can i|could|"
    r"give me|list|any)\b|\?\s*$"
)
CORRECTION_PREFIX_RE = re.compile(
    r"^(actually|correction|sorry|oops|no|nope|wait|i meant|i mean|my bad|make that|make it|change|update|edit|fix)\b[,.!:]?\s*"
)


# ----------------------------------------------------------------- utilities
def _clean(text: str) -> str:
    t = text.strip().lower()
    t = t.replace("’", "'").replace("×", "x")
    t = re.sub(r"\s+", " ", t)
    return t


def singularize(name: str) -> str:
    words = name.split()
    if not words:
        return name
    w = words[-1]
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith(("oes", "ches", "shes", "xes")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us")):
        w = w[:-1]
    words[-1] = w
    return " ".join(words)


def _to_number(token: str) -> float | None:
    token = token.strip()
    if token in WORD_NUMBERS:
        return float(WORD_NUMBERS[token])
    if re.fullmatch(r"\d+/\d+", token):
        a, b = token.split("/")
        return float(a) / float(b) if float(b) else None
    try:
        return float(token)
    except ValueError:
        return None


def extract_quantity(text: str) -> tuple[float | None, str | None]:
    """First quantity (+ canonical unit) in a short reply like '200g', '2 pieces', 'three'."""
    t = _clean(text)
    m = re.search(rf"({NUM}|\d+/\d+)\s*({_UNIT_RE})?\b", t)
    if m:
        return float(_to_number(m.group(1)) or 0) or None, normalize_unit(m.group(2))
    m = re.search(rf"\b({_WORDNUM_RE})\b\s*({_UNIT_RE})?\b", t)
    if m:
        return _to_number(m.group(1)), normalize_unit(m.group(2))
    return None, None


def _detect_meal(t: str) -> tuple[str | None, str]:
    m = re.search(r"\b(?:for|at|in|during|with|as)?\s*(?:my\s+)?(breakfast|lunch|dinner|supper|snacks?)\b", t)
    if not m:
        return None, t
    return MEALS[m.group(1)], (t[: m.start()] + " " + t[m.end():]).strip()


def _detect_day_offset(t: str) -> tuple[int, str]:
    if re.search(r"\byesterday\b", t):
        return -1, re.sub(r"\byesterday('s)?\b", " ", t)
    return 0, re.sub(r"\b(today|tonight|this (morning|afternoon|evening)|just now)\b", " ", t)


# ----------------------------------------------------------------- food
_LEADING_FILLER = re.compile(
    r"^(?:(?:i|we)\s+)?(?:just\s+|also\s+|then\s+)?"
    r"(?:ate|eaten|eat|had|have had|have|consumed|munched on|snacked on|drank|drink|add|added|log|logged|"
    r"include|plus|and|also)\b\s*"
)
_ITEM_RE = re.compile(
    rf"^(?P<qty>{NUM}|\d+/\d+|{_WORDNUM_RE})?\s*(?P<unit>{_UNIT_RE})?\.?\s*(?:of\s+)?(?P<name>.*)$"
)
_SOME_RE = re.compile(r"^(?:some|a bit of|a little|little|a few|few|lots of|a lot of|a portion of|portion of)\s+")


def parse_food_item(chunk: str) -> FoodItem | None:
    c = chunk.strip(" .,!;:-")
    for _ in range(3):
        c2 = _LEADING_FILLER.sub("", c).strip()
        if c2 == c:
            break
        c = c2
    if not c:
        return None
    vague_amount = bool(_SOME_RE.match(c))
    c = _SOME_RE.sub("", c)
    # "200g" (no space) splits naturally because the regex allows \s* between qty and unit.
    m = _ITEM_RE.match(c)
    if not m:
        return None
    qty_raw, unit_raw, name = m.group("qty"), m.group("unit"), (m.group("name") or "").strip(" .,")
    # A unit word swallowed with no name (e.g. "2 slices") is not a food.
    name = re.sub(r"^(?:the|my|of)\s+", "", name).strip()
    if not name or not re.search(r"[a-z]", name):
        return None
    if unit_raw and not qty_raw and unit_raw in ("a", "l", "g"):  # stray single letters
        name = f"{unit_raw} {name}".strip()
        unit_raw = None
    qty = None if vague_amount else (_to_number(qty_raw) if qty_raw else None)
    unit = normalize_unit(unit_raw) if unit_raw else None
    if unit == "vague":
        qty = None  # "a bowl of dal" — size unknown, ask
    return FoodItem(food_name=singularize(name), quantity=qty, unit=unit if unit != "vague" else None)


def parse_food_items(text: str) -> list[FoodItem]:
    t = re.sub(r"\b(for|at)\s*$", "", text)
    parts = re.split(r",|;|\band\b|\bwith\b|&|\+|\bplus\b|\balong with\b", t)
    items = [it for p in parts if (it := parse_food_item(p))]
    return items


# ----------------------------------------------------------------- nutrition facts
def _num_before_or_after(t: str, keywords: str) -> float | None:
    m = re.search(rf"({NUM})\s*(?:g|gm|grams?)?\s*(?:of\s+)?(?:{keywords})\b", t)
    if m:
        return float(m.group(1))
    m = re.search(rf"\b(?:{keywords})\s*(?:is|are|=|:|-)?\s*({NUM})", t)
    return float(m.group(1)) if m else None


def parse_nutrition_facts(text: str) -> NutritionFacts | None:
    t = _clean(text)
    cal = None
    m = re.search(rf"({NUM})\s*(?:kcals?|cals?|calories|kilocalories)\b", t)
    if m:
        cal = float(m.group(1))
    else:
        m = re.search(rf"\b(?:calories|kcal|energy)\s*(?:is|=|:|-)?\s*({NUM})", t)
        cal = float(m.group(1)) if m else None
    protein = _num_before_or_after(t, "protein|proteins")
    carbs = _num_before_or_after(t, "carbs|carb|carbohydrates|carbohydrate")
    fat = _num_before_or_after(t, "fat|fats")
    fiber = _num_before_or_after(t, "fiber|fibre")
    if cal is None and protein is None:
        return None

    basis_q: float | None = None
    basis_u: str | None = None
    unit_words = r"g|gm|grams?|ml|piece|pieces|serving|servings|scoop|scoops|slice|slices|packet|pack|package"
    m = re.search(rf"\bper\s+(?:({NUM})\s*)?({unit_words})\b", t)
    if not m:
        m = re.search(
            rf"(?:^|\b(?:in|every|each)\s+|[:,]\s*)(?:a\s+|one\s+)?({NUM})?\s*({unit_words})\b\s*"
            rf"(?:of it\s+)?(?:contains|contain|has|have|gives|provides|is|=|:|-)",
            t,
        )
    if not m:
        m = re.search(rf"\b(?:each|one|a|1)\s+({unit_words})\b", t)
        if m:
            basis_q, basis_u = 1.0, normalize_unit(m.group(1))
        elif re.search(r"(?:^|\b)(?:each|one|a|1)\s+([a-z]+)\s+(?:has|contains|gives|provides|is|=)", t):
            # "1 bar has 200 kcal" — a countable item of its own kind is one piece.
            basis_q, basis_u = 1.0, "piece"
    else:
        basis_u = normalize_unit(m.group(2))
        basis_q = float(m.group(1)) if m.group(1) else 1.0
    return NutritionFacts(
        basis_quantity=basis_q, basis_unit=basis_u, calories=cal,
        protein_g=protein, carbs_g=carbs, fat_g=fat, fiber_g=fiber,
    )


def _custom_food_name(t: str) -> str | None:
    m = re.search(
        r"(?:custom food|create (?:a )?(?:new )?(?:custom )?food|new food|save (?:a )?(?:new )?food|"
        r"add (?:a )?(?:new |custom )food|update (?:my )?(?:custom )?food|food called|food named)\s*"
        r"(?:called|named)?\s*[\"']?(?P<name>[a-z][a-z0-9 \-']*?)[\"']?\s*(?=[:,(]|\bwith\b|\bwhich\b|\bthat\b|"
        r"\bhas\b|\bcontains\b|\bper\b|\bis\b|\d|$)",
        t,
    )
    return m.group("name").strip() if m and m.group("name").strip() else None


# ----------------------------------------------------------------- workouts
_W_WEIGHT = re.compile(rf"({NUM})\s*(kgs?|kilos?|lbs?|pounds?)\b")
_W_SETS_X = re.compile(r"(\d+)\s*x\s*(\d+)\s*(s|secs?|seconds?)?\b")
_W_SETS_OF = re.compile(r"(\d+)\s*sets?\s*(?:of|x)?\s*(\d+)\s*(?:reps?)?\b")
_W_REPS_SETS = re.compile(r"(\d+)\s*reps?\s*(?:x|for|of)?\s*(\d+)\s*sets?\b")
_W_SETS_ONLY = re.compile(r"(\d+)\s*sets?\b")
_W_REPS_ONLY = re.compile(r"(\d+)\s*reps?\b")
_W_DURATION = re.compile(rf"({NUM})\s*(hours?|hrs?|minutes?|mins?|min|seconds?|secs?|sec)\b")
_W_DISTANCE = re.compile(rf"({NUM})\s*(km|kms|kilometers?|kilometres?|miles?|mi)\b")
_W_FILLER = re.compile(
    r"\b(i|we|did|do|done|doing|completed|finished|today|yesterday|for|at|with|of|and|sets?|reps?|then|"
    r"a|an|the|some|my|workout|session|went|go|got|in|on|each|per|x|also|just|total|plus)\b"
)


def _has_workout_numbers(t: str) -> bool:
    return bool(_W_SETS_X.search(t) or _W_SETS_OF.search(t) or _W_REPS_SETS.search(t) or _W_REPS_ONLY.search(t)
                or _W_SETS_ONLY.search(t) or _W_DURATION.search(t) or _W_WEIGHT.search(t))


def _exercise_name(t: str) -> str:
    s = _W_WEIGHT.sub(" ", t)
    for rx in (_W_SETS_X, _W_SETS_OF, _W_REPS_SETS, _W_DURATION, _W_DISTANCE, _W_SETS_ONLY, _W_REPS_ONLY):
        s = rx.sub(" ", s)
    s = re.sub(r"[@,;:.!()]", " ", s)
    s = re.sub(r"\d+(?:\.\d+)?", " ", s)
    s = _W_FILLER.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -")
    words = [CARDIO_RENAME.get(w, w) for w in s.split()]
    return " ".join(words)


def parse_exercise(chunk: str) -> ExerciseEntry | None:
    t = chunk.strip()
    name = _exercise_name(t)
    if not name or not re.search(r"[a-z]{2,}", name):
        return None
    sets = reps = duration = None
    weight = None
    if m := _W_WEIGHT.search(t):
        w = float(m.group(1))
        weight = round(w * 0.453592, 2) if m.group(2).startswith(("lb", "pound")) else w
    if m := _W_SETS_X.search(t):
        sets = int(m.group(1))
        if m.group(3):  # "3x60s" -> timed sets
            duration = int(m.group(2))
        else:
            reps = int(m.group(2))
    elif m := _W_REPS_SETS.search(t):
        reps, sets = int(m.group(1)), int(m.group(2))
    elif m := _W_SETS_OF.search(t):
        sets, reps = int(m.group(1)), int(m.group(2))
    else:
        if m := _W_SETS_ONLY.search(t):
            sets = int(m.group(1))
        if m := _W_REPS_ONLY.search(t):
            reps = int(m.group(1))
        elif sets is None and (m := re.match(r"^\s*(?:i\s+)?(?:did\s+)?(\d+)\s+[a-z]", t)) and not _W_WEIGHT.match(t[m.start(1):]):
            reps = int(m.group(1))  # "did 20 pushups" -> one set of 20
        if reps and sets is None:
            sets = 1
    if duration is None and (m := _W_DURATION.search(t)):
        v, u = float(m.group(1)), m.group(2)
        duration = int(v * 3600 if u.startswith(("hour", "hr")) else v * 60 if u.startswith("min") else v)
    return ExerciseEntry(
        exercise_name=name, sets=sets, reps=reps, weight_kg=weight, duration_seconds=duration or None
    )


def parse_exercises(text: str) -> list[ExerciseEntry]:
    frags = [f.strip() for f in re.split(r";|\n|\bthen\b|\band\b|,", text) if f.strip()]
    groups: list[str] = []
    for f in frags:
        has_name = bool(re.search(r"[a-z]{3,}", _exercise_name(f)))
        if groups and has_name and _has_workout_numbers(groups[-1]) and re.search(r"[a-z]{3,}", _exercise_name(groups[-1])):
            groups.append(f)
        elif groups:
            groups[-1] = f"{groups[-1]} {f}"
        else:
            groups.append(f)
    return [e for g in groups if (e := parse_exercise(g))]


def _looks_like_workout(t: str) -> bool:
    if FOOD_VERB_RE.search(t) and not re.search(r"\b(did|trained|lifted)\b", t):
        return False
    hint = any(re.search(rf"\b{re.escape(h)}", t) for h in EXERCISE_HINTS)
    strong_numbers = bool(_W_SETS_X.search(t) or _W_SETS_OF.search(t) or _W_REPS_SETS.search(t) or _W_REPS_ONLY.search(t))
    counted = hint and bool(re.search(r"\b(did|done|completed|finished)\b", t) or re.match(r"^\d+\s+[a-z]", t))
    return strong_numbers or counted or (hint and bool(_W_DURATION.search(t) or _W_WEIGHT.search(t) or _W_DISTANCE.search(t)))


# ----------------------------------------------------------------- queries
METRIC_WORDS = [
    ("protein", "protein"), ("calorie", "calories"), ("kcal", "calories"), ("carb", "carbs"),
    ("fat", "fat"), ("fiber", "fiber"), ("fibre", "fiber"), ("water", "water"),
]


def _metric(t: str) -> str | None:
    for word, metric in METRIC_WORDS:
        if word in t:
            return metric
    return None


def _parse_query(t: str, day_offset: int) -> ParsedMessage | None:
    if re.search(r"\b(today'?s|todays|next|my|what|which)\b.*\b(workout|training|split|session|routine|plan)\b|"
                 r"\bwhat (should|do) i (train|do|lift)\b|\bworkout (today|plan)\b", t) and not re.search(
                     r"\b(history|last|frequency|volume|progress|how many)\b", t):
        return ParsedMessage(intent="workout_query", day_offset=day_offset)
    if re.search(r"\b(summary|overview|how am i doing|how'?s my day|so far|status|recap)\b", t):
        return ParsedMessage(intent="daily_summary", day_offset=day_offset)
    if re.search(r"\b(target|goal|bmr|tdee|bmi|maintenance|how much should i|how many calories should)\b", t):
        return ParsedMessage(intent="goal_query", query_metric=_metric(t))
    if re.search(r"\b(progress|lost|gained|trend|weight change|personal record|prs?|best lift|how much weight|"
                 r"how many workouts|volume|frequency|streak)\b", t):
        metric = "workout" if re.search(r"\b(workouts?|prs?|personal record|lift|volume|frequency|streak)\b", t) else "weight"
        return ParsedMessage(intent="progress_query", query_metric=metric)
    metric = _metric(t)
    if metric and re.search(r"\b(how much|how many|total|left|remaining|eaten|had|consumed|drunk|drank|intake|"
                            r"what'?s my|what is my|so far)\b", t):
        return ParsedMessage(intent="nutrition_query", query_metric=metric, day_offset=day_offset)
    if re.search(r"\b(what did i eat|what have i eaten|food log|my meals)\b", t):
        return ParsedMessage(intent="daily_summary", day_offset=day_offset)
    return None


# ----------------------------------------------------------------- corrections
def _parse_correction(t: str) -> ParsedMessage | None:
    had_prefix = bool(CORRECTION_PREFIX_RE.match(t))
    body = CORRECTION_PREFIX_RE.sub("", t).strip()
    if m := re.match(r"^(?:delete|remove|undo|scrap|cancel)\s+(?:the\s+|my\s+)?(?:last\s+)?(?:entry\s*)?(?P<name>.*)$", body):
        name = m.group("name").strip(" .") or None
        if name in ("entry", "log", "one", "that", "it"):
            name = None
        return ParsedMessage(intent="food_correction",
                             correction=Correction(target_name=singularize(name) if name else None, delete=True))

    name: str | None = None
    rest = body
    if m := re.match(r"^(?:change|update|edit|set|make)?\s*(?:the\s+|my\s+)?(?P<name>[a-z][a-z \-']*?)\s+to\s+(?P<rest>.+)$", body):
        name, rest = m.group("name"), m.group("rest")
    elif m := re.match(r"^(?:the\s+|my\s+)?(?P<name>[a-z][a-z \-']*?)\s+(?:was|were|is|are|should be|should have been)\s+"
                       r"(?:actually\s+|only\s+|really\s+)?(?P<rest>.+)$", body):
        name, rest = m.group("name"), m.group("rest")
    elif not had_prefix:
        return None
    if name in ("it", "that", "this", "they", "those", "i", "there"):
        name = None
    if name and re.fullmatch(r"(make|change|update|set|that|it)", name):
        name = None

    rest = rest.strip(" .!")
    is_workout = bool(re.search(r"\b(sets?|reps?|lbs?|pounds?)\b", rest) or _W_SETS_X.search(rest)
                      or (re.search(r"\d\s*kgs?\b", rest) and name and any(h in name for h in EXERCISE_HINTS)))
    if is_workout:
        ex = parse_exercise(f"{name or 'exercise'} {rest}")
        return ParsedMessage(intent="workout_correction", correction=Correction(
            target_name=name, sets=ex.sets if ex else None, reps=ex.reps if ex else None,
            weight_kg=ex.weight_kg if ex else None))

    facts = parse_nutrition_facts(rest)
    if facts and facts.calories is not None:
        return ParsedMessage(intent="food_correction", correction=Correction(
            target_name=singularize(name) if name else None, nutrition_override=facts))

    item = parse_food_item(rest)
    qty, unit = extract_quantity(rest)
    if item and item.quantity is not None and not re.fullmatch(r"(g|ml|kg|l|pieces?|grams?)", item.food_name):
        target = singularize(name) if name else item.food_name
        return ParsedMessage(intent="food_correction",
                             correction=Correction(target_name=target, quantity=item.quantity, unit=item.unit))
    if qty is not None:
        return ParsedMessage(intent="food_correction",
                             correction=Correction(target_name=singularize(name) if name else None, quantity=qty,
                                                   unit=unit if unit != "vague" else None))
    return None


# ----------------------------------------------------------------- main entry
def parse_message(text: str) -> ParsedMessage:
    t = _clean(text)
    if not t:
        return ParsedMessage(intent="unknown")

    # Bare option pick or bare number, e.g. "2", "the first one" — context decides meaning.
    if m := re.fullmatch(r"(?:#|option\s*|number\s*)?(\d{1,2})\.?|(?:the\s+)?(first|second|third|fourth|fifth)(?:\s+one)?\.?", t):
        n = int(m.group(1)) if m.group(1) else ["first", "second", "third", "fourth", "fifth"].index(m.group(2)) + 1
        return ParsedMessage(intent="clarification", selection=n if 1 <= n <= 20 else None)

    day_offset, t_noday = _detect_day_offset(t)
    t_noday = re.sub(r"\s+", " ", t_noday).strip()
    is_question = bool(QUESTION_RE.search(t))

    # Custom food definitions / nutrition facts.
    facts = parse_nutrition_facts(t)
    cf_name = _custom_food_name(t)
    if facts and (cf_name or re.search(r"\b(custom food|create|new food|save)\b", t)):
        intent = "custom_food_update" if re.search(r"\bupdate\b", t) else "custom_food_create"
        return ParsedMessage(intent=intent, custom_food_name=cf_name, nutrition=facts)

    # Corrections come before logs: "actually the rice was 250g".
    if not is_question and (CORRECTION_PREFIX_RE.match(t) or re.search(r"\b(was|were|should be|should have been)\s+(actually\s+|only\s+)?\d", t)
                            or re.match(r"^(delete|remove|undo)\b", t)):
        if corr := _parse_correction(t_noday):
            return corr

    if facts and facts.calories is not None and not is_question:
        # Reply to "what's the nutrition for X?" — context (pending state) gives it meaning.
        return ParsedMessage(intent="clarification", nutrition=facts)

    if is_question:
        if q := _parse_query(t_noday, day_offset):
            return q
        return ParsedMessage(intent="general_fitness_query")

    # Body weight.
    if re.search(r"\b(weigh|weighs|weighed|weight|scale|bodyweight|body weight)\b", t) and not re.search(r"\b(lifted|lift|sets?|reps?)\b", t):
        m = re.search(rf"({NUM})\s*(kgs?|kilos?|lbs?|pounds?)?\b", t_noday)
        if m:
            w = float(m.group(1))
            if m.group(2) and m.group(2).startswith(("lb", "pound")):
                w = round(w * 0.453592, 2)
            if 20 <= w <= 400:
                return ParsedMessage(intent="weight_log", weight_kg=w, day_offset=day_offset)
        return ParsedMessage(intent="weight_log", day_offset=day_offset,
                             clarification_question="What was your weight (in kg)?")

    # Water.
    if re.search(r"\bwater\b", t) and not re.search(r"\b(coconut water|water ?melon)\b", t):
        m = re.search(rf"({NUM})\s*(ml|milliliters?|millilitres?|l|liters?|litres?|ltrs?)\b", t)
        if m:
            amount = float(m.group(1)) * (1 if m.group(2).startswith("m") else 1000)
            return ParsedMessage(intent="water_log", amount_ml=amount, day_offset=day_offset)
        return ParsedMessage(intent="water_log", day_offset=day_offset,
                             clarification_question="How much water was that, in ml or litres?")

    # Workouts.
    if _looks_like_workout(t_noday):
        exercises = parse_exercises(t_noday)
        if exercises:
            return ParsedMessage(intent="workout_log", exercises=exercises, day_offset=day_offset)

    # Food.
    meal, t_food = _detect_meal(t_noday)
    if FOOD_VERB_RE.search(t) or meal or re.match(rf"^(add|log|plus|another|one more|{NUM}|a |an )", t_food) or \
            re.search(rf"{NUM}\s*({_UNIT_RE})\b", t_food):
        items = parse_food_items(t_food)
        if items:
            return ParsedMessage(intent="food_log", items=items, meal=meal, day_offset=day_offset)

    # A short quantity-only reply ("200g") is a clarification answer.
    qty, unit = extract_quantity(t)
    if qty is not None and len(t.split()) <= 3:
        return ParsedMessage(intent="clarification", items=[FoodItem(food_name="_", quantity=qty, unit=unit if unit != "vague" else None)])

    return ParsedMessage(intent="unknown")
