"""
Workflow management routes — exposes n8n orchestration to the dashboard.

Routes:
  POST /api/workflows/run-news-digest   — trigger the AI News Digest workflow
  GET  /api/workflows/history           — in-memory execution log
  GET  /api/workflows/stats             — aggregated statistics
  GET  /api/workflows/list              — registered workflow definitions
"""

import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.schemas.auth import AuthUser
from app.services.n8n_service import (
    get_execution_history,
    get_workflow_list,
    get_workflow_stats,
    trigger_news_digest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/run-news-digest")
async def run_news_digest(
    _user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Trigger the AI News Digest n8n workflow and return the execution result."""
    try:
        return await trigger_news_digest()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="n8n workflow timed out. The workflow may still be running.",
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"n8n responded with HTTP {exc.response.status_code}.",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Unexpected error in run_news_digest endpoint")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger workflow. Please try again.",
        )


@router.get("/history")
async def workflow_history(
    _user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the most recent 50 workflow executions."""
    return {"executions": await get_execution_history()}


@router.get("/stats")
async def workflow_stats(
    _user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return aggregated execution statistics."""
    return await get_workflow_stats()


@router.get("/list")
async def workflow_list(
    _user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the list of registered workflow definitions."""
    return {"workflows": await get_workflow_list()}
