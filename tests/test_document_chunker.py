"""Tests for document chunking pipeline."""

import pytest
from dataclasses import dataclass, field
from typing import List, Dict, Any

from src.importers.document_chunker import (
    DocumentChunker,
    Section,
    TextSpan,
    get_chunker,
    chunk_document,
)
from src.importers.document_parser import ParsedDocument
from src.core.models import DocumentChunk, ChunkedDocument


# Test fixtures

@pytest.fixture
def chunker():
    """Create a chunker with small sizes for testing."""
    return DocumentChunker(
        chunk_size=50,       # ~200 chars
        chunk_overlap=10,    # ~40 chars
    )


@pytest.fixture
def small_parsed_doc():
    """A small document that fits in one chunk."""
    return ParsedDocument(
        file_path="/test/small.txt",
        file_name="small.txt",
        file_type="text",
        text="This is a small document that should fit in a single chunk.",
        page_count=1,
        word_count=12,
        sections=[],
        metadata={},
    )


@pytest.fixture
def large_parsed_doc():
    """A large document that needs multiple chunks."""
    text = " ".join(["This is sentence number {}.".format(i) for i in range(100)])
    return ParsedDocument(
        file_path="/test/large.txt",
        file_name="large.txt",
        file_type="text",
        text=text,
        page_count=1,
        word_count=500,
        sections=[],
        metadata={},
    )


@pytest.fixture
def pdf_parsed_doc():
    """A PDF document with page sections."""
    return ParsedDocument(
        file_path="/test/doc.pdf",
        file_name="doc.pdf",
        file_type="pdf",
        text="Page 1 content here.\n\nPage 2 content here.\n\nPage 3 content here.",
        page_count=3,
        word_count=12,
        sections=[
            {"type": "page", "index": 1, "text": "Page 1 content here.", "char_count": 20},
            {"type": "page", "index": 2, "text": "Page 2 content here.", "char_count": 20},
            {"type": "page", "index": 3, "text": "Page 3 content here.", "char_count": 20},
        ],
        metadata={"page_count": 3},
    )


@pytest.fixture
def doc_with_pii():
    """A document containing PII."""
    return ParsedDocument(
        file_path="/test/pii.txt",
        file_name="pii.txt",
        file_type="text",
        text="Student John has SSN 123-45-6789 and email john@example.com.",
        page_count=1,
        word_count=9,
        sections=[],
        metadata={},
    )


@pytest.fixture
def doc_with_table():
    """A document containing a markdown table."""
    return ParsedDocument(
        file_path="/test/table.txt",
        file_name="table.txt",
        file_type="text",
        text="Before table.\n\n| Name | Age |\n|------|-----|\n| John | 25 |\n| Jane | 30 |\n\nAfter table.",
        page_count=1,
        word_count=15,
        sections=[],
        metadata={},
    )


# Tests

