"""Document chunking for RAG/vector storage.

Splits parsed documents into overlapping chunks that:
- Preserve section boundaries when possible
- Keep tables as complete units
- Track page numbers for citations
- Provide original, redacted, and anonymized text variants
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from src.config import Config
from src.core.models import DocumentChunk, ChunkedDocument, generate_id, now_iso
from src.importers.document_parser import ParsedDocument
from src.importers.pii_detector import PIIDetector, PIIMatch, get_detector


# Constants
CHARS_PER_TOKEN = 4.0  # Approximate characters per token
MIN_CHUNK_SIZE = 100   # Minimum characters for a chunk


@dataclass
class Section:
    """A logical section extracted from a document."""
    text: str
    start_page: int
    end_page: int
    header: str
    section_type: str  # "page", "paragraph", "heading", "table"
    is_table: bool = False


@dataclass
class TextSpan:
    """A text span within a section after splitting."""
    text: str
    start_offset: int
    end_offset: int


class DocumentChunker:
    """Smart document chunker that preserves section boundaries and handles PII."""

    # Table detection patterns
    TABLE_PATTERNS = [
        r'\|[-:]+\|',           # Markdown table separator
        r'^\s*\|.*\|.*\|',      # Markdown table row
        r'^\t.*\t.*\t',         # Tab-separated data
    ]

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        chars_per_token: float = CHARS_PER_TOKEN,
        pii_detector: Optional[PIIDetector] = None,
    ):
        """Initialize chunker with configuration.

        Args:
            chunk_size: Target tokens per chunk (default: Config.CHUNK_SIZE).
            chunk_overlap: Overlap tokens between chunks (default: Config.CHUNK_OVERLAP).
            chars_per_token: Estimated characters per token for conversion.
            pii_detector: Optional PIIDetector instance (default: singleton).
        """
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP
        self.chars_per_token = chars_per_token
        self.pii_detector = pii_detector or get_detector()

        # Convert token targets to character targets
        self.target_chars = int(self.chunk_size * self.chars_per_token)
        self.overlap_chars = int(self.chunk_overlap * self.chars_per_token)

    def chunk_document(
        self,
        parsed: ParsedDocument,
        document_id: str,
    ) -> ChunkedDocument:
        """Chunk a parsed document into overlapping segments.

        Args:
            parsed: ParsedDocument from document_parser.
            document_id: ID to associate chunks with.

        Returns:
            ChunkedDocument with all chunks and metadata.
        """
        if not parsed.text.strip():
            return ChunkedDocument(
                document_id=document_id,
                source_file=parsed.file_path,
                total_chunks=0,
                chunks=[],
                chunking_stats={"empty_document": True},
            )

        # Extract logical sections
        sections = self._extract_sections(parsed)

        # Process sections into chunks
        chunks: List[DocumentChunk] = []
        chunk_index = 0
        previous_overlap = ""

        stats = {
            "total_sections": len(sections),
            "sections_split": 0,
            "tables_preserved": 0,
            "total_chars": len(parsed.text),
            "avg_chunk_chars": 0,
        }

        for section in sections:
            # Check if section is a table (keep whole)
            if section.is_table:
                chunk = self._create_chunk(
                    text=previous_overlap + section.text,
                    chunk_index=chunk_index,
                    document_id=document_id,
                    page_number=section.start_page,
                    section_header=section.header,
                    metadata={
                        "section_type": section.section_type,
                        "is_table": True,
                        "page_range": [section.start_page, section.end_page],
                    },
                )
                chunks.append(chunk)
                chunk_index += 1
                previous_overlap = self._get_overlap(section.text)
                stats["tables_preserved"] += 1
                continue

            # Check if section fits in target size
            section_with_overlap = previous_overlap + section.text
            if len(section_with_overlap) <= self.target_chars:
                chunk = self._create_chunk(
                    text=section_with_overlap,
                    chunk_index=chunk_index,
                    document_id=document_id,
                    page_number=section.start_page,
                    section_header=section.header,
                    metadata={
                        "section_type": section.section_type,
                        "is_table": False,
                        "page_range": [section.start_page, section.end_page],
                    },
                )
                chunks.append(chunk)
                chunk_index += 1
                previous_overlap = self._get_overlap(section.text)
            else:
                # Section too large - split it
                spans = self._split_oversized_section(
                    section.text,
                    self.target_chars,
                    self.overlap_chars,
                )
                stats["sections_split"] += 1

                for i, span in enumerate(spans):
                    # Add overlap from previous only for first span
                    text = (previous_overlap + span.text) if i == 0 else span.text

                    chunk = self._create_chunk(
                        text=text,
                        chunk_index=chunk_index,
                        document_id=document_id,
                        page_number=section.start_page,
                        section_header=section.header,
                        metadata={
                            "section_type": section.section_type,
                            "is_table": False,
                            "page_range": [section.start_page, section.end_page],
                            "split_index": i,
                            "split_total": len(spans),
                        },
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                previous_overlap = self._get_overlap(spans[-1].text if spans else "")

        # Calculate stats
        if chunks:
            stats["avg_chunk_chars"] = sum(len(c.text_original) for c in chunks) // len(chunks)

        return ChunkedDocument(
            document_id=document_id,
            source_file=parsed.file_path,
            total_chunks=len(chunks),
            chunks=chunks,
            chunking_stats=stats,
        )

    def _extract_sections(self, parsed: ParsedDocument) -> List[Section]:
        """Extract logical sections from parsed document.

        Uses parser's sections when available, falls back to text splitting.

        Args:
            parsed: ParsedDocument with text and sections.

        Returns:
            List of Section objects.
        """
        sections: List[Section] = []

        if parsed.sections:
            # Use pre-parsed sections from document parser
            current_header = ""

            for sec_data in parsed.sections:
                text = sec_data.get("text", "")
                if not text.strip():
                    continue

                sec_type = sec_data.get("type", "paragraph")
                page_num = sec_data.get("index", 1)

                # For page-based sections (PDF), index is page number
                if sec_type == "page":
                    page_num = sec_data.get("index", 1)

                # Detect headers (DOCX style or all-caps lines)
                style = sec_data.get("style", "")
                if "heading" in style.lower() or self._is_header(text):
                    current_header = text.strip()[:100]

                # Detect tables
                is_table = self._is_table(text)

                sections.append(Section(
                    text=text,
                    start_page=page_num,
                    end_page=page_num,
                    header=current_header,
                    section_type=sec_type,
                    is_table=is_table,
                ))
        else:
            # Fall back to splitting on double newlines
            paragraphs = parsed.text.split("\n\n")
            current_header = ""

            for i, para in enumerate(paragraphs):
                para = para.strip()
                if not para:
                    continue

                if self._is_header(para):
                    current_header = para[:100]

                sections.append(Section(
                    text=para,
                    start_page=1,
                    end_page=1,
                    header=current_header,
                    section_type="paragraph",
                    is_table=self._is_table(para),
                ))

        return sections

    def _split_oversized_section(
        self,
        text: str,
        target_chars: int,
        overlap_chars: int,
    ) -> List[TextSpan]:
        """Split an oversized section into smaller spans.

        Strategy:
        1. Try paragraph boundaries (double newlines)
        2. Fall back to sentence boundaries
        3. Last resort: word boundaries

        Args:
            text: Text to split.
            target_chars: Target characters per span.
            overlap_chars: Overlap characters between spans.

        Returns:
            List of TextSpan objects.
        """
        if len(text) <= target_chars:
            return [TextSpan(text=text, start_offset=0, end_offset=len(text))]

        spans: List[TextSpan] = []
        current_start = 0

        while current_start < len(text):
            # Determine end position
            remaining = len(text) - current_start
            if remaining <= target_chars:
                # Last chunk - take the rest
                spans.append(TextSpan(
                    text=text[current_start:],
                    start_offset=current_start,
                    end_offset=len(text),
                ))
                break

            # Try to find a good break point
            search_end = min(current_start + target_chars, len(text))
            chunk_text = text[current_start:search_end]

            # Try paragraph break first
            break_pos = self._find_break_point(chunk_text, "\n\n")

            # Try sentence break
            if break_pos < MIN_CHUNK_SIZE:
                break_pos = self._find_break_point(chunk_text, ". ")
                if break_pos < MIN_CHUNK_SIZE:
                    break_pos = self._find_break_point(chunk_text, "? ")
                if break_pos < MIN_CHUNK_SIZE:
                    break_pos = self._find_break_point(chunk_text, "! ")

            # Fall back to word break
            if break_pos < MIN_CHUNK_SIZE:
                break_pos = self._find_break_point(chunk_text, " ")

            # Last resort: hard cut at target
            if break_pos < MIN_CHUNK_SIZE:
                break_pos = target_chars

            actual_end = current_start + break_pos
            spans.append(TextSpan(
                text=text[current_start:actual_end],
                start_offset=current_start,
                end_offset=actual_end,
            ))

            # Move forward with overlap
            current_start = actual_end - overlap_chars
            if current_start < 0:
                current_start = actual_end

        return spans

    def _find_break_point(self, text: str, delimiter: str) -> int:
        """Find the last occurrence of delimiter in text.

        Args:
            text: Text to search.
            delimiter: Delimiter to find.

        Returns:
            Position after the delimiter, or 0 if not found.
        """
        pos = text.rfind(delimiter)
        if pos > 0:
            return pos + len(delimiter)
        return 0

    def _create_chunk(
        self,
        text: str,
        chunk_index: int,
        document_id: str,
        page_number: int,
        section_header: str,
        metadata: Dict[str, Any],
    ) -> DocumentChunk:
        """Create a chunk with all three text variants.

        Args:
            text: Original text for the chunk.
            chunk_index: Position in document.
            document_id: Parent document ID.
            page_number: Primary page number.
            section_header: Nearest section heading.
            metadata: Additional metadata.

        Returns:
            DocumentChunk with original, redacted, and anonymized text.
        """
        # Detect PII once
        pii_matches = self.pii_detector.detect(text)

        # Generate redacted text (type-specific: [REDACTED:SSN])
        text_redacted, _ = self.pii_detector.redact(text, pii_matches)

        # Generate anonymized text (generic: [PII] for embeddings)
        text_anonymized = self._generate_anonymized(text, pii_matches)

        # Add PII info to metadata
        if pii_matches:
            metadata["pii_types"] = list(set(m.pii_type for m in pii_matches))
            metadata["pii_count"] = len(pii_matches)

        return DocumentChunk(
            id=generate_id("chunk"),
            document_id=document_id,
            chunk_index=chunk_index,
            page_number=page_number,
            section_header=section_header,
            text_original=text,
            text_redacted=text_redacted,
            text_anonymized=text_anonymized,
            embedding=[],  # Populated later by embedding pipeline
            metadata=metadata,
            created_at=now_iso(),
        )

    def _generate_anonymized(self, text: str, pii_matches: List[PIIMatch]) -> str:
        """Generate anonymized version for embeddings.

        Unlike redaction which preserves type ([REDACTED:SSN]),
        anonymization uses generic [PII] token to avoid leaking type patterns.

        Args:
            text: Original text.
            pii_matches: Detected PII matches.

        Returns:
            Anonymized text.
        """
        if not pii_matches:
            return text

        result = text
        for match in reversed(pii_matches):
            result = result[:match.start] + "[PII]" + result[match.end:]

        return result

    def _get_overlap(self, text: str) -> str:
        """Get the overlap portion from end of text.

        Args:
            text: Text to get overlap from.

        Returns:
            Last overlap_chars characters, trimmed to word boundary.
        """
        if len(text) <= self.overlap_chars:
            return text

        overlap = text[-self.overlap_chars:]

        # Try to start at a word boundary
        space_pos = overlap.find(" ")
        if space_pos > 0 and space_pos < len(overlap) // 2:
            overlap = overlap[space_pos + 1:]

        return overlap

    def _is_header(self, text: str) -> bool:
        """Check if text looks like a section header.

        Args:
            text: Text to check.

        Returns:
            True if text appears to be a header.
        """
        text = text.strip()

        # Short lines that are all caps
        if len(text) < 100 and text.isupper():
            return True

        # Numbered sections (e.g., "1.2 Title" or "Section 3:")
        if re.match(r'^(\d+\.)+\s*\w', text):
            return True
        if re.match(r'^(Section|Chapter|Part)\s+\d+', text, re.IGNORECASE):
            return True

        return False

    def _is_table(self, text: str) -> bool:
        """Check if text contains a table.

        Args:
            text: Text to check.

        Returns:
            True if text appears to contain a table.
        """
        for pattern in self.TABLE_PATTERNS:
            if re.search(pattern, text, re.MULTILINE):
                return True

        # Check for consistent tab structure
        lines = text.split("\n")
        if len(lines) >= 3:
            tab_counts = [line.count("\t") for line in lines if line.strip()]
            if tab_counts and min(tab_counts) >= 2 and max(tab_counts) - min(tab_counts) <= 1:
                return True

        return False


# Module-level chunker instance
_chunker: Optional[DocumentChunker] = None


def get_chunker() -> DocumentChunker:
    """Get or create the document chunker singleton."""
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker


def chunk_document(parsed: ParsedDocument, document_id: str) -> ChunkedDocument:
    """Convenience function to chunk a document.

    Args:
        parsed: ParsedDocument from document_parser.
        document_id: ID to associate chunks with.

    Returns:
        ChunkedDocument with all chunks.
    """
    return get_chunker().chunk_document(parsed, document_id)
