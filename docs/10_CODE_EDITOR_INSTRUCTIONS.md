# Fitness Logger --- Code Editor Build Instructions

You are building a production-quality MVP called Fitness Logger.

## Primary Requirement

The application is chat-first.

The user should be able to perform the majority of logging actions
through natural-language chat.

Do not build the application as a traditional form-heavy calorie
tracker.

## Stack

Frontend: - Next.js - TypeScript - Tailwind CSS - shadcn/ui - Recharts

Backend: - Python - FastAPI - Pydantic - SQLAlchemy

Database: - PostgreSQL - Supabase is acceptable for managed
PostgreSQL/auth/storage

AI: - OpenAI API - Structured Outputs

Documents: - PyMuPDF

Analytics: - PostgreSQL initially - DuckDB for advanced analytics when
justified

Infrastructure: - Docker - Vercel - Railway/Render

## Implementation Rules

### Rule 1 --- Separation of Concerns

Use:

``` text
routes -> services -> repositories -> database
```

Do not place business logic inside route handlers.

### Rule 2 --- AI

AI should: - classify intent - extract entities - understand
conversational context - request clarification when necessary

AI should NOT: - directly write SQL - directly modify the database -
invent nutrition data - perform authoritative calculations

### Rule 3 --- Validation

All AI structured outputs must pass Pydantic validation before business
logic executes.

### Rule 4 --- Calculations

Nutrition, calorie, protein, macro, workout-volume and progress
calculations must be deterministic Python functions with tests.

### Rule 5 --- Historical Data

Never allow a later change in a food database entry to silently change a
historical food log.

Store the nutrition snapshot used at logging time.

### Rule 6 --- Authorization

Every user-owned database query must be scoped to the authenticated
user.

Never trust `user_id` supplied by the frontend.

### Rule 7 --- Chat Corrections

When a user says:

> Actually the rice was 250g.

Find the relevant recent entry and update it.

Do not create a duplicate unless the user explicitly intends another
entry.

### Rule 8 --- Ambiguity

If required information is missing, ask.

Never invent quantities.

### Rule 9 --- Pagination

Paginate: - chat history - food history - workout history - weight
history - water history - search results

### Rule 10 --- Charts

Charts consume backend analytics.

Do not implement authoritative calculations inside React.

## Development Order

Follow the implementation phases in `09_BUILD_PLAN.md`.

Do not attempt the complete application in one generated patch.

After each phase: 1. Run tests. 2. Verify database migrations. 3. Verify
API behavior. 4. Verify frontend integration. 5. Fix errors. 6. Only
then continue.

## Definition of Done

The MVP is complete when a user can:

1.  Register/login.
2.  Complete a fitness profile.
3.  Receive fitness targets.
4.  Log food through chat.
5.  Add custom nutrition.
6.  Save custom foods.
7.  Correct food logs through chat.
8.  Log workouts through chat.
9.  Upload a workout PDF/TXT.
10. Ask what workout to perform.
11. Log weight.
12. Log water.
13. View daily totals.
14. View nutrition and weight charts.
15. View workout history.
16. View progress analytics.

## Important

Prioritize correctness and data integrity over adding features.

Do not introduce unnecessary technologies.

Do not use DuckDB for transactional application data.

Do not introduce RAG, Kafka, Kubernetes, microservices or complex agent
frameworks unless a concrete requirement appears.
