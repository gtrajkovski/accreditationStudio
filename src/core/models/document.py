"""Document domain models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso
from src.core.models.enums import DocumentType, Language


@dataclass
class Document:
    """A document in the workspace."""
    id: str = field(default_factory=lambda: generate_id("doc"))
    institution_id: str = ""
    program_id: Optional[str] = None
    doc_type: DocumentType = DocumentType.OTHER
    language: Language = Language.EN
    original_filename: str = ""
    file_path: str = ""
    extracted_text: str = ""
    extracted_structure: Dict[str, Any] = field(default_factory=dict)
    page_count: int = 0
    version: int = 1
    status: str = "uploaded"
    last_reviewed_date: Optional[str] = None
    review_cycle_months: int = 12
    uploaded_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "program_id": self.program_id,
            "doc_type": self.doc_type.value,
            "language": self.language.value,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "extracted_text": self.extracted_text,
            "extracted_structure": self.extracted_structure,
            "page_count": self.page_count,
            "version": self.version,
            "status": self.status,
            "last_reviewed_date": self.last_reviewed_date,
            "review_cycle_months": self.review_cycle_months,
            "uploaded_at": self.uploaded_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", generate_id("doc")),
            institution_id=data.get("institution_id", ""),
            program_id=data.get("program_id"),
            doc_type=DocumentType(data.get("doc_type", "other")),
            language=Language(data.get("language", "en")),
            original_filename=data.get("original_filename", ""),
            file_path=data.get("file_path", ""),
            extracted_text=data.get("extracted_text", ""),
            extracted_structure=data.get("extracted_structure", {}),
            page_count=data.get("page_count", 0),
            version=data.get("version", 1),
            status=data.get("status", "uploaded"),
            last_reviewed_date=data.get("last_reviewed_date"),
            review_cycle_months=data.get("review_cycle_months", 12),
            uploaded_at=data.get("uploaded_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class DocumentChunk:
    """A single chunk from a parsed document for RAG/vector storage."""
    id: str = field(default_factory=lambda: generate_id("chunk"))
    document_id: str = ""
    chunk_index: int = 0
    page_number: int = 1
    section_header: str = ""
    text_original: str = ""
    text_redacted: str = ""
    text_anonymized: str = ""
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section_header": self.section_header,
            "text_original": self.text_original,
            "text_redacted": self.text_redacted,
            "text_anonymized": self.text_anonymized,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        return cls(
            id=data.get("id", generate_id("chunk")),
            document_id=data.get("document_id", ""),
            chunk_index=data.get("chunk_index", 0),
            page_number=data.get("page_number", 1),
            section_header=data.get("section_header", ""),
            text_original=data.get("text_original", ""),
            text_redacted=data.get("text_redacted", ""),
            text_anonymized=data.get("text_anonymized", ""),
            embedding=data.get("embedding", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", now_iso()),
        )


@dataclass
class ChunkedDocument:
    """Result of chunking a parsed document."""
    document_id: str = ""
    source_file: str = ""
    total_chunks: int = 0
    chunks: List[DocumentChunk] = field(default_factory=list)
    chunking_stats: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_file": self.source_file,
            "total_chunks": self.total_chunks,
            "chunks": [c.to_dict() for c in self.chunks],
            "chunking_stats": self.chunking_stats,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkedDocument":
        return cls(
            document_id=data.get("document_id", ""),
            source_file=data.get("source_file", ""),
            total_chunks=data.get("total_chunks", 0),
            chunks=[DocumentChunk.from_dict(c) for c in data.get("chunks", [])],
            chunking_stats=data.get("chunking_stats", {}),
            created_at=data.get("created_at", now_iso()),
        )
