"""Team Reports API Blueprint.

Handles team report parsing, finding responses, and response packet management.
"""

import json
from flask import Blueprint, request, jsonify, Response
from typing import Optional

from src.core.models import AgentSession, generate_id, now_iso
from src.db.connection import get_conn
from src.agents.base_agent import AgentType
from src.agents.registry import AgentRegistry


team_reports_bp = Blueprint("team_reports", __name__, url_prefix="/api/team-reports")

_workspace_manager = None


def init_team_reports_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


# =============================================================================
# Team Report CRUD
# =============================================================================

@team_reports_bp.route("/", methods=["GET"])
def list_team_reports():
    """List team reports for an institution."""
    institution_id = request.args.get("institution_id")
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)

    conn = get_conn()
    query = "SELECT * FROM team_reports WHERE 1=1"
    params = []

    if institution_id:
        query += " AND institution_id = ?"
        params.append(institution_id)

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    reports = []
    for row in rows:
        report = dict(row)
        if report.get("commendations"):
            report["commendations"] = json.loads(report["commendations"])
        reports.append(report)

    return jsonify({"reports": reports, "count": len(reports)})


@team_reports_bp.route("/<report_id>", methods=["GET"])
def get_team_report(report_id: str):
    """Get a specific team report with findings."""
    conn = get_conn()

    # Get report
    report = conn.execute(
        "SELECT * FROM team_reports WHERE id = ?",
        (report_id,)
    ).fetchone()

    if not report:
        return jsonify({"error": "Team report not found"}), 404

    report_data = dict(report)
    if report_data.get("commendations"):
        report_data["commendations"] = json.loads(report_data["commendations"])

    # Get findings
    findings = conn.execute(
        "SELECT * FROM team_report_findings WHERE report_id = ? ORDER BY response_priority, finding_number",
        (report_id,)
    ).fetchall()

    report_data["findings"] = []
    for finding in findings:
        finding_data = dict(finding)
        if finding_data.get("evidence_cited"):
            finding_data["evidence_cited"] = json.loads(finding_data["evidence_cited"])
        report_data["findings"].append(finding_data)

    return jsonify(report_data)


