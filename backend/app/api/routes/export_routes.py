"""
Export API Endpoints
Handle conversation export requests
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import get_current_user
from app.services.export_service import (
    export_conversation_json,
    export_conversation_markdown,
    export_conversation_csv,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])


@router.get("/conversation/{thread_id}/json")
async def export_as_json(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Export conversation as JSON."""
    try:
        user_id = current_user.get("sub")
        
        export_data = export_conversation_json(user_id, thread_id)
        
        if not export_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        
        return export_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error exporting conversation as JSON")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting conversation",
        )


@router.get("/conversation/{thread_id}/markdown")
async def export_as_markdown(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Export conversation as Markdown file."""
    try:
        user_id = current_user.get("sub")
        
        markdown = export_conversation_markdown(user_id, thread_id)
        
        if not markdown:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        
        return StreamingResponse(
            iter([markdown]),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=conversation-{thread_id}.md"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error exporting conversation as Markdown")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting conversation",
        )


@router.get("/conversation/{thread_id}/csv")
async def export_as_csv(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Export conversation as CSV file."""
    try:
        user_id = current_user.get("sub")
        
        csv_data = export_conversation_csv(user_id, thread_id)
        
        if not csv_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=conversation-{thread_id}.csv"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error exporting conversation as CSV")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting conversation",
        )
