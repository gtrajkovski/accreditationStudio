"""Audit Trail Export Service.

Provides methods for querying and exporting agent session logs.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from io import BytesIO
import json
import os


class AuditTrailService:
    """Service for querying and exporting audit trail data."""

    @staticmethod
    def query_sessions(
        institution_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        agent_type: Optional[str] = None,
        operation: Optional[str] = None,
        workspace_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """Query sessions with filters.

        Args:
            institution_id: Institution ID
            start_date: ISO8601 start date (inclusive)
            end_date: ISO8601 end date (inclusive)
            agent_type: Filter by agent type (e.g., "compliance_audit")
            operation: Filter by operation in metadata
            workspace_dir: Workspace root directory (default: WORKSPACE_DIR env)

        Returns:
            List of session dictionaries matching criteria, sorted by created_at desc
        """
        if workspace_dir is None:
            workspace_dir = Path(os.getenv("WORKSPACE_DIR", "./workspace"))

        sessions_dir = workspace_dir / institution_id / "agent_sessions"
        if not sessions_dir.exists():
            return []

        results = []
        session_files = list(sessions_dir.glob("*.json"))

        for session_file in session_files:
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session = json.load(f)

                # Date range filtering - timezone-aware
                if start_date or end_date:
                    created_at = session.get("created_at", "")
                    if not created_at:
                        continue

                    session_dt = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )

                    if start_date:
                        start_dt = datetime.fromisoformat(
                            start_date.replace("Z", "+00:00")
                        )
                        if session_dt < start_dt:
                            continue

                    if end_date:
                        end_dt = datetime.fromisoformat(
                            end_date.replace("Z", "+00:00")
                        )
                        if session_dt > end_dt:
                            continue

                # Agent type filtering
                if agent_type and session.get("agent_type") != agent_type:
                    continue

                # Operation filtering (from metadata)
                if operation:
                    session_op = session.get("metadata", {}).get("operation")
                    if session_op != operation:
                        continue

                results.append(session)

            except (FileNotFoundError, json.JSONDecodeError):
                continue  # Skip corrupted or deleted files

        # Sort by created_at descending
        results.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return results

    @staticmethod
    def get_session(
        institution_id: str,
        session_id: str,
        workspace_dir: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a single session by ID.

        Args:
            institution_id: Institution ID
            session_id: Session ID

        Returns:
            Session dictionary or None if not found
        """
        if workspace_dir is None:
            workspace_dir = Path(os.getenv("WORKSPACE_DIR", "./workspace"))

        session_file = workspace_dir / institution_id / "agent_sessions" / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    @staticmethod
    def get_agent_types(
        institution_id: str,
        workspace_dir: Optional[Path] = None
    ) -> List[str]:
        """Get unique agent types from all sessions.

        Args:
            institution_id: Institution ID

        Returns:
            List of unique agent type strings
        """
        sessions = AuditTrailService.query_sessions(
            institution_id=institution_id,
            workspace_dir=workspace_dir
        )
        agent_types = set()
        for session in sessions:
            if session.get("agent_type"):
                agent_types.add(session["agent_type"])
        return sorted(list(agent_types))

    @staticmethod
    def create_audit_package(
        institution_id: str,
        sessions: List[Dict[str, Any]],
        include_report: bool = False,
        report_path: Optional[str] = None,
        workspace_dir: Optional[Path] = None
    ) -> BytesIO:
        """Create ZIP package with audit trails and optional compliance report.

        Args:
            institution_id: Institution ID
            sessions: List of session dictionaries to include
            include_report: Whether to include compliance report PDF
            report_path: Path to report PDF (relative to workspace)
            workspace_dir: Workspace root directory

        Returns:
            BytesIO buffer containing ZIP archive
        """
        import zipfile

        if workspace_dir is None:
            workspace_dir = Path(os.getenv("WORKSPACE_DIR", "./workspace"))

        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add each session as individual JSON file
            for session in sessions:
                session_id = session.get("id", "unknown")
                session_json = json.dumps(session, indent=2, ensure_ascii=False)
                zf.writestr(f"audit_logs/{session_id}.json", session_json)

            # Add compliance report if requested
            if include_report and report_path:
                report_file = workspace_dir / institution_id / report_path
                if report_file.exists():
                    zf.write(report_file, arcname="compliance_report.pdf")

            # Add manifest with export metadata
            manifest = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "institution_id": institution_id,
                "session_count": len(sessions),
                "includes_report": include_report and report_path is not None,
                "export_version": "1.0",
                "session_ids": [s.get("id") for s in sessions],
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        buffer.seek(0)
        return buffer
