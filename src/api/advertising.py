"""Advertising Compliance Scanner API.

Endpoints for scanning marketing materials for FTC and accreditor compliance.
"""

import json
import logging
import queue
import threading
from typing import Dict, Any, Optional

from flask import Blueprint, request, jsonify, Response, stream_with_context

from src.agents.advertising_scanner_agent import AdvertisingScannerAgent
from src.agents.base_agent import AgentType
from src.core.models import AgentSession, generate_id, now_iso
from src.db.connection import get_conn

logger = logging.getLogger(__name__)

advertising_bp = Blueprint("advertising", __name__)

_workspace_manager = None
_active_scans: Dict[str, queue.Queue] = {}


def init_advertising_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager
    return advertising_bp


@advertising_bp.route("/api/advertising/scan-url", methods=["POST"])
def scan_url():
    """Submit a URL for advertising compliance scanning.

    Request Body:
        institution_id: Institution ID (required)
        url: URL to scan (required)

    Returns:
        JSON with scan_id and stream_url for SSE progress.
    """
    data = request.get_json() or {}

    institution_id = data.get("institution_id")
    url = data.get("url")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400
    if not url:
        return jsonify({"error": "url is required"}), 400

    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    # Create scan record
    scan_id = generate_id("adscan")
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO advertising_scans
        (id, institution_id, scan_type, source_url, title, status, scanned_by, created_at)
        VALUES (?, ?, 'url', ?, ?, 'pending', 'user', datetime('now'))
        """,
        (scan_id, institution_id, url, f"Web Scan: {url}"),
    )
    conn.commit()

    # Create progress queue for SSE
    progress_queue: queue.Queue = queue.Queue()
    _active_scans[scan_id] = progress_queue

    def run_scan():
        """Background task to run the scan."""
        try:
            # Create agent session
            session = AgentSession(
                id=generate_id("sess"),
                agent_type=AgentType.ADVERTISING_SCANNER.value,
                institution_id=institution_id,
                orchestrator_request=f"Scan URL for advertising compliance: {url}",
            )

            def on_update(sess):
                progress_queue.put(("progress", {
                    "status": sess.status.value if hasattr(sess.status, 'value') else str(sess.status),
                    "tasks_completed": len([t for t in sess.tasks if t.completed_at]),
                    "total_tasks": len(sess.tasks),
                }))

            agent = AdvertisingScannerAgent(
                session=session,
                workspace_manager=_workspace_manager,
                on_update=on_update,
            )

            # Add initial task
            session.add_task(
                f"Scan URL {url} for advertising compliance",
                f"1. Fetch and analyze content from {url}\n"
                f"2. Extract all advertising claims\n"
                f"3. Verify claims against achievement data\n"
                f"4. Generate compliance report"
            )

            progress_queue.put(("started", {"scan_id": scan_id, "url": url}))

            # Run the agent
            for update in agent.run_task():
                if isinstance(update, dict):
                    progress_queue.put(("update", update))

            progress_queue.put(("complete", {"scan_id": scan_id}))

        except Exception as e:
            logger.exception("Scan failed: %s", e)
            progress_queue.put(("error", {"error": str(e)}))

            # Update scan status
            conn = get_conn()
            conn.execute(
                "UPDATE advertising_scans SET status = 'failed', error_message = ? WHERE id = ?",
                (str(e), scan_id),
            )
            conn.commit()
        finally:
            # Clean up after a delay
            threading.Timer(60, lambda: _active_scans.pop(scan_id, None)).start()

    # Start background thread
    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "scan_id": scan_id,
        "stream_url": f"/api/advertising/scans/{scan_id}/stream",
    }), 202


@advertising_bp.route("/api/advertising/scan-document", methods=["POST"])
def scan_document():
    """Submit a document for advertising compliance scanning.

    Request Body:
        institution_id: Institution ID (required)
        document_id: Document ID (required)

    Returns:
        JSON with scan_id and stream_url for SSE progress.
    """
    data = request.get_json() or {}

    institution_id = data.get("institution_id")
    document_id = data.get("document_id")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400
    if not document_id:
        return jsonify({"error": "document_id is required"}), 400

    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    # Create scan record
    scan_id = generate_id("adscan")
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO advertising_scans
        (id, institution_id, scan_type, document_id, title, status, scanned_by, created_at)
        VALUES (?, ?, 'document', ?, ?, 'pending', 'user', datetime('now'))
        """,
        (scan_id, institution_id, document_id, f"Document Scan: {document_id}"),
    )
    conn.commit()

    # Create progress queue
    progress_queue: queue.Queue = queue.Queue()
    _active_scans[scan_id] = progress_queue

    def run_scan():
        """Background task to run the document scan."""
        try:
            session = AgentSession(
                id=generate_id("sess"),
                agent_type=AgentType.ADVERTISING_SCANNER.value,
                institution_id=institution_id,
                orchestrator_request=f"Scan document {document_id} for advertising compliance",
            )

            agent = AdvertisingScannerAgent(
                session=session,
                workspace_manager=_workspace_manager,
            )

            session.add_task(
                f"Scan document {document_id} for advertising compliance",
                "Extract and verify all advertising claims"
            )

            progress_queue.put(("started", {"scan_id": scan_id, "document_id": document_id}))

            for update in agent.run_task():
                if isinstance(update, dict):
                    progress_queue.put(("update", update))

            progress_queue.put(("complete", {"scan_id": scan_id}))

        except Exception as e:
            logger.exception("Document scan failed: %s", e)
            progress_queue.put(("error", {"error": str(e)}))
        finally:
            threading.Timer(60, lambda: _active_scans.pop(scan_id, None)).start()

    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "scan_id": scan_id,
        "stream_url": f"/api/advertising/scans/{scan_id}/stream",
    }), 202


