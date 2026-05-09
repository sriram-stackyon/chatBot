"""
Token Tracking API Endpoints
Handle token usage monitoring and analytics
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.token_tracker import (
    get_token_usage_stats,
    get_token_usage_by_operation,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("/usage/stats")
async def get_usage_stats(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
):
    """Get token usage statistics for the user."""
    try:
        user_id = current_user.get("sub")
        
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days must be between 1 and 365",
            )
        
        stats = get_token_usage_stats(user_id, days)
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching token usage stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching token usage stats",
        )


@router.get("/usage/by-operation")
async def get_usage_by_operation(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
):
    """Get token usage breakdown by operation type."""
    try:
        user_id = current_user.get("sub")
        
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days must be between 1 and 365",
            )
        
        usage_by_op = get_token_usage_by_operation(user_id, days)
        
        return {
            "period_days": days,
            "breakdown": usage_by_op,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching token usage by operation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching token usage by operation",
        )
