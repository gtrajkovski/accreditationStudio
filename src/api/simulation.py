"""Accreditation Simulation API endpoints.

Provides endpoints for running mock accreditation audits, viewing predictions,
and comparing simulation results over time.

Endpoints:
- POST /api/institutions/<id>/simulations - Start new simulation
- GET /api/institutions/<id>/simulations - List simulations
- GET /api/institutions/<id>/simulations/<sim_id> - Get simulation details
- GET /api/institutions/<id>/simulations/<sim_id>/stream - SSE progress stream
- GET /api/institutions/<id>/simulations/<sim_id>/findings - Get predicted findings
- GET /api/institutions/<id>/simulations/<sim_id>/risk - Get risk assessment
- GET /api/institutions/<id>/simulations/compare - Compare two simulations
- GET /api/institutions/<id>/simulations/history - Simulation trend data
- POST /api/institutions/<id>/simulations/<sim_id>/cancel - Cancel simulation
"""

import json
import queue
import threading
from flask import Blueprint, request, jsonify, Response

from src.services.simulation_service import (
    get_simulation_service,
    SimulationConfig,
)
from src.db.connection import get_conn


# Create Blueprint
simulation_bp = Blueprint("simulation", __name__)

# Module-level references
_workspace_manager = None

# Active simulation threads for SSE
_active_simulations: dict = {}


def init_simulation_bp(workspace_manager):
    """Initialize the simulation blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return simulation_bp


@simulation_bp.route("/api/institutions/<institution_id>/simulations", methods=["POST"])
def start_simulation(institution_id: str):
    """Start a new accreditation simulation.

    Request Body:
        accreditor_code: Accreditor to simulate (default: institution's primary)
        mode: 'quick' or 'deep' (default: 'deep')
        include_federal: Include federal requirements (default: true)
        include_state: Include state requirements (default: true)
        document_ids: Optional list of specific documents (default: all)

    Returns:
        JSON with simulation_id and stream_url.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    config = SimulationConfig(
        mode=data.get("mode", "deep"),
        accreditor_code=data.get("accreditor_code", institution.accreditor_primary or "ACCSC"),
        include_federal=data.get("include_federal", True),
        include_state=data.get("include_state", True),
        confidence_threshold=data.get("confidence_threshold", 0.7),
        document_ids=data.get("document_ids"),
    )

    # Get service and start simulation in background
    service = get_simulation_service(institution_id)

    # Create a queue for progress updates
    progress_queue = queue.Queue()

    def run_simulation():
        try:
            generator = service.run_simulation(config)
            for update in generator:
                progress_queue.put(("progress", update.to_dict()))
            # Generator returns the result
            result = generator.value if hasattr(generator, 'value') else None
            progress_queue.put(("complete", result.to_dict() if result else {}))
        except StopIteration as e:
            # Get return value from StopIteration
            result = e.value
            progress_queue.put(("complete", result.to_dict() if result else {}))
        except Exception as e:
            progress_queue.put(("error", {"error": str(e)}))

    # Start background thread
    thread = threading.Thread(target=run_simulation, daemon=True)
    thread.start()

    # Store reference for SSE streaming
    # Get simulation ID from first progress update
    try:
        event_type, data = progress_queue.get(timeout=5)
        if event_type == "error":
            return jsonify(data), 500
    except queue.Empty:
        return jsonify({"error": "Simulation failed to start"}), 500

    # Get latest simulation for ID
    simulations = service.list_simulations(limit=1)
    if not simulations:
        return jsonify({"error": "Simulation failed to create"}), 500

    simulation_id = simulations[0]["id"]
    _active_simulations[simulation_id] = progress_queue

    return jsonify({
        "success": True,
        "simulation_id": simulation_id,
        "stream_url": f"/api/institutions/{institution_id}/simulations/{simulation_id}/stream",
        "status": "running",
    }), 201


@simulation_bp.route("/api/institutions/<institution_id>/simulations", methods=["GET"])
def list_simulations(institution_id: str):
    """List simulations for an institution.

    Query parameters:
        limit: Maximum results (default: 20)
        status: Filter by status (optional)

    Returns:
        JSON with list of simulations.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    limit = request.args.get("limit", 20, type=int)
    status = request.args.get("status")

    service = get_simulation_service(institution_id)
    simulations = service.list_simulations(limit=limit, status=status)

    return jsonify({
        "success": True,
        "simulations": simulations,
        "total": len(simulations),
    })


@simulation_bp.route("/api/institutions/<institution_id>/simulations/<simulation_id>", methods=["GET"])
def get_simulation(institution_id: str, simulation_id: str):
    """Get simulation details.

    Returns:
        JSON with full simulation details including scores and counts.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    service = get_simulation_service(institution_id)
    simulation = service.get_simulation(simulation_id)

    if not simulation:
        return jsonify({"error": "Simulation not found"}), 404

    return jsonify({
        "success": True,
        "simulation": simulation,
    })


@simulation_bp.route("/api/institutions/<institution_id>/simulations/<simulation_id>/stream", methods=["GET"])
def stream_simulation(institution_id: str, simulation_id: str):
    """Stream simulation progress via Server-Sent Events.

    Returns:
        SSE stream with progress updates.
    """
    def generate():
        # Check if we have an active queue for this simulation
        progress_queue = _active_simulations.get(simulation_id)

        if not progress_queue:
            # Simulation might already be complete, check status
            service = get_simulation_service(institution_id)
            simulation = service.get_simulation(simulation_id)
            if simulation:
                yield f"data: {json.dumps({'type': 'complete', 'data': simulation})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Simulation not found'})}\n\n"
            return

        while True:
            try:
                event_type, data = progress_queue.get(timeout=60)

                if event_type == "progress":
                    yield f"data: {json.dumps({'type': 'progress', 'data': data})}\n\n"
                elif event_type == "complete":
                    yield f"data: {json.dumps({'type': 'complete', 'data': data})}\n\n"
                    # Cleanup
                    if simulation_id in _active_simulations:
                        del _active_simulations[simulation_id]
                    return
                elif event_type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'data': data})}\n\n"
                    if simulation_id in _active_simulations:
                        del _active_simulations[simulation_id]
                    return

            except queue.Empty:
                # Send keepalive
                yield f": keepalive\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@simulation_bp.route("/api/institutions/<institution_id>/simulations/<simulation_id>/findings", methods=["GET"])
