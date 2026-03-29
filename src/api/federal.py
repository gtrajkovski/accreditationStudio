"""Federal regulations API blueprint."""

from flask import Blueprint, jsonify, request
from src.regulatory.federal.bundles import FederalBundleService
from src.core.workspace import WorkspaceManager

federal_bp = Blueprint("federal", __name__, url_prefix="/api/federal")

_workspace_manager = None


def init_federal_bp(workspace_manager: WorkspaceManager):
    """Initialize the federal blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


@federal_bp.route("/bundles", methods=["GET"])
def list_bundles():
    """List all federal regulation bundles.

    Returns summary information for each bundle including ID, name,
    description, requirement count, and applicability rule.
    """
    bundles = FederalBundleService.list_bundles()
    return jsonify({
        "bundles": bundles,
        "count": len(bundles),
        "total_requirements": FederalBundleService.get_total_requirements(),
    })


@federal_bp.route("/bundles/<bundle_id>", methods=["GET"])
def get_bundle(bundle_id: str):
    """Get full bundle details including all requirements.

    Args:
        bundle_id: The bundle identifier (e.g., 'title_iv', 'ferpa')
    """
    bundle = FederalBundleService.get_bundle(bundle_id)
    if not bundle:
        return jsonify({"error": "Bundle not found"}), 404
    return jsonify(bundle.to_dict())


@federal_bp.route("/bundles/<bundle_id>/requirements/<requirement_id>", methods=["GET"])
def get_requirement(bundle_id: str, requirement_id: str):
    """Get a specific requirement by ID.

    Args:
        bundle_id: The bundle identifier
        requirement_id: The requirement identifier
    """
    result = FederalBundleService.get_requirement(bundle_id, requirement_id)
    if not result:
        return jsonify({"error": "Requirement not found"}), 404
    return jsonify(result)


@federal_bp.route("/applicable/<institution_id>", methods=["GET"])
def get_applicable_bundles(institution_id: str):
    """Get bundles applicable to a specific institution.

    Evaluates applicability rules against the institution's profile
    (Title IV eligibility, serves minors, for-profit status, etc.).

    Args:
        institution_id: The institution identifier
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    # Build profile from institution attributes
    profile = {
        "title_iv_eligible": getattr(institution, "title_iv_eligible", True),
        "modality": getattr(institution, "modality", "ground"),
        "serves_minors": getattr(institution, "serves_minors", False),
        "for_profit": getattr(institution, "for_profit", False),
        "offers_certificates": getattr(institution, "offers_certificates", False),
    }

    bundles = FederalBundleService.get_applicable_bundles(profile)

    # Calculate total requirements for applicable bundles
    total_requirements = sum(len(b.requirements) for b in bundles)

    return jsonify({
        "institution_id": institution_id,
        "institution_name": institution.name,
        "profile": profile,
        "applicable_bundles": [b.to_dict() for b in bundles],
        "bundle_count": len(bundles),
        "total_requirements": total_requirements,
    })


@federal_bp.route("/search", methods=["GET"])
def search_requirements():
    """Search across all bundles for matching requirements.

    Query parameter 'q' is required and searches against:
    - Requirement title
    - Requirement description
    - Citation reference
    """
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    if len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400

    results = FederalBundleService.search_requirements(query)
    return jsonify({
        "query": query,
        "results": results,
        "count": len(results),
    })


@federal_bp.route("/profile-check", methods=["POST"])
def check_profile():
    """Check which bundles apply to a given profile.

    Accepts a JSON body with profile attributes:
    {
        "title_iv_eligible": true,
        "serves_minors": false,
        "for_profit": false,
        "offers_certificates": true,
        "modality": "ground"
    }

    Returns applicable bundles without requiring an institution.
    """
    profile = request.get_json() or {}

    # Provide defaults for missing fields
    profile.setdefault("title_iv_eligible", True)
    profile.setdefault("serves_minors", False)
    profile.setdefault("for_profit", False)
    profile.setdefault("offers_certificates", False)
    profile.setdefault("modality", "ground")

    bundles = FederalBundleService.get_applicable_bundles(profile)
    total_requirements = sum(len(b.requirements) for b in bundles)

    return jsonify({
        "profile": profile,
        "applicable_bundles": [b.to_dict() for b in bundles],
        "bundle_count": len(bundles),
        "total_requirements": total_requirements,
    })


@federal_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get summary statistics for the federal library.

    Returns total bundles, requirements, and breakdown by bundle.
    """
    bundles = FederalBundleService.list_bundles()
    total_requirements = FederalBundleService.get_total_requirements()

    return jsonify({
        "total_bundles": len(bundles),
        "total_requirements": total_requirements,
        "bundles": [
            {
                "id": b["id"],
                "short_name": b["short_name"],
                "requirement_count": b["requirement_count"],
            }
            for b in bundles
        ],
    })
