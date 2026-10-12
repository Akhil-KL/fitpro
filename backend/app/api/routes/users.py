from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.profile import ProfileOut, ProfileUpdate, TargetsOut
from app.services.profile_service import ProfileService, local_today

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: DbSession) -> ProfileOut:
    svc = ProfileService(db)
    profile = svc.get_or_create(user)
    db.commit()
    return svc.to_out(profile)


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> ProfileOut:
    svc = ProfileService(db)
    profile = svc.update(user, body)
    db.commit()
    return svc.to_out(profile)


@router.get("/targets", response_model=TargetsOut)
def get_targets(user: CurrentUser, db: DbSession) -> TargetsOut:
    svc = ProfileService(db)
    return svc.targets(user, local_today(svc.get_or_create(user)))
