"""Evidence Highlighting API endpoints.

Provides endpoints for the document viewer with evidence highlighting.

Endpoints:
- GET /api/institutions/<id>/documents/<doc_id>/text - Get document text by pages
- GET /api/institutions/<id>/documents/<doc_id>/evidence - Get evidence highlights
- GET /api/institutions/<id>/documents/<doc_id>/standards - Get linked standards
"""

from flask import Blueprint, request, jsonify

from src.services.evidence_highlighting_service import get_evidence_highlighting_service


# Create Blueprint
evidence_highlighting_bp = Blueprint("evidence_highlighting", __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_evidence_highlighting_bp(workspace_manager):
    """Initialize the evidence highlighting blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return evidence_highlighting_bp


@evidence_highlighting_bp.route(
    "/api/institutions/<institution_id>/documents/<document_id>/text",
    methods=["GET"],
)
def get_document_text(institution_id: str, document_id: str):
    """Get document text content organized by pages.

    Query parameters:
        page: Optional page number to return (default: all pages)

    Returns:
        JSON with document text:
        {
            "document_id": "doc_001",
            "title": "Student Catalog",
            "total_pages": 45,
            "pages": [
                {
                    "page_number": 1,
                    "text": "...",
                    "section_header": "Table of Contents"
                },
                ...
            ]
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    service = get_evidence_highlighting_service(institution_id)
    result = service.get_document_text(document_id)

    if "error" in result:
        return jsonify(result), 404

    # Optional page filter
    page = request.args.get("page", type=int)
    if page is not None:
        filtered_pages = [p for p in result["pages"] if p["page_number"] == page]
        result["pages"] = filtered_pages

    return jsonify({
        "success": True,
        **result,
    })


@evidence_highlighting_bp.route(
    "/api/institutions/<institution_id>/documents/<document_id>/evidence",
    methods=["GET"],
)
def get_document_evidence(institution_id: str, document_id: str):
    """Get all evidence highlights for a document.

    Query parameters:
        page: Optional page number filter
        standard_id: Optional standard ID filter

    Returns:
        JSON with evidence items:
        {
            "document_id": "doc_001",
            "evidence": [
                {
                    "id": "evd_001",
                    "finding_id": "fnd_001",
                    "page": 12,
                    "snippet_text": "The institution maintains...",
                    "start_offset": 1234,
                    "end_offset": 1456,
                    "status": "compliant",
                    "confidence": 0.95,
                    "finding_summary": "Admission policy review",
                    "standards": [
                        {"id": "std_001", "code": "I.A.1", "title": "Mission", "source": "accreditor"}
                    ]
                },
                ...
            ],
            "total": 5
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    page = request.args.get("page", type=int)
    standard_id = request.args.get("standard_id")

    service = get_evidence_highlighting_service(institution_id)
    evidence = service.get_document_evidence(document_id, page)

    # Filter by standard if specified
    if standard_id:
        evidence = [
            e for e in evidence
            if any(s["id"] == standard_id for s in e.get("standards", []))
        ]

    return jsonify({
        "success": True,
        "document_id": document_id,
        "evidence": evidence,
        "total": len(evidence),
    })


@evidence_highlighting_bp.route(
    "/api/institutions/<institution_id>/documents/<document_id>/standards",
    methods=["GET"],
)
def get_document_standards(institution_id: str, document_id: str):
    """Get all standards linked to evidence in this document.

    Returns:
        JSON with standards list:
        {
            "document_id": "doc_001",
            "standards": [
                {
                    "id": "std_001",
                    "code": "I.A.1",
                    "title": "Mission Statement",
                    "accreditor_code": "ACCSC",
                    "evidence_count": 3,
                    "source": "accreditor"
                },
                ...
            ],
            "total": 10,
            "by_source": {"accreditor": 5, "federal": 3, "state": 2}
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    service = get_evidence_highlighting_service(institution_id)
    standards = service.get_document_standards(document_id)

    # Compute by_source counts
    by_source = {}
    for std in standards:
        source = std.get("source", "accreditor")
        by_source[source] = by_source.get(source, 0) + 1

    return jsonify({
        "success": True,
        "document_id": document_id,
        "standards": standards,
        "total": len(standards),
        "by_source": by_source,
    })


@evidence_highlighting_bp.route(
    "/api/institutions/<institution_id>/documents/<document_id>/evidence/<evidence_id>/position",
    methods=["POST"],
)
def compute_evidence_position(institution_id: str, document_id: str, evidence_id: str):
    """Compute and optionally store position for an evidence snippet.

    Request body:
        {
            "page_text": "Full text of the page...",
            "snippet": "The snippet to find...",
            "store": false  // Optional: store the computed position
        }

    Returns:
        JSON with computed position:
        {
            "start_offset": 1234,
            "end_offset": 1456,
            "found": true
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}
    page_text = data.get("page_text", "")
    snippet = data.get("snippet", "")
    store = data.get("store", False)

    if not page_text or not snippet:
        return jsonify({"error": "page_text and snippet are required"}), 400

    service = get_evidence_highlighting_service(institution_id)
    position = service.find_snippet_position(page_text, snippet)

    if position:
        start, end = position

        # Optionally store the computed position
        if store:
            from src.db.connection import get_conn
            conn = get_conn()
            conn.execute(
                """
                UPDATE evidence_refs
                SET start_offset = ?, end_offset = ?
                WHERE id = ?
                """,
                (start, end, evidence_id),
            )
            conn.commit()

        return jsonify({
            "success": True,
            "start_offset": start,
            "end_offset": end,
            "found": True,
        })
    else:
        return jsonify({
            "success": True,
            "start_offset": None,
            "end_offset": None,
            "found": False,
        })
