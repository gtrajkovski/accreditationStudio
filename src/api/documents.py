"""Document upload and management API endpoints.

Provides endpoints for:
- File upload with automatic parsing
- Document text extraction
- PII detection and redaction
- Document search
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime

from src.core.models import Document, DocumentType
from src.importers import parse_document, detect_pii, redact_pii
from src.config import Config
from src.services.change_detection_service import (
    compute_file_hash,
    detect_change,
    record_change,
    store_previous_text,
)
from src.db.connection import get_conn
from src.services import activity_service
from flask import g


# Create Blueprint
documents_bp = Blueprint('documents', __name__)

# Module-level references
_workspace_manager = None

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'pdf', 'docx', 'doc', 'txt', 'md',
    'png', 'jpg', 'jpeg', 'tiff', 'bmp'
}

# Maximum file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


def init_documents_bp(workspace_manager):
    """Initialize the documents blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return documents_bp


def _allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_upload_path(institution_id: str, filename: str) -> Path:
    """Get the path where uploaded file should be stored."""
    workspace_path = _workspace_manager.get_institution_path(institution_id)
    if not workspace_path:
        return None

    originals_dir = workspace_path / "originals"
    originals_dir.mkdir(parents=True, exist_ok=True)

    # Add timestamp to filename to avoid collisions
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    unique_filename = f"{name}_{timestamp}{ext}"

    return originals_dir / secure_filename(unique_filename)


