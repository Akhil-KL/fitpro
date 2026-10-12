from fastapi import APIRouter

from app.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.repositories.user_repository import UserRepository
from app.schemas.common import Message
from app.schemas.profile import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.profile_service import AuthService, ProfileService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict:
    """Tells the frontend which auth flow the server expects."""
    s = get_settings()
    return {"mode": s.auth_mode, "supabase_url": s.supabase_url if s.auth_mode == "supabase" else None}


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: DbSession) -> TokenResponse:
    _, token, expires = AuthService(db).register(body.email, body.password)
    db.commit()
    return TokenResponse(access_token=token, expires_in=expires)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    _, token, expires = AuthService(db).login(body.email, body.password)
    return TokenResponse(access_token=token, expires_in=expires)


@router.post("/logout", response_model=Message)
def logout(_: CurrentUser) -> Message:
    # Access tokens are stateless; the client discards its token. (Supabase: call signOut on the client.)
    return Message(message="Logged out.")


@router.post("/password-reset/request")
def password_reset_request(body: PasswordResetRequest, db: DbSession) -> dict:
    token = AuthService(db).request_reset(body.email)
    resp: dict = {"message": "If that email has an account, a reset link has been sent."}
    if token and get_settings().environment != "production":
        resp["dev_reset_token"] = token  # no mail service in dev: surface the token for testing
    return resp


@router.post("/password-reset/confirm", response_model=Message)
def password_reset_confirm(body: PasswordResetConfirm, db: DbSession) -> Message:
    AuthService(db).confirm_reset(body.token, body.new_password)
    db.commit()
    return Message(message="Password updated. You can log in now.")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser, db: DbSession) -> UserOut:
    out = UserOut.model_validate(user)
    out.has_profile = ProfileService.is_complete(UserRepository(db).profile(user.id))
    return out
