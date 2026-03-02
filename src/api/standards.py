"""Standards Library API endpoints.

Provides endpoints for:
- Standards library management (CRUD)
- Section navigation
- Checklist items retrieval
"""

from typing import Optional
from flask import Blueprint, request, jsonify

from src.core.models import (
    AccreditingBody,
    DocumentType,
    StandardsLibrary,
    StandardsSection,
    ChecklistItem,
    now_iso,
)


# Create Blueprint
standards_bp = Blueprint('standards', __name__)

# Module-level references (set during initialization)
_standards_store = None


def init_standards_bp(standards_store):
    """Initialize the standards blueprint with dependencies.

    Args:
        standards_store: StandardsStore instance for persistence.
    """
    global _standards_store
    _standards_store = standards_store
    return standards_bp


# List and get endpoints

@standards_bp.route('/api/standards', methods=['GET'])
def list_standards():
    """List all standards libraries.

    Query Parameters:
        accreditor: Filter by accrediting body (optional)

    Returns:
        JSON list of standards libraries.
    """
    try:
        accreditor_filter = request.args.get('accreditor')

        if accreditor_filter:
            try:
                accreditor = AccreditingBody(accreditor_filter)
                libraries = _standards_store.list_by_accreditor(accreditor)
            except ValueError:
                valid = [b.value for b in AccreditingBody]
                return jsonify({
                    "error": f"Invalid accreditor. Valid values: {valid}"
                }), 400
        else:
            libraries = _standards_store.list_all()

        # Return summary info only
        result = []
        for lib in libraries:
            result.append({
                "id": lib.id,
                "accrediting_body": lib.accrediting_body.value if isinstance(lib.accrediting_body, AccreditingBody) else lib.accrediting_body,
                "name": lib.name,
                "version": lib.version,
                "effective_date": lib.effective_date,
                "is_system_preset": lib.is_system_preset,
                "section_count": len(lib.sections),
                "checklist_count": len(lib.checklist_items),
            })

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@standards_bp.route('/api/standards/<library_id>', methods=['GET'])
def get_standards(library_id: str):
    """Get a standards library by ID.

    Returns:
        JSON with full standards library data.
    """
    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    return jsonify(library.to_dict()), 200


@standards_bp.route('/api/standards/accreditor/<accreditor>', methods=['GET'])
def get_default_for_accreditor(accreditor: str):
    """Get the default (preset) standards library for an accreditor.

    Returns:
        JSON with standards library data.
    """
    try:
        body = AccreditingBody(accreditor)
    except ValueError:
        valid = [b.value for b in AccreditingBody]
        return jsonify({
            "error": f"Invalid accreditor. Valid values: {valid}"
        }), 400

    library = _standards_store.get_default(body)
    if not library:
        return jsonify({
            "error": f"No default standards library for {accreditor}"
        }), 404

    return jsonify(library.to_dict()), 200


# Section endpoints

@standards_bp.route('/api/standards/<library_id>/sections', methods=['GET'])
def list_sections(library_id: str):
    """List sections in a standards library.

    Query Parameters:
        parent_id: Filter by parent section ID (optional, empty for top-level)

    Returns:
        JSON list of sections.
    """
    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    parent_id = request.args.get('parent_id', '')

    if parent_id:
        sections = _standards_store.get_child_sections(library_id, parent_id)
    else:
        # Return top-level sections
        sections = [s for s in library.sections if not s.parent_section]

    return jsonify([s.to_dict() for s in sections]), 200


@standards_bp.route('/api/standards/<library_id>/sections/<section_id>', methods=['GET'])
def get_section(library_id: str, section_id: str):
    """Get a specific section.

    Returns:
        JSON with section data.
    """
    section = _standards_store.get_section(library_id, section_id)
    if not section:
        return jsonify({"error": "Section not found"}), 404

    return jsonify(section.to_dict()), 200


@standards_bp.route('/api/standards/<library_id>/sections/by-number/<path:number>', methods=['GET'])
def get_section_by_number(library_id: str, number: str):
    """Get a section by its number (e.g., "I.A.1").

    Returns:
        JSON with section data.
    """
    section = _standards_store.get_section_by_number(library_id, number)
    if not section:
        return jsonify({"error": f"Section {number} not found"}), 404

    return jsonify(section.to_dict()), 200


@standards_bp.route('/api/standards/<library_id>/sections/tree', methods=['GET'])
def get_section_tree(library_id: str):
    """Get the full section hierarchy as a tree.

    Returns:
        JSON with nested section structure.
    """
    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    # Build tree structure
    sections_by_id = {s.id: s.to_dict() for s in library.sections}
    for s in sections_by_id.values():
        s['children'] = []

    tree = []
    for section in library.sections:
        section_dict = sections_by_id[section.id]
        if section.parent_section and section.parent_section in sections_by_id:
            sections_by_id[section.parent_section]['children'].append(section_dict)
        else:
            tree.append(section_dict)

    return jsonify(tree), 200


# Checklist endpoints

