# Fitness Logger --- Implementation Plan

Build the MVP in vertical slices rather than building the entire
frontend first and backend later.

## Phase 1 --- Project Foundation

Create: - Next.js frontend - FastAPI backend - PostgreSQL/Supabase -
Environment configuration - Docker configuration - Basic CI/test setup

Verify frontend can call backend.

## Phase 2 --- Authentication and Profile

Implement: - Authentication - User profile - Profile update - Goal
selection - Activity level

Implement deterministic: - BMI - BMR - TDEE - calorie target - protein
target

Write unit tests.

## Phase 3 --- Database and Food Model

Implement: - foods - custom_foods - food_logs - nutrition snapshots

Implement food search.

Add database indexes.

## Phase 4 --- Chat Foundation

Build: - conversation model - chat message model - chat UI - POST
`/chat/messages`

Add AI intent parsing.

Initially support: - food_log - weight_log - water_log - workout_log

## Phase 5 --- Nutrition Chat

Implement: - food recognition - nutrition lookup - quantity scaling -
custom nutrition - custom foods - nutrition overrides - ambiguous-input
clarification

Test conversational corrections.

## Phase 6 --- Workout Chat

Implement: - workout logging - exercises - sets/reps/weight - workout
history - workout queries

## Phase 7 --- Workout Document Upload

Implement: - Supabase Storage - PDF upload - PyMuPDF extraction -
structured workout parsing - workout-plan storage - processing status

## Phase 8 --- Dashboard

Build: - daily summary - calorie progress - protein progress - macro
chart - weight chart - workout summary

Use Recharts.

## Phase 9 --- Historical Analytics

Implement: - daily aggregation - weekly aggregation - monthly
aggregation - weight progression - workout volume - exercise progression

Use PostgreSQL initially.

## Phase 10 --- DuckDB

Only after useful analytics exist.

Introduce DuckDB for: - complex aggregations - reporting - trend
analysis

Do not introduce it just for simple CRUD analytics.

## Phase 11 --- Quality

Test: - authentication - authorization - calculations - food scaling -
AI structured outputs - ambiguous inputs - corrections - document
parsing - analytics

Add: - error monitoring - rate limiting - logging - API validation

## Phase 12 --- Production

Deploy: - Next.js → Vercel - FastAPI → Railway/Render - PostgreSQL →
Supabase - Storage → Supabase Storage

Use Docker for backend.

Configure: - environment variables - production secrets - CORS - HTTPS -
monitoring - backups

## Coding Principles

1.  Keep API routes thin.
2.  Put business logic in services.
3.  Keep calculations deterministic.
4.  Never trust LLM output without validation.
5.  Never allow LLM-generated SQL.
6.  Never let users access another user's records.
7.  Keep historical nutrition snapshots.
8.  Use migrations for database changes.
9.  Write tests for calculations.
10. Use pagination for historical data.
11. Keep frontend calculations limited to presentation.
12. Avoid premature microservices.
