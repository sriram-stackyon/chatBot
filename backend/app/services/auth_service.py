import base64
import hashlib
import hmac
import os
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.db.postgres import get_db_cursor
from app.schemas.auth import AuthTokenResponse, AuthUser, MeResponse


def _normalise_password(password: str) -> str:
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


def ensure_employee_email(email: str | None) -> None:
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user is missing an email address",
        )

    expected_domain = settings.EMPLOYEE_EMAIL_DOMAIN.strip().lower().lstrip("@")
    if not expected_domain:
        return

    actual_domain = email.strip().lower().rsplit("@", 1)[-1]
    if actual_domain != expected_domain:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only @{expected_domain} employee accounts are allowed",
        )


def verify_access_token(access_token: str) -> AuthUser:
    try:
        payload = jwt.decode(
            access_token,
            settings.get_auth_secret(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token payload",
        )

    ensure_employee_email(email)

    return AuthUser(user_id=user_id, email=email)


def _hash_password(password: str) -> str:
    password = _normalise_password(password)
    salt = os.urandom(16)
    iterations = 390000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(derived).decode("ascii"),
    )


def _verify_password(password: str, encoded: str | None) -> bool:
    password = _normalise_password(password)
    if not encoded:
        return False

    try:
        scheme, iter_s, salt_s, hash_s = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iter_s)
        salt = base64.urlsafe_b64decode(salt_s.encode("ascii"))
        expected = base64.urlsafe_b64decode(hash_s.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.get_auth_secret(), algorithm="HS256")


def _get_or_create_profile(email: str, full_name: str | None = None) -> MeResponse:
    normalized_email = email.strip().lower()
    ensure_employee_email(normalized_email)
    normalized_full_name = (full_name or "").strip() or None

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select id, email, full_name
            from public.profiles
            where email = %s
            limit 1
            """,
            (normalized_email,),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                update public.profiles
                set full_name = coalesce(%s, full_name)
                where id = %s
                returning id, email, full_name
                """,
                (normalized_full_name, existing["id"]),
            )
            row = cursor.fetchone()
            return MeResponse(
                id=str(row["id"]),
                email=row["email"],
                full_name=row.get("full_name"),
            )

        user_id = str(uuid4())
        cursor.execute(
            """
            insert into public.profiles(id, email, full_name)
            values (%s, %s, %s)
            returning id, email, full_name
            """,
            (user_id, normalized_email, normalized_full_name),
        )
        created = cursor.fetchone()
        return MeResponse(
            id=str(created["id"]),
            email=created["email"],
            full_name=created.get("full_name"),
        )


def _build_google_state(next_path: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "next": next_path,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    return jwt.encode(payload, settings.get_auth_secret(), algorithm="HS256")


def _parse_google_state(state_token: str) -> str:
    try:
        payload = jwt.decode(state_token, settings.get_auth_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    next_path = str(payload.get("next") or settings.GOOGLE_FRONTEND_CALLBACK_PATH)
    if not next_path.startswith("/") or next_path.startswith("//"):
        return settings.GOOGLE_FRONTEND_CALLBACK_PATH
    return next_path


def get_google_login_url(next_path: str | None = None) -> str:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not settings.GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured",
        )

    requested_next = (next_path or settings.GOOGLE_FRONTEND_CALLBACK_PATH).strip()
    if not requested_next.startswith("/") or requested_next.startswith("//"):
        requested_next = settings.GOOGLE_FRONTEND_CALLBACK_PATH

    query = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": _build_google_state(requested_next),
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(query)}"


async def sign_in_with_google_code(code: str, state_token: str) -> tuple[AuthTokenResponse, str]:
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Google auth code")

    next_path = _parse_google_state(state_token)

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_resp.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google token exchange failed")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google access token missing")

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_resp.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google user info fetch failed")

        userinfo = userinfo_resp.json()

    email = (userinfo.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account email not available")

    ensure_employee_email(email)
    user = _get_or_create_profile(email=email, full_name=userinfo.get("name"))
    app_token = _create_access_token(user.id, user.email or email)
    return (
        AuthTokenResponse(access_token=app_token, user=user),
        next_path,
    )


def sign_up_employee(email: str, password: str, full_name: str | None = None) -> AuthTokenResponse:
    normalized_email = email.strip().lower()
    ensure_employee_email(normalized_email)
    normalized_full_name = (full_name or "").strip() or None

    user_id = str(uuid4())
    password_hash = _hash_password(password)

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            insert into public.profiles(id, email, password_hash, full_name)
            values (%s, %s, %s, %s)
            on conflict (email) do nothing
            returning id, email, full_name
            """,
            (user_id, normalized_email, password_hash, normalized_full_name),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_id = str(row["id"])
    token = _create_access_token(user_id, row["email"])
    return AuthTokenResponse(
        access_token=token,
        user=MeResponse(id=user_id, email=row["email"], full_name=row.get("full_name")),
    )


def sign_in_employee(email: str, password: str) -> AuthTokenResponse:
    normalized_email = email.strip().lower()
    ensure_employee_email(normalized_email)

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select id, email, password_hash, full_name
            from public.profiles
            where email = %s
            limit 1
            """,
            (normalized_email,),
        )
        row = cursor.fetchone()

    if not row or not _verify_password(password, row.get("password_hash")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_id = str(row["id"])
    token = _create_access_token(user_id, row["email"])
    return AuthTokenResponse(
        access_token=token,
        user=MeResponse(id=user_id, email=row["email"], full_name=row.get("full_name")),
    )

def ensure_profile_exists(user: AuthUser) -> None:
    """Create or update profile row for authenticated users."""
    ensure_employee_email(user.email)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            insert into public.profiles(id, email)
            values (%s, %s)
            on conflict (id) do update set email = excluded.email
            """,
            (user.user_id, (user.email or "").lower() or None),
        )