@standards_bp.route('/api/standards/<library_id>/checklist', methods=['GET'])
def list_checklist_items(library_id: str):
    """List checklist items in a standards library.

    Query Parameters:
        category: Filter by category (optional)
        doc_type: Filter by applicable document type (optional)

    Returns:
        JSON list of checklist items.
    """
    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    category = request.args.get('category')
    doc_type = request.args.get('doc_type')

    if doc_type:
        try:
            dtype = DocumentType(doc_type)
            items = _standards_store.get_items_for_document_type(library_id, dtype)
        except ValueError:
            valid = [t.value for t in DocumentType]
            return jsonify({
                "error": f"Invalid doc_type. Valid values: {valid}"
            }), 400
    elif category:
        items = _standards_store.get_checklist_items(library_id, category)
    else:
        items = library.checklist_items

    return jsonify([item.to_dict() for item in items]), 200


@standards_bp.route('/api/standards/<library_id>/checklist/categories', methods=['GET'])
def list_checklist_categories(library_id: str):
    """List unique categories in the checklist.

    Returns:
        JSON list of category names.
    """
    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    categories = sorted(set(item.category for item in library.checklist_items))
    return jsonify(categories), 200


# Create and update endpoints

@standards_bp.route('/api/standards', methods=['POST'])
def create_standards():
    """Create a new custom standards library.

    Request Body:
        accrediting_body: Accrediting body code (required)
        name: Library name (required)
        version: Version string (optional)
        effective_date: Effective date (optional)
        sections: List of section objects (optional)
        checklist_items: List of checklist item objects (optional)
        full_text: Full standards document text (optional)

    Returns:
        JSON with created library.
    """
    data = request.get_json() or {}

    accreditor = data.get('accrediting_body')
    name = data.get('name')

    if not accreditor:
        return jsonify({"error": "accrediting_body is required"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400

    # Validate accrediting body
    try:
        body = AccreditingBody(accreditor)
    except ValueError:
        valid = [b.value for b in AccreditingBody]
        return jsonify({
            "error": f"Invalid accrediting_body. Valid values: {valid}"
        }), 400

    # Parse sections
    sections = []
    for s_data in data.get('sections', []):
        sections.append(StandardsSection.from_dict(s_data))

    # Parse checklist items
    checklist_items = []
    for c_data in data.get('checklist_items', []):
        checklist_items.append(ChecklistItem.from_dict(c_data))

    # Create library
    library = StandardsLibrary(
        accrediting_body=body,
        name=name,
        version=data.get('version', ''),
        effective_date=data.get('effective_date', ''),
        sections=sections,
        checklist_items=checklist_items,
        full_text=data.get('full_text', ''),
        is_system_preset=False,
    )

    try:
        _standards_store.save(library)
        return jsonify(library.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@standards_bp.route('/api/standards/<library_id>', methods=['PUT'])
def update_standards(library_id: str):
    """Update a standards library.

    System presets cannot be modified.

    Request Body:
        name: Library name (optional)
        version: Version string (optional)
        effective_date: Effective date (optional)
        sections: List of section objects (optional)
        checklist_items: List of checklist item objects (optional)
        full_text: Full standards document text (optional)

    Returns:
        JSON with updated library.
    """
    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    if library.is_system_preset:
        return jsonify({
            "error": "Cannot modify system preset. Duplicate it first."
        }), 403

    data = request.get_json() or {}

    # Update fields
    if 'name' in data:
        library.name = data['name']
    if 'version' in data:
        library.version = data['version']
    if 'effective_date' in data:
        library.effective_date = data['effective_date']
    if 'full_text' in data:
        library.full_text = data['full_text']

    # Replace sections if provided
    if 'sections' in data:
        library.sections = [StandardsSection.from_dict(s) for s in data['sections']]

    # Replace checklist items if provided
    if 'checklist_items' in data:
        library.checklist_items = [ChecklistItem.from_dict(c) for c in data['checklist_items']]

    library.updated_at = now_iso()

    try:
        _standards_store.save(library)
        return jsonify(library.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@standards_bp.route('/api/standards/<library_id>', methods=['DELETE'])
def delete_standards(library_id: str):
    """Delete a standards library.

    System presets cannot be deleted.

    Returns:
        JSON with success status.
    """
    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    if library.is_system_preset:
        return jsonify({
            "error": "Cannot delete system preset"
        }), 403

    try:
        _standards_store.delete(library_id)
        return jsonify({
            "success": True,
            "message": "Standards library deleted",
            "library_id": library_id,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@standards_bp.route('/api/standards/<library_id>/duplicate', methods=['POST'])
def duplicate_standards(library_id: str):
    """Duplicate a standards library.

    Useful for customizing system presets.

    Request Body:
        name: Name for the new library (required)

    Returns:
        JSON with new library.
    """
    data = request.get_json() or {}
    name = data.get('name')

    if not name:
        return jsonify({"error": "name is required"}), 400

    library = _standards_store.load(library_id)
    if not library:
        return jsonify({"error": "Standards library not found"}), 404

    try:
        new_library = _standards_store.duplicate(library_id, name)
        if new_library:
            return jsonify(new_library.to_dict()), 201
        else:
            return jsonify({"error": "Failed to duplicate library"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
