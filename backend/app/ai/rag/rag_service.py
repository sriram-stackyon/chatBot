"""
RAG (Retrieval-Augmented Generation) Service
Orchestrates PDF indexing and semantic search for chat augmentation
"""

import logging
from pathlib import Path
from typing import Optional

from app.ai.rag.embeddings_vectordb import (
    delete_collection_chunks,
    index_pdf_chunks,
    search_similar_chunks,
)
from app.ai.rag.pdf_processor import chunk_text, extract_pdf_text, validate_pdf_file
from app.core.config import settings
from app.db.postgres import get_db_cursor

logger = logging.getLogger(__name__)


def process_and_index_pdf(
    user_id: str,
    thread_id: str,
    attachment_id: str,
    original_filename: str,
    storage_path: str,
) -> dict:
    """
    Complete PDF processing pipeline:
    1. Extract text from PDF
    2. Split into chunks
    3. Generate embeddings
    4. Store in ChromaDB
    
    Args:
        user_id: User ID
        thread_id: Thread ID
        attachment_id: Attachment ID
        original_filename: Original PDF filename
        storage_path: Relative path to stored PDF
        
    Returns:
        Processing result dictionary
    """
    try:
        # Get absolute path to PDF
        pdf_path = Path(settings.UPLOAD_DIR) / storage_path
        
        if not pdf_path.exists():
            logger.warning("PDF file not found: %s", pdf_path)
            return {
                "success": False,
                "error": "PDF file not found on disk",
                "chunks_indexed": 0,
            }
        
        # Validate PDF
        if not validate_pdf_file(pdf_path):
            logger.warning("Invalid PDF file: %s", pdf_path)
            return {
                "success": False,
                "error": "Invalid or corrupted PDF file",
                "chunks_indexed": 0,
            }
        
        # Extract text from PDF
        text, page_count = extract_pdf_text(pdf_path)
        
        if not text.strip():
            logger.warning("No text extracted from PDF: %s", original_filename)
            return {
                "success": False,
                "error": "No text content found in PDF",
                "chunks_indexed": 0,
                "page_count": page_count,
            }
        
        # Chunk text
        chunks = chunk_text(
            text,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )
        
        # Index chunks in ChromaDB
        chunks_indexed = index_pdf_chunks(
            user_id=user_id,
            thread_id=thread_id,
            attachment_id=attachment_id,
            filename=original_filename,
            chunks=chunks,
        )
        
        # Store PDF indexing metadata in database
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                update public.chat_attachments
                set indexed_at = now(), chunks_indexed = %s
                where id = %s
                """,
                (chunks_indexed, attachment_id),
            )
        
        logger.info(
            "Successfully processed PDF: %s (%d pages, %d chunks indexed)",
            original_filename,
            page_count,
            chunks_indexed,
        )
        
        return {
            "success": True,
            "page_count": page_count,
            "chunks_indexed": chunks_indexed,
            "total_text_length": len(text),
        }
    except Exception as e:
        logger.exception(
            "Error processing PDF: %s for attachment_id=%s",
            original_filename,
            attachment_id,
        )
        return {
            "success": False,
            "error": f"Failed to process PDF: {str(e)}",
            "chunks_indexed": 0,
        }


def retrieve_pdf_context(
    user_id: str,
    thread_id: str,
    query: str,
    top_k: Optional[int] = None,
) -> str:
    """
    Retrieve relevant PDF chunks based on semantic similarity.
    
    Args:
        user_id: User ID
        thread_id: Thread ID
        query: User question/query
        top_k: Number of results (uses config if None)
        
    Returns:
        Formatted context string with source citations
    """
    try:
        if not query or not query.strip():
            return ""
        
        if top_k is None:
            top_k = settings.RAG_TOP_K
        
        # Search for similar chunks
        similar_chunks = search_similar_chunks(
            user_id=user_id,
            thread_id=thread_id,
            query=query,
            top_k=top_k,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
        )
        
        if not similar_chunks:
            return ""
        
        # Format retrieved chunks with source citations
        context_parts = ["**Retrieved PDF Context:**\n"]
        
        for idx, chunk in enumerate(similar_chunks, 1):
            page_ref = f"(Page {chunk['page']})" if chunk["page"] else ""
            filename = chunk["filename"]
            score = chunk["similarity_score"]
            content = chunk["content"][:500]  # Truncate long content
            
            context_parts.append(
                f"\n**Source {idx}: {filename} {page_ref}** [Score: {score}]\n"
                f"{content}..."
            )
        
        context = "\n---\n".join(context_parts)
        logger.debug(
            "Retrieved %d relevant chunks for thread=%s",
            len(similar_chunks),
            thread_id,
        )
        return context
    except Exception as e:
        logger.exception(
            "Error retrieving PDF context for thread=%s",
            thread_id,
        )
        return ""


def cleanup_attachment_vectors(
    user_id: str,
    thread_id: str,
    attachment_id: str,
) -> bool:
    """
    Delete vectors associated with a deleted attachment.
    
    Args:
        user_id: User ID
        thread_id: Thread ID
        attachment_id: Attachment ID to delete
        
    Returns:
        Success flag
    """
    try:
        deleted_count = delete_collection_chunks(
            user_id=user_id,
            thread_id=thread_id,
            attachment_id=attachment_id,
        )
        logger.info(
            "Cleaned up %d vectors for attachment_id=%s",
            deleted_count,
            attachment_id,
        )
        return True
    except Exception as e:
        logger.exception(
            "Error cleaning up vectors for attachment_id=%s",
            attachment_id,
        )
        return False
