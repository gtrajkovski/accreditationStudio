"""Tests for SearchContext model and scope detection."""

import pytest
from src.core.models import SearchScope, SearchContext


class TestSearchScope:
    """Tests for SearchScope enum."""

    def test_has_six_values(self):
        """SearchScope has exactly 6 scope levels."""
        scopes = list(SearchScope)
        assert len(scopes) == 6
        assert SearchScope.GLOBAL in scopes
        assert SearchScope.INSTITUTION in scopes
        assert SearchScope.PROGRAM in scopes
        assert SearchScope.DOCUMENT in scopes
        assert SearchScope.STANDARDS in scopes
        assert SearchScope.COMPLIANCE in scopes


class TestSearchContextFactory:
    """Tests for SearchContext.from_page() factory method."""

    def test_dashboard_returns_global(self):
        """Dashboard page returns GLOBAL scope."""
        ctx = SearchContext.from_page("dashboard", {})
        assert ctx.scope == SearchScope.GLOBAL
        assert ctx.institution_id is None

    def test_portfolios_returns_global(self):
        """Portfolio pages return GLOBAL scope."""
        ctx = SearchContext.from_page("portfolios_list", {})
        assert ctx.scope == SearchScope.GLOBAL

    def test_institution_overview_returns_institution(self):
        """Institution overview returns INSTITUTION scope with ID."""
        ctx = SearchContext.from_page("institution_overview", {"institution_id": "inst_123"})
        assert ctx.scope == SearchScope.INSTITUTION
        assert ctx.institution_id == "inst_123"
        assert ctx.program_id is None

    def test_institution_program_detail_returns_program(self):
        """Institution program page returns PROGRAM scope."""
        ctx = SearchContext.from_page(
            "institution_program_detail",
            {"institution_id": "inst_123", "program_id": "prog_456"}
        )
        assert ctx.scope == SearchScope.PROGRAM
        assert ctx.institution_id == "inst_123"
        assert ctx.program_id == "prog_456"

    def test_institution_compliance_returns_compliance(self):
        """Institution compliance page returns COMPLIANCE scope."""
        ctx = SearchContext.from_page(
            "institution_compliance_audit",
            {"institution_id": "inst_123"}
        )
        assert ctx.scope == SearchScope.COMPLIANCE
        assert ctx.institution_id == "inst_123"

    def test_institution_audit_returns_compliance(self):
        """Institution audit page returns COMPLIANCE scope."""
        ctx = SearchContext.from_page(
            "institution_audit_detail",
            {"institution_id": "inst_123"}
        )
        assert ctx.scope == SearchScope.COMPLIANCE
        assert ctx.institution_id == "inst_123"

    def test_institution_document_returns_document(self):
        """Institution document page returns DOCUMENT scope."""
        ctx = SearchContext.from_page(
            "institution_document_viewer",
            {"institution_id": "inst_123", "document_id": "doc_789"}
        )
        assert ctx.scope == SearchScope.DOCUMENT
        assert ctx.institution_id == "inst_123"
        assert ctx.document_id == "doc_789"

    def test_standards_page_returns_standards(self):
        """Standards page returns STANDARDS scope."""
        ctx = SearchContext.from_page("standards", {"accreditor_id": "ACCSC"})
        assert ctx.scope == SearchScope.STANDARDS
        assert ctx.accreditor_id == "ACCSC"

    def test_standards_detail_returns_standards(self):
        """Standards detail page returns STANDARDS scope."""
        ctx = SearchContext.from_page("standards_detail", {"accreditor_id": "SACSCOC"})
        assert ctx.scope == SearchScope.STANDARDS
        assert ctx.accreditor_id == "SACSCOC"

    def test_unknown_page_returns_global(self):
        """Unknown page type returns GLOBAL scope."""
        ctx = SearchContext.from_page("unknown_page", {})
        assert ctx.scope == SearchScope.GLOBAL


