# Phase 24: Standards Harvester MVP - Research

**Researched:** 2026-03-22
**Domain:** Web scraping, PDF parsing, version control, diff generation
**Confidence:** HIGH

## Summary

The Standards Harvester MVP will enable fetching accreditation standards from three sources (web scraping, PDF parsing, manual upload), track versions using SHA256 hashing, and display side-by-side diffs of changes. The existing codebase provides strong foundations with established patterns for PDF parsing (`document_parser.py`), SHA256 hashing (`change_detection_service.py`), and diff generation (`difflib.HtmlDiff`). The phase requires minimal new dependencies — only `beautifulsoup4` and `lxml` for web scraping, both of which are already available in the Python ecosystem and compatible with the Flask architecture.

**Primary recommendation:** Use BeautifulSoup + requests for static HTML scraping (ACCSC standards pages), reuse existing `DocumentParser` for PDF extraction, implement SHA256-based versioning following the `document_changes` table pattern, and leverage existing `difflib.HtmlDiff` for side-by-side diff display.

## User Constraints (from CONTEXT.md)

### Locked Decisions
1. **Three fetch methods:** Web scraping, PDF parsing, AND manual upload (all three required, not alternatives)
2. **Version tracking:** SHA256 hash + timestamp for each version
3. **Diff display:** Side-by-side comparison showing additions/removals/modifications
4. **MVP scope:** Manual trigger only (no auto-scheduling), ACCSC first (single accreditor), version-level tracking only (not standard-by-standard)

### Claude's Discretion
- Database schema design for `standards_versions` table
- UI layout for harvester configuration and diff viewer
- Error handling and retry logic for web scraping
- Rate limiting strategy for web requests

### Deferred Ideas (OUT OF SCOPE)
- Auto-scheduling harvests (manual trigger only for MVP)
- Multiple accreditors simultaneously (start with ACCSC)
- Standard-by-standard granular tracking (version-level only)

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| beautifulsoup4 | 4.14.3+ | HTML parsing for web scraping | Industry standard for static HTML parsing, 70% faster than Selenium, zero browser overhead |
| lxml | 6.0.2+ | Fast XML/HTML parser backend for BeautifulSoup | High-performance C-based parser, faster than html.parser |
| requests | 2.32.3+ | HTTP client for fetching web pages | De facto standard for HTTP requests, simple API, already in requirements.txt |
| pdfplumber | 0.11.9+ | PDF text extraction | Already in use (`document_parser.py`), excellent table extraction, active maintenance |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| difflib | 3.x (stdlib) | Side-by-side text diff | Already used in `change_detection_service.py`, no additional dependency |
| hashlib | 3.x (stdlib) | SHA256 hashing | Already used for file versioning in `change_detection_service.py`, proven pattern |
| pytesseract | 0.3.10+ | OCR for image-based PDFs | Already in use, fallback if PDF text extraction fails |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| BeautifulSoup | Selenium/Playwright | Selenium needed only if JavaScript rendering required (ACCSC uses static HTML) — 70% slower, browser overhead |
| difflib | diff-match-patch | 20x faster but adds dependency — difflib sufficient for standards documents (< 50KB text) |
| requests | urllib/httpx | requests simpler API, already in stack — httpx adds async but not needed for manual triggers |

**Installation:**
```bash
# Already in requirements.txt
pip install beautifulsoup4 lxml requests pdfplumber
```

**Version verification:** Verified 2026-03-22 via pip show on development environment.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── harvesters/
│   ├── __init__.py
│   ├── base_harvester.py         # Abstract base class
│   ├── web_harvester.py          # BeautifulSoup scraper
│   ├── pdf_harvester.py          # PDF download + parse
│   └── manual_harvester.py       # User upload handler
├── services/
│   └── standards_versioning_service.py  # Version storage, diff generation
├── api/
│   └── standards_harvester.py    # Flask blueprint
└── db/migrations/
    └── 0032_standards_harvester.sql
```

### Pattern 1: Harvester Base Class (Registry Pattern)
**What:** Abstract base with `fetch()` method, concrete implementations for each source type
**When to use:** Enables consistent interface across web/PDF/manual sources
**Example:**
```python
# Reuses agent registry pattern from src/agents/registry.py
from abc import ABC, abstractmethod
from enum import Enum

class HarvesterType(str, Enum):
    WEB_SCRAPER = "web_scraper"
    PDF_PARSER = "pdf_parser"
    MANUAL_UPLOAD = "manual_upload"

class BaseHarvester(ABC):
    @abstractmethod
    def fetch(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch standards content from source.

        Returns:
            {
                "text": str,
                "metadata": {...},
                "source_url": str
            }
        """
        pass

@register_harvester(HarvesterType.WEB_SCRAPER)
class WebHarvester(BaseHarvester):
    def fetch(self, source_config):
        url = source_config["url"]
        # BeautifulSoup implementation
```

### Pattern 2: SHA256 Versioning (Change Detection Pattern)
**What:** Compute file hash, store with timestamp, compare to detect changes
**When to use:** Every time standards are fetched/uploaded
**Example:**
```python
# Source: src/services/change_detection_service.py (lines 56-67)
import hashlib
from pathlib import Path

def compute_file_hash(file_path: str) -> Optional[str]:
    """Compute SHA256 hash of file (chunked for large files)."""
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to compute hash: {e}")
        return None
```

### Pattern 3: Web Scraping with Rate Limiting
**What:** requests + BeautifulSoup with polite crawling (10-15s delays, User-Agent, robots.txt check)
**When to use:** Fetching ACCSC standards HTML pages
**Example:**
```python
import requests
from bs4 import BeautifulSoup
import time

def fetch_accsc_standards(url: str) -> str:
    """Fetch ACCSC standards with rate limiting."""
    headers = {
        'User-Agent': 'AccreditAI Standards Harvester/1.0 (Educational Tool)'
    }

    # Rate limit: 10-15 seconds between requests
    time.sleep(12)

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'lxml')
    # Extract standards text from HTML structure
    content = soup.find('div', class_='standards-content')
    return content.get_text(strip=True) if content else ""
```

### Pattern 4: Diff Generation (Existing Pattern)
**What:** `difflib.HtmlDiff` for side-by-side comparison
**When to use:** Displaying changes between versions
**Example:**
```python
# Source: src/services/change_detection_service.py (lines 378-409)
from difflib import HtmlDiff

def generate_standards_diff(old_text: str, new_text: str) -> str:
    """Generate side-by-side HTML diff."""
    if not old_text:
        return '<div class="diff-info">New version - no previous version</div>'

    differ = HtmlDiff(wrapcolumn=80)
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    html = differ.make_table(
        old_lines,
        new_lines,
        fromdesc="Previous Version",
        todesc="Current Version",
        context=True,   # Only show changed sections
        numlines=3      # 3 lines of context
    )
    return html
```

### Anti-Patterns to Avoid
- **Selenium for static HTML:** ACCSC standards pages are static — BeautifulSoup is 70% faster and avoids browser overhead
- **Storing full text in database:** Store file paths, load text on demand (database bloat with 50KB+ documents)
- **Manual diff parsing:** `difflib.HtmlDiff` handles all edge cases (line wrapping, encoding, whitespace normalization)
- **Ignoring robots.txt:** Always check `/robots.txt` before scraping, respect crawl delays

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML parsing | Regex-based tag extraction | BeautifulSoup with lxml parser | Handles malformed HTML, nested tags, encoding detection — regex fails on complex HTML |
| PDF text extraction | Custom PDF reader | pdfplumber (already in use) | Handles complex layouts, tables, embedded fonts, scanned PDFs — custom parser misses edge cases |
| Text diff generation | Line-by-line comparison logic | difflib.HtmlDiff (stdlib) | Handles whitespace normalization, context windows, HTML escaping — reinventing introduces bugs |
| File hashing | Custom checksum | hashlib.sha256 (stdlib) | Cryptographically secure, optimized C implementation, handles large files via chunking |
| HTTP retry logic | Manual retry loops | requests with tenacity/urllib3.Retry | Exponential backoff, jitter, timeout handling — manual loops miss edge cases |

**Key insight:** Document processing and web scraping have mature, battle-tested libraries. Custom implementations introduce bugs (encoding issues, edge cases, performance) without adding value.

## Common Pitfalls

### Pitfall 1: Scraping Without Rate Limiting
**What goes wrong:** Accreditor websites block IP or return 429 errors after too many rapid requests
**Why it happens:** Developers focus on speed, ignore server load and robots.txt directives
**How to avoid:**
- Implement 10-15 second delays between requests (conservative baseline per web scraping best practices 2026)
- Set descriptive User-Agent header: `AccreditAI Standards Harvester/1.0 (Educational Tool)`
- Check robots.txt before first request, cache allowed paths
- Monitor HTTP 429/503 responses, implement exponential backoff
**Warning signs:** HTTP 429 responses, connection timeouts, IP blocks

### Pitfall 2: Hash Mismatch on Identical Content
**What goes wrong:** SHA256 hash changes even when standards text is identical (whitespace, encoding, metadata changes)
**Why it happens:** PDF metadata updates, HTML formatting changes, line ending normalization issues
**How to avoid:**
- Hash extracted text content, not raw PDF/HTML bytes
- Normalize whitespace: `text.strip().replace('\r\n', '\n')`
- Strip PDF metadata before extraction: use pdfplumber text-only mode
- Consider semantic diff: if hashes differ but text diff is empty, mark as "metadata-only change"
**Warning signs:** Every fetch triggers "new version" despite no visible content changes

### Pitfall 3: PDF Text Extraction Failures
**What goes wrong:** pdfplumber returns empty string for scanned PDFs or image-based documents
**Why it happens:** PDF contains images of text, not actual text layers
**How to avoid:**
- Check `parsed.text` length after extraction — if < 100 chars, likely failed
- Fall back to pytesseract OCR (already in stack): `_parse_image()` pattern from `document_parser.py`
- Log extraction method used (text vs. OCR) for debugging
- Store `extraction_method` in metadata: `{"method": "ocr", "confidence": "low"}`
**Warning signs:** Empty text from large PDFs, nonsensical diff output

### Pitfall 4: Encoding Errors on HTML Parsing
**What goes wrong:** BeautifulSoup garbles accented characters, symbols render as `�`
**Why it happens:** Incorrect charset detection, server sends wrong Content-Type header
**How to avoid:**
- Use BeautifulSoup's auto-detection: `BeautifulSoup(response.content, 'lxml')` (bytes, not text)
- Respect `<meta charset>` tags: lxml handles this automatically
- Validate encoding: check if text contains `�`, re-parse with different encoding
- Store original encoding in metadata: `response.encoding`
**Warning signs:** Garbled text in diffs, Unicode replacement characters (`U+FFFD`)

### Pitfall 5: Large Diff Performance
**What goes wrong:** `difflib.HtmlDiff` takes 10+ seconds for 100KB+ standards documents
**Why it happens:** Diff algorithm is O(n*m) — large documents cause exponential slowdown
**How to avoid:**
- Pre-filter: if hash identical, skip diff generation entirely
- Section-by-section diff: split standards into sections (I.A, I.B, etc.), diff each independently
- Show summary first: "23 changes in 5 sections" with expandable details
- Consider diff-match-patch for 100KB+ documents (20x faster but adds dependency)
**Warning signs:** Browser timeout on diff page load, high CPU usage

## Code Examples

Verified patterns from codebase:

### Example 1: File Hash Computation (Existing Pattern)
```python
# Source: src/services/change_detection_service.py (lines 56-67)
import hashlib
from pathlib import Path

def compute_file_hash(file_path: str) -> Optional[str]:
    """Compute SHA256 hash with chunking for large files."""
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            # 8KB chunks to handle large PDFs
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to compute hash for {file_path}: {e}")
        return None
```

### Example 2: PDF Parsing (Existing Pattern)
```python
# Source: src/importers/document_parser.py (lines 155-207)
import pdfplumber

def parse_standards_pdf(file_path: str) -> str:
    """Extract text from standards PDF."""
    pages_text = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)
    except Exception as e:
        raise ValueError(f"PDF parse error: {e}")

    full_text = "\n\n".join(pages_text)
    return full_text.strip()
```

### Example 3: Web Scraping with BeautifulSoup
```python
# Pattern for ACCSC standards page scraping
import requests
from bs4 import BeautifulSoup
import time

def scrape_accsc_standards(url: str) -> Dict[str, Any]:
    """Scrape ACCSC standards from official website."""
    headers = {
        'User-Agent': 'AccreditAI Standards Harvester/1.0 (Educational Tool)',
        'Accept': 'text/html,application/xhtml+xml'
    }

    # Rate limiting: 12 seconds between requests
    time.sleep(12)

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'lxml')

    # Extract standards content (selector depends on ACCSC HTML structure)
    content_div = soup.find('div', id='standards-content')
    if not content_div:
        raise ValueError("Standards content not found in HTML")

    # Get text with preserved structure
    text = content_div.get_text(separator='\n', strip=True)

    # Extract metadata
    title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Unknown"
    effective_date = soup.find('span', class_='effective-date')
    effective_date_text = effective_date.get_text(strip=True) if effective_date else None

    return {
        "text": text,
        "metadata": {
            "title": title,
            "effective_date": effective_date_text,
            "source_url": url,
            "scraped_at": datetime.now().isoformat(),
            "encoding": response.encoding
        }
    }
```

### Example 4: Version Comparison Logic
```python
# Pattern for detecting version changes
from dataclasses import dataclass
from typing import Optional

@dataclass
class StandardsVersion:
    id: str
    accreditor_id: str
    version_date: str
    content_hash: str
    file_path: str
    source_type: str  # 'web_scrape', 'pdf_parse', 'manual_upload'
    source_url: Optional[str]
    metadata: Dict[str, Any]

def detect_standards_change(
    accreditor_id: str,
    new_text: str,
    new_metadata: Dict[str, Any],
    conn
) -> Dict[str, Any]:
    """Detect if standards have changed since last version."""
    # Normalize text for hashing
    normalized_text = new_text.strip().replace('\r\n', '\n')
    new_hash = hashlib.sha256(normalized_text.encode()).hexdigest()

    # Get latest version from database
    cursor = conn.execute("""
        SELECT content_hash, version_date, file_path
        FROM standards_versions
        WHERE accreditor_id = ?
        ORDER BY version_date DESC
        LIMIT 1
    """, (accreditor_id,))

    row = cursor.fetchone()

    if not row:
        return {
            "changed": True,
            "is_new": True,
            "previous_hash": None,
            "new_hash": new_hash
        }

    if row["content_hash"] == new_hash:
        return {
            "changed": False,
            "is_new": False,
            "previous_hash": row["content_hash"],
            "new_hash": new_hash
        }

    return {
        "changed": True,
        "is_new": False,
        "previous_hash": row["content_hash"],
        "new_hash": new_hash,
        "previous_version_date": row["version_date"],
        "previous_file_path": row["file_path"]
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Regex HTML parsing | BeautifulSoup with lxml | Stable since 2015 | Handles malformed HTML, faster parsing |
| PyPDF2 text extraction | pdfplumber | Adopted ~2020 | Better table extraction, active maintenance |
| Manual diff display | difflib.HtmlDiff | Stdlib since Python 2.1 | Zero dependencies, consistent output |
| Manual rate limiting | requests + time.sleep + robots.txt check | Best practice 2026 | Respects server load, avoids blocks |

**Deprecated/outdated:**
- **PyPDF2:** Unmaintained since 2022, replaced by pdfplumber or pypdf (fork)
- **Selenium for static HTML:** Overkill for ACCSC (static pages) — BeautifulSoup 70% faster
- **MD5 hashing:** SHA256 now standard (MD5 cryptographically broken, avoid for security-sensitive use)

## Open Questions

1. **ACCSC HTML structure stability**
   - What we know: ACCSC publishes standards at https://www.accsc.org/seeking-accreditation/the-standards-of-accreditation/
   - What's unclear: Exact HTML selectors, whether content is in single page or multi-page structure
   - Recommendation: Implement flexible selectors with fallbacks, log HTML structure on first fetch for debugging

2. **Version date source**
   - What we know: ACCSC standards have "effective date" metadata
   - What's unclear: Whether effective date is in HTML, PDF metadata, or requires manual entry
   - Recommendation: Extract from HTML/PDF if available, fall back to user input during manual upload

3. **Storage location for standards files**
   - What we know: Existing documents stored in `workspace/{institution_id}/...`
   - What's unclear: Whether standards (global, not institution-specific) should be in workspace or separate directory
   - Recommendation: Store in `standards_library/versions/{accreditor_id}/{version_date}/` (global, shared across institutions)

## Validation Architecture

> Phase testing enabled (workflow.nyquist_validation not explicitly disabled in .planning/config.json)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.0+ |
| Config file | None — see Wave 0 |
| Quick run command | `pytest tests/test_standards_harvester.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HARV-01 | Fetch ACCSC standards from official URL | integration | `pytest tests/test_web_harvester.py::test_fetch_accsc_standards -x` | ❌ Wave 0 |
| HARV-02 | Store version with date and SHA256 hash | unit | `pytest tests/test_standards_versioning_service.py::test_store_version -x` | ❌ Wave 0 |
| HARV-03 | Display diff against previous version | integration | `pytest tests/test_standards_versioning_service.py::test_generate_diff -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_standards_harvester.py -x` (stop on first failure)
- **Per wave merge:** `pytest tests/ -v` (verbose output, all tests)
- **Phase gate:** Full suite green + manual smoke test (fetch ACCSC, view diff) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_web_harvester.py` — covers HARV-01 (web scraping with BeautifulSoup)
- [ ] `tests/test_pdf_harvester.py` — covers PDF parsing (reuses document_parser.py patterns)
- [ ] `tests/test_standards_versioning_service.py` — covers HARV-02, HARV-03 (storage, diff generation)
- [ ] `tests/conftest.py` — fixtures for mock HTML responses, sample PDFs
- [ ] Framework install: Already installed (`pytest>=7.4.0` in requirements.txt)

## Sources

### Primary (HIGH confidence)
- Existing codebase patterns:
  - `src/importers/document_parser.py` — pdfplumber implementation (lines 155-207)
  - `src/services/change_detection_service.py` — SHA256 hashing (lines 56-67), difflib.HtmlDiff (lines 378-409)
  - `src/db/migrations/0012_change_detection.sql` — version tracking table pattern
  - `templates/partials/diff_viewer.html` — diff UI pattern
- Official Python documentation:
  - difflib.HtmlDiff: https://docs.python.org/3/library/difflib.html
  - hashlib.sha256: https://docs.python.org/3/library/hashlib.html

### Secondary (MEDIUM confidence)
- [Selenium vs. BeautifulSoup in 2026: Which Is Better? - ZenRows](https://www.zenrows.com/blog/selenium-vs-beautifulsoup)
- [BeautifulSoup vs. Selenium: A Detailed Comparison | BrowserStack](https://www.browserstack.com/guide/beautifulsoup-vs-selenium)
- [Best Python Libraries to Extract Tables From PDF in 2026](https://unstract.com/blog/extract-tables-from-pdf-python/)
- [PDFPlumber – Extract & Process PDF Data Easily](https://www.pdfplumber.com/)
- [Web Scraping Best Practices in 2026 | ScrapingBee](https://www.scrapingbee.com/blog/web-scraping-best-practices/)
- [Ethical Web Scraping: Legal Rules, Best Practices and Compliance Guide for 2025](https://scrapingapi.ai/blog/ethical-web-scraping)
- [SHA-256 Hash: Prove File Integrity | LegalStamp](https://legalstamp.app/en/blog/sha-256-hash-prove-file-integrity)
- [File Hashing Guide | ByteTools](https://bytetools.io/guides/file-hashing)

### Tertiary (LOW confidence)
- [The Standards of Accreditation - ACCSC](https://www.accsc.org/seeking-accreditation/the-standards-of-accreditation/) — HTML structure needs verification during implementation
- [Comparing Python Diff Libraries](https://czarrar.github.io/python-diff/) — Overview of alternatives (diff-match-patch), not implementation-specific

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - BeautifulSoup, pdfplumber, difflib all verified in existing codebase or requirements.txt, version numbers confirmed via pip
- Architecture: HIGH - Patterns directly reused from existing services (change_detection, document_parser), proven in production
- Pitfalls: MEDIUM - Web scraping pitfalls based on best practices articles, PDF extraction pitfalls from codebase experience
- Storage schema: MEDIUM - Follows existing migration patterns, but specific fields need validation during implementation

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (30 days — stable domain, libraries mature)
