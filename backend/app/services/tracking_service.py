"""Body weight and water logging."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import User, WaterLog, WeightLog
from app.services.profile_service import ProfileService


class TrackingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log_weight(self, user: User, weight_kg: float, logged_at: datetime) -> WeightLog:
        entry = WeightLog(user_id=user.id, weight_kg=round(weight_kg, 2), logged_at=logged_at)
        self.db.add(entry)
        self.db.flush()
        # Keep the profile's current weight in sync and recompute targets (new history row if they change).
        profiles = ProfileService(self.db)
        profile = profiles.get_or_create(user)
        latest = self.db.query(WeightLog).filter(WeightLog.user_id == user.id).order_by(WeightLog.logged_at.desc()).first()
        if latest is not None and latest.id == entry.id:
            profile.current_weight_kg = entry.weight_kg
            self.db.flush()
            profiles.refresh_targets(user, profile)
        return entry

    def log_water(self, user: User, amount_ml: float, logged_at: datetime) -> WaterLog:
        entry = WaterLog(user_id=user.id, amount_ml=int(round(amount_ml)), logged_at=logged_at)
        self.db.add(entry)
        self.db.flush()
        return entry
