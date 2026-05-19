import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError

from app.api.deps import get_current_user
from app.schemas.auth import AuthUser
from app.schemas.sql_chat import SQLChatRequest, SQLChatResponse
from app.services.sql_query_service import run_sql_query_safe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sql-chat"])


@router.post("/sql/chat", response_model=SQLChatResponse)
async def sql_chat(
    request: SQLChatRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> SQLChatResponse:
    try:
        payload = await run_sql_query_safe(request.message, current_user.email)
        return SQLChatResponse(**payload)
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected SQL chat error")
        raise HTTPException(
            status_code=500,
            detail={"error": "unexpected", "message": str(exc)},
        ) from exc
