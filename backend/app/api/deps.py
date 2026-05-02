from fastapi import Header, HTTPException, status

from app.schemas.auth import AuthUser
from app.services.auth_service import ensure_profile_exists, verify_access_token


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be Bearer token",
        )

    user = verify_access_token(parts[1])
    ensure_profile_exists(user)
    return user
