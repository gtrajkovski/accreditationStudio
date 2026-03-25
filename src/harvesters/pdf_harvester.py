"""PDF parsing harvester for standards content.

Uses pdfplumber for text extraction.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any

import requests
import pdfplumber

from src.harvesters.base_harvester import BaseHarvester
from src.core.models import now_iso


logger = logging.getLogger(__name__)


class PdfHarvester(BaseHarvester):
    """Harvester for extracting standards from PDF files.

    Supports both local file paths and remote PDF URLs.
    """

    def fetch(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch standards by parsing a PDF file.

        Args:
            source_config: Must contain either:
                - {"file_path": str} for local file
                - {"url": str} for remote PDF

        Returns:
            {
                "text": str (extracted text),
                "metadata": {
                    "file_path": str,
                    "page_count": int,
                    "extraction_method": "pdfplumber",
                    "fetched_at": str
                }
            }

        Raises:
            ValueError: If neither file_path nor url provided, or parsing fails
        """
        file_path = source_config.get("file_path")
        url = source_config.get("url")

        if not file_path and not url:
            raise ValueError("PDF harvester requires either 'file_path' or 'url' in source_config")

        # Download PDF if URL provided
        if url and not file_path:
            logger.info(f"Downloading PDF from {url}")
            file_path = self._download_pdf(url)

        # Verify file exists
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"PDF file not found: {file_path}")

        logger.info(f"Parsing PDF: {file_path}")

        # Extract text with pdfplumber
        pages_text = []

        try:
            with pdfplumber.open(path) as pdf:
                page_count = len(pdf.pages)

                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages_text.append(text)

        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise ValueError(f"PDF parse error: {e}")

        full_text = "\n\n".join(pages_text)

        # Warn if text extraction yielded very little (possible image-based PDF)
        if len(full_text) < 100:
            logger.warning(
                f"PDF text extraction returned only {len(full_text)} chars. "
                "This may be an image-based PDF requiring OCR."
            )

        metadata = {
            "file_path": str(path),
            "page_count": page_count,
            "extraction_method": "pdfplumber",
            "fetched_at": now_iso()
        }

        logger.info(f"Successfully extracted {len(full_text)} characters from {page_count} pages")

        return {
            "text": full_text,
            "metadata": metadata
        }

    def _download_pdf(self, url: str) -> str:
        """Download PDF from URL to local file.

        Args:
            url: URL of PDF file

        Returns:
            Path to downloaded file

        Raises:
            ValueError: If download fails
        """
        try:
            # Create download directory
            download_dir = Path("standards_library/downloads")
            download_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from URL
            filename = Path(url).name
            if not filename.endswith('.pdf'):
                filename = "standards.pdf"

            file_path = download_dir / filename

            # Download with timeout
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            # Save to file
            with open(file_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded PDF to {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Failed to download PDF from {url}: {e}")
            raise ValueError(f"PDF download failed: {e}")
