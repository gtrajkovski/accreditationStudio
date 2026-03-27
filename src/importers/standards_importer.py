"""Standards import pipeline orchestrator.

Coordinates extraction, parsing, validation, and StandardsLibrary creation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import logging
import time
import hashlib
import tempfile

from src.core.models import (
    StandardsLibrary,
    StandardsSection,
    ChecklistItem,
    generate_id,
    now_iso,
)
from src.core.models.enums import AccreditingBody
from src.importers.standards_extractors import (
    ExtractorFactory,
    ExtractedContent,
    ExtractorType,
)
from src.importers.standards_parser import StandardsParser, ParseResult
from src.importers.standards_validator import StandardsValidator, ValidationResult

logger = logging.getLogger(__name__)


class ImportStatus:
    """Import status constants."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    PARSING = "parsing"
    VALIDATING = "validating"
    READY = "ready"
    IMPORTED = "imported"
    FAILED = "failed"


@dataclass
class ImportProgress:
    """Progress tracking for import pipeline."""
    status: str = ImportStatus.PENDING
    step: int = 0
    total_steps: int = 4
    message: str = ""
    percentage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "step": self.step,
            "total_steps": self.total_steps,
            "message": self.message,
            "percentage": self.percentage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImportProgress":
        return cls(
            status=data.get("status", ImportStatus.PENDING),
            step=data.get("step", 0),
            total_steps=data.get("total_steps", 4),
            message=data.get("message", ""),
            percentage=data.get("percentage", 0.0),
        )


@dataclass
class ImportResult:
    """Complete import result."""
    import_id: str = field(default_factory=lambda: generate_id("imp"))
    status: str = ImportStatus.PENDING
    source_type: str = ""
    source_path: str = ""
    source_hash: str = ""

    # Pipeline outputs
    extracted: Optional[ExtractedContent] = None
    parsed: Optional[ParseResult] = None
    validation: Optional[ValidationResult] = None
    library: Optional[StandardsLibrary] = None

    # Tracking
    sections_detected: int = 0
    items_detected: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Timing
    started_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "import_id": self.import_id,
            "status": self.status,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "sections_detected": self.sections_detected,
            "items_detected": self.items_detected,
            "errors": self.errors,
            "warnings": self.warnings,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "can_import": self.validation.can_import if self.validation else False,
            "quality_score": self.validation.quality.overall if self.validation else 0,
            "library_id": self.library.id if self.library else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImportResult":
        return cls(
            import_id=data.get("import_id", generate_id("imp")),
            status=data.get("status", ImportStatus.PENDING),
            source_type=data.get("source_type", ""),
            source_path=data.get("source_path", ""),
            source_hash=data.get("source_hash", ""),
            sections_detected=data.get("sections_detected", 0),
            items_detected=data.get("items_detected", 0),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            started_at=data.get("started_at", now_iso()),
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms", 0),
        )


