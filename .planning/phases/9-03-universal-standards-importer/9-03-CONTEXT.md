---
phase: 9-03
name: Universal Standards Importer
status: planning
created: 2026-03-27
---

# Phase 9-03: Universal Standards Importer

## Goal

Enable users to import accreditation standards from any source (PDF, Excel, CSV, web, text) and automatically parse them into the structured StandardsLibrary format used by the audit engine.

## Problem Statement

Currently, AccreditAI has 5 hardcoded system presets (ACCSC, SACSCOC, HLC, ABHES, COE) with limited structure. Users cannot:
- Import standards from their specific accreditor if not in presets
- Parse PDF handbooks into structured sections
- Import state regulatory requirements
- Import professional licensure standards
- Create custom standards from Excel/CSV

The existing harvester framework extracts raw text but doesn't parse structure.

## Success Criteria

1. **Multi-Format Import**: Support PDF, Excel/CSV, plain text, and web URL sources
2. **Intelligent Parsing**: Detect section hierarchy (I, I.A, I.A.1) and extract requirements
3. **Schema Mapping**: Convert extracted data to StandardsLibrary format
4. **Validation**: Check for duplicate sections, orphaned items, missing fields
5. **AI Enhancement**: Optional AI-powered description improvement
6. **Import History**: Track all imports with status and error logging
7. **UI Workflow**: Guided import with preview, mapping, and confirmation

## Constraints

- Must integrate with existing StandardsStore persistence
- Must follow existing serialization patterns (to_dict/from_dict)
- Agent must use registry pattern with @register_agent decorator
- Blueprint must use init_*_bp() dependency injection
- No external dependencies beyond what's already installed (pdfplumber, openpyxl available)

## Non-Goals

- Real-time sync with accreditor websites (one-time import only)
- Automatic updates when standards change (handled by existing versioning service)
- Multi-language standards parsing (English only for now)

## Dependencies

- Existing harvesters (`src/harvesters/`) for raw text extraction
- Existing StandardsStore for persistence
- Existing StandardsLibrary/Section/ChecklistItem models
- Database migration system

## Risks

- PDF parsing quality varies (image-based PDFs need OCR)
- Section numbering schemes vary by accreditor
- Checklist item extraction is ambiguous without AI assistance

## Decisions Made

1. Three-layer architecture: Extraction → Parsing → Validation
2. Factory pattern for pluggable extractors
3. AI agent for intelligent parsing assistance
4. Database table for import tracking/history
