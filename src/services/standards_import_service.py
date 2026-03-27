"""Standards import service for business logic orchestration.

Coordinates between the importer pipeline, AI agent, and database
for complete import workflow management.
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator
from dataclasses import dataclass, field

from src.core.models import (
    StandardsLibrary,
    AgentSession,
    generate_id,
    now_iso,
)
from src.core.models.enums import AccreditingBody
from src.importers.standards_importer import (
    StandardsImporter,
    ImportResult,
    ImportStatus,
    ImportProgress,
)
from src.importers.standards_extractors import ExtractorFactory, ExtractedContent
from src.agents.base_agent import AgentType
from src.agents.registry import AgentRegistry
from src.db.connection import get_conn

logger = logging.getLogger(__name__)


@dataclass
class ImportRecord:
    """Database record for import history."""
    id: str = field(default_factory=lambda: generate_id("imp"))
    institution_id: Optional[str] = None
    accreditor_code: str = "CUSTOM"
    source_type: str = ""
    source_name: str = ""
    source_hash: str = ""
    status: str = ImportStatus.PENDING
    library_id: Optional[str] = None
    sections_detected: int = 0
    checklist_items_detected: int = 0
    quality_score: float = 0.0
    validation_errors: List[Dict[str, Any]] = field(default_factory=list)
    validation_warnings: List[Dict[str, Any]] = field(default_factory=list)
    user_mappings: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: int = 0
    imported_by: str = "user"
    error_message: Optional[str] = None
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "accreditor_code": self.accreditor_code,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "source_hash": self.source_hash,
            "status": self.status,
            "library_id": self.library_id,
            "sections_detected": self.sections_detected,
            "checklist_items_detected": self.checklist_items_detected,
            "quality_score": self.quality_score,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "user_mappings": self.user_mappings,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "imported_by": self.imported_by,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row) -> "ImportRecord":
        """Create from database row."""
        return cls(
            id=row["id"],
            institution_id=row["institution_id"],
            accreditor_code=row["accreditor_code"],
            source_type=row["source_type"],
            source_name=row["source_name"],
            source_hash=row["source_hash"] or "",
            status=row["status"],
            library_id=row["library_id"],
            sections_detected=row["sections_detected"] or 0,
            checklist_items_detected=row["checklist_items_detected"] or 0,
            quality_score=row["quality_score"] or 0.0,
            validation_errors=json.loads(row["validation_errors"] or "[]"),
            validation_warnings=json.loads(row["validation_warnings"] or "[]"),
            user_mappings=json.loads(row["user_mappings"] or "{}"),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"] or 0,
            imported_by=row["imported_by"] or "user",
            error_message=row["error_message"],
            created_at=row["created_at"],
        )


class StandardsImportService:
    """Service for managing standards imports."""

    def __init__(self, standards_store=None, workspace_manager=None):
        """Initialize service.

        Args:
            standards_store: StandardsStore for saving libraries
            workspace_manager: WorkspaceManager for agent sessions
        """
        self.standards_store = standards_store
        self.workspace_manager = workspace_manager
        self.importer = StandardsImporter(standards_store)

    def import_file(
        self,
        file_path: str,
        accreditor_code: str = "CUSTOM",
        name: Optional[str] = None,
        version: str = "",
        institution_id: Optional[str] = None,
        use_ai: bool = False,
    ) -> Generator[Dict[str, Any], None, ImportResult]:
        """Import standards from a file.

        Args:
            file_path: Path to file (PDF, Excel, CSV, text)
            accreditor_code: Accrediting body code
            name: Name for the library
            version: Version string
            institution_id: Optional institution to associate
            use_ai: Whether to use AI agent for enhanced parsing

        Yields:
            Progress updates

        Returns:
            ImportResult with parsed library
        """
        # Create import record
        record = ImportRecord(
            institution_id=institution_id,
            accreditor_code=accreditor_code,
            source_type="file",
            source_name=Path(file_path).name,
            source_hash=self._compute_file_hash(file_path),
            started_at=now_iso(),
        )
        self._save_record(record)

        try:
            # Parse accreditor
            try:
                accreditor = AccreditingBody(accreditor_code)
            except ValueError:
                accreditor = AccreditingBody.CUSTOM

            if use_ai:
                # Use AI agent for parsing
                result = yield from self._import_with_agent(
                    file_path, accreditor, name, version, record
                )
            else:
                # Use standard pipeline with progress updates
                def on_progress(progress: ImportProgress):
                    record.status = progress.status
                    self._save_record(record)

                yield {
                    "type": "progress",
                    "import_id": record.id,
                    "status": ImportStatus.EXTRACTING,
                    "message": "Starting import...",
                    "percentage": 0,
                }

                result = self.importer.import_from_file(
                    file_path=file_path,
                    accreditor=accreditor,
                    name=name,
                    version=version,
                    on_progress=on_progress,
                )

            # Update record with result
            record.status = result.status
            record.sections_detected = result.sections_detected
            record.checklist_items_detected = result.items_detected
            if result.validation:
                record.quality_score = result.validation.quality.overall
                record.validation_errors = [i.to_dict() for i in result.validation.issues if i.severity.value == "error"]
                record.validation_warnings = [i.to_dict() for i in result.validation.issues if i.severity.value == "warning"]
            if result.library:
                record.library_id = result.library.id
            record.completed_at = now_iso()
            self._save_record(record)

            yield {"type": "complete", "import_id": record.id, "result": result.to_dict()}
            return result

        except Exception as e:
            logger.exception(f"Import failed: {e}")
            record.status = ImportStatus.FAILED
            record.error_message = str(e)
            record.completed_at = now_iso()
            self._save_record(record)
            raise

    def _import_with_agent(
        self,
        file_path: str,
        accreditor: AccreditingBody,
        name: Optional[str],
        version: str,
        record: ImportRecord,
    ) -> Generator[Dict[str, Any], None, ImportResult]:
        """Import using AI agent for enhanced parsing."""
        # Extract content first
        extractor = ExtractorFactory.from_file(file_path)
        extracted = extractor.extract(file_path)

        # Create agent session
        session = AgentSession(
            institution_id=record.institution_id,
            agent_type=AgentType.STANDARDS_IMPORTER.value,
        )

        # Create agent
        agent = AgentRegistry.create(
            AgentType.STANDARDS_IMPORTER,
            session=session,
            workspace_manager=self.workspace_manager,
            standards_store=self.standards_store,
        )

        if not agent:
            raise ValueError("Failed to create Standards Importer agent")

        # Set extracted content
        agent.set_extracted_content(extracted)

        # Run agent
        prompt = f"""Parse the following standards document into structured sections and checklist items.

