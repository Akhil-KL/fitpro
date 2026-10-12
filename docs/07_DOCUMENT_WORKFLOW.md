# Fitness Logger --- Workout Document Workflow

## 1. Supported Inputs

Initial support: - PDF - TXT

DOCX can be added later.

## 2. Upload

User uploads workout split.

Frontend sends multipart upload to backend.

Backend: 1. Validates file type. 2. Validates file size. 3. Stores file.
4. Creates document record. 5. Marks processing status as `pending`. 6.
Starts processing.

## 3. PDF Extraction

Use PyMuPDF.

Extract: - Text - Page information - Relevant headings - Exercise lines

If extraction quality is poor, flag the document for processing
review/fallback.

## 4. Structured Parsing

Convert text into:

``` text
Workout Plan
  |
  +-- Day
       |
       +-- Exercise
            |
            +-- sets
            +-- reps
            +-- weight
            +-- duration
            +-- order
```

## 5. Example

Input:

``` text
Day 1 - Push

Bench Press 4x8
Incline DB Press 3x10
Lateral Raise 3x15
```

Structured:

``` json
{
  "name": "My Workout Plan",
  "days": [
    {
      "day_number": 1,
      "name": "Push",
      "exercises": [
        {
          "exercise_name": "Bench Press",
          "sets": 4,
          "target_reps": 8
        },
        {
          "exercise_name": "Incline DB Press",
          "sets": 3,
          "target_reps": 10
        },
        {
          "exercise_name": "Lateral Raise",
          "sets": 3,
          "target_reps": 15
        }
      ]
    }
  ]
}
```

## 6. Processing Status

Use:

``` text
pending
processing
completed
failed
```

The UI should show status.

## 7. User Experience

After successful processing:

> Your workout plan has been imported successfully.

The user can then ask:

> What is today's workout?

The system determines the relevant workout day and returns the
structured exercises.

## 8. Security

Users must only be able to access their own uploaded documents.

Do not expose raw storage paths to unauthorized users.