def _require_department_head(f):
    """Helper to check department_head role or higher."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import current_app, g, jsonify
        if not current_app.config.get('AUTH_ENABLED', True):
            return f(*args, **kwargs)
        user = g.get('current_user')
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        role = user.get('role', 'viewer')
        allowed_roles = {'department_head', 'compliance_officer', 'admin', 'owner'}
        if role not in allowed_roles:
            return jsonify({'error': 'Insufficient permissions'}), 403
        return f(*args, **kwargs)
    return decorated


@documents_bp.route('/api/institutions/<institution_id>/documents/upload', methods=['POST'])
@_require_department_head
def upload_document(institution_id: str):
    """Upload a document file with automatic parsing.

    Form Data:
        file: The document file (required)
        doc_type: Document type (optional, will auto-classify if not provided)
        title: Document title (optional, uses filename if not provided)
        description: Document description (optional)

    Returns:
        JSON with created document including extracted text preview.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    # Check for file in request
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not _allowed_file(file.filename):
        return jsonify({
            "error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    # Check file size by reading content length or seeking
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        return jsonify({
            "error": f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"
        }), 400

    # Get upload path
    upload_path = _get_upload_path(institution_id, file.filename)
    if not upload_path:
        return jsonify({"error": "Could not determine upload path"}), 500

    try:
        # Save the file
        file.save(str(upload_path))

        # Compute SHA256 of uploaded file (per CHG-01)
        new_hash = compute_file_hash(str(upload_path))

        # Parse the document
        parsed = parse_document(str(upload_path))

        # Get form data
        doc_type_str = request.form.get('doc_type', 'other')

        # Validate document type
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            doc_type = DocumentType.OTHER

        # Detect PII in extracted text
        pii_matches = detect_pii(parsed.text) if parsed.text else []

        # Create document record
        document = Document(
            doc_type=doc_type,
            file_path=str(upload_path),
            institution_id=institution_id,
            original_filename=file.filename,
            page_count=parsed.page_count,
            extracted_text=redact_pii(parsed.text) if parsed.text else "",
            extracted_structure={
                "file_type": parsed.file_type,
                "word_count": parsed.word_count,
                "has_pii": len(pii_matches) > 0,
                "pii_count": len(pii_matches),
                "parse_errors": parsed.parse_errors,
                "parsed_at": parsed.parsed_at,
            },
        )

        # Add to institution
        institution.documents.append(document)
        institution.updated_at = datetime.now().isoformat()

        _workspace_manager.save_institution(institution)

        # Store the computed hash in extracted_structure for future change detection
        document.extracted_structure["file_sha256"] = new_hash

        # Check if document exists in database for change detection
        try:
            conn = get_conn()
            cursor = conn.execute("SELECT file_sha256 FROM documents WHERE id = ?", (document.id,))
            db_row = cursor.fetchone()

            if db_row and db_row["file_sha256"]:
                # Document exists in DB - detect changes
                old_hash = db_row["file_sha256"]
                if old_hash != new_hash:
                    # Store previous text for diff
                    old_text_path = None
                    if parsed.text:
                        old_text_path = store_previous_text(
                            institution_id, document.id, parsed.text
                        )

                    # Record change event
                    change_id = record_change(
                        document_id=document.id,
                        institution_id=institution_id,
                        old_hash=old_hash,
                        new_hash=new_hash,
                        old_text_path=old_text_path,
                        conn=conn
                    )

                    # Update hash in database
                    conn.execute(
                        "UPDATE documents SET file_sha256 = ?, updated_at = datetime('now') WHERE id = ?",
                        (new_hash, document.id)
                    )
                    conn.commit()
        except Exception as e:
            # Database may not have this document yet - that's okay
            pass

        # Return response with preview
        response = document.to_dict()
        text = parsed.text or ""
        response["text_preview"] = text[:500] + "..." if len(text) > 500 else text
        response["pii_detected"] = [
            {"type": m.pii_type, "confidence": m.confidence}
            for m in pii_matches
        ]
        response["file_sha256"] = new_hash

        # Log activity
        user = g.get('current_user')
        if user:
            activity_service.log_activity(
                user_id=user.get('id'),
                user_name=user.get('name') or user.get('email'),
                institution_id=institution_id,
                action='document.upload',
                entity_type='document',
                entity_id=document.id,
                details=f"Uploaded {file.filename}",
                ip_address=request.remote_addr
            )

        return jsonify(response), 201

    except Exception as e:
        # Clean up file if document creation failed
        if upload_path.exists():
            upload_path.unlink()
        return jsonify({"error": str(e)}), 500


@documents_bp.route('/api/institutions/<institution_id>/documents/<document_id>/text', methods=['GET'])
def get_document_text(institution_id: str, document_id: str):
    """Get the extracted text from a document.

    Query Parameters:
        redact: Set to 'true' to redact PII (default: true)
        full: Set to 'true' to get full text (default: false, returns preview)

    Returns:
        JSON with document text.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    document = None
    for doc in institution.documents:
        if doc.id == document_id:
            document = doc
            break

    if not document:
        return jsonify({"error": "Document not found"}), 404

    redact = request.args.get('redact', 'true').lower() == 'true'
    full = request.args.get('full', 'false').lower() == 'true'

    # Get text from stored extracted_text or re-parse
    text = getattr(document, 'extracted_text', '')

    if not text and document.file_path:
        # Re-parse if needed
        parsed = parse_document(document.file_path)
        text = parsed.text

    if redact:
        text = redact_pii(text)

    if not full and len(text) > 2000:
        text = text[:2000] + "..."

    return jsonify({
        "document_id": document_id,
        "title": document.title,
        "text": text,
        "word_count": len(text.split()),
        "redacted": redact,
        "truncated": not full and len(text) > 2000,
    }), 200


@documents_bp.route('/api/institutions/<institution_id>/documents/<document_id>/reparse', methods=['POST'])
def reparse_document(institution_id: str, document_id: str):
    """Re-parse a document to extract text again.

    Useful if parsing was updated or failed initially.

    Returns:
        JSON with updated document metadata.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    document = None
    for doc in institution.documents:
        if doc.id == document_id:
            document = doc
            break

    if not document:
        return jsonify({"error": "Document not found"}), 404

    if not document.file_path or not Path(document.file_path).exists():
        return jsonify({"error": "Document file not found"}), 404

    try:
        # Re-parse
        parsed = parse_document(document.file_path)

        # Detect PII
        pii_matches = detect_pii(parsed.text) if parsed.text else []

        # Update metadata
        document.metadata = {
            **getattr(document, 'metadata', {}),
            "file_type": parsed.file_type,
            "page_count": parsed.page_count,
            "word_count": parsed.word_count,
            "has_pii": len(pii_matches) > 0,
            "pii_count": len(pii_matches),
            "parse_errors": parsed.parse_errors,
            "parsed_at": parsed.parsed_at,
        }

        # Update extracted text
        document.extracted_text = redact_pii(parsed.text) if parsed.text else ""
        document.updated_at = datetime.now().isoformat()

        _workspace_manager.save_institution(institution)

        return jsonify({
            "success": True,
            "document_id": document_id,
            "word_count": parsed.word_count,
            "page_count": parsed.page_count,
            "pii_count": len(pii_matches),
            "parse_errors": parsed.parse_errors,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@documents_bp.route('/api/institutions/<institution_id>/documents/<document_id>/pii', methods=['GET'])
def get_document_pii(institution_id: str, document_id: str):
    """Get PII detection results for a document.

    Returns:
        JSON with PII matches and summary.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    document = None
    for doc in institution.documents:
        if doc.id == document_id:
            document = doc
            break

    if not document:
        return jsonify({"error": "Document not found"}), 404

    # Get original text (not redacted)
    text = ""
    if document.file_path and Path(document.file_path).exists():
        parsed = parse_document(document.file_path)
        text = parsed.text

    # Detect PII
    matches = detect_pii(text)

    # Build summary
    summary = {}
    for match in matches:
        pii_type = match.pii_type
        if pii_type not in summary:
            summary[pii_type] = {"count": 0, "examples": []}
        summary[pii_type]["count"] += 1
        # Store redacted example (show first/last chars only)
        if len(summary[pii_type]["examples"]) < 3:
            value = match.value
            if len(value) > 4:
                redacted_example = value[:2] + "*" * (len(value) - 4) + value[-2:]
            else:
                redacted_example = "*" * len(value)
            summary[pii_type]["examples"].append(redacted_example)

    return jsonify({
        "document_id": document_id,
        "title": document.title,
        "pii_found": len(matches) > 0,
        "pii_count": len(matches),
        "pii_summary": summary,
        "pii_types": list(summary.keys()),
    }), 200


@documents_bp.route('/api/documents/types', methods=['GET'])
def list_document_types():
    """List all valid document types.

    Returns:
        JSON list of document type values and labels.
    """
    types = []
    for dt in DocumentType:
        types.append({
            "value": dt.value,
            "label": dt.value.replace("_", " ").title(),
        })

    return jsonify(types), 200
