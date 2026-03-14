"""Impact Analysis API.

Provides endpoints for analyzing the impact of changing institutional facts,
simulating changes before committing, and visualizing fact-to-document dependencies.

Endpoints:
- GET /api/institutions/<id>/facts - List all facts with reference counts
- GET /api/institutions/<id>/facts/<key>/references - Get document references for a fact
- POST /api/institutions/<id>/impact/simulate - Run "what-if" simulation
- GET /api/institutions/<id>/impact/simulations/<sim_id> - Get simulation results
- POST /api/institutions/<id>/impact/simulations/<sim_id>/apply - Apply change
- GET /api/institutions/<id>/impact/graph - Get visualization data
- POST /api/institutions/<id>/facts/scan - Trigger reference scan
- GET /api/institutions/<id>/impact/history - Get change history
"""

from flask import Blueprint, jsonify, request
from typing import Optional

from src.services.impact_analysis_service import (
    list_facts_with_counts,
    get_fact_references,
    simulate_change,
    get_simulation,
    apply_simulation,
    build_impact_graph,
    scan_all_documents,
    get_change_history,
)

impact_analysis_bp = Blueprint('impact_analysis', __name__, url_prefix='/api')

_workspace_manager = None


def init_impact_analysis_bp(workspace_manager):
    """Initialize the impact analysis blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


# =============================================================================
# Facts Endpoints
# =============================================================================

@impact_analysis_bp.route('/institutions/<institution_id>/facts', methods=['GET'])
def list_facts(institution_id: str):
    """List all facts in truth index with their reference counts.

    Query params:
        category: Filter by category (institution, programs, policies)

    Returns:
        {
            "success": true,
            "facts": [
                {
                    "key": "institution.name",
                    "value": "CEM College",
                    "category": "institution",
                    "reference_count": 47
                },
                ...
            ],
            "total": 25
        }
    """
    category = request.args.get('category')

    try:
        facts = list_facts_with_counts(institution_id)

        # Filter by category if specified
        if category:
            facts = [f for f in facts if f.get("category") == category]

        # Group by category for UI
        by_category = {}
        for fact in facts:
            cat = fact.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(fact)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "facts": facts,
            "by_category": by_category,
            "total": len(facts),
            "categories": list(by_category.keys())
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "facts": []
        }), 500


@impact_analysis_bp.route('/institutions/<institution_id>/facts/<path:fact_key>/references', methods=['GET'])
def get_fact_refs(institution_id: str, fact_key: str):
    """Get all document references for a specific fact.

    Returns:
        {
            "success": true,
            "fact_key": "institution.name",
            "references": [
                {
                    "id": "ref_xxx",
                    "document_id": "doc_xxx",
                    "page_number": 12,
                    "section_header": "Institution Overview",
                    "matched_text": "CEM College",
                    "context_snippet": "...enrolled at CEM College in San Juan...",
                    "reference_type": "literal",
                    "confidence": 0.95
                },
                ...
            ],
            "total": 47
        }
    """
    try:
        references = get_fact_references(institution_id, fact_key)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "fact_key": fact_key,
            "references": [r.to_dict() for r in references],
            "total": len(references)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "references": []
        }), 500


# =============================================================================
# Impact Simulation Endpoints
# =============================================================================

@impact_analysis_bp.route('/institutions/<institution_id>/impact/simulate', methods=['POST'])
def create_simulation(institution_id: str):
    """Run "what-if" simulation for a proposed fact change.

    Request body:
        {
            "fact_key": "programs.prog_123.total_cost",
            "proposed_value": "15000.00",
            "change_reason": "Tuition increase for Fall 2026"
        }

    Returns:
        {
            "success": true,
            "simulation_id": "sim_abc123",
            "fact_key": "programs.prog_123.total_cost",
            "current_value": "12500.00",
            "proposed_value": "15000.00",
            "impact_summary": {
                "documents_affected": 4,
                "chunks_affected": 12,
                "standards_affected": ["ACCSC VII.A.4"],
                "impact_severity": "high",
                "auto_remediation_possible": true
            },
            "affected_documents": [...],
            "dependent_facts": [...],
            "preview_diffs": {...}
        }
    """
    data = request.get_json() or {}

    fact_key = data.get('fact_key')
    proposed_value = data.get('proposed_value')
    change_reason = data.get('change_reason')

    if not fact_key:
        return jsonify({
            "success": False,
            "error": "fact_key is required"
        }), 400

    if proposed_value is None:
        return jsonify({
            "success": False,
            "error": "proposed_value is required"
        }), 400

    try:
        simulation = simulate_change(
            institution_id,
            fact_key,
            str(proposed_value),
            change_reason
        )

        return jsonify({
            "success": True,
            "simulation_id": simulation.id,
            "institution_id": institution_id,
            "fact_key": simulation.fact_key,
            "current_value": simulation.current_value,
            "proposed_value": simulation.proposed_value,
            "change_reason": simulation.change_reason,
            "impact_summary": {
                "documents_affected": simulation.documents_affected,
                "chunks_affected": simulation.chunks_affected,
                "standards_affected": simulation.standards_affected,
                "impact_severity": simulation.impact_severity,
                "auto_remediation_possible": simulation.auto_remediation_possible
            },
            "affected_documents": [d.to_dict() for d in simulation.affected_documents],
            "dependent_facts": [f.to_dict() for f in simulation.dependent_facts],
            "preview_diffs": simulation.preview_diffs,
            "status": simulation.status,
            "computed_at": simulation.computed_at
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@impact_analysis_bp.route('/institutions/<institution_id>/impact/simulations/<simulation_id>', methods=['GET'])
def get_simulation_result(institution_id: str, simulation_id: str):
    """Get simulation results by ID.

    Returns:
        Full simulation object with affected documents and preview diffs
    """
    try:
        simulation = get_simulation(simulation_id)

        if not simulation:
            return jsonify({
                "success": False,
                "error": "Simulation not found"
            }), 404

        if simulation.institution_id != institution_id:
            return jsonify({
                "success": False,
                "error": "Simulation does not belong to this institution"
            }), 403

        return jsonify({
            "success": True,
            "simulation": simulation.to_dict()
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@impact_analysis_bp.route('/institutions/<institution_id>/impact/simulations/<simulation_id>/apply', methods=['POST'])
def apply_simulation_change(institution_id: str, simulation_id: str):
    """Apply a simulated change and trigger remediation.

    Request body (optional):
        {
            "user_id": "user_xxx"
        }

    Returns:
        {
            "success": true,
            "simulation_id": "sim_xxx",
            "fact_key": "institution.name",
            "new_value": "New Institution Name",
            "documents_updated": 4,
            "remediation_jobs": ["rem_xxx", "rem_yyy"],
            "history_id": "hist_xxx"
        }
    """
    data = request.get_json() or {}
    user_id = data.get('user_id')

    try:
        # Verify simulation belongs to institution
        simulation = get_simulation(simulation_id)
        if not simulation:
            return jsonify({
                "success": False,
                "error": "Simulation not found"
            }), 404

        if simulation.institution_id != institution_id:
            return jsonify({
                "success": False,
                "error": "Simulation does not belong to this institution"
            }), 403

        result = apply_simulation(simulation_id, user_id)

        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Impact Graph Endpoint
# =============================================================================

@impact_analysis_bp.route('/institutions/<institution_id>/impact/graph', methods=['GET'])
def get_impact_graph(institution_id: str):
    """Get fact-to-document dependency graph for visualization.

    Returns:
        {
            "success": true,
            "nodes": [
                {"id": "institution.name", "type": "fact", "label": "name", "ref_count": 47},
                {"id": "doc_xxx", "type": "document", "label": "Catalog", "doc_type": "catalog"}
            ],
            "edges": [
                {"source": "institution.name", "target": "doc_xxx", "weight": 15}
            ],
            "clusters": {
                "high_impact_facts": ["institution.name"]
            },
            "stats": {
                "total_facts": 12,
                "total_documents": 8,
                "total_edges": 45
            }
        }
    """
    try:
        graph = build_impact_graph(institution_id)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            **graph
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "nodes": [],
            "edges": []
        }), 500


# =============================================================================
# Scan Endpoint
# =============================================================================

@impact_analysis_bp.route('/institutions/<institution_id>/facts/scan', methods=['POST'])
def trigger_facts_scan(institution_id: str):
    """Trigger scan to detect fact references in all documents.

    This scans all documents for the institution and updates the
    fact_references table with detected references.

    Returns:
        {
            "success": true,
            "documents_scanned": 15,
            "references_found": 234,
            "scanned_at": "2026-03-08T..."
        }
    """
    try:
        # Get truth index from workspace
        if _workspace_manager:
            truth_index = _workspace_manager.get_truth_index(institution_id)
        else:
            truth_index = {}

        if not truth_index:
            return jsonify({
                "success": False,
                "error": "Truth index not found for institution"
            }), 404

        result = scan_all_documents(institution_id, truth_index)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            **result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# History Endpoint
# =============================================================================

@impact_analysis_bp.route('/institutions/<institution_id>/impact/history', methods=['GET'])
def get_impact_history(institution_id: str):
    """Get history of applied fact changes.

    Query params:
        limit: Maximum records to return (default 50)

    Returns:
        {
            "success": true,
            "history": [
                {
                    "id": "hist_xxx",
                    "fact_key": "institution.name",
                    "old_value": "Old Name",
                    "new_value": "New Name",
                    "documents_updated": 4,
                    "impact_severity": "high",
                    "applied_at": "2026-03-08T..."
                },
                ...
            ],
            "total": 12
        }
    """
    limit = request.args.get('limit', 50, type=int)

    try:
        history = get_change_history(institution_id, limit)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "history": history,
            "total": len(history)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "history": []
        }), 500


# =============================================================================
# Preview Endpoint
# =============================================================================

@impact_analysis_bp.route('/institutions/<institution_id>/impact/simulations/<simulation_id>/preview/<document_id>', methods=['GET'])
def get_document_preview(institution_id: str, simulation_id: str, document_id: str):
    """Get detailed diff preview for a specific document in a simulation.

    Returns:
        {
            "success": true,
            "document_id": "doc_xxx",
            "diffs": [
                {
                    "page": 12,
                    "section": "Program Costs",
                    "before": "Total cost: $12,500.00",
                    "after": "Total cost: $15,000.00",
                    "context": "...surrounding text..."
                },
                ...
            ]
        }
    """
    try:
        simulation = get_simulation(simulation_id)

        if not simulation:
            return jsonify({
                "success": False,
                "error": "Simulation not found"
            }), 404

        if simulation.institution_id != institution_id:
            return jsonify({
                "success": False,
                "error": "Simulation does not belong to this institution"
            }), 403

        # Find document in affected documents
        doc_diffs = simulation.preview_diffs.get(document_id, {})

        # Find affected document details
        affected_doc = None
        for doc in simulation.affected_documents:
            if doc.document_id == document_id:
                affected_doc = doc
                break

        if not affected_doc:
            return jsonify({
                "success": False,
                "error": "Document not found in simulation"
            }), 404

        # Format diffs for display
        formatted_diffs = []
        for key, diff in doc_diffs.items():
            formatted_diffs.append({
                "location": key,
                "before": diff.get("before", ""),
                "after": diff.get("after", ""),
                "pages": affected_doc.pages_affected,
                "sections": affected_doc.sections_affected
            })

        return jsonify({
            "success": True,
            "simulation_id": simulation_id,
            "document_id": document_id,
            "document_title": affected_doc.title,
            "document_type": affected_doc.doc_type,
            "diffs": formatted_diffs,
            "total_references": affected_doc.references_count
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
