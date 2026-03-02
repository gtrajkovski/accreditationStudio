"""Semantic search module for AccreditAI.

Provides embedding generation and vector search for document chunks.
"""

from src.search.embeddings import EmbeddingService, get_embedding_service
from src.search.vector_store import VectorStore, SearchResult
from src.search.search_service import SearchService, get_search_service

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "VectorStore",
    "SearchResult",
    "SearchService",
    "get_search_service",
]
