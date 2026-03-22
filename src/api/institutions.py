"""Institution and Program CRUD API endpoints.

Provides endpoints for:
- Institution management (CRUD)
- Program management (CRUD)
- Document upload and management
"""

import json
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify
from datetime import datetime
from pathlib import Path

from src.core.models import (
    Institution,
    Program,
    Document,
    AccreditingBody,
    CredentialLevel,
    Modality,
    DocumentType,
)
from src.db.connection import get_conn


# Create Blueprint
institutions_bp = Blueprint('institutions', __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_institutions_bp(workspace_manager):
    """Initialize the institutions blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return institutions_bp


# Institution endpoints

@institutions_bp.route('/api/institutions', methods=['GET'])
def list_institutions():
    """List all institutions.

    Returns:
        JSON list of institution summaries.
    """
    try:
        institutions = _workspace_manager.list_institutions()
        return jsonify(institutions), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions', methods=['POST'])
def create_institution():
    """Create a new institution.

    Request Body:
        name: Institution name (required)
        accrediting_body: Accrediting body code (required)
        opeid: OPE ID (optional)
        website: Institution website (optional)

    Returns:
        JSON with created institution.
    """
    data = request.get_json() or {}

    name = data.get('name')
    accrediting_body = data.get('accrediting_body')

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not accrediting_body:
        return jsonify({"error": "accrediting_body is required"}), 400

    # Validate accrediting body
    try:
        body = AccreditingBody(accrediting_body)
    except ValueError:
        valid_bodies = [b.value for b in AccreditingBody]
        return jsonify({
            "error": f"Invalid accrediting_body. Valid values: {valid_bodies}"
        }), 400

    # Create institution
    institution = Institution(
        name=name,
        accrediting_body=body,
        opeid=data.get('opeid', ''),
        website=data.get('website', ''),
    )

    try:
        # Create workspace and save
        _workspace_manager.create_institution_workspace(institution)
        _workspace_manager.save_institution(institution)

        return jsonify(institution.to_dict()), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions/<institution_id>', methods=['GET'])
def get_institution(institution_id: str):
    """Get institution details.

    Returns:
        JSON with institution data.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    return jsonify(institution.to_dict()), 200


@institutions_bp.route('/api/institutions/<institution_id>', methods=['PUT'])
def update_institution(institution_id: str):
    """Update institution details.

    Request Body:
        name: Institution name (optional)
        accrediting_body: Accrediting body code (optional)
        opeid: OPE ID (optional)
        website: Institution website (optional)

    Returns:
        JSON with updated institution.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    # Update fields
    if 'name' in data:
        institution.name = data['name']
    if 'accrediting_body' in data:
        try:
            institution.accrediting_body = AccreditingBody(data['accrediting_body'])
        except ValueError:
            valid_bodies = [b.value for b in AccreditingBody]
            return jsonify({
                "error": f"Invalid accrediting_body. Valid values: {valid_bodies}"
            }), 400
    if 'opeid' in data:
        institution.opeid = data['opeid']
    if 'website' in data:
        institution.website = data['website']

    institution.updated_at = datetime.now().isoformat()

    try:
        _workspace_manager.save_institution(institution)
        return jsonify(institution.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions/<institution_id>', methods=['DELETE'])
def delete_institution(institution_id: str):
    """Delete an institution and all its data.

    Returns:
        JSON with success status.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    try:
        _workspace_manager.delete_institution(institution_id)
        return jsonify({
            "success": True,
            "message": "Institution deleted",
            "institution_id": institution_id,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Program endpoints

@institutions_bp.route('/api/institutions/<institution_id>/programs', methods=['GET'])
def list_programs(institution_id: str):
    """List all programs for an institution.

    Returns:
        JSON list of programs.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    programs = [p.to_dict() for p in institution.programs]
    return jsonify(programs), 200


@institutions_bp.route('/api/institutions/<institution_id>/programs', methods=['POST'])
def create_program(institution_id: str):
    """Create a new program.

    Request Body:
        name_en: Program name in English (required)
        name_es: Program name in Spanish (optional)
        credential_level: Credential level (required)
        modality: Delivery modality (optional, default: on_ground)
        duration_months: Program duration in months (optional)
        total_credits: Total credit hours (optional)
        total_cost: Total program cost (optional)
        academic_periods: Number of academic periods (optional)
        licensure_required: Whether licensure is required (optional)
        licensure_exam: Licensure exam name (optional)
        professional_body: Professional licensing body (optional)

    Returns:
        JSON with created program.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    name_en = data.get('name_en')
    credential_level = data.get('credential_level')

    if not name_en:
        return jsonify({"error": "name_en is required"}), 400
    if not credential_level:
        return jsonify({"error": "credential_level is required"}), 400

    # Validate credential level
    try:
        level = CredentialLevel(credential_level)
    except ValueError:
        valid_levels = [l.value for l in CredentialLevel]
        return jsonify({
            "error": f"Invalid credential_level. Valid values: {valid_levels}"
        }), 400

    # Validate modality if provided
    modality = Modality.ON_GROUND
    if 'modality' in data:
        try:
            modality = Modality(data['modality'])
        except ValueError:
            valid_modalities = [m.value for m in Modality]
            return jsonify({
                "error": f"Invalid modality. Valid values: {valid_modalities}"
            }), 400

    # Create program
    program = Program(
        name_en=name_en,
        name_es=data.get('name_es'),
        credential_level=level,
        modality=modality,
        duration_months=data.get('duration_months', 0),
        total_credits=data.get('total_credits', 0),
        total_cost=data.get('total_cost', 0.0),
        academic_periods=data.get('academic_periods', 0),
        cost_per_period=data.get('cost_per_period', 0.0),
        book_cost=data.get('book_cost', 0.0),
        licensure_required=data.get('licensure_required', False),
        licensure_exam=data.get('licensure_exam'),
        professional_body=data.get('professional_body'),
        programmatic_accreditor=data.get('programmatic_accreditor'),
    )

    # Add to institution
    institution.programs.append(program)
    institution.updated_at = datetime.now().isoformat()

    try:
        _workspace_manager.save_institution(institution)
        return jsonify(program.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions/<institution_id>/programs/<program_id>', methods=['GET'])
def get_program(institution_id: str, program_id: str):
    """Get program details.

    Returns:
        JSON with program data.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    program = _find_program(institution, program_id)
    if not program:
        return jsonify({"error": "Program not found"}), 404

    return jsonify(program.to_dict()), 200


@institutions_bp.route('/api/institutions/<institution_id>/programs/<program_id>', methods=['PUT'])
def update_program(institution_id: str, program_id: str):
    """Update program details.

    Request Body:
        name_en: Program name in English (optional)
        name_es: Program name in Spanish (optional)
        credential_level: Credential level (optional)
        modality: Delivery modality (optional)
        duration_months: Program duration in months (optional)
        total_credits: Total credit hours (optional)
        total_cost: Total program cost (optional)
        academic_periods: Number of academic periods (optional)
        licensure_required: Whether licensure is required (optional)
        licensure_exam: Licensure exam name (optional)
        professional_body: Professional licensing body (optional)

    Returns:
        JSON with updated program.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    program = _find_program(institution, program_id)
    if not program:
        return jsonify({"error": "Program not found"}), 404

    data = request.get_json() or {}

    # Update fields
    if 'name_en' in data:
        program.name_en = data['name_en']
    if 'name_es' in data:
        program.name_es = data['name_es']
    if 'credential_level' in data:
        try:
            program.credential_level = CredentialLevel(data['credential_level'])
        except ValueError:
            valid_levels = [l.value for l in CredentialLevel]
            return jsonify({
                "error": f"Invalid credential_level. Valid values: {valid_levels}"
            }), 400
    if 'modality' in data:
        try:
            program.modality = Modality(data['modality'])
        except ValueError:
            valid_modalities = [m.value for m in Modality]
            return jsonify({
                "error": f"Invalid modality. Valid values: {valid_modalities}"
            }), 400
    if 'duration_months' in data:
        program.duration_months = data['duration_months']
    if 'total_credits' in data:
        program.total_credits = data['total_credits']
    if 'total_cost' in data:
        program.total_cost = data['total_cost']
    if 'academic_periods' in data:
        program.academic_periods = data['academic_periods']
    if 'cost_per_period' in data:
        program.cost_per_period = data['cost_per_period']
    if 'book_cost' in data:
        program.book_cost = data['book_cost']
    if 'licensure_required' in data:
        program.licensure_required = data['licensure_required']
    if 'licensure_exam' in data:
        program.licensure_exam = data['licensure_exam']
    if 'professional_body' in data:
        program.professional_body = data['professional_body']
    if 'programmatic_accreditor' in data:
        program.programmatic_accreditor = data['programmatic_accreditor']

    program.updated_at = datetime.now().isoformat()
    institution.updated_at = datetime.now().isoformat()

    try:
        _workspace_manager.save_institution(institution)
        return jsonify(program.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions/<institution_id>/programs/<program_id>', methods=['DELETE'])
def delete_program(institution_id: str, program_id: str):
    """Delete a program.

    Returns:
        JSON with success status.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    program = _find_program(institution, program_id)
    if not program:
        return jsonify({"error": "Program not found"}), 404

    institution.programs = [p for p in institution.programs if p.id != program_id]
    institution.updated_at = datetime.now().isoformat()

    try:
        _workspace_manager.save_institution(institution)
        return jsonify({
            "success": True,
            "message": "Program deleted",
            "program_id": program_id,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Document endpoints

@institutions_bp.route('/api/institutions/<institution_id>/documents', methods=['GET'])
def list_documents(institution_id: str):
    """List all documents for an institution.

    Query Parameters:
        doc_type: Filter by document type (optional)

    Returns:
        JSON list of documents.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    documents = institution.documents

    # Filter by type if specified
    doc_type = request.args.get('doc_type')
    if doc_type:
        documents = [d for d in documents if d.doc_type.value == doc_type]

    return jsonify([d.to_dict() for d in documents]), 200


@institutions_bp.route('/api/institutions/<institution_id>/documents', methods=['POST'])
def create_document(institution_id: str):
    """Create a document record (metadata only, file upload separate).

    Request Body:
        title: Document title (required)
        doc_type: Document type (required)
        file_path: Path to uploaded file (optional)
        description: Document description (optional)

    Returns:
        JSON with created document.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    title = data.get('title')
    doc_type = data.get('doc_type')

    if not title:
        return jsonify({"error": "title is required"}), 400
    if not doc_type:
        return jsonify({"error": "doc_type is required"}), 400

    # Validate document type
    try:
        dtype = DocumentType(doc_type)
    except ValueError:
        valid_types = [t.value for t in DocumentType]
        return jsonify({
            "error": f"Invalid doc_type. Valid values: {valid_types}"
        }), 400

    # Create document
    document = Document(
        title=title,
        doc_type=dtype,
        file_path=data.get('file_path', ''),
        description=data.get('description', ''),
        institution_id=institution_id,
    )

    # Add to institution
    institution.documents.append(document)
    institution.updated_at = datetime.now().isoformat()

    try:
        _workspace_manager.save_institution(institution)
        return jsonify(document.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions/<institution_id>/documents/<document_id>', methods=['GET'])
def get_document(institution_id: str, document_id: str):
    """Get document details.

    Returns:
        JSON with document data.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    document = _find_document(institution, document_id)
    if not document:
        return jsonify({"error": "Document not found"}), 404

    return jsonify(document.to_dict()), 200


@institutions_bp.route('/api/institutions/<institution_id>/documents/<document_id>', methods=['DELETE'])
def delete_document(institution_id: str, document_id: str):
    """Delete a document.

    Returns:
        JSON with success status.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    document = _find_document(institution, document_id)
    if not document:
        return jsonify({"error": "Document not found"}), 404

    institution.documents = [d for d in institution.documents if d.id != document_id]
    institution.updated_at = datetime.now().isoformat()

    try:
        _workspace_manager.save_institution(institution)
        return jsonify({
            "success": True,
            "message": "Document deleted",
            "document_id": document_id,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Truth Index endpoints

@institutions_bp.route('/api/institutions/<institution_id>/truth-index', methods=['GET'])
def get_truth_index(institution_id: str):
    """Get the Single Source of Truth index for an institution.

    Returns:
        JSON with truth index data.
    """
    truth_index = _workspace_manager.get_truth_index(institution_id)
    if truth_index is None:
        return jsonify({"error": "Institution not found"}), 404

    return jsonify(truth_index), 200


@institutions_bp.route('/api/institutions/<institution_id>/truth-index', methods=['PATCH'])
def update_truth_index(institution_id: str):
    """Update the truth index.

    Request Body:
        updates: Dictionary of updates to apply
        path: Optional dot-separated path for nested updates

    Returns:
        JSON with updated truth index.
    """
    data = request.get_json() or {}

    updates = data.get('updates', {})
    path = data.get('path', [])

    if isinstance(path, str):
        path = path.split('.') if path else []

    try:
        _workspace_manager.update_truth_index(institution_id, updates, path)
        truth_index = _workspace_manager.get_truth_index(institution_id)
        return jsonify(truth_index), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Checkpoint endpoints (for packet export override flow)

@institutions_bp.route('/api/institutions/<institution_id>/checkpoints', methods=['POST'])
def create_checkpoint(institution_id: str):
    """Create a checkpoint for export override.

    Request Body:
        packet_id: The packet requiring override (required)
        type: Checkpoint type, e.g. 'finalize_submission' (required)
        context: Additional context data (optional)

    Returns:
        JSON with checkpoint_id and details.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    packet_id = data.get('packet_id')
    checkpoint_type = data.get('type', 'finalize_submission')
    context = data.get('context', {})

    if not packet_id:
        return jsonify({"error": "packet_id is required"}), 400

    try:
        conn = get_conn()

        # Generate checkpoint ID
        checkpoint_id = f"cp_{packet_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now = datetime.now().isoformat()

        # Build reason from context
        override_reason = context.get('override_reason', 'Manual override requested')
        validation = context.get('validation', {})

        reasons = []
        if validation.get('missing_standards'):
            reasons.append(f"{len(validation['missing_standards'])} standards lack evidence")
        if validation.get('blocking_findings'):
            reasons.append(f"{len(validation['blocking_findings'])} critical findings unresolved")

        reason = "; ".join(reasons) if reasons else override_reason

        # Store context as JSON notes
        import json
        notes = json.dumps({
            "packet_id": packet_id,
            "validation": validation,
            "override_reason": override_reason,
            "created_at": now,
        })

        conn.execute("""
            INSERT INTO human_checkpoints
            (id, institution_id, checkpoint_type, status, requested_by, reason, notes, created_at)
            VALUES (?, ?, ?, 'pending', 'user', ?, ?, ?)
        """, (checkpoint_id, institution_id, checkpoint_type, reason, notes, now))
        conn.commit()

        return jsonify({
            "checkpoint_id": checkpoint_id,
            "checkpoint_type": checkpoint_type,
            "status": "pending",
            "reason": reason,
            "created_at": now,
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions/<institution_id>/checkpoints/<checkpoint_id>', methods=['PATCH'])
def update_checkpoint(institution_id: str, checkpoint_id: str):
    """Update/resolve a checkpoint.

    Request Body:
        status: New status ('resolved', 'approved', 'rejected') (required)
        resolution: Resolution reason/notes (optional)

    Returns:
        JSON with updated checkpoint.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    status = data.get('status')
    resolution = data.get('resolution', '')

    if not status:
        return jsonify({"error": "status is required"}), 400

    if status not in ('resolved', 'approved', 'rejected', 'pending'):
        return jsonify({"error": "Invalid status. Valid values: resolved, approved, rejected, pending"}), 400

    try:
        conn = get_conn()

        # Verify checkpoint exists and belongs to this institution
        cursor = conn.execute("""
            SELECT id, institution_id, status
            FROM human_checkpoints
            WHERE id = ?
        """, (checkpoint_id,))

        checkpoint = cursor.fetchone()
        if not checkpoint:
            return jsonify({"error": "Checkpoint not found"}), 404

        if checkpoint["institution_id"] != institution_id:
            return jsonify({"error": "Checkpoint does not belong to this institution"}), 403

        now = datetime.now().isoformat()

        # Update checkpoint
        conn.execute("""
            UPDATE human_checkpoints
            SET status = ?, resolved_by = 'user', resolved_at = ?, reason = COALESCE(?, reason)
            WHERE id = ?
        """, (status, now if status in ('resolved', 'approved') else None, resolution or None, checkpoint_id))
        conn.commit()

        return jsonify({
            "checkpoint_id": checkpoint_id,
            "status": status,
            "resolution": resolution,
            "resolved_at": now if status in ('resolved', 'approved') else None,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@institutions_bp.route('/api/institutions/<institution_id>/checkpoints/<checkpoint_id>', methods=['GET'])
def get_checkpoint(institution_id: str, checkpoint_id: str):
    """Get checkpoint details.

    Returns:
        JSON with checkpoint data.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    try:
        conn = get_conn()

        cursor = conn.execute("""
            SELECT id, institution_id, checkpoint_type, status, requested_by,
                   reason, notes, created_at, resolved_by, resolved_at
            FROM human_checkpoints
            WHERE id = ?
        """, (checkpoint_id,))

        checkpoint = cursor.fetchone()
        if not checkpoint:
            return jsonify({"error": "Checkpoint not found"}), 404

        if checkpoint["institution_id"] != institution_id:
            return jsonify({"error": "Checkpoint does not belong to this institution"}), 403

        return jsonify({
            "checkpoint_id": checkpoint["id"],
            "institution_id": checkpoint["institution_id"],
            "checkpoint_type": checkpoint["checkpoint_type"],
            "status": checkpoint["status"],
            "requested_by": checkpoint["requested_by"],
            "reason": checkpoint["reason"],
            "notes": checkpoint["notes"],
            "created_at": checkpoint["created_at"],
            "resolved_by": checkpoint["resolved_by"],
            "resolved_at": checkpoint["resolved_at"],
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Helper functions

def _find_program(institution: Institution, program_id: str) -> Optional[Program]:
    """Find a program by ID."""
    for program in institution.programs:
        if program.id == program_id:
            return program
    return None


def _find_document(institution: Institution, document_id: str) -> Optional[Document]:
    """Find a document by ID."""
    for document in institution.documents:
        if document.id == document_id:
            return document
    return None
