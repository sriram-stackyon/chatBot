from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user
from app.schemas.auth import (
    AuthTokenResponse,
    AuthUser,
    MeResponse,
    SignInRequest,
    SignUpRequest,
)
from app.core.config import settings
from app.services.auth_service import (
    get_google_login_url,
    sign_in_employee,
    sign_in_with_google_code,
    sign_up_employee,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthTokenResponse)
async def signup(request: SignUpRequest) -> AuthTokenResponse:
    return sign_up_employee(request.email, request.password, request.full_name)


@router.post("/login", response_model=AuthTokenResponse)
async def login(request: SignInRequest) -> AuthTokenResponse:
    return sign_in_employee(request.email, request.password)


@router.get("/google/login")
async def google_login(next: str = Query(default=settings.GOOGLE_FRONTEND_CALLBACK_PATH)) -> RedirectResponse:
    return RedirectResponse(url=get_google_login_url(next), status_code=307)


@router.get("/google/callback")
async def google_callback(code: str = Query(default=""), state: str = Query(default="")) -> RedirectResponse:
    auth_response, next_path = await sign_in_with_google_code(code=code, state_token=state)
    query = urlencode(
        {
            "token": auth_response.access_token,
            "id": auth_response.user.id,
            "email": auth_response.user.email or "",
        }
    )
    target = f"{settings.FRONTEND_BASE_URL.rstrip('/')}{next_path}?{query}"
    return RedirectResponse(url=target, status_code=307)


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: AuthUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=current_user.user_id, email=current_user.email)
