---
phase: 9-03
type: research
created: 2026-03-27
---

# Phase 9-03: Universal Standards Importer - Research

## Current Architecture

### Standards Store (`src/core/standards_store.py`)
- 526 lines, manages persistence of StandardsLibrary objects
- System presets: ACCSC, SACSCOC, HLC, ABHES, COE (5 total)
- JSON file persistence in `standards/` directory
- CRUD: load(), save(), delete(), list_all(), list_by_accreditor()
- Protection: system presets cannot be modified directly

### Standards Models (`src/core/models/standards.py`)
- `StandardsLibrary`: id, accrediting_body, name, version, effective_date, sections, checklist_items, full_text
- `StandardsSection`: id, number, title, text, parent_section
- `ChecklistItem`: number, category, description, section_reference, applies_to
- All implement to_dict()/from_dict() serialization

### Harvester Framework (`src/harvesters/`)
- BaseHarvester abstract class with fetch() method
- WebHarvester: BeautifulSoup HTML scraping
- PdfHarvester: pdfplumber text extraction (143 lines)
- ManualHarvester: direct text passthrough
- Factory: create_harvester(HarvesterType)

### Versioning Service (`src/services/standards_versioning_service.py`)
- SHA256 content hashing for change detection
- HtmlDiff for version comparison
- Database: standards_versions table (0032 migration)

### Current Limitations
| Feature | Current State | Needed |
|---------|--------------|--------|
| Raw text extraction | ✅ Done | ✅ |
| Section hierarchy detection | ❌ Manual | ✅ Parse numbering |
| Section text extraction | ❌ Not available | ✅ Segment by sections |
| Requirement extraction | ❌ Manual | ✅ Find checklist items |
| Schema mapping | ❌ Not available | ✅ Map to models |
| Validation | ❌ None | ✅ Required fields, duplicates |
| Excel/CSV import | ❌ Not available | ✅ Tabular format |

## Technical Approach

### Three-Layer Pipeline

```
Layer 1: EXTRACTION
├─ ExtractorFactory (by file type)
├─ PdfExtractor (pdfplumber)
├─ ExcelExtractor (openpyxl)
├─ CsvExtractor (csv stdlib)
├─ TextExtractor (regex)
└─ WebExtractor (existing harvester)

Layer 2: PARSING
├─ HierarchyParser (detect I, I.A, I.A.1 patterns)
├─ SectionSegmenter (split text by sections)
├─ RequirementExtractor (find checklist items)
├─ MetadataExtractor (title, version, date)
└─ SchemaMapper (raw → models)

Layer 3: VALIDATION
├─ SchemaValidator (required fields)
├─ ConflictDetector (duplicates, orphans)
├─ DocumentTypeMapper (infer applies_to)
└─ QualityScorer (confidence metrics)
```

### Files to Create

```
src/importers/
├─ standards_importer.py       # Pipeline orchestrator
├─ standards_extractors.py     # ExtractorFactory + impls
├─ standards_parser.py         # Hierarchy + segmentation
└─ standards_validator.py      # Validation + conflict detection

src/agents/
└─ standards_importer_agent.py # AI parsing agent (8 tools)

src/services/
└─ standards_import_service.py # Business logic orchestration

src/api/
└─ standards_importer_bp.py    # REST endpoints

src/db/migrations/
└─ 0038_standards_importer.sql # imports tracking table

templates/
└─ standards_importer.html     # UI page
```

### Database Schema

```sql
CREATE TABLE standards_imports (
    id TEXT PRIMARY KEY,
    institution_id TEXT,
    accreditor_code TEXT NOT NULL,
    source_type TEXT NOT NULL,       -- pdf, excel, csv, text, web
    source_name TEXT,
    status TEXT NOT NULL,            -- parsing, validating, complete, failed
    sections_detected INTEGER,
    checklist_items_detected INTEGER,
    validation_errors TEXT,          -- JSON array
    import_mapping TEXT,             -- JSON mapping decisions
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

### Agent Tools (8)

1. `parse_section_hierarchy` - Detect numbering scheme from text
2. `extract_section_text` - Segment full_text by sections
3. `extract_checklist_items` - Find requirements in section text
4. `detect_conflicts` - Find duplicates/orphans
5. `infer_document_types` - Map requirements to applies_to
6. `enhance_descriptions` - Improve section/item descriptions
7. `validate_structure` - Check completeness
8. `create_standards_library` - Assemble final StandardsLibrary

### API Endpoints

```
POST /api/standards-importer/upload     # Upload file
POST /api/standards-importer/parse      # Parse uploaded file
POST /api/standards-importer/validate   # Validate parsed data
POST /api/standards-importer/import     # Create StandardsLibrary
GET  /api/standards-importer/imports    # List import history
GET  /api/standards-importer/imports/<id>  # Get import details
POST /api/standards-importer/preview    # Quick preview without saving
```

### UI Flow

1. **Upload**: File upload or URL/text input
2. **Preview**: Show detected sections with confidence scores
3. **Mapping**: User adjusts hierarchy, assigns document types
4. **Validation**: Display errors/warnings with fix suggestions
5. **Import**: Create StandardsLibrary, show success
6. **History**: View past imports with status

## Existing Patterns to Follow

### Blueprint DI Pattern
```python
standards_importer_bp = Blueprint("standards_importer", __name__, url_prefix="/api/standards-importer")
_import_service = None

def init_standards_importer_bp(import_service, ai_client):
    global _import_service
    _import_service = import_service
    return standards_importer_bp
```

### Agent Registration Pattern
```python
@register_agent(AgentType.STANDARDS_IMPORTER)
class StandardsImporterAgent(BaseAgent):
    @property
    def agent_type(self) -> AgentType:
        return AgentType.STANDARDS_IMPORTER
```

### Model Serialization Pattern
```python
@dataclass
class ImportResult:
    sections: List[StandardsSection]
    checklist_items: List[ChecklistItem]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "checklist_items": [c.to_dict() for c in self.checklist_items]
        }
```

## Estimated Scope

| Component | Lines | Complexity |
|-----------|-------|------------|
| standards_extractors.py | 200 | Medium |
| standards_parser.py | 300 | High |
| standards_validator.py | 150 | Medium |
| standards_importer.py | 150 | Medium |
| standards_import_service.py | 200 | Medium |
| standards_importer_agent.py | 350 | High |
| standards_importer_bp.py | 200 | Medium |
| Migration | 50 | Low |
| Tests | 400 | Medium |
| UI Template | 300 | Medium |
| **Total** | **~2,300** | |

## Risk Mitigations

1. **PDF parsing quality**: Use confidence scores, flag low-confidence sections
2. **Numbering scheme variance**: Support multiple patterns (I, 1, A, §)
3. **Checklist ambiguity**: Use AI agent for context-aware extraction
4. **Large files**: Chunk processing with progress tracking

## Dependencies (Already Installed)

- pdfplumber: PDF text extraction
- openpyxl: Excel reading
- BeautifulSoup4: HTML parsing
- Anthropic SDK: AI agent calls
