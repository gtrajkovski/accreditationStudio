"""Workspace manager for local folder structure.

Manages the persistent local folder structure for each institution.
Creates and maintains the workspace directory hierarchy, handles
file versioning, and manages the truth index.
"""

import json
import shutil
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.config import Config
from src.core.models import Institution, Program


class WorkspaceManager:
    """Manages institution workspace folders on disk.

    Each institution gets a persistent folder structure:
    workspace/{institution_slug}/
    ├── institution.json
    ├── truth_index.json
    ├── programs/{program_slug}/
    │   ├── program.json
    │   ├── originals/
    │   ├── audits/
    │   ├── redlines/
    │   ├── finals/
    │   ├── crossrefs/
    │   └── checklists/
    ├── catalog/
    ├── policies/
    ├── exhibits/
    ├── faculty/
    ├── achievements/
    ├── visit_prep/
    ├── responses/
    ├── submissions/
    └── agent_sessions/
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize workspace manager.

        Args:
            base_dir: Root directory for workspaces. Defaults to Config.WORKSPACE_DIR.
        """
        self.base_dir = base_dir or Config.WORKSPACE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a name to a filesystem-safe slug.

        Args:
            name: The name to slugify.

        Returns:
            Lowercase slug with spaces replaced by hyphens.
        """
        slug = name.lower().strip()
        slug = slug.replace(" ", "-")
        # Remove any characters that aren't alphanumeric, hyphen, or underscore
        slug = "".join(c for c in slug if c.isalnum() or c in "-_")
        # Remove consecutive hyphens
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-") or "unnamed"

    @staticmethod
    def _sanitize_path(path_part: str) -> str:
        """Sanitize a path component to prevent traversal attacks.

        Args:
            path_part: Path component to sanitize.

        Returns:
            Sanitized path component.

        Raises:
            ValueError: If path is invalid after sanitization.
        """
        sanitized = str(path_part).replace("/", "").replace("\\", "").replace("..", "")
        if not sanitized:
            raise ValueError("Invalid path component")
        return sanitized

    def _acquire_lock(self, lock_path: Path) -> None:
        """Acquire a file lock for synchronization."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        max_attempts = 50
        attempt = 0

        while attempt < max_attempts:
            try:
                fd = lock_path.open("x")
                fd.close()
                return
            except FileExistsError:
                time.sleep(0.01)
                attempt += 1

        # Force acquire if orphaned
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        fd = lock_path.open("x")
        fd.close()

    def _release_lock(self, lock_path: Path) -> None:
        """Release a file lock."""
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON data with file locking."""
        lock_path = path.with_suffix(path.suffix + ".lock")
        self._acquire_lock(lock_path)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        finally:
            self._release_lock(lock_path)

    def _read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON data with file locking."""
        lock_path = path.with_suffix(path.suffix + ".lock")
        self._acquire_lock(lock_path)

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        finally:
            self._release_lock(lock_path)

    def get_institution_dir(self, institution_id: str) -> Path:
        """Get the workspace directory for an institution.

        Args:
            institution_id: Institution identifier.

        Returns:
            Path to institution's workspace directory.
        """
        safe_id = self._sanitize_path(institution_id)
        return self.base_dir / safe_id

    def get_institution_path(self, institution_id: str) -> Optional[Path]:
        """Get the workspace path for an institution if it exists.

        Args:
            institution_id: Institution identifier.

        Returns:
            Path to institution's workspace directory, or None if not found.
        """
        inst_dir = self.get_institution_dir(institution_id)
        if inst_dir.exists():
            return inst_dir
        return None

    def create_institution_workspace(self, institution: Institution) -> Path:
        """Create the full workspace structure for an institution.

        Args:
            institution: Institution to create workspace for.

        Returns:
            Path to the created workspace directory.
        """
        inst_dir = self.get_institution_dir(institution.id)
        inst_dir.mkdir(parents=True, exist_ok=True)

        # Create top-level directories
        subdirs = [
            "catalog/originals",
            "catalog/audit",
            "catalog/redlines",
            "catalog/finals",
            "policies",
            "exhibits",
            "faculty",
            "achievements",
            "visit_prep",
            "responses",
            "submissions",
            "agent_sessions",
        ]

        for subdir in subdirs:
            (inst_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Create program directories
        for program in institution.programs:
            self._create_program_dirs(inst_dir, program.id)

        # Save institution.json
        self._write_json(inst_dir / "institution.json", institution.to_dict())

        # Initialize truth_index.json if it doesn't exist
        truth_path = inst_dir / "truth_index.json"
        if not truth_path.exists():
            self._write_json(truth_path, self._create_default_truth_index(institution))

        return inst_dir

    def _create_program_dirs(self, inst_dir: Path, program_id: str) -> Path:
        """Create directory structure for a program.

        Args:
            inst_dir: Institution workspace directory.
            program_id: Program identifier.

        Returns:
            Path to program directory.
        """
        safe_id = self._sanitize_path(program_id)
        program_dir = inst_dir / "programs" / safe_id

        subdirs = [
            "originals",
            "audits",
            "redlines",
            "finals",
            "crossrefs",
            "checklists",
            "_versions",
        ]

        for subdir in subdirs:
            (program_dir / subdir).mkdir(parents=True, exist_ok=True)

        return program_dir

    def _create_default_truth_index(self, institution: Institution) -> Dict[str, Any]:
        """Create a default truth index for an institution.

        Args:
            institution: Institution to create truth index for.

        Returns:
            Default truth index dictionary.
        """
        return {
            "institution": {
                "name": institution.name,
                "accreditor_school_ids": institution.school_ids,
                "campuses": institution.campuses,
                "state_authority": institution.state_authority,
            },
            "programs": {
                p.id: {
                    "name_en": p.name_en,
                    "name_es": p.name_es,
                    "total_credits": p.total_credits,
                    "total_cost": p.total_cost,
                    "duration_months": p.duration_months,
                    "academic_periods": p.academic_periods,
                    "cost_per_period": p.cost_per_period,
                    "book_cost": p.book_cost,
                    "modality": p.modality.value,
                }
                for p in institution.programs
            },
            "policies": {},
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    def save_institution(self, institution: Institution) -> Path:
        """Save institution data to workspace.

        Creates workspace if it doesn't exist. Updates institution.json
        and creates any new program directories.

        Args:
            institution: Institution to save.

        Returns:
            Path to institution.json file.
        """
        inst_dir = self.get_institution_dir(institution.id)

        if not inst_dir.exists():
            return self.create_institution_workspace(institution)

        # Ensure all program directories exist
        for program in institution.programs:
            program_dir = inst_dir / "programs" / self._sanitize_path(program.id)
            if not program_dir.exists():
                self._create_program_dirs(inst_dir, program.id)

        # Update institution.json
        institution_file = inst_dir / "institution.json"
        self._write_json(institution_file, institution.to_dict())

        return institution_file

    def load_institution(self, institution_id: str) -> Optional[Institution]:
        """Load institution from workspace.

        Args:
            institution_id: Institution identifier.

        Returns:
            Institution object if found, None otherwise.
        """
        inst_dir = self.get_institution_dir(institution_id)
        institution_file = inst_dir / "institution.json"

        if not institution_file.exists():
            return None

        data = self._read_json(institution_file)
        return Institution.from_dict(data)

    def list_institutions(self) -> List[Dict[str, Any]]:
        """List all institutions in the workspace.

        Returns:
            List of institution metadata dictionaries including:
            - id, name, accrediting_body
            - program_count, document_count
            - compliance_status (compliant/partial/non_compliant/not_assessed)
            - updated_at
        """
        institutions = []

        for inst_dir in self.base_dir.iterdir():
            if inst_dir.is_dir():
                institution_file = inst_dir / "institution.json"
                if institution_file.exists():
                    try:
                        data = self._read_json(institution_file)
                        documents = data.get("documents", [])

                        # Calculate compliance status from documents/audits
                        compliance_status = self._calculate_compliance_status(data)

                        institutions.append({
                            "id": data.get("id"),
                            "name": data.get("name"),
                            "accrediting_body": data.get("accrediting_body"),
                            "program_count": len(data.get("programs", [])),
                            "document_count": len(documents),
                            "compliance_status": compliance_status,
                            "updated_at": data.get("updated_at"),
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue

        return sorted(institutions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def _calculate_compliance_status(self, data: Dict[str, Any]) -> str:
        """Calculate overall compliance status for an institution.

        Args:
            data: Institution data dictionary.

        Returns:
            One of: 'compliant', 'partial', 'non_compliant', 'not_assessed'
        """
        # Check if there are any audits with findings
        documents = data.get("documents", [])
        if not documents:
            return "not_assessed"

        # Look for audit results in the workspace
        # For now, return not_assessed until audits are implemented
        # TODO: Aggregate from actual audit findings
        return "not_assessed"

    def delete_institution(self, institution_id: str) -> bool:
        """Delete an institution's workspace.

        Args:
            institution_id: Institution identifier.

        Returns:
            True if deleted, False if not found.
        """
        inst_dir = self.get_institution_dir(institution_id)

        if inst_dir.exists():
            shutil.rmtree(inst_dir)
            return True
        return False

    # ===========================
    # Truth Index Operations
    # ===========================

    def get_truth_index(self, institution_id: str) -> Optional[Dict[str, Any]]:
        """Get the truth index for an institution.

        Args:
            institution_id: Institution identifier.

        Returns:
            Truth index dictionary if found, None otherwise.
        """
        inst_dir = self.get_institution_dir(institution_id)
        truth_path = inst_dir / "truth_index.json"

        if not truth_path.exists():
            return None

        return self._read_json(truth_path)

    def update_truth_index(
        self,
        institution_id: str,
        updates: Dict[str, Any],
        path: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update values in the truth index.

        Args:
            institution_id: Institution identifier.
            updates: Dictionary of updates to apply.
            path: Optional path to nested location (e.g., ["programs", "prog_123"]).

        Returns:
            Updated truth index.
        """
        inst_dir = self.get_institution_dir(institution_id)
        truth_path = inst_dir / "truth_index.json"

        if not truth_path.exists():
            raise ValueError(f"Truth index not found for institution {institution_id}")

        truth_index = self._read_json(truth_path)

        # Navigate to the target location if path is provided
        target = truth_index
        if path:
            for key in path:
                if key not in target:
                    target[key] = {}
                target = target[key]

        # Apply updates
        target.update(updates)
        truth_index["updated_at"] = datetime.utcnow().isoformat() + "Z"

        self._write_json(truth_path, truth_index)
        return truth_index

    # ===========================
    # File Operations
    # ===========================

    def save_file(
        self,
        institution_id: str,
        relative_path: str,
        content: bytes,
        create_version: bool = True
    ) -> Path:
        """Save a file to the workspace.

        Args:
            institution_id: Institution identifier.
            relative_path: Path relative to institution directory.
            content: File content as bytes.
            create_version: Whether to version the previous file.

        Returns:
            Path to saved file.
        """
        inst_dir = self.get_institution_dir(institution_id)
        file_path = inst_dir / relative_path

        # Version existing file if requested
        if create_version and file_path.exists():
            self._version_file(file_path)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(file_path, "wb") as f:
            f.write(content)

        return file_path

    def _version_file(self, file_path: Path) -> Path:
        """Create a versioned backup of a file.

        Args:
            file_path: Path to file to version.

        Returns:
            Path to versioned file.
        """
        versions_dir = file_path.parent / "_versions"
        versions_dir.mkdir(exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        version_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        version_path = versions_dir / version_name

        shutil.copy2(file_path, version_path)
        return version_path

    def read_file(self, institution_id: str, relative_path: str) -> Optional[bytes]:
        """Read a file from the workspace.

        Args:
            institution_id: Institution identifier.
            relative_path: Path relative to institution directory.

        Returns:
            File content as bytes, or None if not found.
        """
        inst_dir = self.get_institution_dir(institution_id)
        file_path = inst_dir / relative_path

        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            return f.read()

    def list_files(
        self,
        institution_id: str,
        relative_path: str = "",
        pattern: str = "*"
    ) -> List[Dict[str, Any]]:
        """List files in a workspace directory.

        Args:
            institution_id: Institution identifier.
            relative_path: Path relative to institution directory.
            pattern: Glob pattern to match files.

        Returns:
            List of file metadata dictionaries.
        """
        inst_dir = self.get_institution_dir(institution_id)
        target_dir = inst_dir / relative_path if relative_path else inst_dir

        if not target_dir.exists():
            return []

        files = []
        for path in target_dir.glob(pattern):
            if path.is_file() and not path.name.endswith(".lock"):
                stat = path.stat()
                files.append({
                    "name": path.name,
                    "path": str(path.relative_to(inst_dir)),
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return sorted(files, key=lambda x: x["modified_at"], reverse=True)

    def get_file_versions(
        self,
        institution_id: str,
        relative_path: str
    ) -> List[Dict[str, Any]]:
        """Get version history for a file.

        Args:
            institution_id: Institution identifier.
            relative_path: Path to file relative to institution directory.

        Returns:
            List of version metadata dictionaries.
        """
        inst_dir = self.get_institution_dir(institution_id)
        file_path = inst_dir / relative_path
        versions_dir = file_path.parent / "_versions"

        if not versions_dir.exists():
            return []

        stem = file_path.stem
        versions = []

        for path in versions_dir.glob(f"{stem}_*{file_path.suffix}"):
            stat = path.stat()
            versions.append({
                "name": path.name,
                "path": str(path.relative_to(inst_dir)),
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        return sorted(versions, key=lambda x: x["created_at"], reverse=True)

    # ===========================
    # Agent Session Operations
    # ===========================

    def save_agent_session(
        self,
        institution_id: str,
        session_data: Dict[str, Any]
    ) -> Path:
        """Save an agent session log.

        Args:
            institution_id: Institution identifier.
            session_data: Session data dictionary.

        Returns:
            Path to saved session file.
        """
        inst_dir = self.get_institution_dir(institution_id)
        sessions_dir = inst_dir / "agent_sessions"
        sessions_dir.mkdir(exist_ok=True)

        session_id = session_data.get("id", "unknown")
        session_file = sessions_dir / f"{session_id}.json"

        self._write_json(session_file, session_data)
        return session_file

    def load_agent_session(
        self,
        institution_id: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load an agent session log.

        Args:
            institution_id: Institution identifier.
            session_id: Session identifier.

        Returns:
            Session data dictionary if found, None otherwise.
        """
        inst_dir = self.get_institution_dir(institution_id)
        session_file = inst_dir / "agent_sessions" / f"{session_id}.json"

        if not session_file.exists():
            return None

        return self._read_json(session_file)

    def list_agent_sessions(
        self,
        institution_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List recent agent sessions.

        Args:
            institution_id: Institution identifier.
            limit: Maximum number of sessions to return.

        Returns:
            List of session summary dictionaries.
        """
        inst_dir = self.get_institution_dir(institution_id)
        sessions_dir = inst_dir / "agent_sessions"

        if not sessions_dir.exists():
            return []

        sessions = []
        for session_file in sessions_dir.glob("*.json"):
            try:
                data = self._read_json(session_file)
                sessions.append({
                    "id": data.get("id"),
                    "orchestrator_request": data.get("orchestrator_request", "")[:100],
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                    "completed_at": data.get("completed_at"),
                    "total_api_calls": data.get("total_api_calls", 0),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions[:limit]
