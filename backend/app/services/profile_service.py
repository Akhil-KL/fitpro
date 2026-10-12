"""Auth accounts, profile and nutrition-target history."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.aggregation import get_zone
from app.calculations.profile import bmi, bmi_category, bmr, compute_targets, tdee
from app.config import get_settings
from app.core.errors import Conflict, NotFound, Unauthorized, ValidationFailed
from app.core.security import (
    create_access_token,
    create_reset_token,
    decode_local_token,
    hash_password,
    password_fingerprint,
    verify_password,
)
from app.models import NutritionTarget, User, UserProfile, WeightLog
from app.repositories.user_repository import UserRepository
from app.schemas.profile import ProfileOut, ProfileUpdate, TargetsOut

log = logging.getLogger(__name__)

REQUIRED_FOR_TARGETS = ("age", "gender", "height_cm", "current_weight_kg", "activity_level", "fitness_goal")


def local_today(profile: UserProfile | None) -> date:
    tz = get_zone(profile.timezone if profile else None)
    return datetime.now(tz).date()


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def _ensure_local(self) -> None:
        if get_settings().auth_mode != "local":
            raise ValidationFailed("Password login is handled by Supabase Auth on this server.")

    def register(self, email: str, password: str) -> tuple[User, str, int]:
        self._ensure_local()
        email = email.lower()
        if self.users.by_email(email):
            raise Conflict("An account with this email already exists.")
        user_id = uuid.uuid4()
        user = User(id=user_id, auth_provider_id=f"local:{user_id}", email=email, password_hash=hash_password(password))
        self.users.add(user)
        token, expires = create_access_token(str(user.id))
        return user, token, expires

    def login(self, email: str, password: str) -> tuple[User, str, int]:
        self._ensure_local()
        user = self.users.by_email(email.lower())
        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            raise Unauthorized("Incorrect email or password.")
        token, expires = create_access_token(str(user.id))
        return user, token, expires

    def request_reset(self, email: str) -> str | None:
        """Returns the token (development only). In production deliver it by email; never reveal existence."""
        self._ensure_local()
        user = self.users.by_email(email.lower())
        if user is None:
            return None
        token = create_reset_token(str(user.id), user.password_hash)
        link = f"{get_settings().frontend_url}/reset-password?token={token}"
        log.info("Password reset requested for user %s. Reset link: %s", user.id, link)
        return token

    def confirm_reset(self, token: str, new_password: str) -> None:
        self._ensure_local()
        claims = decode_local_token(token, expected_type="reset")
        user = self.users.get(uuid.UUID(claims["sub"]))
        if user is None or claims.get("pwf") != password_fingerprint(user.password_hash):
            raise Unauthorized("This reset link is invalid or has already been used.")
        user.password_hash = hash_password(new_password)
        self.db.flush()


class ProfileService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def get_or_create(self, user: User) -> UserProfile:
        profile = self.users.profile(user.id)
        if profile is None:
            profile = UserProfile(user_id=user.id, timezone="UTC")
            self.db.add(profile)
            self.db.flush()
        return profile

    @staticmethod
    def is_complete(profile: UserProfile | None) -> bool:
        return profile is not None and all(getattr(profile, f) is not None for f in REQUIRED_FOR_TARGETS)

    def to_out(self, profile: UserProfile) -> ProfileOut:
        out = ProfileOut.model_validate(profile)
        out.is_complete = self.is_complete(profile)
        if profile.current_weight_kg and profile.height_cm:
            out.bmi = bmi(profile.current_weight_kg, profile.height_cm)
            out.bmi_category = bmi_category(out.bmi)
        if out.is_complete:
            out.bmr = bmr(profile.current_weight_kg, profile.height_cm, profile.age, profile.gender)  # type: ignore[arg-type]
            out.tdee = tdee(out.bmr, profile.activity_level)  # type: ignore[arg-type]
        return out

    def update(self, user: User, data: ProfileUpdate) -> UserProfile:
        profile = self.get_or_create(user)
        changes = data.model_dump(exclude_unset=True)
        for k, v in changes.items():
            setattr(profile, k, v)
        if changes.get("current_weight_kg") is not None and not self._has_weight_logs(user):
            # Starting point for weight progress: the weight given at onboarding.
            self.db.add(WeightLog(user_id=user.id, weight_kg=changes["current_weight_kg"],
                                  logged_at=datetime.now(timezone.utc)))
        self.db.flush()
        self.refresh_targets(user, profile)
        return profile

    def _has_weight_logs(self, user: User) -> bool:
        return self.db.scalar(select(WeightLog.id).where(WeightLog.user_id == user.id).limit(1)) is not None

    def refresh_targets(self, user: User, profile: UserProfile) -> NutritionTarget | None:
        """Write a new target row effective today (replacing only today's row; history is kept)."""
        if not self.is_complete(profile):
            return None
        r = compute_targets(
            weight_kg=profile.current_weight_kg,  # type: ignore[arg-type]
            height_cm=profile.height_cm,  # type: ignore[arg-type]
            age=profile.age,  # type: ignore[arg-type]
            gender=profile.gender,  # type: ignore[arg-type]
            activity_level=profile.activity_level,  # type: ignore[arg-type]
            goal=profile.fitness_goal,  # type: ignore[arg-type]
        )
        today = local_today(profile)
        values = dict(
            calorie_target=r.calorie_target, protein_target_g=r.protein_target_g, carbs_target_g=r.carbs_target_g,
            fat_target_g=r.fat_target_g, water_target_ml=r.water_target_ml,
        )
        current = self.users.active_targets(user.id, today)
        if current is not None and all(getattr(current, k) == v for k, v in values.items()):
            return current  # unchanged: no new history row
        row = self.users.target_on_exact(user.id, today)
        if row is None:
            row = NutritionTarget(user_id=user.id, effective_from=today, **values)
            self.db.add(row)
        else:
            for k, v in values.items():
                setattr(row, k, v)
        self.db.flush()
        return row

    def targets(self, user: User, on: date | None = None) -> TargetsOut:
        t = self.users.active_targets(user.id, on)
        if t is None:
            raise NotFound("Complete your profile to get targets.", code="profile_incomplete")
        return TargetsOut.model_validate(t)
