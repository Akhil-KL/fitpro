# Fitness Logger --- Product Requirements Document

## 1. Product Overview

Fitness Logger is a chat-first fitness tracking application.

The primary interaction model is conversational: users log food,
nutrition, workouts, body weight, water intake, corrections, and other
fitness information through natural-language chat.

The system converts chat messages into structured data, validates the
extracted information, stores it in PostgreSQL, performs deterministic
fitness calculations, and presents historical analytics through charts
and dashboards.

The application also allows users to upload workout plans as PDF or text
documents. Uploaded plans are parsed into structured workout plans that
can be referenced during future chat interactions.

## 2. Core Product Principle

The chat interface is the primary data-entry mechanism.

Users should not be forced to navigate forms for normal logging.

Example:

> I ate 3 eggs, 200g rice and 150g chicken for lunch.

The system should identify the food items, quantities, units, meal
context, retrieve or request nutrition information, calculate totals,
validate the result, and save the log.

## 3. Target Users

Users who want to track: - Calories - Protein - Macronutrients - Food
intake - Workouts - Weight - Water - Fitness goals - Workout-plan
adherence - Long-term progress

## 4. MVP Functional Scope

### Authentication

-   Registration
-   Login
-   Logout
-   Password/account recovery
-   Protected user resources

### User Profile

-   Name
-   Age
-   Height
-   Weight
-   Gender
-   Ethnicity
-   Activity level
-   Fitness goal
-   Target weight where applicable

### Nutrition

-   Daily calorie target
-   Daily protein target
-   Macro targets
-   Food logging through chat
-   Custom foods
-   Custom nutrition values
-   Nutrition overrides
-   Daily nutrition totals
-   Food history

### Workout

-   Workout logging through chat
-   Exercise name
-   Sets
-   Reps
-   Weight
-   Duration where applicable
-   Workout history
-   Workout-plan upload
-   PDF/text workout-plan parsing
-   Planned vs completed workout tracking

### Body Tracking

-   Weight logging through chat
-   Weight history
-   Progress toward goal

### Water

-   Water logging through chat
-   Daily water total

### Analytics

-   Daily calorie summary
-   Daily protein summary
-   Macro distribution
-   Weekly/monthly calorie trends
-   Protein trends
-   Weight progression
-   Workout frequency
-   Workout volume
-   Exercise progression
-   Goal adherence

### Dashboard

-   Daily summary
-   Weekly summary
-   Charts
-   Progress indicators
-   Recent activity

## 5. Chat Requirements

The chat must support:

### New log

"I ate 3 eggs."

### Multiple logs

"I ate 3 eggs, 200g rice and 150g chicken."

### Workout

"I did bench press 60kg for 4 sets of 8."

### Weight

"My weight today is 66.8kg."

### Water

"I drank 750ml water."

### Correction

"Actually, the rice was 250g."

### Follow-up

"Add another egg."

### Query

"How much protein have I eaten today?"

### Plan query

"What is today's workout?"

## 6. Ambiguity Handling

The system must not invent missing quantities or nutrition values.

Example:

> I ate some chicken.

The assistant should ask for the missing quantity.

If a food is unknown, the assistant should offer custom nutrition entry.

## 7. Custom Nutrition

Users can provide: - Calories - Protein - Carbohydrates - Fat - Fiber -
Sodium if supported later - Serving size - Serving unit

Nutrition can be defined per: - 100g - 100ml - Piece - Serving - Package

Custom foods should be saved for future use.

## 8. Dashboard Visualization

Use: - Pie/donut charts for macro composition - Bar charts for
categorical daily comparisons - Line charts for weight and other
time-series trends - Progress indicators for targets

The frontend should never calculate authoritative fitness totals
independently. Backend analytics should provide the data used for
charts.

## 9. Non-Functional Requirements

### Security

-   Secure authentication
-   Passwords must never be stored in plaintext
-   User data must be isolated by user ID
-   Protected APIs require authentication
-   Validate all user input
-   Secrets must be stored in environment variables

### Performance

-   Chat responses should normally return quickly
-   Database queries should be indexed
-   History endpoints must support pagination
-   Expensive document processing should be asynchronous when required

### Reliability

-   Do not save invalid structured data
-   Use transactions for multi-step writes
-   Preserve user corrections
-   Handle LLM/API/database failures gracefully

### Scalability

-   Modular backend
-   PostgreSQL as operational source of truth
-   DuckDB as analytics engine when analytical workload grows
-   Redis/background jobs when needed

### Maintainability

-   Typed schemas
-   Modular services
-   Clear separation of AI parsing, business logic, persistence, and
    analytics
-   Automated tests for calculations and parsing

## 10. Out of Scope for MVP

Do not initially implement: - Kubernetes - Microservices - Kafka -
Complex agent orchestration - RAG unless a real knowledge-base
requirement appears - Multiple operational databases - Wearable
integrations - Social features - Payments

## 11. Success Criteria

A user should be able to: 1. Create an account. 2. Complete their
fitness profile. 3. Receive calculated targets. 4. Log food entirely
through chat. 5. Add custom nutrition when necessary. 6. Log workouts
through chat. 7. Upload a workout split. 8. Ask what workout they should
do. 9. Log weight and water. 10. View daily and historical analytics.
11. Correct previous entries conversationally. 12. See charts generated
from stored data.
