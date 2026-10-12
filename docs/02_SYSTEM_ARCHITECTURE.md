# Fitness Logger --- System Architecture

## 1. Architecture

Use a modular monolithic architecture for the MVP.

Do NOT split the application into microservices.

``` text
Next.js Frontend
      |
      | HTTPS / REST
      v
FastAPI Backend
      |
      +------------------+
      |                  |
      v                  v
AI Parsing Layer     Business Logic
      |                  |
      +---------+--------+
                |
                v
          PostgreSQL
          Source of Truth
                |
                v
          Analytics Layer
                |
                v
             DuckDB
                |
                v
        Analytics API Data
                |
                v
         Next.js Charts
```

## 2. Frontend

Technology: - Next.js - TypeScript - Tailwind CSS - shadcn/ui - Recharts

Primary pages: - `/login` - `/register` - `/onboarding` - `/chat` -
`/dashboard` - `/progress` - `/workouts` - `/foods` - `/profile` -
`/settings`

The chat page is the primary application experience.

## 3. Backend

Technology: - Python - FastAPI - Pydantic - SQLAlchemy - PostgreSQL
driver

Suggested backend structure:

``` text
backend/
  app/
    main.py
    config.py

    api/
      routes/
        auth.py
        chat.py
        users.py
        foods.py
        nutrition.py
        workouts.py
        progress.py
        analytics.py
        documents.py

    models/
      user.py
      profile.py
      food.py
      food_log.py
      workout.py
      workout_plan.py
      weight_log.py
      water_log.py
      chat.py

    schemas/
      chat.py
      food.py
      workout.py
      profile.py
      analytics.py

    services/
      chat_service.py
      ai_parser.py
      nutrition_service.py
      workout_service.py
      document_service.py
      analytics_service.py

    repositories/
      food_repository.py
      workout_repository.py
      user_repository.py

    calculations/
      calorie.py
      protein.py
      macros.py
      workout.py

    db/
      session.py
      migrations/

    tests/
```

## 4. AI Layer

The AI should be responsible for language understanding, not
authoritative calculations.

Pipeline:

``` text
User Message
   |
   v
AI Parser
   |
   v
Structured Intent
   |
   v
Pydantic Validation
   |
   v
Business Logic
   |
   v
Database
```

The LLM should return structured output.

Example:

``` json
{
  "intent": "food_log",
  "items": [
    {
      "food_name": "egg",
      "quantity": 3,
      "unit": "piece"
    },
    {
      "food_name": "rice",
      "quantity": 200,
      "unit": "g"
    }
  ],
  "meal": "lunch"
}
```

## 5. Source of Truth

PostgreSQL is the authoritative application database.

DuckDB is not the primary transactional database.

Use PostgreSQL for: - Users - Profiles - Food records - Workout
records - Chat records - Goals - Documents - Custom foods

Use DuckDB for: - Aggregation - Trend analysis - Reporting - Advanced
analytics

## 6. File Processing

Upload flow:

``` text
PDF/TXT
  |
  v
Supabase Storage
  |
  v
Document Extraction
  |
  v
Workout Parser
  |
  v
Structured Workout Plan
  |
  v
PostgreSQL
```

Use PyMuPDF for PDF extraction.

## 7. Authentication

Use Supabase Auth or another established authentication provider.

Do not implement password authentication cryptography manually.

The backend must validate authenticated identity and enforce user-level
authorization.

## 8. Error Boundary

Each layer must handle failures:

``` text
Frontend
  -> API error state

API
  -> validation/business error

AI
  -> parsing failure/ambiguity

Database
  -> transaction failure

Document parser
  -> extraction failure
```

Never expose raw stack traces to users.