Accreditor: {accreditor.value}
Name: {name or Path(file_path).stem}
Version: {version}

Document text (first 5000 chars):
{extracted.raw_text[:5000]}

Please:
1. Use parse_section_hierarchy to detect the numbering scheme
2. Use extract_section_text to segment the content
3. Use extract_checklist_items for each section
4. Use validate_structure to check the result
5. Use create_standards_library to assemble the final library
"""

        for update in agent.run_turn(prompt):
            yield {"type": "agent_update", "import_id": record.id, **update}

        # Get result from agent
        library = agent.get_parsed_library()
        if library:
            library.accrediting_body = accreditor
            library.name = name or Path(file_path).stem
            library.version = version
            library.full_text = extracted.raw_text

            if self.standards_store:
                self.standards_store.save(library)

        result = ImportResult(
            import_id=record.id,
            status=ImportStatus.IMPORTED if library else ImportStatus.FAILED,
            source_type=extracted.source_type.value,
            source_path=file_path,
            sections_detected=len(library.sections) if library else 0,
            items_detected=len(library.checklist_items) if library else 0,
            library=library,
        )

        return result

    def import_text(
        self,
        text: str,
        accreditor_code: str = "CUSTOM",
        name: str = "Custom Standards",
        version: str = "",
        institution_id: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, ImportResult]:
        """Import standards from raw text.

        Args:
            text: Standards text content
            accreditor_code: Accrediting body code
            name: Name for the library
            version: Version string
            institution_id: Optional institution to associate

        Yields:
            Progress updates

        Returns:
            ImportResult with parsed library
        """
        # Create import record
        record = ImportRecord(
            institution_id=institution_id,
            accreditor_code=accreditor_code,
            source_type="text",
            source_name="<text input>",
            source_hash=hashlib.sha256(text.encode('utf-8')).hexdigest()[:16],
            started_at=now_iso(),
        )
        self._save_record(record)

        try:
            # Parse accreditor
            try:
                accreditor = AccreditingBody(accreditor_code)
            except ValueError:
                accreditor = AccreditingBody.CUSTOM

            yield {
                "type": "progress",
                "import_id": record.id,
                "status": ImportStatus.EXTRACTING,
                "message": "Processing text content...",
                "percentage": 0,
            }

            result = self.importer.import_from_text(
                text=text,
                accreditor=accreditor,
                name=name,
                version=version,
            )

            # Update record
            record.status = result.status
            record.sections_detected = result.sections_detected
            record.checklist_items_detected = result.items_detected
            if result.validation:
                record.quality_score = result.validation.quality.overall
            if result.library:
                record.library_id = result.library.id
            record.completed_at = now_iso()
            self._save_record(record)

            yield {"type": "complete", "import_id": record.id, "result": result.to_dict()}
            return result

        except Exception as e:
            logger.exception(f"Text import failed: {e}")
            record.status = ImportStatus.FAILED
            record.error_message = str(e)
            record.completed_at = now_iso()
            self._save_record(record)
            raise

    def finalize_import(
        self,
        import_id: str,
        user_mappings: Optional[Dict[str, Any]] = None,
    ) -> StandardsLibrary:
        """Finalize an import after user review.

        Args:
            import_id: Import record ID
            user_mappings: User adjustments to apply

        Returns:
            Finalized StandardsLibrary
        """
        record = self.get_import(import_id)
        if not record:
            raise ValueError(f"Import {import_id} not found")

        if record.status != ImportStatus.READY:
            raise ValueError(f"Cannot finalize import with status: {record.status}")

        if record.library_id and self.standards_store:
            library = self.standards_store.load(record.library_id)
            if library and user_mappings:
                library = self._apply_mappings(library, user_mappings)
                self.standards_store.save(library)

            record.status = ImportStatus.IMPORTED
            record.user_mappings = user_mappings or {}
            self._save_record(record)
            return library

        raise ValueError("No library available to finalize")

    def get_import(self, import_id: str) -> Optional[ImportRecord]:
        """Get an import record by ID."""
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM standards_imports WHERE id = ?",
            (import_id,)
        ).fetchone()
        return ImportRecord.from_row(row) if row else None

    def list_imports(
        self,
        institution_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[ImportRecord]:
        """List import records."""
        conn = get_conn()
        query = "SELECT * FROM standards_imports WHERE 1=1"
        params = []

        if institution_id:
            query += " AND institution_id = ?"
            params.append(institution_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [ImportRecord.from_row(row) for row in rows]

    def delete_import(self, import_id: str) -> bool:
        """Delete an import record."""
        conn = get_conn()
        result = conn.execute(
            "DELETE FROM standards_imports WHERE id = ?",
            (import_id,)
        )
        conn.commit()
        return result.rowcount > 0

    def _save_record(self, record: ImportRecord) -> None:
        """Save import record to database."""
        conn = get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO standards_imports (
                id, institution_id, accreditor_code, source_type, source_name,
                source_hash, status, library_id, sections_detected,
                checklist_items_detected, quality_score, validation_errors,
                validation_warnings, user_mappings, started_at, completed_at,
                duration_ms, imported_by, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.id,
            record.institution_id,
            record.accreditor_code,
            record.source_type,
            record.source_name,
            record.source_hash,
            record.status,
            record.library_id,
            record.sections_detected,
            record.checklist_items_detected,
            record.quality_score,
            json.dumps(record.validation_errors),
            json.dumps(record.validation_warnings),
            json.dumps(record.user_mappings),
            record.started_at,
            record.completed_at,
            record.duration_ms,
            record.imported_by,
            record.error_message,
            record.created_at,
        ))
        conn.commit()

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()[:16]

    def _apply_mappings(
        self,
        library: StandardsLibrary,
        mappings: Dict[str, Any],
    ) -> StandardsLibrary:
        """Apply user mappings to library."""
        # Apply section updates
        section_updates = mappings.get("sections", {})
        for section in library.sections:
            if section.number in section_updates:
                update = section_updates[section.number]
                if "title" in update:
                    section.title = update["title"]
                if "number" in update:
                    section.number = update["number"]

        # Apply item updates
        item_updates = mappings.get("items", {})
        for item in library.checklist_items:
            if item.number in item_updates:
                update = item_updates[item.number]
                if "category" in update:
                    item.category = update["category"]
                if "applies_to" in update:
                    item.applies_to = update["applies_to"]
                if "description" in update:
                    item.description = update["description"]

        library.updated_at = now_iso()
        return library


# Module-level singleton
_service: Optional[StandardsImportService] = None


def get_import_service(
    standards_store=None,
    workspace_manager=None,
) -> StandardsImportService:
    """Get or create the import service singleton."""
    global _service
    if _service is None:
        _service = StandardsImportService(standards_store, workspace_manager)
    return _service
