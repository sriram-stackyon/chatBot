"""
PDF Processing and Text Extraction Module
Handles PDF loading, text extraction, and chunking for RAG
"""

import logging
from pathlib import Path
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Configuration
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
SEPARATOR = "\n\n"


def extract_pdf_text(pdf_path: str | Path) -> tuple[str, int]:
    """
    Extract text from PDF file with page tracking.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Tuple of (extracted_text, page_count)
    """
    try:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        
        text_parts = []
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                # Add page marker for source tracking
                text_parts.append(f"[Page {page_num}]\n{page_text}")
        
        full_text = "\n\n".join(text_parts)
        logger.info(
            "Successfully extracted %d pages from PDF: %s",
            page_count,
            pdf_path.name
        )
        return full_text, page_count
    except Exception as e:
        logger.exception("Error extracting text from PDF: %s", pdf_path)
        raise


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split text into semantically meaningful chunks using LangChain.
    
    Args:
        text: Full text to chunk
        chunk_size: Size of each chunk in characters
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of chunk dictionaries with content and metadata
    """
    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        
        chunks = splitter.split_text(text)
        
        # Extract page numbers from chunk text for source tracking
        chunk_dicts = []
        for idx, chunk in enumerate(chunks):
            page_match = None
            # Look for page marker in chunk
            if "[Page " in chunk:
                import re
                match = re.search(r"\[Page (\d+)\]", chunk)
                if match:
                    page_match = int(match.group(1))
            
            chunk_dicts.append({
                "content": chunk,
                "chunk_index": idx,
                "page": page_match,
            })
        
        logger.info(
            "Split text into %d chunks (size=%d, overlap=%d)",
            len(chunks),
            chunk_size,
            chunk_overlap,
        )
        return chunk_dicts
    except Exception as e:
        logger.exception("Error chunking text")
        raise


def validate_pdf_file(file_path: str | Path) -> bool:
    """Validate if file is a valid PDF."""
    try:
        file_path = Path(file_path)
        if not file_path.suffix.lower() == ".pdf":
            return False
        
        reader = PdfReader(str(file_path))
        return len(reader.pages) > 0
    except Exception:
        return False
