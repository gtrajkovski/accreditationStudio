"""Accreditor Registry for dynamic accreditor package loading."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

ACCREDITORS_DIR = Path(__file__).parent


@dataclass
class AccreditorManifest:
    """Accreditor package manifest."""
    id: str
    name: str
    code: str
    type: str  # institutional | programmatic
    scope: str = ""
    default_language: str = "en-US"
    recognized_by: List[str] = field(default_factory=list)
    website: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccreditorManifest":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            code=data.get("code", ""),
            type=data.get("type", "institutional"),
            scope=data.get("scope", ""),
            default_language=data.get("default_language", "en-US"),
            recognized_by=data.get("recognized_by", []),
            website=data.get("website", ""),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "type": self.type,
            "scope": self.scope,
            "default_language": self.default_language,
            "recognized_by": self.recognized_by,
            "website": self.website,
            "notes": self.notes,
        }


class AccreditorRegistry:
    """Registry for accreditor packages."""

    _packages: Dict[str, AccreditorManifest] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Load all accreditor packages."""
        if cls._initialized:
            return

        for package_dir in ACCREDITORS_DIR.iterdir():
            if package_dir.is_dir() and not package_dir.name.startswith("_"):
                manifest_path = package_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f:
                            data = json.load(f)
                        manifest = AccreditorManifest.from_dict(data)
                        cls._packages[manifest.code.upper()] = manifest
                    except Exception as e:
                        logger.warning(f"Failed to load accreditor manifest {manifest_path}: {e}")

        cls._initialized = True

    @classmethod
    def list_all(cls) -> List[AccreditorManifest]:
        """List all registered accreditors."""
        cls._ensure_initialized()
        return list(cls._packages.values())

    @classmethod
    def get(cls, code: str) -> Optional[AccreditorManifest]:
        """Get accreditor by code."""
        cls._ensure_initialized()
        return cls._packages.get(code.upper())

    @classmethod
    def get_sources_module(cls, code: str):
        """Dynamically import sources module for an accreditor."""
        import importlib
        try:
            return importlib.import_module(f"src.accreditors.{code.lower()}.sources")
        except ImportError:
            logger.debug(f"No sources module found for accreditor {code}")
            return None

    @classmethod
    def get_parser_module(cls, code: str):
        """Dynamically import parser module for an accreditor."""
        import importlib
        try:
            return importlib.import_module(f"src.accreditors.{code.lower()}.parser")
        except ImportError:
            logger.debug(f"No parser module found for accreditor {code}")
            return None


def list_accreditors() -> List[Dict[str, Any]]:
    """List all accreditors as dicts."""
    return [m.to_dict() for m in AccreditorRegistry.list_all()]


def get_accreditor(code: str) -> Optional[Dict[str, Any]]:
    """Get accreditor manifest as dict."""
    manifest = AccreditorRegistry.get(code)
    return manifest.to_dict() if manifest else None
