"""ChromaDB-backed vector storage for document chunks."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings

from src.config import Config
from src.core.models import DocumentChunk


@dataclass
class SearchResult:
    """A search result with chunk and relevance score."""
    chunk: DocumentChunk
    score: float  # Similarity score (0-1, higher is better)
    distance: float  # Raw distance from ChromaDB


class VectorStore:
    """ChromaDB-backed vector storage for document chunks."""

    def __init__(self, institution_id: str, persist_dir: Optional[Path] = None):
        """Initialize vector store for an institution.

        Args:
            institution_id: Institution ID for collection isolation.
            persist_dir: Directory for ChromaDB persistence.
        """
        self.institution_id = institution_id

        if persist_dir is None:
            persist_dir = Config.WORKSPACE_DIR / institution_id / "vectors"

        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.client.get_or_create_collection(
            name=f"chunks_{institution_id}",
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Add embedded chunks to the store.

        Args:
            chunks: Chunks with embeddings populated.

        Returns:
            Number of chunks added.
        """
        if not chunks:
            return 0

        # Filter chunks that have embeddings
        valid_chunks = [c for c in chunks if c.embedding]
        if not valid_chunks:
            return 0

        ids = [c.id for c in valid_chunks]
        embeddings = [c.embedding for c in valid_chunks]
        documents = [c.text_anonymized or c.text_original for c in valid_chunks]
        metadatas = [
            {
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "section_header": c.section_header or "",
                "doc_type": c.metadata.get("doc_type", ""),
            }
            for c in valid_chunks
        ]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        return len(valid_chunks)

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        filter_doc_type: Optional[str] = None,
        filter_document_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search for similar chunks.

        Args:
            query_embedding: Query embedding vector.
            n_results: Maximum results to return.
            filter_doc_type: Optional document type filter.
            filter_document_id: Optional document ID filter.

        Returns:
            List of SearchResult ordered by relevance.
        """
        where = {}
        if filter_doc_type:
            where["doc_type"] = filter_doc_type
        if filter_document_id:
            where["document_id"] = filter_document_id

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                # Convert cosine distance to similarity score
                score = 1 - distance

                chunk = DocumentChunk(
                    id=chunk_id,
                    document_id=results["metadatas"][0][i].get("document_id", ""),
                    chunk_index=results["metadatas"][0][i].get("chunk_index", 0),
                    page_number=results["metadatas"][0][i].get("page_number", 1),
                    section_header=results["metadatas"][0][i].get("section_header", ""),
                    text_anonymized=results["documents"][0][i] if results["documents"] else "",
                )

                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score,
                    distance=distance,
                ))

        return search_results

    def delete_document(self, document_id: str) -> int:
        """Remove all chunks for a document.

        Args:
            document_id: Document ID to remove.

        Returns:
            Number of chunks deleted.
        """
        # Get IDs of chunks to delete
        results = self.collection.get(
            where={"document_id": document_id},
            include=[],
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])

        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Return collection statistics."""
        return {
            "institution_id": self.institution_id,
            "total_chunks": self.collection.count(),
            "collection_name": self.collection.name,
        }
