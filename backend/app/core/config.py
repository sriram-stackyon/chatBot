import hashlib
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
    MAX_UPLOAD_MB: int = 20
    UPLOAD_DIR: str = "./uploads"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # LLM (configured via existing LiteLLM env vars)
    LLM_API_BASE: str = Field(..., validation_alias="LITELLM_PROXY_URL")
    LLM_API_KEY: str = Field(
        ...,
        validation_alias=AliasChoices("LITELLM_API_KEY", "LITELLM_VIRTUAL_KEY"),
    )
    LLM_MODEL: str = Field("gemini/gemini-2.5-flash", validation_alias="LITELLM_MODEL")
    LLM_TEMPERATURE: float = Field(0.7, validation_alias="LITELLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(2048, validation_alias="LITELLM_MAX_TOKENS")
    LITELLM_PROXY_URL: str = Field(..., validation_alias="LITELLM_PROXY_URL")
    LITELLM_API_KEY: str = Field(
        ...,
        validation_alias=AliasChoices("LITELLM_API_KEY", "LITELLM_VIRTUAL_KEY"),
    )
    IMAGE_GEN_MODEL: str = Field(
        "gemini/imagen-4.0-fast-generate-001",
        validation_alias="IMAGE_GEN_MODEL",
    )

    # RAG Configuration
    EMBEDDING_MODEL: str = Field("text-embedding-3-large", validation_alias="EMBEDDING_MODEL")
    CHROMA_PERSIST_DIR: str = Field("./chroma_db", validation_alias="CHROMA_PERSIST_DIR")
    RAG_CHUNK_SIZE: int = Field(1500, validation_alias="RAG_CHUNK_SIZE")
    RAG_CHUNK_OVERLAP: int = Field(200, validation_alias="RAG_CHUNK_OVERLAP")
    RAG_TOP_K: int = Field(5, validation_alias="RAG_TOP_K")
    RAG_SCORE_THRESHOLD: float = Field(0.3, validation_alias="RAG_SCORE_THRESHOLD")
    RAG_ENABLE_SUMMARIZATION: bool = Field(True, validation_alias="RAG_ENABLE_SUMMARIZATION")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(True, validation_alias="RATE_LIMIT_ENABLED")
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(60, validation_alias="RATE_LIMIT_REQUESTS_PER_MINUTE")
    RATE_LIMIT_TOKENS_PER_DAY: int = Field(1000000, validation_alias="RATE_LIMIT_TOKENS_PER_DAY")

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
            if len(self.AUTH_SECRET_KEY.encode("utf-8")) >= 32:
                return self.AUTH_SECRET_KEY
            return hashlib.sha256(self.AUTH_SECRET_KEY.encode("utf-8")).hexdigest()

        fallback = self.LLM_API_KEY
        if not fallback:
            raise RuntimeError("AUTH_SECRET_KEY is not configured")
        if len(fallback.encode("utf-8")) >= 32:
            return fallback
        return hashlib.sha256(fallback.encode("utf-8")).hexdigest()

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
