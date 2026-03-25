"""Web scraping harvester for standards content.

Uses BeautifulSoup + requests for static HTML parsing.
"""

import time
import logging
from typing import Dict, Any

import requests
from bs4 import BeautifulSoup

from src.harvesters.base_harvester import BaseHarvester
from src.core.models import now_iso


logger = logging.getLogger(__name__)


class WebHarvester(BaseHarvester):
    """Harvester for scraping standards from web pages.

    Implements polite crawling with rate limiting and flexible content extraction.
    """

    def fetch(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch standards by scraping a web page.

        Args:
            source_config: Must contain {"url": str}

        Returns:
            {
                "text": str (extracted text),
                "metadata": {
                    "source_url": str,
                    "title": str,
                    "fetched_at": str,
                    "encoding": str
                }
            }

        Raises:
            ValueError: If URL is missing or fetch fails
        """
        url = source_config.get("url")
        if not url:
            raise ValueError("Web harvester requires 'url' in source_config")

        logger.info(f"Fetching standards from {url}")

        # Rate limiting: 12 seconds per research recommendation
        time.sleep(12)

        # HTTP request with polite User-Agent
        headers = {
            'User-Agent': 'AccreditAI Standards Harvester/1.0 (Educational Tool)',
            'Accept': 'text/html,application/xhtml+xml'
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise ValueError(f"HTTP request failed: {e}")

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'lxml')

        # Extract text with fallback strategy
        content = None

        # Try common content containers
        for selector in [
            ('main', {}),
            ('article', {}),
            ('div', {'class': 'content'}),
            ('div', {'id': 'standards-content'}),
            ('div', {'class': 'standards-content'}),
        ]:
            tag, attrs = selector
            content = soup.find(tag, attrs)
            if content:
                logger.debug(f"Found content in {tag} {attrs}")
                break

        # Fallback to body if no specific container found
        if not content:
            content = soup.find('body')
            logger.warning("No specific content container found, using full body")

        if not content:
            raise ValueError("No content found in HTML")

        # Extract text with preserved structure
        text = content.get_text(separator='\n', strip=True)

        if len(text) < 50:
            logger.warning(f"Extracted text is very short ({len(text)} chars)")

        # Extract metadata
        title = soup.title.string.strip() if soup.title and soup.title.string else "Unknown"

        metadata = {
            "source_url": url,
            "title": title,
            "fetched_at": now_iso(),
            "encoding": response.encoding or "utf-8"
        }

        logger.info(f"Successfully fetched {len(text)} characters from {url}")

        return {
            "text": text,
            "metadata": metadata
        }