@team_reports_bp.route("/", methods=["POST"])
def create_team_report():
    """Create a new team report entry."""
    data = request.get_json()

    if not data.get("institution_id"):
        return jsonify({"error": "institution_id is required"}), 400

    report_id = generate_id("tr")
    now = now_iso()

    conn = get_conn()
    conn.execute(
        """INSERT INTO team_reports
           (id, institution_id, accreditor_code, visit_date, report_date,
            team_chair, overall_recommendation, response_due_date,
            commendations, status, document_path, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            report_id,
            data.get("institution_id"),
            data.get("accreditor_code", ""),
            data.get("visit_date", ""),
            data.get("report_date", ""),
            data.get("team_chair", ""),
            data.get("overall_recommendation", ""),
            data.get("response_due_date", ""),
            json.dumps(data.get("commendations", [])),
            data.get("status", "received"),
            data.get("document_path", ""),
            now,
            now,
        )
    )
    conn.commit()

    return jsonify({"id": report_id, "status": "created"}), 201


@team_reports_bp.route("/<report_id>", methods=["PATCH"])
def update_team_report(report_id: str):
    """Update a team report."""
    data = request.get_json()
    conn = get_conn()

    # Check exists
    existing = conn.execute(
        "SELECT id FROM team_reports WHERE id = ?",
        (report_id,)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Team report not found"}), 404

    # Build update
    updates = []
    params = []

    for field in ["accreditor_code", "visit_date", "report_date", "team_chair",
                  "overall_recommendation", "response_due_date", "status", "document_path"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if "commendations" in data:
        updates.append("commendations = ?")
        params.append(json.dumps(data["commendations"]))

    if updates:
        updates.append("updated_at = ?")
        params.append(now_iso())
        params.append(report_id)

        conn.execute(
            f"UPDATE team_reports SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

    return jsonify({"id": report_id, "status": "updated"})


# =============================================================================
# Findings
# =============================================================================

@team_reports_bp.route("/<report_id>/findings", methods=["GET"])
def list_findings(report_id: str):
    """List findings for a team report."""
    conn = get_conn()

    severity = request.args.get("severity")
    status = request.args.get("status")

    query = "SELECT * FROM team_report_findings WHERE report_id = ?"
    params = [report_id]

    if severity:
        query += " AND severity = ?"
        params.append(severity)

    if status:
        query += " AND response_status = ?"
        params.append(status)

    query += " ORDER BY response_priority, finding_number"

    findings = conn.execute(query, params).fetchall()

    result = []
    for finding in findings:
        finding_data = dict(finding)
        if finding_data.get("evidence_cited"):
            finding_data["evidence_cited"] = json.loads(finding_data["evidence_cited"])
        result.append(finding_data)

    return jsonify({"findings": result, "count": len(result)})


@team_reports_bp.route("/<report_id>/findings", methods=["POST"])
def create_finding(report_id: str):
    """Add a finding to a team report."""
    data = request.get_json()
    conn = get_conn()

    # Check report exists
    report = conn.execute(
        "SELECT id FROM team_reports WHERE id = ?",
        (report_id,)
    ).fetchone()

    if not report:
        return jsonify({"error": "Team report not found"}), 404

    finding_id = generate_id("trf")

    conn.execute(
        """INSERT INTO team_report_findings
           (id, report_id, finding_number, standard_reference, severity,
            finding_text, requirement_text, evidence_cited, response_deadline,
            response_status, response_priority, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            finding_id,
            report_id,
            data.get("finding_number", ""),
            data.get("standard_reference", ""),
            data.get("severity", "moderate"),
            data.get("finding_text", ""),
            data.get("requirement_text", ""),
            json.dumps(data.get("evidence_cited", [])),
            data.get("response_deadline", ""),
            data.get("response_status", "pending"),
            data.get("response_priority", 0),
            now_iso(),
        )
    )
    conn.commit()

    return jsonify({"id": finding_id, "status": "created"}), 201