def get_simulation_findings(institution_id: str, simulation_id: str):
    """Get predicted findings for a simulation.

    Query parameters:
        status: Filter by predicted status (optional)

    Returns:
        JSON with list of predicted findings.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    status_filter = request.args.get("status")

    service = get_simulation_service(institution_id)
    findings = service.get_simulation_findings(simulation_id, status_filter)

    return jsonify({
        "success": True,
        "findings": findings,
        "total": len(findings),
    })


@simulation_bp.route("/api/institutions/<institution_id>/simulations/<simulation_id>/risk", methods=["GET"])
def get_simulation_risk(institution_id: str, simulation_id: str):
    """Get risk assessment for a simulation.

    Returns:
        JSON with risk assessment by category.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    service = get_simulation_service(institution_id)
    risk = service.get_risk_assessment(simulation_id)

    return jsonify({
        "success": True,
        "risk_assessment": risk,
    })


@simulation_bp.route("/api/institutions/<institution_id>/simulations/compare", methods=["GET"])
def compare_simulations(institution_id: str):
    """Compare two simulation runs.

    Query parameters:
        sim1: First simulation ID
        sim2: Second simulation ID

    Returns:
        JSON with comparison data including deltas.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    sim1 = request.args.get("sim1")
    sim2 = request.args.get("sim2")

    if not sim1 or not sim2:
        return jsonify({"error": "Both sim1 and sim2 parameters required"}), 400

    service = get_simulation_service(institution_id)
    comparison = service.compare_simulations(sim1, sim2)

    if "error" in comparison:
        return jsonify(comparison), 404

    return jsonify({
        "success": True,
        "comparison": comparison,
    })


@simulation_bp.route("/api/institutions/<institution_id>/simulations/history", methods=["GET"])
def get_simulation_history(institution_id: str):
    """Get simulation history for trend analysis.

    Query parameters:
        limit: Maximum results (default: 10)

    Returns:
        JSON with historical simulation scores.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    limit = request.args.get("limit", 10, type=int)

    service = get_simulation_service(institution_id)
    history = service.get_simulation_history(limit)

    return jsonify({
        "success": True,
        "history": history,
    })


@simulation_bp.route("/api/institutions/<institution_id>/simulations/<simulation_id>/cancel", methods=["POST"])
def cancel_simulation(institution_id: str, simulation_id: str):
    """Cancel a running simulation.

    Returns:
        JSON with success status.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    # Update status in database
    conn = get_conn()
    cursor = conn.execute(
        """
        UPDATE simulation_runs
        SET status = 'cancelled', completed_at = datetime('now')
        WHERE id = ? AND institution_id = ? AND status = 'running'
        """,
        (simulation_id, institution_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Simulation not found or not running"}), 404

    # Cleanup active simulation
    if simulation_id in _active_simulations:
        del _active_simulations[simulation_id]

    return jsonify({"success": True})
