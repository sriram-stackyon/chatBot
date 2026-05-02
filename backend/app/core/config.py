from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Amzur ChatBot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    GOOGLE_FRONTEND_CALLBACK_PATH: str = "/auth/google/callback"
    DATABASE_URL: str = ""
    EMPLOYEE_EMAIL_DOMAIN: str = ""
    AUTH_SECRET_KEY: str = ""
    AUTH_TOKEN_EXPIRE_MINUTES: int = 60
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # LLM (configured via existing LiteLLM env vars)
    LLM_API_BASE: str = Field(..., validation_alias="LITELLM_PROXY_URL")
    LLM_API_KEY: str = Field(..., validation_alias="LITELLM_VIRTUAL_KEY")
    LLM_MODEL: str = Field("gemini/gemini-2.5-flash", validation_alias="LITELLM_MODEL")
    LLM_TEMPERATURE: float = Field(0.7, validation_alias="LITELLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(2048, validation_alias="LITELLM_MAX_TOKENS")

    # Supabase
    SUPABASE_URL: str = Field(
        "",
        validation_alias=AliasChoices("SUPABASE_URL", "SUPABASE_PROJECT_URL"),
    )
    SUPABASE_ANON_KEY: str = Field(
        "",
        validation_alias=AliasChoices(
            "SUPABASE_ANON_KEY",
            "SUPABASE_KEY",
            "SUPABASE_PUBLIC_KEY",
            "SUPABASE_API_KEY",
        ),
    )
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        "",
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SERVICE_KEY",
            "SUPABASE_SECRET_KEY",
        ),
    )

    def get_auth_secret(self) -> str:
        if self.AUTH_SECRET_KEY:
            return self.AUTH_SECRET_KEY

        # Fall back to API key if dedicated auth secret is not provided.
        fallback = self.LLM_API_KEY
        if not fallback:
            raise RuntimeError("AUTH_SECRET_KEY is not configured")
        return fallback

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
