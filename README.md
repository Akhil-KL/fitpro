# fitpro — chat-first Fitness Logger

Log food, workouts, body weight and water by typing the way you talk. The backend turns each message into
validated structured data, stores raw events in PostgreSQL, does every calculation deterministically in Python,
and serves analytics that the Next.js dashboard only draws.

```
I ate 3 eggs, 200g rice and 150g chicken for lunch
→ Logged 3 × egg, 200 g white rice (cooked) and 150 g chicken breast (cooked) — 724 kcal and 70.8 g protein.
Actually, the rice was 250g
→ Updated 200 g white rice (cooked) → 250 g white rice (cooked): now 325 kcal and 6.8 g protein.
I ate some chicken
→ How much chicken did you have? (in grams)
```

The full product spec this implements is in [`docs/`](docs/). **To install and run it, follow [SETUP.md](SETUP.md).**

## Project layout

```
fitpro/
├── docker-compose.yml        PostgreSQL + backend + frontend
├── docs/                     product, architecture, data-model, API and build-plan specs
├── backend/                  FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2
│   ├── app/
│   │   ├── api/routes/       thin HTTP layer (auth, profile, chat, foods, workouts, tracking, analytics)
│   │   ├── services/         business logic: chat orchestration, nutrition, workouts, documents, analytics
│   │   │   ├── ai_parser.py      OpenAI Structured Outputs → ParsedMessage (validated, retried, falls back)
│   │   │   ├── rule_parser.py    deterministic parser used without an API key / on LLM failure
│   │   │   └── plan_parser.py    workout-plan text → days → exercises
│   │   ├── repositories/     every query scoped to the authenticated user
│   │   ├── calculations/     pure, unit-tested maths (BMR/TDEE/targets, scaling, volume, aggregation)
│   │   ├── models/           SQLAlchemy models (18 tables)
│   │   ├── schemas/          Pydantic request/response + AI output schemas
│   │   └── data/seed_foods.py  ~45 starter foods incl. Indian staples (roti, dal, idli, paneer…)
│   ├── alembic/              migrations (0001 = full schema)
│   └── tests/                44 tests: calculations, parsers, end-to-end API flows
└── frontend/                 Next.js 15 · TypeScript · Tailwind · Recharts
    ├── app/(auth)/           login, register, forgot/reset password
    ├── app/(app)/            chat, dashboard, progress, workouts, foods, profile, settings, onboarding
    ├── components/           shadcn-style primitives, charts, macro bar, app shell
    └── lib/                  API client, auth (local or Supabase), types, formatting
```

## Run it

### With Docker (recommended)

```bash
cd fitpro
cp backend/.env.example backend/.env        # optional: add OPENAI_API_KEY, change JWT_SECRET
docker compose up --build
```

- App: http://localhost:3000 — register, complete onboarding, start chatting.
- API docs: http://localhost:8000/docs
- The backend runs `alembic upgrade head` on start and seeds the food database once.

### Without Docker

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Either point DATABASE_URL at PostgreSQL and run:  alembic upgrade head
# or, for a quick local try, set in .env:  DATABASE_URL=sqlite:///./fitpro.db  and  AUTO_CREATE_TABLES=true
uvicorn app.main:app --reload
pytest                                    # 44 tests
```

Frontend (Node 20+):

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev                               # http://localhost:3000
```

## Configuration

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | backend | PostgreSQL (`postgresql+psycopg://…`). SQLite accepted for local tries/tests. |
| `AUTH_MODE` | backend | `local` (email + password, Argon2 via pwdlib, signed JWT) or `supabase` (backend only validates Supabase JWTs). |
| `JWT_SECRET` | backend | Required for `local` mode. Use a long random string. |
| `SUPABASE_URL`, `SUPABASE_JWT_SECRET` | backend | `supabase` mode. Without the secret, keys are fetched from the project's JWKS. |
| `AI_PROVIDER` | backend | `rules`, `openai`, or `gemini`. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | backend | Enables the OpenAI parser when `AI_PROVIDER=openai`. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | backend | Enables the Gemini parser when `AI_PROVIDER=gemini`. |
| `STORAGE_BACKEND` | backend | `local` disk or `supabase` Storage (`SUPABASE_SERVICE_KEY`, `SUPABASE_STORAGE_BUCKET`). |
| `CORS_ORIGINS` | backend | Comma-separated frontend origins. |
| `NEXT_PUBLIC_API_URL` | frontend | Backend base URL. |
| `NEXT_PUBLIC_AUTH_MODE` | frontend | Must match the backend's `AUTH_MODE`. Supabase mode also needs `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`. |

## How a chat message is handled

1. `POST /api/v1/chat/messages` → `ChatService.handle` loads the conversation, its structured state (any pending
   question) and the last 8 messages — never unlimited history.
2. `AIParser` asks the model for a `ParsedMessage` (Structured Outputs). The result is re-validated with Pydantic
   (ranges, enums). Invalid output is retried once, then the rule parser takes over.
3. The service decides what to write — the parser never touches the database or SQL. Missing quantities, unknown
   foods, ambiguous matches and unconvertible units ("2 cups of rice" against a per-100 g entry) become questions,
   stored as pending state so the next reply ("150", "2", "100g has 350 kcal…") completes them.
4. Each food log stores a **nutrition snapshot**; corrections rescale the snapshot, so editing a food later never
   changes history. One transaction per message.
5. The reply is built from backend-calculated numbers only.

Supported intents: food log (multi-item, meals, "add another egg"), corrections and deletes, nutrition overrides
("the chicken was 300 kcal"), custom foods, workouts (sets×reps, weight, timed sets, cardio), workout corrections,
weight, water, daily summary, nutrition / goal / progress queries and "what is today's workout?".

## Calculations

Mifflin-St Jeor BMR → TDEE (activity multiplier) → goal adjustment (lose −500, recomp −200, gain +300, with a
safety floor) → protein by g/kg (1.6–2.0) → fat 25 % of calories → carbs = remainder → water 35 ml/kg. Targets are
versioned by `effective_from`; a change creates a new row for today and past days keep theirs. Volume = Σ reps ×
weight; estimated 1RM uses Epley. All of it lives in `backend/app/calculations` with unit tests.

## Workout plans

Upload a PDF (PyMuPDF) or TXT on the Workouts page. Processing runs in the background (`pending → processing →
completed | failed`) and the UI polls the status. Recognised layouts: `Day 1 - Push`, weekday headers, split names,
and lines like `Bench Press 4x8`, `3 sets of 10-12 reps`, `Deadlift 3x5 @ 100kg`, `Plank 3x60s`, `Treadmill 20 min`.
With an OpenAI key, unusual layouts fall back to LLM extraction (still validated). Scanned PDFs without a text
layer are reported as failed with an explanation.

## Deployment

- Backend → Railway or Render using `backend/Dockerfile` (migrations run on boot; set `ENVIRONMENT=production`,
  `JWT_SECRET`, `DATABASE_URL`, `CORS_ORIGINS`).
- Database and file storage → Supabase (Postgres connection string + a private `workout-plans` bucket).
- Frontend → Vercel with `NEXT_PUBLIC_API_URL` (and the Supabase keys if using Supabase Auth).

## What was verified, and what wasn't

- **Backend**: the full test suite (44 tests, including end-to-end chat flows, user isolation, corrections,
  custom-food snapshots, document upload and analytics) passes on SQLite. The Alembic migration was applied,
  checked for drift against the models (`alembic check`: no changes) and rendered as PostgreSQL SQL.
- **Not run in the build environment** (no package registry access there): PostgreSQL itself, PyMuPDF on a real
  PDF, the OpenAI call path, Argon2 (tests used a stand-in hasher when argon2 was unavailable), and `next build`.
  The frontend was type-checked against React 19 types with stubs for Next.js/Recharts/Supabase. CI
  (`.github/workflows/ci.yml`) runs all of these for real on the first push.

## Deliberately deferred (per the build plan)

- DuckDB (Phase 10): analytics aggregate in Python over date-bounded, indexed PostgreSQL queries; the pure
  functions in `calculations/aggregation.py` are the seam for a DuckDB extraction when volume justifies it.
- Redis: the chat rate limiter is in-process; swap for Redis when running more than one backend instance.
- Email delivery for password reset in `local` mode: the reset link is logged and, outside production, returned
  to the UI. Supabase mode uses Supabase's emails.
- Access tokens are kept in `localStorage`; moving to httpOnly cookies is the next security hardening step.
- Cardio distance ("ran 5 km") isn't stored yet; duration is.
#   f i t p r o  
 