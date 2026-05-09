"""
Document Summarization and Analysis
Generates summaries of uploaded PDFs using LLM
"""

import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from app.ai.llm import get_chat_llm
from app.ai.rag.pdf_processor import extract_pdf_text
from app.core.config import settings
from pathlib import Path

logger = logging.getLogger(__name__)


async def summarize_pdf_document(
    pdf_path: str,
    max_length: int = 500,
    style: str = "bullet_points",
) -> Optional[str]:
    """
    Generate a summary of a PDF document.
    
    Args:
        pdf_path: Path to PDF file
        max_length: Maximum length of summary
        style: Summary style - 'bullet_points', 'paragraph', or 'abstract'
        
    Returns:
        Summary text or None if failed
    """
    try:
        # Extract PDF text
        text, page_count = extract_pdf_text(pdf_path)
        
        if not text or len(text) < 100:
            logger.warning("PDF too short to summarize: %s", pdf_path)
            return None
        
        # Truncate to reasonable size for LLM
        text_to_summarize = text[:5000]
        
        # Create summary prompt
        style_instructions = {
            "bullet_points": "Provide a bulleted summary with key points.",
            "paragraph": "Provide a concise paragraph summary.",
            "abstract": "Provide an academic-style abstract."
        }
        
        prompt = (
            f"Summarize the following document in {style_instructions.get(style, 'bullet_points')} "
            f"Keep it under {max_length} words.\n\nDocument:\n{text_to_summarize}"
        )
        
        # Get LLM summary
        llm = get_chat_llm()
        response = await llm.ainvoke([
            SystemMessage(content="You are a document summarization expert."),
            HumanMessage(content=prompt)
        ])
        
        summary = response.content if isinstance(response.content, str) else ""
        
        logger.info("Successfully summarized PDF: %s", Path(pdf_path).name)
        return summary if summary else None
    except Exception as e:
        logger.exception("Error summarizing PDF: %s", pdf_path)
        return None


async def extract_key_topics(
    pdf_path: str,
    num_topics: int = 5,
) -> Optional[list[str]]:
    """
    Extract key topics from a PDF document.
    
    Args:
        pdf_path: Path to PDF file
        num_topics: Number of topics to extract
        
    Returns:
        List of key topics or None if failed
    """
    try:
        # Extract PDF text
        text, _ = extract_pdf_text(pdf_path)
        
        if not text:
            return None
        
        # Create topic extraction prompt
        prompt = (
            f"Extract the {num_topics} most important topics/themes from this document. "
            f"Return only the topics as a comma-separated list.\n\nDocument:\n{text[:3000]}"
        )
        
        # Get LLM response
        llm = get_chat_llm()
        response = await llm.ainvoke([
            SystemMessage(content="You are a document analysis expert."),
            HumanMessage(content=prompt)
        ])
        
        topics_text = response.content if isinstance(response.content, str) else ""
        topics = [t.strip() for t in topics_text.split(",") if t.strip()]
        
        logger.info("Extracted %d topics from PDF: %s", len(topics), Path(pdf_path).name)
        return topics if topics else None
    except Exception as e:
        logger.exception("Error extracting topics from PDF: %s", pdf_path)
        return None
