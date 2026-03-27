---
plan: 9-03-01
phase: 9-03
subsystem: importers
tags: [standards, parsing, extraction, validation]
dependency_graph:
  requires: []
  provides: [standards-extractors, standards-parser, standards-validator, standards-importer]
  affects: [standards-library, audit-engine]
tech_stack:
  added: []
  patterns: [factory-pattern, pipeline-pattern, dataclass-serialization]
key_files:
  created:
    - src/importers/standards_extractors.py
    - src/importers/standards_parser.py
    - src/importers/standards_validator.py
    - src/importers/standards_importer.py
    - src/db/migrations/0038_standards_importer.sql
  modified: []
decisions:
  - Factory pattern for pluggable extractors (PDF, Excel, CSV, text, web)
  - Three-layer pipeline: extract -> parse -> validate -> create library
  - Quality scoring with weighted structure/content/coverage scores
  - Confidence thresholds for automated import decisions
metrics:
  duration: ~15 minutes
  completed: 2026-03-27
---

# Phase 9-03 Plan 01: Core Extraction and Parsing Pipeline Summary

Factory-based standards extraction pipeline with hierarchy detection, requirement extraction, and quality validation for importing accreditation standards from any source format.

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| e86180b | feat | add standards extractors with factory pattern |
| 7996112 | feat | add standards parser with hierarchy detection |
| a281361 | feat | add standards validator |
| 248b3f3 | feat | add standards importer pipeline |
| b32c8bf | feat | add migration for standards_imports table |

## What Was Built

### Standards Extractors (`src/importers/standards_extractors.py`)
- **ExtractorFactory**: Routes to correct extractor by file type/URL
- **PdfExtractor**: Uses pdfplumber for text and table extraction
- **ExcelExtractor**: Uses openpyxl for multi-sheet workbooks
- **CsvExtractor**: Handles delimited data with encoding detection
- **TextExtractor**: Plain text with heading pattern detection
- **WebExtractor**: Fetches URLs, uses BeautifulSoup if available
- **ExtractedContent**: Dataclass with raw_text, structural_hints, tables, metadata

### Standards Parser (`src/importers/standards_parser.py`)
- **HierarchyParser**: Detects numbering schemes (Roman, Arabic, letter, combined)
- **RequirementExtractor**: Finds requirements using indicator patterns (must, shall, required)
- **MetadataExtractor**: Extracts title, version, date, accreditor from content
- **StandardsParser**: Orchestrates parsing pipeline
- Supports both hierarchical text and tabular (Excel/CSV) formats
- Infers parent-child relationships from section numbering

### Standards Validator (`src/importers/standards_validator.py`)
- **SchemaValidator**: Checks required fields (number, title, description)
- **ConflictDetector**: Finds duplicates, orphans, circular references
- **QualityScorer**: Computes 0-100 scores for structure, content, coverage
- **ValidationResult**: Issues categorized by severity (error/warning/info)
- Auto-fixable flags for certain issues

### Standards Importer (`src/importers/standards_importer.py`)
- **StandardsImporter**: Full pipeline orchestrator
- `import_from_file()`: PDF, Excel, CSV, text files
- `import_from_url()`: Web page standards
- `import_from_text()`: Raw text input
- **ImportResult**: Contains all pipeline outputs
- Progress callback for UI updates
- `finalize_import()`: Applies user mappings, saves to StandardsStore
- Source hash computation for deduplication

### Database Migration (`src/db/migrations/0038_standards_importer.sql`)
- `standards_imports` table for tracking import history
- Fields: source info, status, results, validation, timing
- Indexes: institution, status, accreditor, created_at, library_id, source_hash

## Numbering Schemes Detected

| Scheme | Pattern | Example |
|--------|---------|---------|
| roman_upper | I, II, III | I. Introduction |
| arabic | 1, 2, 3 | 1. Standards |
| letter_upper | A, B, C | A. General |
| combined_decimal | 1.1, 1.2 | 1.2 Requirements |
| triple_decimal | 1.1.1 | 1.2.3 Specific |
| accsc_style | I.A.1 | I.A.1 Eligibility |
| sacscoc_style | 1.A.1 | 1.A.1 Mission |

## Quality Score Components

| Component | Weight | Factors |
|-----------|--------|---------|
| Structure | 30% | Hierarchy depth, section count, parent links |
| Content | 35% | Text length, descriptions present |
| Coverage | 35% | Items per section, categories, applies_to |
| Issue Penalty | - | -10 per error, -2 per warning (max 40) |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] src/importers/standards_extractors.py exists
- [x] src/importers/standards_parser.py exists
- [x] src/importers/standards_validator.py exists
- [x] src/importers/standards_importer.py exists
- [x] src/db/migrations/0038_standards_importer.sql exists
- [x] Commit e86180b exists
- [x] Commit 7996112 exists
- [x] Commit a281361 exists
- [x] Commit 248b3f3 exists
- [x] Commit b32c8bf exists
- [x] Module imports successfully
