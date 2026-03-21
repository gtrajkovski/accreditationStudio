"""Audit Trail Export Service.

Provides methods for querying and exporting agent session logs.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
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
