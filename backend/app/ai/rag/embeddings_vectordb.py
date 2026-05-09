"""
Embeddings and Vector Database Management
Handles OpenAI embeddings and ChromaDB integration for RAG
"""

import logging
from functools import lru_cache
from typing import Optional

import chromadb
from chromadb.config import Settings
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings_client() -> OpenAI:
    """Get cached OpenAI embeddings client."""
    return OpenAI(
        base_url=settings.LLM_API_BASE,
        api_key=settings.LLM_API_KEY,
    )


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.Client:
    """Get persistent ChromaDB client."""
    from pathlib import Path
    chroma_dir = Path(settings.CHROMA_PERSIST_DIR)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(path=str(chroma_dir))
    logger.info("ChromaDB client initialized at: %s", chroma_dir)
    return client


def generate_embeddings(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """
    Generate embeddings for texts using OpenAI API.
    
    Args:
        texts: List of texts to embed
        batch_size: Batch size for API calls
        
    Returns:
        List of embedding vectors
    """
    try:
        client = get_embeddings_client()
        embeddings = []
        
        # Process in batches to avoid token limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=batch,
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
            logger.debug(f"Generated embeddings for batch {i // batch_size + 1}")
        
        logger.info("Successfully generated %d embeddings", len(embeddings))
        return embeddings
    except Exception as e:
        logger.exception("Error generating embeddings")
        raise


def get_or_create_collection(user_id: str, thread_id: str) -> chromadb.Collection:
    """
    Get or create a ChromaDB collection for a user/thread.
    
    Args:
        user_id: User identifier
        thread_id: Thread identifier
        
    Returns:
        ChromaDB collection
    """
    try:
        client = get_chroma_client()
        collection_name = f"pdf_rag_{user_id}_{thread_id}".replace("-", "_").lower()[:60]
        
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={
                "user_id": user_id,
                "thread_id": thread_id,
                "hnsw:space": "cosine",
            },
        )
        logger.info(
            "Collection '%s' ready for user=%s thread=%s",
            collection_name,
            user_id,
            thread_id,
        )
        return collection
    except Exception as e:
        logger.exception("Error creating ChromaDB collection")
        raise


def index_pdf_chunks(
    user_id: str,
    thread_id: str,
    attachment_id: str,
    filename: str,
    chunks: list[dict],
) -> int:
    """
    Index PDF chunks in ChromaDB with embeddings.
    
    Args:
        user_id: User ID
        thread_id: Thread ID
        attachment_id: Attachment ID
        filename: Original filename
        chunks: List of chunks with content and metadata
        
    Returns:
        Number of chunks indexed
    """
    try:
        if not chunks:
            logger.warning("No chunks to index for attachment: %s", attachment_id)
            return 0
        
        # Generate embeddings for all chunks
        chunk_texts = [c["content"] for c in chunks]
        embeddings = generate_embeddings(chunk_texts)
        
        # Prepare data for ChromaDB
        ids = [f"{attachment_id}:chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "attachment_id": attachment_id,
                "filename": filename,
                "chunk_index": str(c["chunk_index"]),
                "page": str(c.get("page") or 0),
            }
            for c in chunks
        ]
        
        # Index in ChromaDB
        collection = get_or_create_collection(user_id, thread_id)
        collection.upsert(
            ids=ids,
            documents=chunk_texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        
        logger.info(
            "Indexed %d chunks for attachment_id=%s in thread=%s",
            len(chunks),
            attachment_id,
            thread_id,
        )
        return len(chunks)
    except Exception as e:
        logger.exception("Error indexing PDF chunks")
        raise


def search_similar_chunks(
    user_id: str,
    thread_id: str,
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.3,
) -> list[dict]:
    """
    Search for similar chunks using semantic similarity.
    
    Args:
        user_id: User ID
        thread_id: Thread ID
        query: Search query
        top_k: Number of results to return
        score_threshold: Minimum similarity score (0-1)
        
    Returns:
        List of similar chunks with metadata and scores
    """
    try:
        collection = get_or_create_collection(user_id, thread_id)
        
        if collection.count() == 0:
            logger.debug("No chunks in collection for thread=%s", thread_id)
            return []
        
        # Generate query embedding
        query_embeddings = generate_embeddings([query])
        query_embedding = query_embeddings[0]
        
        # Search in ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        
        # Format results with distance scores
        similar_chunks = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        for doc, metadata, distance in zip(documents, metadatas, distances):
            # Convert distance to similarity score (lower distance = higher similarity)
            similarity_score = 1 - (distance / 2)  # Normalize for cosine distance
            
            if similarity_score >= score_threshold:
                similar_chunks.append({
                    "content": doc,
                    "filename": metadata.get("filename", "unknown"),
                    "page": int(metadata.get("page", 0)),
                    "chunk_index": int(metadata.get("chunk_index", 0)),
                    "attachment_id": metadata.get("attachment_id"),
                    "similarity_score": round(similarity_score, 4),
                })
        
        logger.debug(
            "Found %d similar chunks for query in thread=%s",
            len(similar_chunks),
            thread_id,
        )
        return similar_chunks
    except Exception as e:
        logger.exception("Error searching similar chunks")
        return []


def delete_collection_chunks(user_id: str, thread_id: str, attachment_id: str) -> int:
    """
    Delete chunks associated with an attachment.
    
    Args:
        user_id: User ID
        thread_id: Thread ID
        attachment_id: Attachment ID
        
    Returns:
        Number of chunks deleted
    """
    try:
        collection = get_or_create_collection(user_id, thread_id)
        
        # Find and delete chunks for this attachment
        items = collection.get(
            where={"attachment_id": {"$eq": attachment_id}}
        )
        
        deleted_count = len(items.get("ids", []))
        if deleted_count > 0:
            collection.delete(
                ids=items["ids"]
            )
            logger.info(
                "Deleted %d chunks for attachment_id=%s",
                deleted_count,
                attachment_id,
            )
        
        return deleted_count
    except Exception as e:
        logger.exception("Error deleting chunks")
        return 0
