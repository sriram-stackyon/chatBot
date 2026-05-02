from pydantic import BaseModel, EmailStr, Field


class AuthUser(BaseModel):
    user_id: str
    email: EmailStr | None = None


class MeResponse(BaseModel):
    id: str
    email: EmailStr | None = None
    full_name: str | None = None


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, min_length=2, max_length=100)


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeResponse
