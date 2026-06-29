"""
N8N Digest Endpoint
Non-streaming, API-key authenticated endpoint designed for n8n workflow integration.

Auth: X-N8N-API-Key header must match the N8N_API_KEY env variable.
"""

import logging
import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from app.ai.llm import get_chat_llm
from app.core.config import settings
from app.db.postgres import get_db_cursor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/n8n", tags=["n8n"])

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _require_n8n_api_key(x_n8n_api_key: str = Header(..., alias="X-N8N-API-Key")) -> None:
    """Validate the shared API key sent by n8n.  Constant-time comparison."""
    configured = settings.N8N_API_KEY
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="N8N integration is not configured on this server.",
        )
    if not secrets.compare_digest(x_n8n_api_key, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ArticleItem(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    url: str = Field(..., min_length=10, max_length=2000)
    score: int = Field(default=0, ge=0)
    source: str = Field(default="unknown", max_length=100)

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class DigestRequest(BaseModel):
    articles: list[ArticleItem] = Field(..., min_length=1, max_length=20)
    run_date: date = Field(default_factory=date.today)
    persist: bool = Field(default=True, description="Write result to digest_history table")


class DigestResponse(BaseModel):
    digest: str
    article_count: int
    delivery_method: Literal["email", "slack", "none"]
    run_date: date
    persisted: bool


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/digest",
    response_model=DigestResponse,
    summary="Generate an AI digest from articles and optionally persist the result",
)
async def generate_digest(
    request: DigestRequest,
    _: None = Depends(_require_n8n_api_key),
) -> DigestResponse:
    """
    Called by the n8n workflow.
    1. Accepts a validated list of articles from the n8n Function node.
    2. Generates a structured AI digest via LiteLLM.
    3. Recommends email (≥3 articles) or slack (<3 articles) delivery.
    4. Optionally persists run metadata to digest_history for audit trail.
    """
    article_count = len(request.articles)

    # Build article list for the prompt
    article_lines = "\n".join(
        f"{i + 1}. [{a.source}] {a.title} (score: {a.score})\n   {a.url}"
        for i, a in enumerate(request.articles)
    )

    system_prompt = (
        "You are an expert technology newsletter editor. "
        "Given a list of trending articles, produce a concise daily digest. "
        "Format: a short intro sentence, then bullet points (one per article) with title, "
        "one-sentence insight, and the URL. Keep the total under 400 words. "
        "End with a one-line 'Today's theme' observation."
    )
    user_prompt = (
        f"Date: {request.run_date}\n\n"
        f"Today's top {article_count} articles:\n\n{article_lines}\n\n"
        "Generate the digest."
    )

    llm = get_chat_llm()
    response = await llm.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    )
    digest_text: str = response.content  # type: ignore[assignment]

    delivery_method: Literal["email", "slack", "none"] = (
        "email" if article_count >= 3 else "slack"
    )

    persisted = False
    if request.persist:
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.digest_history
                        (run_date, articles_found, digest_text, delivery_method, status)
                    VALUES (%s, %s, %s, %s, 'success')
                    """,
                    (request.run_date, article_count, digest_text, delivery_method),
                )
            persisted = True
        except Exception:
            logger.exception("Failed to persist digest_history row — continuing anyway")

    return DigestResponse(
        digest=digest_text,
        article_count=article_count,
        delivery_method=delivery_method,
        run_date=request.run_date,
        persisted=persisted,
    )


@router.post(
    "/digest/error-log",
    status_code=204,
    summary="Log a workflow error to digest_history (called by n8n error branch)",
)
async def log_digest_error(
    run_date: date,
    error_message: str = Query(..., max_length=1000),
    _: None = Depends(_require_n8n_api_key),
) -> None:
    """Allows the n8n Error Trigger branch to write a failure row to digest_history."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.digest_history
                    (run_date, articles_found, delivery_method, status, error_message)
                VALUES (%s, 0, 'none', 'error', %s)
                """,
                (run_date, error_message[:1000]),
            )
    except Exception:
        logger.exception("Failed to log digest error to database")
