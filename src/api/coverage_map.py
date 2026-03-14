"""Evidence Coverage Map API endpoints.

Provides endpoints for the D3.js treemap visualization of evidence coverage
across accreditation standards.

Endpoints:
- GET /api/institutions/<id>/coverage-map - Get coverage tree data
- GET /api/institutions/<id>/coverage-map/summary - Get summary stats
- GET /api/institutions/<id>/coverage-map/standard/<std_id>/evidence - Get evidence for standard
"""

from flask import Blueprint, request, jsonify

from src.services.coverage_map_service import get_coverage_map_service


# Create Blueprint
coverage_map_bp = Blueprint("coverage_map", __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_coverage_map_bp(workspace_manager):
    """Initialize the coverage map blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return coverage_map_bp


@coverage_map_bp.route("/api/institutions/<institution_id>/coverage-map", methods=["GET"])
def get_coverage_tree(institution_id: str):
    """Get the evidence coverage tree for treemap visualization.

    Query parameters:
        accreditor: Optional accreditor code filter (default: institution's primary)

    Returns:
        JSON with hierarchical tree structure:
        {
            "id": "accreditor_id",
            "name": "ACCSC",
            "code": "ACCSC",
            "level": "accreditor",
            "coverage_pct": 75.5,
            "children": [
                {
                    "id": "std_001",
                    "name": "Mission",
                    "code": "1.0",
                    "level": "section",
                    "coverage_pct": 80.0,
                    "children": [...] or "value": 5
                },
                ...
            ]
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    accreditor_code = request.args.get("accreditor")

    service = get_coverage_map_service(institution_id, accreditor_code)
    tree = service.get_coverage_tree()

    return jsonify({
        "success": True,
        "tree": tree,
    })


@coverage_map_bp.route("/api/institutions/<institution_id>/coverage-map/summary", methods=["GET"])
def get_coverage_summary(institution_id: str):
    """Get summary statistics for the coverage map.

    Returns:
        JSON with summary stats:
        {
            "total_standards": 45,
            "covered_standards": 30,
            "coverage_pct": 66.7,
            "findings_by_status": {"compliant": 25, "partial": 10, "non_compliant": 5},
            "accreditor_code": "ACCSC",
            "accreditor_name": "Accrediting Commission of Career Schools and Colleges"
        }
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    accreditor_code = request.args.get("accreditor")

    service = get_coverage_map_service(institution_id, accreditor_code)
    stats = service.get_summary_stats()

    return jsonify({
        "success": True,
        **stats,
    })


@coverage_map_bp.route(
    "/api/institutions/<institution_id>/coverage-map/standard/<standard_id>/evidence",
    methods=["GET"],
)
def get_standard_evidence(institution_id: str, standard_id: str):
    """Get all evidence items linked to a specific standard.

    Returns:
        JSON with list of evidence items:
        {
            "evidence": [
                {
                    "id": "evd_001",
                    "type": "finding",
                    "title": "Enrollment Policy Review",
                    "status": "compliant",
                    "confidence": 0.95,
                    "document_id": "doc_001",
                    "page": 12
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

    service = get_coverage_map_service(institution_id)
    evidence = service.get_standard_evidence(standard_id)

    return jsonify({
        "success": True,
        "evidence": evidence,
        "total": len(evidence),
    })


@coverage_map_bp.route("/api/institutions/<institution_id>/coverage-map/gaps", methods=["GET"])
def get_coverage_gaps(institution_id: str):
    """Get standards with poor or missing coverage.

    Query parameters:
        threshold: Coverage threshold to consider as gap (default: 50)
        limit: Maximum gaps to return (default: 20)

    Returns:
        JSON with list of gap standards.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    threshold = request.args.get("threshold", 50, type=float)
    limit = request.args.get("limit", 20, type=int)
    accreditor_code = request.args.get("accreditor")

    service = get_coverage_map_service(institution_id, accreditor_code)
    tree = service.get_coverage_tree()

    # Collect gaps from tree
    gaps = []

    def collect_gaps(node, parent_path=""):
        path = f"{parent_path}/{node['code']}" if parent_path else node["code"]

        # Only check leaf nodes or nodes with low coverage
        if "children" not in node:
            if node["coverage_pct"] < threshold:
                gaps.append({
                    "id": node["id"],
                    "code": node["code"],
                    "name": node["name"],
                    "path": path,
                    "coverage_pct": node["coverage_pct"],
                    "evidence_count": node.get("evidence_count", 0),
                    "level": node["level"],
                })
        else:
            # Also include sections with low coverage
            if node["coverage_pct"] < threshold and node["level"] == "section":
                gaps.append({
                    "id": node["id"],
                    "code": node["code"],
                    "name": node["name"],
                    "path": path,
                    "coverage_pct": node["coverage_pct"],
                    "evidence_count": node.get("evidence_count", 0),
                    "level": node["level"],
                })

            for child in node.get("children", []):
                collect_gaps(child, path)

    collect_gaps(tree)

    # Sort by coverage (lowest first) and limit
    gaps.sort(key=lambda g: g["coverage_pct"])
    gaps = gaps[:limit]

    return jsonify({
        "success": True,
        "gaps": gaps,
        "total": len(gaps),
        "threshold": threshold,
    })
