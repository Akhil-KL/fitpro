# Fitness Logger --- Nutrition and Calculation Logic

## 1. Principle

Fitness calculations must be deterministic and implemented in backend
Python services.

The LLM may identify inputs, but it should not be the authoritative
calculator.

## 2. Profile Calculations

The system should calculate: - BMI - BMR - TDEE - Daily calorie target -
Protein target - Macro targets

Calculation formulas should be isolated in testable Python modules.

Do not hard-code calculation logic into API route handlers.

## 3. Nutrition Calculation

Every food log should resolve to a nutrition snapshot.

For a nutrition profile expressed per 100g:

``` text
scaled_value = nutrition_per_100g × quantity / 100
```

For serving-based foods, use the serving basis.

## 4. Historical Snapshot

When a food is logged, save the actual nutrition values used at that
time.

Example:

``` text
Food database:
Chicken = 165 kcal / 100g

User logs:
150g

Historical log stores:
247.5 kcal
46.5g protein
...
```

If the food database changes later, historical logs must not silently
change.

## 5. Daily Totals

Daily nutrition should be calculated from food logs for the user's local
date.

Return:

``` text
Calories consumed
Protein consumed
Carbs consumed
Fat consumed
Fiber consumed
```

Also return targets and remaining amounts.

## 6. Macro Distribution

Macro charts should use calculated macro totals.

Do not derive percentages from calorie totals incorrectly.

Use the selected nutrition model consistently.

## 7. Weight Analytics

Calculate: - Current weight - Starting weight - Change - Average weekly
change - Progress toward target where applicable

Use line charts for weight over time.

## 8. Workout Analytics

Calculate: - Workout count - Weekly workout frequency - Exercise
volume - Reps - Sets - Weight progression - Personal records where rules
are defined

A simple volume metric can be:

``` text
volume = sets × reps × weight
```

For bodyweight exercises or timed exercises, use an appropriate
alternative.

## 9. Target Changes

Nutrition targets can change when profile information or goals change.

Do not overwrite old targets if historical reporting is important.

Create a new target record with an effective date.

## 10. Testing

Create unit tests for: - BMR - TDEE - calorie targets - protein
targets - macro targets - food scaling - daily aggregation - weekly
aggregation - workout volume - progress calculations
