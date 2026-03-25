"""Manual upload harvester for standards content.

Accepts user-provided text directly.
"""

import logging
from typing import Dict, Any

from src.harvesters.base_harvester import BaseHarvester
from src.core.models import now_iso


logger = logging.getLogger(__name__)


class ManualHarvester(BaseHarvester):
    """Harvester for manually uploaded standards text.

    Simplest harvester - just passes through user-provided text.
    """

    def fetch(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch standards from manually provided text.

        Args:
            source_config: Must contain:
                - "text": str (standards content)
                - "notes": str (optional notes about this version)
                - "version_date": str (optional version date)

        Returns:
            {
                "text": str (provided text),
                "metadata": {
                    "source_type": "manual_upload",
                    "notes": str,
                    "uploaded_at": str
                }
            }

        Raises:
            ValueError: If 'text' is missing
        """
        text = source_config.get("text")
        if not text:
            raise ValueError("Manual harvester requires 'text' in source_config")

        notes = source_config.get("notes", "")

        logger.info(f"Manual upload: {len(text)} characters")

        metadata = {
            "source_type": "manual_upload",
            "notes": notes,
            "uploaded_at": now_iso()
        }

        return {
            "text": text,
            "metadata": metadata
        }
