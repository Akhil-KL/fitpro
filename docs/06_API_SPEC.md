# Fitness Logger --- API Specification

Base URL:

``` text
/api/v1
```

All protected endpoints require authenticated user identity.

## Authentication

Authentication may be delegated to Supabase Auth.

Backend must validate the authenticated identity.

## Profile

### GET /profile

Return current user's profile.

### PUT /profile

Update profile.

### GET /targets

Return active nutrition targets.

## Chat

### POST /chat/messages

Request:

``` json
{
  "conversation_id": "uuid",
  "message": "I ate 3 eggs and 200g rice"
}
```

Response should contain: - Assistant response - Parsed action/result -
Updated entities - Any clarification requirement

Example:

``` json
{
  "conversation_id": "uuid",
  "message": "Logged 3 eggs and 200g rice — 506 kcal and 18g protein.",
  "intent": "food_log",
  "status": "completed"
}
```

### GET /chat/conversations

Paginated conversation list.

### GET /chat/conversations/{id}/messages

Paginated messages.

## Foods

### GET /foods/search?q=chicken

Search application/custom food sources.

Must be paginated.

### POST /foods/custom

Create custom food.

### PUT /foods/custom/{id}

Update custom food.

### DELETE /foods/custom/{id}

Delete custom food if not protected by historical references.

## Food Logs

### GET /food-logs

Query parameters: - date - from - to - page - page_size

Must be paginated.

### PUT /food-logs/{id}

Manual/correction update.

### DELETE /food-logs/{id}

Delete a food log.

## Workouts

### GET /workouts

Paginated workout history.

### POST /workouts

Create workout session when needed.

### GET /workouts/{id}

Get workout details.

## Workout Plans

### POST /workout-plans/upload

Upload PDF/TXT.

### GET /workout-plans

List user workout plans.

### GET /workout-plans/{id}

Get structured plan.

## Weight

### GET /weight-logs

Paginated historical weight.

### POST /weight-logs

Create weight log.

## Water

### GET /water-logs

Paginated water history.

### POST /water-logs

Create water log.

## Analytics

### GET /analytics/daily

Return daily totals.

### GET /analytics/nutrition

Query: - from - to - granularity

Return calorie/protein/macro series.

### GET /analytics/weight

Return time-series weight data.

### GET /analytics/workouts

Return workout analytics.

### GET /analytics/summary

Return dashboard-ready aggregate data.

## API Principles

-   Validate request bodies with Pydantic.
-   Never trust client user IDs.
-   Return consistent error schemas.
-   Use pagination for histories.
-   Keep API routes thin; business logic belongs in services.
