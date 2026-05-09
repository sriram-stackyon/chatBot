# RAG (Retrieval-Augmented Generation) Module
# Handles PDF processing, embeddings, and semantic search for chat augmentation

from app.ai.rag.embeddings_vectordb import (
    delete_collection_chunks,
    generate_embeddings,
    get_chroma_client,
    get_or_create_collection,
    index_pdf_chunks,
    search_similar_chunks,
)
from app.ai.rag.pdf_processor import (
    chunk_text,
    extract_pdf_text,
    validate_pdf_file,
)
from app.ai.rag.rag_service import (
    cleanup_attachment_vectors,
    process_and_index_pdf,
    retrieve_pdf_context,
)

__all__ = [
    # PDF Processing
    "extract_pdf_text",
    "chunk_text",
    "validate_pdf_file",
    # Embeddings & Vector DB
    "generate_embeddings",
    "get_chroma_client",
    "get_or_create_collection",
    "index_pdf_chunks",
    "search_similar_chunks",
    "delete_collection_chunks",
    # RAG Service
    "process_and_index_pdf",
    "retrieve_pdf_context",
    "cleanup_attachment_vectors",
]

