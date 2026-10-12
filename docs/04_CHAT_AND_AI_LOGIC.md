# Fitness Logger --- Chat and AI Logic

## 1. Goal

Turn natural language into reliable structured fitness events.

The AI is a parser and conversational assistant.

It is NOT the source of truth for calculations.

## 2. Intent Types

Initial supported intents:

``` text
food_log
food_correction
custom_food_create
custom_food_update
workout_log
workout_correction
weight_log
water_log
daily_summary
nutrition_query
workout_query
progress_query
goal_query
general_fitness_query
clarification
unknown
```

## 3. Food Logging

Input:

> I ate 3 eggs and 200g rice.

Expected structured result:

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
  ]
}
```

Backend then resolves nutrition.

## 4. Ambiguous Food

Input:

> I ate some chicken.

Do not assume quantity.

Return clarification:

> How much chicken did you eat?

## 5. Unknown Food

Input:

> I ate 100g of homemade protein atta.

If no nutrition exists:

``` text
Unknown Food
   |
   v
Ask for nutrition
   |
   v
Save custom food?
   |
   v
Calculate current log
```

## 6. Custom Nutrition

Support:

``` text
Calories
Protein
Carbohydrates
Fat
Fiber
Serving size
Serving unit
```

Example:

> 100g contains 350 kcal, 25g protein, 50g carbs and 8g fat.

The system should store nutrition per 100g or the explicitly supplied
serving basis.

## 7. Food Correction

Input:

> Actually the rice was 250g.

The system must identify the relevant recent food log and update it.

It must not create a duplicate entry.

If multiple possible entries exist, ask which one the user means.

## 8. Workout Logging

Input:

> Bench press 60kg, 4 sets of 8.

Output:

``` json
{
  "intent": "workout_log",
  "exercise": "bench press",
  "sets": 4,
  "reps": 8,
  "weight_kg": 60
}
```

## 9. Weight Logging

Input:

> My weight is 66.8kg today.

Output:

``` json
{
  "intent": "weight_log",
  "weight_kg": 66.8
}
```

## 10. Water Logging

Input:

> I drank 750ml water.

Output:

``` json
{
  "intent": "water_log",
  "amount_ml": 750
}
```

## 11. Conversation Context

The chat service should provide enough recent conversation context to
resolve follow-ups.

Example:

User: \> I ate 200g rice.

User: \> Add 100g chicken.

The second message should be interpreted as another food log.

Do not send unlimited conversation history to the LLM. Use a bounded
context window and structured conversation state.

## 12. AI Safety and Reliability

Never let the LLM: - Directly execute SQL - Directly modify arbitrary
database records - Invent nutrition values - Invent quantities - Change
another user's data - Override business rules

The LLM produces structured intent. Backend services decide what is
actually written.

## 13. Response Generation

After the backend completes the operation, generate a concise
user-facing response.

Example:

> Logged 3 eggs and 200g rice --- 506 kcal and 18g protein.

The response must be based on backend-calculated values, not values
hallucinated by the LLM.

## 14. Query Handling

For:

> How much protein have I eaten today?

The backend should query stored data and calculate the result.

Do not ask the LLM to calculate from memory if authoritative data exists
in PostgreSQL.

## 15. Structured Output

Use Pydantic models for all supported AI outputs.

Reject or retry invalid model output.

Keep parsing and business logic separate.