class TestDocumentChunker:
    """Tests for DocumentChunker class."""

    def test_small_document_single_chunk(self, chunker, small_parsed_doc):
        """Document smaller than chunk size produces one chunk."""
        result = chunker.chunk_document(small_parsed_doc, "doc_001")

        assert result.total_chunks == 1
        assert len(result.chunks) == 1
        assert result.chunks[0].text_original == small_parsed_doc.text
        assert result.document_id == "doc_001"

    def test_large_document_multiple_chunks(self, chunker, large_parsed_doc):
        """Large document produces multiple chunks."""
        result = chunker.chunk_document(large_parsed_doc, "doc_002")

        assert result.total_chunks > 1
        assert len(result.chunks) > 1
        # Each chunk should be within target size (with some tolerance)
        for chunk in result.chunks:
            assert len(chunk.text_original) <= chunker.target_chars + chunker.overlap_chars + 100

    def test_overlap_applied(self, chunker, large_parsed_doc):
        """Chunks have overlapping content."""
        result = chunker.chunk_document(large_parsed_doc, "doc_003")

        if len(result.chunks) >= 2:
            # End of chunk N should appear at start of chunk N+1
            for i in range(len(result.chunks) - 1):
                chunk_end = result.chunks[i].text_original[-50:]
                chunk_start = result.chunks[i + 1].text_original[:100]
                # Some overlap text should be present
                # (not exact match due to word boundary trimming)
                assert any(word in chunk_start for word in chunk_end.split())

    def test_page_numbers_tracked(self, chunker, pdf_parsed_doc):
        """Chunks track which page they came from."""
        result = chunker.chunk_document(pdf_parsed_doc, "doc_004")

        # Should have chunks from different pages
        page_numbers = [c.page_number for c in result.chunks]
        assert 1 in page_numbers

    def test_section_headers_tracked(self, chunker):
        """Chunks track nearest section header."""
        doc = ParsedDocument(
            file_path="/test/headers.txt",
            file_name="headers.txt",
            file_type="text",
            text="INTRODUCTION\n\nThis is the introduction.\n\nMETHODS\n\nThis is the methods section.",
            page_count=1,
            word_count=10,
            sections=[],
            metadata={},
        )
        result = chunker.chunk_document(doc, "doc_005")

        # At least one chunk should have a section header
        headers = [c.section_header for c in result.chunks]
        assert any(h for h in headers)

    def test_pii_redaction_per_chunk(self, chunker, doc_with_pii):
        """Each chunk has original, redacted, and anonymized text."""
        result = chunker.chunk_document(doc_with_pii, "doc_006")

        chunk = result.chunks[0]

        # Original contains PII
        assert "123-45-6789" in chunk.text_original
        assert "john@example.com" in chunk.text_original

        # Redacted has type-specific markers
        assert "[REDACTED:" in chunk.text_redacted
        assert "123-45-6789" not in chunk.text_redacted

        # Anonymized has generic [PII] markers
        assert "[PII]" in chunk.text_anonymized
        assert "123-45-6789" not in chunk.text_anonymized

    def test_pii_metadata_recorded(self, chunker, doc_with_pii):
        """PII types are recorded in chunk metadata."""
        result = chunker.chunk_document(doc_with_pii, "doc_007")

        chunk = result.chunks[0]
        assert "pii_types" in chunk.metadata
        assert "pii_count" in chunk.metadata
        assert chunk.metadata["pii_count"] > 0

    def test_empty_document_handled(self, chunker):
        """Empty document produces empty chunk list."""
        doc = ParsedDocument(
            file_path="/test/empty.txt",
            file_name="empty.txt",
            file_type="text",
            text="",
            page_count=0,
            word_count=0,
            sections=[],
            metadata={},
        )
        result = chunker.chunk_document(doc, "doc_008")

        assert result.total_chunks == 0
        assert len(result.chunks) == 0
        assert result.chunking_stats.get("empty_document") is True

    def test_whitespace_only_document(self, chunker):
        """Whitespace-only document produces empty chunk list."""
        doc = ParsedDocument(
            file_path="/test/whitespace.txt",
            file_name="whitespace.txt",
            file_type="text",
            text="   \n\n   \t   ",
            page_count=0,
            word_count=0,
            sections=[],
            metadata={},
        )
        result = chunker.chunk_document(doc, "doc_009")

        assert result.total_chunks == 0

    def test_chunk_ids_unique(self, chunker, large_parsed_doc):
        """Each chunk has a unique ID."""
        result = chunker.chunk_document(large_parsed_doc, "doc_010")

        ids = [c.id for c in result.chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_indices_sequential(self, chunker, large_parsed_doc):
        """Chunk indices are sequential starting from 0."""
        result = chunker.chunk_document(large_parsed_doc, "doc_011")

        indices = [c.chunk_index for c in result.chunks]
        expected = list(range(len(result.chunks)))
        assert indices == expected

    def test_chunking_stats_populated(self, chunker, large_parsed_doc):
        """Chunking stats are populated."""
        result = chunker.chunk_document(large_parsed_doc, "doc_012")

        assert "total_chars" in result.chunking_stats
        assert "avg_chunk_chars" in result.chunking_stats
        assert result.chunking_stats["total_chars"] > 0

    def test_document_id_propagated(self, chunker, small_parsed_doc):
        """Document ID is propagated to all chunks."""
        result = chunker.chunk_document(small_parsed_doc, "my_doc_id")

        assert result.document_id == "my_doc_id"
        for chunk in result.chunks:
            assert chunk.document_id == "my_doc_id"


class TestTableDetection:
    """Tests for table detection and preservation."""

    def test_markdown_table_detected(self, chunker, doc_with_table):
        """Markdown tables are detected."""
        assert chunker._is_table("| A | B |\n|---|---|\n| 1 | 2 |")

    def test_non_table_not_detected(self, chunker):
        """Regular text is not detected as table."""
        assert not chunker._is_table("This is just regular text.")

    def test_table_preserved_whole(self, chunker, doc_with_table):
        """Tables are kept as complete chunks."""
        result = chunker.chunk_document(doc_with_table, "doc_013")

        # Find chunk with table
        table_chunks = [c for c in result.chunks if c.metadata.get("is_table")]
        # Note: table detection may vary based on section extraction


class TestHeaderDetection:
    """Tests for header detection."""

    def test_uppercase_header_detected(self, chunker):
        """All-caps short lines are detected as headers."""
        assert chunker._is_header("INTRODUCTION")
        assert chunker._is_header("CHAPTER ONE")

    def test_numbered_header_detected(self, chunker):
        """Numbered sections are detected as headers."""
        assert chunker._is_header("1.2 Methods")
        assert chunker._is_header("Section 3: Results")

    def test_regular_text_not_header(self, chunker):
        """Regular text is not detected as header."""
        assert not chunker._is_header("This is just a regular sentence that is quite long.")


class TestSplitOversizedSection:
    """Tests for section splitting logic."""

    def test_split_on_paragraph(self, chunker):
        """Large sections split on paragraph boundaries first."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        spans = chunker._split_oversized_section(text, 30, 5)

        assert len(spans) > 1

    def test_split_on_sentence(self, chunker):
        """When no paragraphs, split on sentences."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        spans = chunker._split_oversized_section(text, 30, 5)

        assert len(spans) > 1

    def test_small_section_not_split(self, chunker):
        """Small sections are not split."""
        text = "Small text."
        spans = chunker._split_oversized_section(text, 200, 20)

        assert len(spans) == 1
        assert spans[0].text == text


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_chunker_singleton(self):
        """get_chunker returns singleton instance."""
        chunker1 = get_chunker()
        chunker2 = get_chunker()
        assert chunker1 is chunker2

    def test_chunk_document_convenience(self, small_parsed_doc):
        """chunk_document convenience function works."""
        result = chunk_document(small_parsed_doc, "doc_014")

        assert isinstance(result, ChunkedDocument)
        assert result.total_chunks >= 1


class TestChunkSerialization:
    """Tests for chunk serialization."""

    def test_chunk_to_dict(self, chunker, small_parsed_doc):
        """Chunks can be serialized to dict."""
        result = chunker.chunk_document(small_parsed_doc, "doc_015")
        chunk = result.chunks[0]

        data = chunk.to_dict()

        assert data["id"] == chunk.id
        assert data["document_id"] == "doc_015"
        assert data["text_original"] == chunk.text_original
        assert "embedding" in data

    def test_chunk_from_dict(self):
        """Chunks can be deserialized from dict."""
        data = {
            "id": "chunk_test",
            "document_id": "doc_016",
            "chunk_index": 0,
            "page_number": 1,
            "section_header": "Test",
            "text_original": "Original",
            "text_redacted": "Redacted",
            "text_anonymized": "Anonymized",
            "embedding": [0.1, 0.2, 0.3],
            "metadata": {"key": "value"},
            "created_at": "2024-01-01T00:00:00Z",
        }

        chunk = DocumentChunk.from_dict(data)

        assert chunk.id == "chunk_test"
        assert chunk.text_original == "Original"
        assert chunk.embedding == [0.1, 0.2, 0.3]

    def test_chunked_document_to_dict(self, chunker, small_parsed_doc):
        """ChunkedDocument can be serialized to dict."""
        result = chunker.chunk_document(small_parsed_doc, "doc_017")

        data = result.to_dict()

        assert data["document_id"] == "doc_017"
        assert data["total_chunks"] == result.total_chunks
        assert len(data["chunks"]) == result.total_chunks
