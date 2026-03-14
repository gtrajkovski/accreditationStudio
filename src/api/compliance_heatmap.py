"""Compliance Heatmap API endpoints.

Provides endpoints for the document × standard compliance matrix visualization.

Endpoints:
- GET /api/institutions/<id>/compliance-heatmap - Get matrix data
- GET /api/institutions/<id>/compliance-heatmap/cell/<doc_id>/<std_id> - Get cell findings
- GET /api/institutions/<id>/compliance-heatmap/document/<doc_id>/summary - Document summary
"""

from flask import Blueprint, request, jsonify

from src.services.compliance_heatmap_service import get_compliance_heatmap_service


# Create Blueprint
compliance_heatmap_bp = Blueprint("compliance_heatmap", __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_compliance_heatmap_bp(workspace_manager):
    """Initialize the compliance heatmap blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return compliance_heatmap_bp


@compliance_heatmap_bp.route(
    "/api/institutions/<institution_id>/compliance-heatmap",
    methods=["GET"],
)
def get_heatmap(institution_id: str):
    """Get complete heatmap data: documents, standards, and compliance matrix.

    Query parameters:
        accreditor: Optional accreditor code filter (default: institution's primary)
        doc_type: Optional document type filter (e.g., 'catalog', 'policy')
        level: Optional standard level filter ('section', 'standard')

    Returns:
        JSON with:
        {
            "documents": [{"id", "title", "doc_type"}, ...],
            "standards": [{"id", "code", "title"}, ...],
            "matrix": [
                {
                    "document_id": "doc_001",
                    "standard_id": "std_001",
                    "status": "compliant",
                    "finding_count": 3,
                    "evidence_count": 5,
                    "avg_confidence": 0.85,
                    "max_severity": "advisory"
                },
                ...
            ],
            "summary": {
                "total_documents": 10,
                "total_standards": 45,
                "compliant_pct": 65.5,
                "partial_pct": 20.0,
                "non_compliant_pct": 5.0,
                "not_evaluated_pct": 9.5
            }
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    accreditor_code = request.args.get("accreditor")
    doc_type_filter = request.args.get("doc_type")
    standard_level = request.args.get("level")

    service = get_compliance_heatmap_service(institution_id, accreditor_code)
    data = service.get_heatmap_data(
        doc_type_filter=doc_type_filter,
        standard_level=standard_level,
    )

    return jsonify({
        "success": True,
        **data,
    })


@compliance_heatmap_bp.route(
    "/api/institutions/<institution_id>/compliance-heatmap/cell/<doc_id>/<std_id>",
    methods=["GET"],
)
def get_cell_findings(institution_id: str, doc_id: str, std_id: str):
    """Get detailed findings for a specific document-standard cell.

    Returns:
        JSON with findings list:
        {
            "findings": [
                {
                    "id": "fnd_001",
                    "status": "compliant",
                    "severity": "advisory",
                    "summary": "...",
                    "recommendation": "...",
                    "confidence": 0.92,
                    "checklist_item": "1.2.3",
                    "evidence": [
                        {"id": "evd_001", "page": 5, "snippet": "..."}
                    ]
                },
                ...
            ],
            "document_id": "doc_001",
            "standard_id": "std_001"
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    service = get_compliance_heatmap_service(institution_id)
    findings = service.get_cell_findings(doc_id, std_id)

    return jsonify({
        "success": True,
        "findings": findings,
        "document_id": doc_id,
        "standard_id": std_id,
        "total": len(findings),
    })


@compliance_heatmap_bp.route(
    "/api/institutions/<institution_id>/compliance-heatmap/document/<doc_id>/summary",
    methods=["GET"],
)
def get_document_summary(institution_id: str, doc_id: str):
    """Get compliance summary for a single document.

    Returns:
        JSON with document compliance summary:
        {
            "document_id": "doc_001",
            "total_findings": 15,
            "compliant": 10,
            "partial": 3,
            "non_compliant": 2,
            "compliance_rate": 66.7
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    service = get_compliance_heatmap_service(institution_id)
    summary = service.get_document_summary(doc_id)

    return jsonify({
        "success": True,
        **summary,
    })
