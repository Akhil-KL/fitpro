# Fitness Logger --- Data Model

## 1. Core Principle

Store raw structured fitness events.

Do not store only final daily totals.

Daily totals and charts should be derived from underlying records.

## 2. Main Entities

### users

``` text
id
auth_provider_id
created_at
updated_at
```

### user_profiles

``` text
id
user_id
name
age
gender
ethnicity
height_cm
current_weight_kg
activity_level
fitness_goal
target_weight_kg
created_at
updated_at
```

### nutrition_targets

``` text
id
user_id
calorie_target
protein_target_g
carbs_target_g
fat_target_g
water_target_ml
effective_from
created_at
```

Keep target history rather than overwriting historical targets.

### foods

Application-level food database.

``` text
id
name
serving_size
serving_unit
calories
protein_g
carbs_g
fat_g
fiber_g
source
created_at
updated_at
```

### custom_foods

User-specific foods.

``` text
id
user_id
name
serving_size
serving_unit
calories
protein_g
carbs_g
fat_g
fiber_g
created_at
updated_at
```

### food_logs

``` text
id
user_id
food_id nullable
custom_food_id nullable
quantity
unit
meal_type nullable
logged_at
source
notes nullable
created_at
updated_at
```

The record should retain enough information to reproduce the nutrition
calculation.

### food_log_nutrition

Snapshot of nutrition actually used for the log.

``` text
id
food_log_id
calories
protein_g
carbs_g
fat_g
fiber_g
calculation_source
```

This prevents future food-database changes from altering historical
records.

### workout_plans

``` text
id
user_id
name
source_document_id nullable
created_at
updated_at
```

### workout_plan_days

``` text
id
workout_plan_id
day_number
name
description
```

### planned_exercises

``` text
id
workout_plan_day_id
exercise_name
sets
target_reps
target_weight nullable
duration_seconds nullable
order_index
```

### workout_sessions

``` text
id
user_id
workout_plan_day_id nullable
started_at
completed_at nullable
notes nullable
```

### workout_exercises

``` text
id
workout_session_id
exercise_name
order_index
```

### workout_sets

``` text
id
workout_exercise_id
set_number
reps
weight_kg nullable
duration_seconds nullable
```

### weight_logs

``` text
id
user_id
weight_kg
logged_at
```

### water_logs

``` text
id
user_id
amount_ml
logged_at
```

### conversations

``` text
id
user_id
created_at
updated_at
```

### chat_messages

``` text
id
conversation_id
role
content
parsed_intent nullable
parsed_payload nullable
created_at
```

Store parsed payload for debugging/auditing, but the authoritative
fitness records must remain in their own tables.

### documents

``` text
id
user_id
file_name
file_type
storage_path
processing_status
extracted_text nullable
created_at
processed_at nullable
```

## 3. Important Relationships

``` text
User
 ├── Profile
 ├── Nutrition Targets
 ├── Food Logs
 ├── Custom Foods
 ├── Workout Plans
 ├── Workout Sessions
 ├── Weight Logs
 ├── Water Logs
 ├── Conversations
 └── Documents
```

## 4. Indexing

At minimum index:

``` text
food_logs(user_id, logged_at)
workout_sessions(user_id, started_at)
weight_logs(user_id, logged_at)
water_logs(user_id, logged_at)
chat_messages(conversation_id, created_at)
custom_foods(user_id, name)
```

Use pagination on historical endpoints.

## 5. Data Integrity

Every user-owned table must enforce user isolation through application
authorization.

Use foreign keys.

Use transactions for multi-record operations.

Never trust user_id supplied by the client when an authenticated
identity is available. Derive it from the authenticated session/token.
