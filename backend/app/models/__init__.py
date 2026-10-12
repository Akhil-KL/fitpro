"""Import every model so Base.metadata is complete (Alembic, create_all)."""

from app.models.food import CustomFood, Food, FoodLog, FoodLogNutrition
from app.models.tracking import ChatMessage, Conversation, Document, WaterLog, WeightLog
from app.models.user import NutritionTarget, User, UserProfile
from app.models.workout import (
    PlannedExercise,
    WorkoutExercise,
    WorkoutPlan,
    WorkoutPlanDay,
    WorkoutSession,
    WorkoutSet,
)

__all__ = [
    "User",
    "UserProfile",
    "NutritionTarget",
    "Food",
    "CustomFood",
    "FoodLog",
    "FoodLogNutrition",
    "WorkoutPlan",
    "WorkoutPlanDay",
    "PlannedExercise",
    "WorkoutSession",
    "WorkoutExercise",
    "WorkoutSet",
    "WeightLog",
    "WaterLog",
    "Conversation",
    "ChatMessage",
    "Document",
]
