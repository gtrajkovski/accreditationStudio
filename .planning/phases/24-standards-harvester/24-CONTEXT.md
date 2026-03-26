---
phase: 24-standards-harvester
created: 2026-03-22
---

# Phase 24: Standards Harvester MVP

## Goal
Fetch standards from accreditor websites and track version changes.

## User Decisions

### Fetch Methods (All Three)
User requested support for ALL methods:
1. **Web scraping** — Scrape accreditor website HTML, extract standards text
2. **PDF parsing** — Download/upload PDFs, extract text with existing document parser
3. **Manual upload** — User uploads new standards version for diff comparison

### Expected Workflow
1. User configures accreditor source (URL, PDF, or manual)
2. System fetches/parses standards content
3. System stores with version date and SHA256 hash
4. On re-fetch, system detects changes via hash comparison
5. User views side-by-side diff of changed sections

## Requirements (from ROADMAP.md)
- **HARV-01**: Fetch ACCSC standards from official URL
- **HARV-02**: Store with version date and hash
- **HARV-03**: User can view diff against previous version

## Success Criteria
1. Standards can be fetched via web scraping, PDF parsing, OR manual upload
2. Each version stored with timestamp and SHA256 hash
3. Diff viewer shows changes between versions (additions/removals/modifications)

## Technical Considerations
- Reuse existing `document_parser.py` for PDF extraction
- Web scraping needs rate limiting and error handling
- Store standards versions in database (new table `standards_versions`)
- Diff algorithm: Python difflib for text comparison
- UI: Similar pattern to change detection diff viewer (Phase 22)

## Out of Scope (MVP)
- Auto-scheduling harvests (manual trigger only for MVP)
- Multiple accreditors simultaneously (start with ACCSC)
- Standard-by-standard granular tracking (version-level only)
