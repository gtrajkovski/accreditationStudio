"""Standards Importer API endpoints.

Provides endpoints for:
- File upload and parsing
- Preview of detected structure
- Validation and conflict reporting
- Import finalization
- Import history
"""

import os
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify, Response
import json

from src.core.models import AccreditingBody, now_iso

logger = logging.getLogger(__name__)

# Create Blueprint
standards_importer_bp = Blueprint("standards_importer", __name__, url_prefix="/api/standards-importer")

# Module-level references (set during initialization)
_import_service = None
_standards_store = None
_upload_dir = Path("uploads/standards")


def init_standards_importer_bp(import_service, standards_store, upload_dir: str = None):
    """Initialize the standards importer blueprint with dependencies.

    Args:
        import_service: StandardsImportService instance
        standards_store: StandardsStore instance
        upload_dir: Optional custom upload directory
    """
    global _import_service, _standards_store, _upload_dir
    _import_service = import_service
    _standards_store = standards_store
    if upload_dir:
        _upload_dir = Path(upload_dir)
    _upload_dir.mkdir(parents=True, exist_ok=True)
    return standards_importer_bp


@standards_importer_bp.route("/upload", methods=["POST"])
def upload_file():
    """Upload a standards file for parsing.

    Request:
        - Form data with 'file' field
        - Optional 'accreditor' field (default: CUSTOM)

    Returns:
        JSON with upload ID and file info
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".xlsx", ".xls", ".csv", ".txt", ".md"}
    if ext not in allowed:
        return jsonify({
            "error": f"Unsupported file type: {ext}",
            "allowed": list(allowed),
        }), 400

    # Save file
    from src.core.models import generate_id
    upload_id = generate_id("upl")
    filename = f"{upload_id}{ext}"
    file_path = _upload_dir / filename
    file.save(str(file_path))

    return jsonify({
        "upload_id": upload_id,
        "filename": file.filename,
        "file_path": str(file_path),
        "file_type": ext[1:],
        "size_bytes": file_path.stat().st_size,
    }), 200


@standards_importer_bp.route("/parse", methods=["POST"])
def parse_file():
    """Parse an uploaded file and return preview.

    Request Body:
        file_path: Path to uploaded file
        accreditor: Accrediting body code (optional)
        name: Library name (optional)
        version: Version string (optional)

    Returns:
        JSON with parsed structure preview
    """
    data = request.get_json() or {}
    file_path = data.get("file_path")

    if not file_path or not Path(file_path).exists():
        return jsonify({"error": "File not found"}), 400

    accreditor_code = data.get("accreditor", "CUSTOM")
    name = data.get("name")
    version = data.get("version", "")

    try:
        # Use importer for initial parse
        from src.importers.standards_importer import StandardsImporter
        importer = StandardsImporter(_standards_store)

        try:
            accreditor = AccreditingBody(accreditor_code)
        except ValueError:
            accreditor = AccreditingBody.CUSTOM

        result = importer.import_from_file(
            file_path=file_path,
            accreditor=accreditor,
            name=name,
            version=version,
        )

        return jsonify({
            "import_id": result.import_id,
            "status": result.status,
            "sections": [s.to_dict() for s in result.parsed.hierarchy.sections] if result.parsed else [],
            "checklist_items": [i.to_dict() for i in result.parsed.requirements.checklist_items] if result.parsed else [],
            "sections_count": result.sections_detected,
            "items_count": result.items_detected,
            "validation": result.validation.to_dict() if result.validation else None,
            "can_import": result.validation.can_import if result.validation else False,
            "quality_score": result.validation.quality.overall if result.validation else 0,
            "numbering_scheme": result.parsed.hierarchy.numbering_scheme.type if result.parsed else "unknown",
        }), 200

    except Exception as e:
        logger.exception(f"Parse failed: {e}")
        return jsonify({"error": str(e)}), 500


@standards_importer_bp.route("/parse-ai", methods=["POST"])
def parse_with_ai():
    """Parse file using AI agent for enhanced extraction.

    Returns SSE stream with progress updates.

    Request Body:
        file_path: Path to uploaded file
        accreditor: Accrediting body code (optional)
        name: Library name (optional)
        version: Version string (optional)
        institution_id: Institution ID (optional)
    """
    data = request.get_json() or {}
    file_path = data.get("file_path")

    if not file_path or not Path(file_path).exists():
        return jsonify({"error": "File not found"}), 400

    def generate():
        try:
            for update in _import_service.import_file(
                file_path=file_path,
                accreditor_code=data.get("accreditor", "CUSTOM"),
                name=data.get("name"),
                version=data.get("version", ""),
                institution_id=data.get("institution_id"),
                use_ai=True,
            ):
                yield f"data: {json.dumps(update)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@standards_importer_bp.route("/validate", methods=["POST"])
def validate_import():
    """Validate parsed data structure.

    Request Body:
        sections: List of section objects
        checklist_items: List of checklist item objects

    Returns:
        JSON with validation result
    """
    data = request.get_json() or {}
    sections_data = data.get("sections", [])
    items_data = data.get("checklist_items", [])

    from src.core.models import StandardsSection, ChecklistItem
    from src.importers.standards_validator import StandardsValidator

    sections = [StandardsSection.from_dict(s) for s in sections_data]
    items = [ChecklistItem.from_dict(i) for i in items_data]

    validator = StandardsValidator()
    result = validator.validate(sections, items)

    return jsonify(result.to_dict()), 200


@standards_importer_bp.route("/import", methods=["POST"])
def finalize_import():
    """Finalize import and create StandardsLibrary.

    Request Body:
        import_id: Import ID from parse step (optional)
        accreditor: Accrediting body code
        name: Library name
        version: Version string (optional)
        effective_date: Effective date (optional)
        sections: List of section objects
        checklist_items: List of checklist item objects
        full_text: Full document text (optional)
        user_mappings: User adjustments (optional)

    Returns:
        JSON with created library
    """
    data = request.get_json() or {}

    # Required fields
    accreditor_code = data.get("accreditor")
    name = data.get("name")
    sections_data = data.get("sections", [])

    if not accreditor_code:
        return jsonify({"error": "accreditor is required"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not sections_data:
        return jsonify({"error": "sections are required"}), 400

    try:
        accreditor = AccreditingBody(accreditor_code)
    except ValueError:
        accreditor = AccreditingBody.CUSTOM

    from src.core.models import StandardsLibrary, StandardsSection, ChecklistItem

    sections = [StandardsSection.from_dict(s) for s in sections_data]
    items = [ChecklistItem.from_dict(i) for i in data.get("checklist_items", [])]

    library = StandardsLibrary(
        accrediting_body=accreditor,
        name=name,
        version=data.get("version", ""),
        effective_date=data.get("effective_date", ""),
        sections=sections,
        checklist_items=items,
        full_text=data.get("full_text", ""),
        is_system_preset=False,
    )

    # Apply user mappings if provided
    user_mappings = data.get("user_mappings")
    if user_mappings and _import_service:
        library = _import_service._apply_mappings(library, user_mappings)

    # Save to store
    if _standards_store:
        _standards_store.save(library)

    # Update import record if provided
    import_id = data.get("import_id")
    if import_id and _import_service:
        record = _import_service.get_import(import_id)
        if record:
            record.status = "imported"
            record.library_id = library.id
            record.completed_at = now_iso()
            _import_service._save_record(record)

    return jsonify({
        "success": True,
        "library": library.to_dict(),
    }), 201


@standards_importer_bp.route("/preview", methods=["POST"])
def quick_preview():
    """Quick preview without saving to database.

    Request Body:
        file_path: Path to file OR
        text: Raw text to parse

    Returns:
        JSON with preview of detected structure
    """
    data = request.get_json() or {}
    file_path = data.get("file_path")
    text = data.get("text")

    if not file_path and not text:
        return jsonify({"error": "file_path or text required"}), 400

    from src.importers.standards_extractors import ExtractorFactory, ExtractorType, ExtractedContent
    from src.importers.standards_parser import StandardsParser

    try:
        if file_path:
            extractor = ExtractorFactory.from_file(file_path)
            extracted = extractor.extract(file_path)
        else:
            extracted = ExtractedContent(
                source_type=ExtractorType.TEXT,
                source_path="direct_input",
                raw_text=text,
            )

        parser = StandardsParser()
        result = parser.parse(extracted)

        return jsonify({
            "numbering_scheme": result.hierarchy.numbering_scheme.type,
            "sections_count": len(result.hierarchy.sections),
            "items_count": len(result.requirements.checklist_items),
            "categories": result.requirements.categories_detected,
            "sample_sections": [
                {"number": s.number, "title": s.title}
                for s in result.hierarchy.sections[:10]
            ],
            "sample_items": [
                {"number": i.number, "category": i.category, "description": i.description[:100]}
                for i in result.requirements.checklist_items[:10]
            ],
            "confidence": min(result.hierarchy.confidence, result.requirements.confidence),
        }), 200

    except Exception as e:
        logger.exception(f"Preview failed: {e}")
        return jsonify({"error": str(e)}), 500


@standards_importer_bp.route("/imports", methods=["GET"])
def list_imports():
    """List import history.

    Query Parameters:
        institution_id: Filter by institution (optional)
        status: Filter by status (optional)
        limit: Max results (default 50)

    Returns:
        JSON list of import records
    """
    institution_id = request.args.get("institution_id")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))

    records = _import_service.list_imports(
        institution_id=institution_id,
        status=status,
        limit=limit,
    )

    return jsonify([r.to_dict() for r in records]), 200


@standards_importer_bp.route("/imports/<import_id>", methods=["GET"])
def get_import(import_id: str):
    """Get a specific import record.

    Returns:
        JSON with import record details
    """
    record = _import_service.get_import(import_id)
    if not record:
        return jsonify({"error": "Import not found"}), 404

    return jsonify(record.to_dict()), 200


@standards_importer_bp.route("/imports/<import_id>", methods=["DELETE"])
def delete_import(import_id: str):
    """Delete an import record.

    Returns:
        JSON with success status
    """
    deleted = _import_service.delete_import(import_id)
    if not deleted:
        return jsonify({"error": "Import not found"}), 404

    return jsonify({"success": True, "deleted_id": import_id}), 200


@standards_importer_bp.route("/accreditors", methods=["GET"])
def list_accreditors():
    """List available accrediting body codes.

    Returns:
        JSON list of accreditor codes with names
    """
    accreditors = [
        {"code": body.value, "name": _get_accreditor_name(body)}
        for body in AccreditingBody
    ]
    return jsonify(accreditors), 200


def _get_accreditor_name(body: AccreditingBody) -> str:
    """Get human-readable name for accreditor."""
    names = {
        AccreditingBody.ACCSC: "Accrediting Commission of Career Schools and Colleges",
        AccreditingBody.SACSCOC: "Southern Association of Colleges and Schools Commission on Colleges",
        AccreditingBody.HLC: "Higher Learning Commission",
        AccreditingBody.WASC: "Western Association of Schools and Colleges",
        AccreditingBody.ABHES: "Accrediting Bureau of Health Education Schools",
        AccreditingBody.COE: "Council on Occupational Education",
        AccreditingBody.DEAC: "Distance Education Accrediting Commission",
        AccreditingBody.CUSTOM: "Custom/Other",
    }
    return names.get(body, body.value)