class StandardsImporter:
    """Orchestrates the standards import pipeline."""

    def __init__(self, standards_store=None):
        """Initialize importer.

        Args:
            standards_store: Optional StandardsStore for saving imported libraries
        """
        self.parser = StandardsParser()
        self.validator = StandardsValidator()
        self.standards_store = standards_store

    def import_from_file(
        self,
        file_path: str,
        accreditor: AccreditingBody = AccreditingBody.CUSTOM,
        name: Optional[str] = None,
        version: str = "",
        on_progress: Optional[Callable[[ImportProgress], None]] = None,
    ) -> ImportResult:
        """Import standards from a file.

        Args:
            file_path: Path to PDF, Excel, CSV, or text file
            accreditor: Accrediting body for the standards
            name: Name for the standards library
            version: Version string
            on_progress: Optional callback for progress updates

        Returns:
            ImportResult with library if successful
        """
        start_time = time.time()
        result = ImportResult(
            source_type="file",
            source_path=file_path,
        )

        logger.info(f"Starting import from file: {file_path}")

        try:
            # Compute source hash
            result.source_hash = self._compute_file_hash(file_path)

            # Step 1: Extract
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.EXTRACTING,
                step=1,
                message="Extracting content from file...",
                percentage=25,
            ))

            extractor = ExtractorFactory.from_file(file_path)
            result.extracted = extractor.extract(file_path)
            result.source_type = result.extracted.source_type.value

            if result.extracted.errors:
                result.errors.extend(result.extracted.errors)

            # Step 2: Parse
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.PARSING,
                step=2,
                message="Parsing section hierarchy...",
                percentage=50,
            ))

            result.parsed = self.parser.parse(result.extracted)
            result.sections_detected = len(result.parsed.hierarchy.sections)
            result.items_detected = len(result.parsed.requirements.checklist_items)

            if result.parsed.warnings:
                result.warnings.extend(result.parsed.warnings)
            if result.parsed.errors:
                result.errors.extend(result.parsed.errors)

            # Step 3: Validate
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.VALIDATING,
                step=3,
                message="Validating structure...",
                percentage=75,
            ))

            result.validation = self.validator.validate(
                result.parsed.hierarchy.sections,
                result.parsed.requirements.checklist_items,
            )

            # Add validation warnings
            for issue in result.validation.issues:
                if issue.severity.value == "warning":
                    result.warnings.append(f"{issue.code}: {issue.message}")
                elif issue.severity.value == "error":
                    result.errors.append(f"{issue.code}: {issue.message}")

            # Step 4: Create library if valid
            if result.validation.can_import:
                result.library = self._create_library(
                    sections=result.parsed.hierarchy.sections,
                    items=result.parsed.requirements.checklist_items,
                    accreditor=accreditor,
                    name=name or Path(file_path).stem,
                    version=version or result.parsed.metadata.get("version", ""),
                    full_text=result.extracted.raw_text,
                    metadata=result.parsed.metadata,
                )
                result.status = ImportStatus.READY
            else:
                result.status = ImportStatus.FAILED
                result.errors.append("Validation failed - cannot import")

            self._update_progress(on_progress, ImportProgress(
                status=result.status,
                step=4,
                message="Import complete" if result.library else "Import failed",
                percentage=100,
            ))

        except Exception as e:
            logger.exception(f"Import failed: {e}")
            result.status = ImportStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = now_iso()
        result.duration_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Import completed: status={result.status}, duration={result.duration_ms}ms")

        return result

    def import_from_url(
        self,
        url: str,
        accreditor: AccreditingBody = AccreditingBody.CUSTOM,
        name: Optional[str] = None,
        version: str = "",
        on_progress: Optional[Callable[[ImportProgress], None]] = None,
    ) -> ImportResult:
        """Import standards from a web URL."""
        start_time = time.time()
        result = ImportResult(
            source_type="web",
            source_path=url,
        )

        logger.info(f"Starting import from URL: {url}")

        try:
            # Step 1: Extract
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.EXTRACTING,
                step=1,
                message="Fetching content from URL...",
                percentage=25,
            ))

            extractor = ExtractorFactory.from_url(url)
            result.extracted = extractor.extract(url)
            result.source_type = result.extracted.source_type.value

            # Compute hash of extracted content
            result.source_hash = hashlib.sha256(
                result.extracted.raw_text.encode('utf-8')
            ).hexdigest()[:16]

            if result.extracted.errors:
                result.errors.extend(result.extracted.errors)

            # Step 2: Parse
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.PARSING,
                step=2,
                message="Parsing section hierarchy...",
                percentage=50,
            ))

            result.parsed = self.parser.parse(result.extracted)
            result.sections_detected = len(result.parsed.hierarchy.sections)
            result.items_detected = len(result.parsed.requirements.checklist_items)

            if result.parsed.warnings:
                result.warnings.extend(result.parsed.warnings)
            if result.parsed.errors:
                result.errors.extend(result.parsed.errors)

            # Step 3: Validate
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.VALIDATING,
                step=3,
                message="Validating structure...",
                percentage=75,
            ))

            result.validation = self.validator.validate(
                result.parsed.hierarchy.sections,
                result.parsed.requirements.checklist_items,
            )

            # Step 4: Create library if valid
            if result.validation.can_import:
                # Extract name from URL if not provided
                if not name:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(url)
                    name = parsed_url.netloc.replace("www.", "").split(".")[0].title()

                result.library = self._create_library(
                    sections=result.parsed.hierarchy.sections,
                    items=result.parsed.requirements.checklist_items,
                    accreditor=accreditor,
                    name=name,
                    version=version or result.parsed.metadata.get("version", ""),
                    full_text=result.extracted.raw_text,
                    metadata=result.parsed.metadata,
                )
                result.status = ImportStatus.READY
            else:
                result.status = ImportStatus.FAILED
                result.errors.append("Validation failed - cannot import")

            self._update_progress(on_progress, ImportProgress(
                status=result.status,
                step=4,
                message="Import complete" if result.library else "Import failed",
                percentage=100,
            ))

        except Exception as e:
            logger.exception(f"URL import failed: {e}")
            result.status = ImportStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = now_iso()
        result.duration_ms = int((time.time() - start_time) * 1000)

        return result

    def import_from_text(
        self,
        text: str,
        accreditor: AccreditingBody = AccreditingBody.CUSTOM,
        name: str = "Custom Standards",
        version: str = "",
        on_progress: Optional[Callable[[ImportProgress], None]] = None,
    ) -> ImportResult:
        """Import standards from raw text."""
        start_time = time.time()
        result = ImportResult(
            source_type="text",
            source_path="<text input>",
        )

        logger.info(f"Starting import from text ({len(text)} chars)")

        try:
            # Compute hash
            result.source_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

            # Step 1: Create extracted content directly
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.EXTRACTING,
                step=1,
                message="Processing text content...",
                percentage=25,
            ))

            result.extracted = ExtractedContent(
                source_type=ExtractorType.TEXT,
                source_path="<text input>",
                raw_text=text,
                confidence=0.7,
            )

            # Step 2: Parse
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.PARSING,
                step=2,
                message="Parsing section hierarchy...",
                percentage=50,
            ))

            result.parsed = self.parser.parse(result.extracted)
            result.sections_detected = len(result.parsed.hierarchy.sections)
            result.items_detected = len(result.parsed.requirements.checklist_items)

            if result.parsed.warnings:
                result.warnings.extend(result.parsed.warnings)
            if result.parsed.errors:
                result.errors.extend(result.parsed.errors)

            # Step 3: Validate
            self._update_progress(on_progress, ImportProgress(
                status=ImportStatus.VALIDATING,
                step=3,
                message="Validating structure...",
                percentage=75,
            ))

            result.validation = self.validator.validate(
                result.parsed.hierarchy.sections,
                result.parsed.requirements.checklist_items,
            )

            # Step 4: Create library if valid
            if result.validation.can_import:
                result.library = self._create_library(
                    sections=result.parsed.hierarchy.sections,
                    items=result.parsed.requirements.checklist_items,
                    accreditor=accreditor,
                    name=name,
                    version=version,
                    full_text=text,
                    metadata=result.parsed.metadata,
                )
                result.status = ImportStatus.READY
            else:
                result.status = ImportStatus.FAILED
                result.errors.append("Validation failed - cannot import")

            self._update_progress(on_progress, ImportProgress(
                status=result.status,
                step=4,
                message="Import complete" if result.library else "Import failed",
                percentage=100,
            ))

        except Exception as e:
            logger.exception(f"Text import failed: {e}")
            result.status = ImportStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = now_iso()
        result.duration_ms = int((time.time() - start_time) * 1000)

        return result

    def finalize_import(
        self,
        import_result: ImportResult,
        user_mappings: Optional[Dict[str, Any]] = None,
    ) -> StandardsLibrary:
        """Finalize import after user review/mapping adjustments.

        Args:
            import_result: Previous import result in READY status
            user_mappings: Optional user adjustments to sections/items

        Returns:
            Saved StandardsLibrary
        """
        if import_result.status != ImportStatus.READY:
            raise ValueError(f"Cannot finalize import with status: {import_result.status}")

        if not import_result.library:
            raise ValueError("Import result has no library to finalize")

        library = import_result.library

        # Apply user mappings if provided
        if user_mappings:
            library = self._apply_user_mappings(library, user_mappings)

        # Save to store
        if self.standards_store:
            self.standards_store.save(library)
            logger.info(f"Saved library {library.id} to standards store")

        import_result.status = ImportStatus.IMPORTED
        return library

    def _create_library(
        self,
        sections: List[StandardsSection],
        items: List[ChecklistItem],
        accreditor: AccreditingBody,
        name: str,
        version: str,
        full_text: str,
        metadata: Dict[str, Any],
    ) -> StandardsLibrary:
        """Create StandardsLibrary from parsed data."""
        return StandardsLibrary(
            accrediting_body=accreditor,
            name=name,
            version=version or metadata.get("version", ""),
            effective_date=metadata.get("effective_date", ""),
            sections=sections,
            checklist_items=items,
            full_text=full_text,
            is_system_preset=False,
        )

    def _apply_user_mappings(
        self,
        library: StandardsLibrary,
        mappings: Dict[str, Any],
    ) -> StandardsLibrary:
        """Apply user-specified mappings to the library.

        Mappings can adjust:
        - Section titles/numbers
        - Item categories
        - applies_to document types
        - Name and version
        """
        # Update library metadata
        if "name" in mappings:
            library.name = mappings["name"]
        if "version" in mappings:
            library.version = mappings["version"]
        if "accreditor" in mappings:
            try:
                library.accrediting_body = AccreditingBody(mappings["accreditor"])
            except ValueError:
                library.accrediting_body = AccreditingBody.CUSTOM

        # Update sections
        section_mappings = mappings.get("sections", {})
        for section in library.sections:
            if section.id in section_mappings:
                section_updates = section_mappings[section.id]
                if "number" in section_updates:
                    section.number = section_updates["number"]
                if "title" in section_updates:
                    section.title = section_updates["title"]

        # Update items
        item_mappings = mappings.get("items", {})
        for item in library.checklist_items:
            if item.number in item_mappings:
                item_updates = item_mappings[item.number]
                if "category" in item_updates:
                    item.category = item_updates["category"]
                if "applies_to" in item_updates:
                    item.applies_to = item_updates["applies_to"]
                if "description" in item_updates:
                    item.description = item_updates["description"]

        library.updated_at = now_iso()
        return library

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file content."""
        try:
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()[:16]
        except Exception as e:
            logger.warning(f"Failed to compute file hash: {e}")
            return ""

    def _update_progress(
        self,
        callback: Optional[Callable[[ImportProgress], None]],
        progress: ImportProgress,
    ) -> None:
        """Update progress if callback provided."""
        if callback:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")


# Module-level singleton
_importer: Optional[StandardsImporter] = None


def get_importer(standards_store=None) -> StandardsImporter:
    """Get or create the importer singleton."""
    global _importer
    if _importer is None:
        _importer = StandardsImporter(standards_store)
    elif standards_store and _importer.standards_store is None:
        _importer.standards_store = standards_store
    return _importer


def import_standards_from_file(
    file_path: str,
    accreditor: AccreditingBody = AccreditingBody.CUSTOM,
    name: Optional[str] = None,
    version: str = "",
    on_progress: Optional[Callable[[ImportProgress], None]] = None,
) -> ImportResult:
    """Convenience function to import standards from a file."""
    importer = get_importer()
    return importer.import_from_file(file_path, accreditor, name, version, on_progress)


def import_standards_from_url(
    url: str,
    accreditor: AccreditingBody = AccreditingBody.CUSTOM,
    name: Optional[str] = None,
    version: str = "",
    on_progress: Optional[Callable[[ImportProgress], None]] = None,
) -> ImportResult:
    """Convenience function to import standards from a URL."""
    importer = get_importer()
    return importer.import_from_url(url, accreditor, name, version, on_progress)


def import_standards_from_text(
    text: str,
    accreditor: AccreditingBody = AccreditingBody.CUSTOM,
    name: str = "Custom Standards",
    version: str = "",
    on_progress: Optional[Callable[[ImportProgress], None]] = None,
) -> ImportResult:
    """Convenience function to import standards from text."""
    importer = get_importer()
    return importer.import_from_text(text, accreditor, name, version, on_progress)
