"""High-level semantic search service."""

from pathlib import Path
from typing import List, Optional, Dict, Any

from src.core.models import ChunkedDocument, DocumentChunk
from src.search.embeddings import get_embedding_service, EmbeddingService
from src.search.vector_store import VectorStore, SearchResult


class SearchService:
    """High-level semantic search API."""

    def __init__(self, institution_id: str, persist_dir: Optional[Path] = None):
        """Initialize search service for an institution.

        Args:
            institution_id: Institution ID.
            persist_dir: Optional custom persistence directory.
        """
        self.institution_id = institution_id
        self.embedding_service = get_embedding_service()
        self.vector_store = VectorStore(institution_id, persist_dir)

    def index_document(self, chunked_doc: ChunkedDocument) -> int:
        """Embed and index all chunks from a document.

        Args:
            chunked_doc: Chunked document to index.

        Returns:
            Number of chunks indexed.
        """
        if not chunked_doc.chunks:
            return 0

        # Embed chunks (modifies in place)
        self.embedding_service.embed_chunks(chunked_doc.chunks)

        # Add to vector store
        return self.vector_store.add_chunks(chunked_doc.chunks)

    def search(
        self,
        query: str,
        n_results: int = 10,
        doc_type: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search for relevant chunks.

        Args:
            query: Search query text.
            n_results: Maximum results to return.
            doc_type: Optional document type filter.
            document_id: Optional document ID filter.

        Returns:
            List of SearchResult ordered by relevance.
        """
        # Embed query
        query_embedding = self.embedding_service.embed_text(query)

        # Search
        return self.vector_store.search(
            query_embedding=query_embedding,
            n_results=n_results,
            filter_doc_type=doc_type,
            filter_document_id=document_id,
        )

    def delete_document(self, document_id: str) -> int:
        """Remove a document from the index.

        Args:
            document_id: Document ID to remove.

        Returns:
            Number of chunks removed.
        """
        return self.vector_store.delete_document(document_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return self.vector_store.get_stats()


# Factory for search services (one per institution)
_search_services: Dict[str, SearchService] = {}


def get_search_service(institution_id: str) -> SearchService:
    """Get or create a search service for an institution.

    Args:
        institution_id: Institution ID.

    Returns:
        SearchService instance.
    """
    if institution_id not in _search_services:
        _search_services[institution_id] = SearchService(institution_id)
    return _search_services[institution_id]
