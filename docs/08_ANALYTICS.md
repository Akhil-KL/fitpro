# Fitness Logger --- Analytics Specification

## 1. Purpose

Analytics transform stored fitness events into useful trends and
visualizations.

PostgreSQL remains the source of truth.

DuckDB is optional for advanced analytics and can be introduced after
the MVP.

## 2. Daily Dashboard

Return:

``` text
Calories consumed
Calorie target
Calories remaining
Protein consumed
Protein target
Protein remaining
Carbs
Fat
Water
Workout status
Current weight
```

## 3. Chart Types

### Macro Composition

Pie/donut chart.

Data: - Protein - Carbohydrates - Fat

### Calories

Bar chart for daily comparisons.

### Protein

Bar or line chart depending on time range.

### Weight

Line chart.

### Workout Frequency

Bar chart.

### Exercise Progression

Line chart for an exercise over time.

## 4. Time Ranges

Support: - Today - Last 7 days - Last 30 days - Custom date range

## 5. Data Granularity

For time-series charts: - Daily for short ranges - Weekly for longer
ranges - Monthly for long-term reports

Do not discard available data unnecessarily.

## 6. DuckDB Usage

For MVP, PostgreSQL aggregation may be sufficient.

Introduce DuckDB for: - Large analytical queries - Complex trend
calculations - Reporting - Exportable reports - Advanced statistical
analysis

Suggested flow:

``` text
PostgreSQL
    |
    v
Analytics extraction
    |
    v
DuckDB
    |
    v
Aggregations
    |
    v
FastAPI Analytics Service
    |
    v
Frontend
```

## 7. Analytics Rules

Charts must be based on backend-calculated values.

The frontend should only visualize data.

Do not put nutrition/business calculations in React components.

## 8. Future Analytics

Possible future features: - Calorie adherence score - Protein adherence
score - Workout consistency score - Weight trend prediction - Training
volume trends - Goal completion estimates - Personal records
