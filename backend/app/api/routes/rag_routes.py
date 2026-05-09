"""
RAG API Endpoints
Handle PDF analysis and document management
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File

from app.api.deps import get_current_user
from app.ai.rag.document_analyzer import summarize_pdf_document, extract_key_topics
from app.core.config import settings
from pathlib import Path
import aiofiles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/summarize/{attachment_id}")
async def summarize_document(
    attachment_id: str,
    max_length: int = 500,
    style: str = "bullet_points",
    current_user: dict = Depends(get_current_user),
):
    """Summarize an uploaded PDF document."""
    try:
        user_id = current_user.get("sub")
        
        if not settings.RAG_ENABLE_SUMMARIZATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document summarization is not enabled",
            )
        
        # Find attachment file path
        from app.db.postgres import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                select a.storage_path, a.filename
                from public.chat_attachments a
                join public.chat_messages m on m.id = a.message_id
                join public.chat_threads t on t.id = m.thread_id
                where a.id = %s and t.user_id = %s
            """, (attachment_id, user_id))
            
            row = cursor.fetchone()
            if not row or not row.get("storage_path"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Attachment not found",
                )
        
        pdf_path = row["storage_path"]
        
        # Check if file exists
        if not Path(pdf_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF file not found on server",
            )
        
        # Summarize
        summary = await summarize_pdf_document(pdf_path, max_length, style)
        
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to summarize document",
            )
        
        return {
            "attachment_id": attachment_id,
            "filename": row["filename"],
            "summary": summary,
            "style": style,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error summarizing document")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error summarizing document",
        )


@router.post("/extract-topics/{attachment_id}")
async def extract_topics(
    attachment_id: str,
    num_topics: int = 5,
    current_user: dict = Depends(get_current_user),
):
    """Extract key topics from a PDF document."""
    try:
        user_id = current_user.get("sub")
        
        # Find attachment file path
        from app.db.postgres import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                select a.storage_path, a.filename
                from public.chat_attachments a
                join public.chat_messages m on m.id = a.message_id
                join public.chat_threads t on t.id = m.thread_id
                where a.id = %s and t.user_id = %s
            """, (attachment_id, user_id))
            
            row = cursor.fetchone()
            if not row or not row.get("storage_path"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Attachment not found",
                )
        
        pdf_path = row["storage_path"]
        
        # Check if file exists
        if not Path(pdf_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF file not found on server",
            )
        
        # Extract topics
        topics = await extract_key_topics(pdf_path, num_topics)
        
        if not topics:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract topics",
            )
        
        return {
            "attachment_id": attachment_id,
            "filename": row["filename"],
            "topics": topics,
            "count": len(topics),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error extracting topics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error extracting topics",
        )