@advertising_bp.route("/api/advertising/scans/<scan_id>", methods=["GET"])
def get_scan(scan_id: str):
    """Get scan results by ID.

    Returns:
        JSON with scan details and findings.
    """
    conn = get_conn()
    cursor = conn.execute(
        "SELECT * FROM advertising_scans WHERE id = ?",
        (scan_id,),
    )
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Scan not found"}), 404

    # Get findings
    findings_cursor = conn.execute(
        """
        SELECT * FROM advertising_findings
        WHERE scan_id = ?
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'significant' THEN 2
                WHEN 'advisory' THEN 3
                ELSE 4
            END,
            CASE finding_type
                WHEN 'violation' THEN 1
                WHEN 'warning' THEN 2
                WHEN 'unverifiable' THEN 3
                ELSE 4
            END
        """,
        (scan_id,),
    )

    return jsonify({
        "success": True,
        "scan": dict(row),
        "findings": [dict(f) for f in findings_cursor.fetchall()],
    })


@advertising_bp.route("/api/advertising/scans/<scan_id>/stream", methods=["GET"])
def stream_scan(scan_id: str):
    """SSE stream for scan progress.

    Returns:
        Server-Sent Events stream with progress updates.
    """
    def generate():
        progress_queue = _active_scans.get(scan_id)

        if not progress_queue:
            # Check if scan is already complete
            conn = get_conn()
            cursor = conn.execute(
                "SELECT status FROM advertising_scans WHERE id = ?",
                (scan_id,),
            )
            row = cursor.fetchone()
            if row:
                if row["status"] == "completed":
                    yield f"data: {json.dumps({'type': 'complete', 'scan_id': scan_id})}\n\n"
                elif row["status"] == "failed":
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Scan failed'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'status', 'status': row['status']})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Scan not found'})}\n\n"
            return

        while True:
            try:
                event_type, data = progress_queue.get(timeout=30)
                yield f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"
                if event_type in ("complete", "error"):
                    return
            except queue.Empty:
                # Send keepalive
                yield f": keepalive\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@advertising_bp.route("/api/institutions/<institution_id>/advertising/scans", methods=["GET"])
def list_scans(institution_id: str):
    """List all scans for an institution.

    Query Parameters:
        limit: Maximum number of results (default: 20)
        status: Filter by status (optional)

    Returns:
        JSON list of scans.
    """
    limit = request.args.get("limit", 20, type=int)
    status_filter = request.args.get("status")

    conn = get_conn()

    query = """
        SELECT id, scan_type, source_url, document_id, title, status,
               compliance_score, risk_level, violation_count, warning_count,
               total_claims, verified_claims,
               created_at, completed_at
        FROM advertising_scans
        WHERE institution_id = ?
    """
    params = [institution_id]

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)

    return jsonify({
        "success": True,
        "scans": [dict(row) for row in cursor.fetchall()],
    })


@advertising_bp.route("/api/advertising/scans/<scan_id>", methods=["DELETE"])
def delete_scan(scan_id: str):
    """Delete a scan and its findings.

    Returns:
        JSON with success status.
    """
    conn = get_conn()

    # Check if scan exists
    cursor = conn.execute(
        "SELECT id FROM advertising_scans WHERE id = ?",
        (scan_id,),
    )
    if not cursor.fetchone():
        return jsonify({"error": "Scan not found"}), 404

    # Delete findings first (foreign key)
    conn.execute(
        "DELETE FROM advertising_findings WHERE scan_id = ?",
        (scan_id,),
    )

    # Delete scan
    conn.execute(
        "DELETE FROM advertising_scans WHERE id = ?",
        (scan_id,),
    )
    conn.commit()

    return jsonify({
        "success": True,
        "message": "Scan deleted",
        "scan_id": scan_id,
    })