class TestSearchContextSQLGeneration:
    """Tests for SearchContext.to_sql_conditions()."""

    def test_global_returns_empty(self):
        """GLOBAL scope returns empty conditions."""
        ctx = SearchContext(scope=SearchScope.GLOBAL)
        sql, params = ctx.to_sql_conditions()
        assert sql == ""
        assert params == []

    def test_institution_returns_institution_filter(self):
        """INSTITUTION scope returns institution_id filter."""
        ctx = SearchContext(scope=SearchScope.INSTITUTION, institution_id="inst_123")
        sql, params = ctx.to_sql_conditions()
        assert sql == "institution_id = ?"
        assert params == ["inst_123"]

    def test_program_returns_both_filters(self):
        """PROGRAM scope returns institution_id and program_id filters."""
        ctx = SearchContext(
            scope=SearchScope.PROGRAM,
            institution_id="inst_123",
            program_id="prog_456"
        )
        sql, params = ctx.to_sql_conditions()
        assert "institution_id = ?" in sql
        assert "program_id = ?" in sql
        assert " AND " in sql
        assert params == ["inst_123", "prog_456"]

    def test_document_returns_three_filters(self):
        """DOCUMENT scope returns institution_id, program_id, document_id filters."""
        ctx = SearchContext(
            scope=SearchScope.DOCUMENT,
            institution_id="inst_123",
            document_id="doc_789"
        )
        sql, params = ctx.to_sql_conditions()
        assert "institution_id = ?" in sql
        assert "document_id = ?" in sql
        assert " AND " in sql
        assert "inst_123" in params
        assert "doc_789" in params

    def test_standards_returns_accreditor_filter(self):
        """STANDARDS scope returns accreditor_id filter."""
        ctx = SearchContext(scope=SearchScope.STANDARDS, accreditor_id="ACCSC")
        sql, params = ctx.to_sql_conditions()
        assert sql == "accreditor_id = ?"
        assert params == ["ACCSC"]


class TestSearchContextChromaDBGeneration:
    """Tests for SearchContext.to_chromadb_where()."""

    def test_global_returns_none(self):
        """GLOBAL scope returns None for ChromaDB."""
        ctx = SearchContext(scope=SearchScope.GLOBAL)
        where = ctx.to_chromadb_where()
        assert where is None

    def test_institution_returns_dict(self):
        """INSTITUTION scope returns metadata dict."""
        ctx = SearchContext(scope=SearchScope.INSTITUTION, institution_id="inst_123")
        where = ctx.to_chromadb_where()
        assert where == {"institution_id": "inst_123"}

    def test_program_returns_dict(self):
        """PROGRAM scope returns metadata dict with both IDs."""
        ctx = SearchContext(
            scope=SearchScope.PROGRAM,
            institution_id="inst_123",
            program_id="prog_456"
        )
        where = ctx.to_chromadb_where()
        assert where == {
            "institution_id": "inst_123",
            "program_id": "prog_456"
        }

    def test_document_returns_dict(self):
        """DOCUMENT scope returns metadata dict with document_id."""
        ctx = SearchContext(
            scope=SearchScope.DOCUMENT,
            institution_id="inst_123",
            document_id="doc_789"
        )
        where = ctx.to_chromadb_where()
        assert where == {
            "institution_id": "inst_123",
            "document_id": "doc_789"
        }

    def test_empty_ids_returns_none(self):
        """Context with no IDs returns None."""
        ctx = SearchContext(scope=SearchScope.INSTITUTION)
        where = ctx.to_chromadb_where()
        assert where is None


class TestSearchContextSerialization:
    """Tests for SearchContext.to_dict()."""

    def test_to_dict_serializes_all_fields(self):
        """to_dict() includes all fields."""
        ctx = SearchContext(
            scope=SearchScope.PROGRAM,
            institution_id="inst_123",
            program_id="prog_456"
        )
        data = ctx.to_dict()
        assert data["scope"] == "program"
        assert data["institution_id"] == "inst_123"
        assert data["program_id"] == "prog_456"
        assert data["document_id"] is None
        assert data["accreditor_id"] is None