@team_reports_bp.route("/findings/<finding_id>", methods=["PATCH"])
def update_finding(finding_id: str):
    """Update a finding."""
    data = request.get_json()
    conn = get_conn()

    # Check exists
    existing = conn.execute(
        "SELECT id FROM team_report_findings WHERE id = ?",
        (finding_id,)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Finding not found"}), 404

    updates = []
    params = []

    for field in ["finding_number", "standard_reference", "severity", "finding_text",
                  "requirement_text", "response_deadline", "response_status", "response_priority"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if "evidence_cited" in data:
        updates.append("evidence_cited = ?")
        params.append(json.dumps(data["evidence_cited"]))

    if updates:
        params.append(finding_id)
        conn.execute(
            f"UPDATE team_report_findings SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

    return jsonify({"id": finding_id, "status": "updated"})


# =============================================================================
# Responses
# =============================================================================

@team_reports_bp.route("/findings/<finding_id>/response", methods=["GET"])
def get_finding_response(finding_id: str):
    """Get the response for a finding."""
    conn = get_conn()

    response = conn.execute(
        "SELECT * FROM finding_responses WHERE finding_id = ? ORDER BY created_at DESC LIMIT 1",
        (finding_id,)
    ).fetchone()

    if not response:
        return jsonify({"error": "No response found"}), 404

    response_data = dict(response)
    if response_data.get("evidence_refs"):
        response_data["evidence_refs"] = json.loads(response_data["evidence_refs"])
    if response_data.get("action_items"):
        response_data["action_items"] = json.loads(response_data["action_items"])

    return jsonify(response_data)


@team_reports_bp.route("/findings/<finding_id>/response", methods=["POST"])
def create_finding_response(finding_id: str):
    """Create or update a response for a finding."""
    data = request.get_json()
    conn = get_conn()

    # Check finding exists
    finding = conn.execute(
        "SELECT id FROM team_report_findings WHERE id = ?",
        (finding_id,)
    ).fetchone()

    if not finding:
        return jsonify({"error": "Finding not found"}), 404

    response_id = generate_id("resp")
    now = now_iso()

    conn.execute(
        """INSERT INTO finding_responses
           (id, finding_id, response_text, evidence_refs, action_items,
            word_count, ai_confidence, requires_review, reviewer_notes,
            status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            response_id,
            finding_id,
            data.get("response_text", ""),
            json.dumps(data.get("evidence_refs", [])),
            json.dumps(data.get("action_items", [])),
            data.get("word_count", 0),
            data.get("ai_confidence", 0.0),
            1 if data.get("requires_review", True) else 0,
            data.get("reviewer_notes", ""),
            data.get("status", "draft"),
            now,
            now,
        )
    )

    # Update finding status
    conn.execute(
        "UPDATE team_report_findings SET response_status = ? WHERE id = ?",
        ("drafted", finding_id)
    )

    conn.commit()

    return jsonify({"id": response_id, "status": "created"}), 201


@team_reports_bp.route("/responses/<response_id>", methods=["PATCH"])
def update_response(response_id: str):
    """Update a response."""
    data = request.get_json()
    conn = get_conn()

    existing = conn.execute(
        "SELECT id, finding_id FROM finding_responses WHERE id = ?",
        (response_id,)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Response not found"}), 404

    updates = []
    params = []

    for field in ["response_text", "word_count", "ai_confidence",
                  "reviewer_notes", "status", "reviewer_id"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if "requires_review" in data:
        updates.append("requires_review = ?")
        params.append(1 if data["requires_review"] else 0)

    if "evidence_refs" in data:
        updates.append("evidence_refs = ?")
        params.append(json.dumps(data["evidence_refs"]))

    if "action_items" in data:
        updates.append("action_items = ?")
        params.append(json.dumps(data["action_items"]))

    if updates:
        updates.append("updated_at = ?")
        params.append(now_iso())
        params.append(response_id)

        conn.execute(
            f"UPDATE finding_responses SET {', '.join(updates)} WHERE id = ?",
            params
        )

        # Update finding status if response status changed
        if "status" in data:
            finding_id = existing["finding_id"]
            status_map = {
                "draft": "drafted",
                "reviewed": "reviewed",
                "approved": "reviewed",
                "submitted": "submitted",
            }
            new_status = status_map.get(data["status"], "drafted")
            conn.execute(
                "UPDATE team_report_findings SET response_status = ? WHERE id = ?",
                (new_status, finding_id)
            )

        conn.commit()

    return jsonify({"id": response_id, "status": "updated"})


# =============================================================================
# Agent Integration
# =============================================================================

@team_reports_bp.route("/<report_id>/parse", methods=["POST"])
def parse_team_report(report_id: str):
    """Use AI agent to parse a team report document."""
    data = request.get_json()

    if not data.get("report_text"):
        return jsonify({"error": "report_text is required"}), 400

    conn = get_conn()

    # Get report
    report = conn.execute(
        "SELECT * FROM team_reports WHERE id = ?",
        (report_id,)
    ).fetchone()

    if not report:
        return jsonify({"error": "Team report not found"}), 404

    # Create agent session
    session = AgentSession(
        agent_type=AgentType.TEAM_REPORT.value,
        institution_id=report["institution_id"],
    )

    # Create agent
    agent = AgentRegistry.create(
        AgentType.TEAM_REPORT,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Team Report agent"}), 500

    # Parse report
    result = agent._tool_parse_report({
        "institution_id": report["institution_id"],
        "accreditor_code": report["accreditor_code"] or data.get("accreditor_code", ""),
        "report_text": data["report_text"],
        "visit_date": report["visit_date"] or data.get("visit_date", ""),
        "response_due_date": report["response_due_date"] or data.get("response_due_date", ""),
    })

    if "error" in result:
        return jsonify(result), 400

    # Save findings to database
    now = now_iso()
    for finding_summary in result.get("findings_summary", []):
        # Get full finding data from agent
        for f in agent._current_report.findings:
            if f.id == finding_summary["id"]:
                conn.execute(
                    """INSERT INTO team_report_findings
                       (id, report_id, finding_number, standard_reference, severity,
                        finding_text, requirement_text, response_status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f.id,
                        report_id,
                        f.finding_number,
                        f.standard_reference,
                        f.severity,
                        f.finding_text,
                        f.requirement_text,
                        "pending",
                        now,
                    )
                )

    # Update report
    conn.execute(
        """UPDATE team_reports
           SET status = ?, overall_recommendation = ?,
               commendations = ?, updated_at = ?
           WHERE id = ?""",
        (
            "analyzing",
            result.get("overall_recommendation", ""),
            json.dumps(agent._current_report.commendations),
            now,
            report_id,
        )
    )

    conn.commit()

    return jsonify(result)


@team_reports_bp.route("/findings/<finding_id>/draft-response", methods=["POST"])
def draft_finding_response(finding_id: str):
    """Use AI agent to draft a response for a finding."""
    data = request.get_json() or {}
    conn = get_conn()

    # Get finding
    finding = conn.execute(
        """SELECT f.*, r.institution_id, r.accreditor_code
           FROM team_report_findings f
           JOIN team_reports r ON f.report_id = r.id
           WHERE f.id = ?""",
        (finding_id,)
    ).fetchone()

    if not finding:
        return jsonify({"error": "Finding not found"}), 404

    # Create agent session
    session = AgentSession(
        agent_type=AgentType.TEAM_REPORT.value,
        institution_id=finding["institution_id"],
    )

    # Create agent
    agent = AgentRegistry.create(
        AgentType.TEAM_REPORT,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Team Report agent"}), 500

    # Load finding into agent
    from src.agents.team_report_agent import TeamReportFinding, TeamReport

    agent._current_report = TeamReport(
        institution_id=finding["institution_id"],
        accreditor_code=finding["accreditor_code"] or "",
    )
    agent._current_report.findings.append(TeamReportFinding(
        id=finding_id,
        finding_number=finding["finding_number"] or "",
        standard_reference=finding["standard_reference"] or "",
        severity=finding["severity"] or "moderate",
        finding_text=finding["finding_text"] or "",
        requirement_text=finding["requirement_text"] or "",
    ))

    # Draft response
    result = agent._tool_draft_response({
        "finding_id": finding_id,
        "evidence_summary": data.get("evidence_summary", ""),
        "corrective_actions": data.get("corrective_actions", ""),
        "responsible_party": data.get("responsible_party", ""),
        "completion_date": data.get("completion_date", ""),
    })

    if "error" in result:
        return jsonify(result), 400

    # Save response to database
    now = now_iso()
    response_id = generate_id("resp")

    conn.execute(
        """INSERT INTO finding_responses
           (id, finding_id, response_text, word_count, ai_confidence,
            requires_review, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            response_id,
            finding_id,
            result.get("response_text", ""),
            result.get("word_count", 0),
            0.75,
            1,
            "draft",
            now,
            now,
        )
    )

    conn.execute(
        "UPDATE team_report_findings SET response_status = ? WHERE id = ?",
        ("drafted", finding_id)
    )

    conn.commit()

    result["response_id"] = response_id
    return jsonify(result)


# =============================================================================
# Response Packets
# =============================================================================

@team_reports_bp.route("/<report_id>/packets", methods=["GET"])
def list_packets(report_id: str):
    """List response packets for a team report."""
    conn = get_conn()

    packets = conn.execute(
        """SELECT * FROM response_packets
           WHERE report_id = ?
           ORDER BY created_at DESC""",
        (report_id,)
    ).fetchall()

    return jsonify({
        "packets": [dict(p) for p in packets],
        "count": len(packets)
    })


@team_reports_bp.route("/<report_id>/packets", methods=["POST"])
def create_packet(report_id: str):
    """Create a response packet for submission."""
    data = request.get_json() or {}
    conn = get_conn()

    # Get report
    report = conn.execute(
        "SELECT * FROM team_reports WHERE id = ?",
        (report_id,)
    ).fetchone()

    if not report:
        return jsonify({"error": "Team report not found"}), 404

    # Count findings and responses
    stats = conn.execute(
        """SELECT
             COUNT(*) as findings_count,
             SUM(CASE WHEN response_status IN ('drafted', 'reviewed', 'submitted') THEN 1 ELSE 0 END) as responses_count
           FROM team_report_findings
           WHERE report_id = ?""",
        (report_id,)
    ).fetchone()

    packet_id = generate_id("pkt")
    now = now_iso()

    conn.execute(
        """INSERT INTO response_packets
           (id, institution_id, report_id, packet_name, format,
            findings_count, responses_included, include_evidence,
            status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            packet_id,
            report["institution_id"],
            report_id,
            data.get("packet_name", f"Response Packet - {now[:10]}"),
            data.get("format", "docx"),
            stats["findings_count"] or 0,
            stats["responses_count"] or 0,
            1 if data.get("include_evidence", False) else 0,
            "draft",
            now,
        )
    )
    conn.commit()

    return jsonify({
        "id": packet_id,
        "status": "created",
        "findings_count": stats["findings_count"] or 0,
        "responses_included": stats["responses_count"] or 0,
    }), 201


@team_reports_bp.route("/packets/<packet_id>/export", methods=["POST"])
def export_packet(packet_id: str):
    """Export a response packet."""
    conn = get_conn()

    packet = conn.execute(
        "SELECT * FROM response_packets WHERE id = ?",
        (packet_id,)
    ).fetchone()

    if not packet:
        return jsonify({"error": "Packet not found"}), 404

    # Get all findings and responses
    findings = conn.execute(
        """SELECT f.*, r.response_text, r.evidence_refs, r.action_items, r.status as response_status_detail
           FROM team_report_findings f
           LEFT JOIN finding_responses r ON f.id = r.finding_id
           WHERE f.report_id = ?
           ORDER BY f.response_priority, f.finding_number""",
        (packet["report_id"],)
    ).fetchall()

    # Build export data
    export_data = {
        "packet_id": packet_id,
        "report_id": packet["report_id"],
        "institution_id": packet["institution_id"],
        "created_at": now_iso(),
        "findings": []
    }

    for finding in findings:
        finding_data = {
            "finding_number": finding["finding_number"],
            "standard_reference": finding["standard_reference"],
            "severity": finding["severity"],
            "finding_text": finding["finding_text"],
            "response_text": finding["response_text"] or "",
        }

        if finding["action_items"]:
            finding_data["action_items"] = json.loads(finding["action_items"])

        if packet["include_evidence"] and finding["evidence_refs"]:
            finding_data["evidence_refs"] = json.loads(finding["evidence_refs"])

        export_data["findings"].append(finding_data)

    # Save to workspace
    if _workspace_manager:
        filename = f"response_packet_{packet_id}_{now_iso()[:10]}.json"
        path = f"responses/packets/{filename}"

        _workspace_manager.save_file(
            packet["institution_id"],
            path,
            export_data
        )

        # Update packet with file path
        conn.execute(
            "UPDATE response_packets SET file_path = ?, status = ? WHERE id = ?",
            (path, "final", packet_id)
        )
        conn.commit()

        return jsonify({
            "success": True,
            "path": path,
            "findings_count": len(export_data["findings"]),
        })

    return jsonify(export_data)
