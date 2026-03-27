"""Search context domain models."""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from src.core.models.enums import SearchScope


@dataclass
class SearchContext:
    """Captures user's current location for search scoping."""
    scope: SearchScope
    institution_id: Optional[str] = None
    program_id: Optional[str] = None
    document_id: Optional[str] = None
    accreditor_id: Optional[str] = None

    @classmethod
    def from_page(cls, page_type: str, context: Dict[str, Any]) -> "SearchContext":
        """Factory method to create context from page type and context dict.

        Args:
            page_type: Flask endpoint name (e.g., 'institution_overview', 'dashboard')
            context: Dict with institution_id, program_id, document_id, accreditor_id
        """
        # Map page endpoints to scope levels
        if page_type in ("dashboard", "portfolios_list", "portfolios_index"):
            return cls(scope=SearchScope.GLOBAL)
        elif page_type.startswith("institution_"):
            inst_id = context.get("institution_id")
            if "program" in page_type:
                return cls(
                    scope=SearchScope.PROGRAM,
                    institution_id=inst_id,
                    program_id=context.get("program_id")
                )
            elif "compliance" in page_type or "audit" in page_type:
                return cls(
                    scope=SearchScope.COMPLIANCE,
                    institution_id=inst_id
                )
            elif "document" in page_type:
                return cls(
                    scope=SearchScope.DOCUMENT,
                    institution_id=inst_id,
                    document_id=context.get("document_id")
                )
            else:
                return cls(scope=SearchScope.INSTITUTION, institution_id=inst_id)
        elif page_type == "standards" or page_type.startswith("standards_"):
            return cls(
                scope=SearchScope.STANDARDS,
                accreditor_id=context.get("accreditor_id")
            )
        else:
            return cls(scope=SearchScope.GLOBAL)

    def to_chromadb_where(self) -> Optional[Dict[str, Any]]:
        """Convert context to ChromaDB where clause."""
        if self.scope == SearchScope.GLOBAL:
            return None

        where = {}
        if self.institution_id:
            where["institution_id"] = self.institution_id
        if self.program_id:
            where["program_id"] = self.program_id
        if self.document_id:
            where["document_id"] = self.document_id

        return where if where else None

    def to_sql_conditions(self) -> tuple:
        """Convert context to SQL WHERE clause and params.

        Returns:
            Tuple of (sql_string, params_list)
        """
        if self.scope == SearchScope.GLOBAL:
            return "", []

        conditions = []
        params = []

        if self.institution_id:
            conditions.append("institution_id = ?")
            params.append(self.institution_id)
        if self.program_id:
            conditions.append("program_id = ?")
            params.append(self.program_id)
        if self.document_id:
            conditions.append("document_id = ?")
            params.append(self.document_id)
        if self.accreditor_id:
            conditions.append("accreditor_id = ?")
            params.append(self.accreditor_id)

        sql = " AND ".join(conditions)
        return sql, params

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scope": self.scope.value,
            "institution_id": self.institution_id,
            "program_id": self.program_id,
            "document_id": self.document_id,
            "accreditor_id": self.accreditor_id,
        }
