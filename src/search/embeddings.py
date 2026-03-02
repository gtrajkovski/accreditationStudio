"""Embedding service using sentence-transformers."""

from typing import List, Optional
from src.config import Config
from src.core.models import DocumentChunk

# Lazy import to avoid loading model on module import
_model = None


def _get_model():
    """Lazy load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(Config.EMBEDDING_MODEL)
    return _model


class EmbeddingService:
    """Generate embeddings using sentence-transformers."""

    def __init__(self, model_name: Optional[str] = None):
        """Initialize embedding service.

        Args:
            model_name: Optional model name override.
        """
        self.model_name = model_name or Config.EMBEDDING_MODEL

    def _get_model(self):
        """Get the model, using global cache."""
        return _get_model()

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        model = self._get_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in batch.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]

    def embed_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Embed chunks using text_anonymized, populate embedding field.

        Args:
            chunks: Chunks to embed (modified in place).

        Returns:
            Same chunks with embedding field populated.
        """
        if not chunks:
            return chunks

        # Use anonymized text for embeddings (PII-safe)
        texts = [c.text_anonymized or c.text_original for c in chunks]
        embeddings = self.embed_texts(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        return chunks


# Module singleton
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
