# Regulatory Intelligence Layer

## Overview

Transform AccreditAI from "audit tool" to "regulatory intelligence system" that:
1. **Pulls** accreditor requirements from their sites
2. **Builds** the full federal + multi-state regulatory stack
3. **Detects** standards updates and tells the school what must change

---

## Feature Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGULATION UPDATE WATCH                       │
│    Scheduled checks → hash comparison → event generation         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STANDARDS WEB HARVESTER                        │
│    fetch → normalize → parse → version → store                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STANDARDS CHANGE DETECTOR                     │
│    diff → added/removed/modified → impact analysis               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REGULATORY STACK BUILDER                      │
│  accreditor + federal + state[] + professional → merged stack    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       IMPACT ANALYZER                            │
│   changed requirements → document search → remediation tasks     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Feature 1: Standards Web Harvester + Versioned Store

### Purpose
Fetch accreditor standards from official websites, parse into structured tree, store with versioning.

### Data Flow
```
Official Site → fetch(HTML/PDF) → parse → normalize → store
```

### Storage Structure
```
workspace/_standards/{accreditor}/
├── sources/{yyyymmdd}/          # Raw downloads
│   ├── standards.pdf
│   └── checklist.pdf
├── versions/{yyyymmdd}/         # Parsed versions
│   ├── standards.json           # Structured tree
│   └── meta.json                # Source URLs, hash, dates
├── diffs/{old}_{new}.json       # Change diffs
└── explanations/{standard_id}.json  # Cached explanations
```

### Accreditor Sources (Initial)

| Accreditor | Standards URL | Format |
|------------|---------------|--------|
| ACCSC | accsc.org/Resources/Accreditation-Standards | PDF |
| SACSCOC | sacscoc.org/app/uploads/2020/01/2018PrinciplesOfAcreditation.pdf | PDF |
| HLC | hlcommission.org/Policies/criteria-and-core-components.html | HTML + PDF |
| ABHES | abhes.org/accreditation-standards | PDF |
| COE | council.org/standards | PDF |

### Files to Create
- `src/regulatory/standards_sources.py` - Source definitions per accreditor
- `src/importers/standards_web_harvester.py` - Fetch + download logic
- `src/core/standards_store.py` - Already exists, extend for versioning

---

## Feature 2: Requirement Explainer Agent

### Purpose
Plain English explanations with evidence guidance for any standard.

### Agent Output
```json
{
  "standard_id": "VII.A.4",
  "plain_english": "You must clearly tell students how refunds are calculated...",
  "typical_evidence": [
    "Catalog refund policy section",
    "Enrollment agreement refund disclosure",
    "Sample refund calculation worksheet"
  ],
  "typical_documents": ["catalog", "enrollment_agreement"],
  "common_mistakes": [
    "Missing pro-rata calculation method",
    "Inconsistent periods across documents"
  ],
  "risk_level": "high",
  "citations": ["ACCSC VII.A.4.a", "34 CFR 668.22"]
}
```

### Files to Create
- `src/agents/requirement_explainer.py` - New agent

---

## Feature 3: Multi-State Regulatory Stack Builder

### Institution Profile Extensions
```python
@dataclass
class Institution:
    # ... existing fields ...
    operating_states: List[str] = field(default_factory=list)  # ["FL", "GA", "TX"]
    home_state: str = ""
    modality: Modality = Modality.ON_GROUND
    title_iv_participant: bool = True
    serves_minors: bool = False
    offers_payment_plans: bool = False
    conflict_policy: str = "strictest"  # strictest | home_state | manual
    applicability_overrides: Dict[str, Any] = field(default_factory=dict)
```

### State Module Structure
```
src/regulatory/states/
├── __init__.py
├── index.py          # State code → module loader
├── fl.py             # Florida regulations
├── ga.py             # Georgia regulations
├── tx.py             # Texas regulations
├── ca.py             # California (BPPE)
└── common.py         # Shared patterns
```

### State Module Interface
```python
def get_requirements(profile: Institution) -> List[RegRequirement]:
    """Return state-specific requirements based on institution profile."""

@dataclass
class RegRequirement:
    id: str
    source: str  # e.g., "FL-CIE-6E-2.006"
    title: str
    text: str
    applicability_rule: str
    topics: List[str]  # ["refund", "cancellation", "disclosure"]
    threshold_value: Optional[str]  # For conflict detection
    citations: List[str]
```

### Conflict Detection
```python
def detect_conflicts(requirements: List[RegRequirement]) -> List[Conflict]:
    """Find requirements on same topic with different thresholds."""
    # Example: FL refund = 3 days, TX refund = 5 days
```

---

## Feature 4: Federal Regs Library

### Applicability Rules
```python
FEDERAL_BUNDLES = {
    "title_iv": {
        "id": "TITLE_IV",
        "citations": ["34 CFR Part 668", "34 CFR Part 600"],
        "applicability": lambda p: p.title_iv_participant,
        "requirements": [...],
    },
    "ferpa": {
        "id": "FERPA",
        "citations": ["34 CFR Part 99"],
        "applicability": lambda p: True,  # Always applies to schools
        "requirements": [...],
    },
    "title_ix": {
        "id": "TITLE_IX",
        "citations": ["34 CFR Part 106"],
        "applicability": lambda p: True,
        "requirements": [...],
    },
    "clery": {
        "id": "CLERY",
        "citations": ["34 CFR Part 668.46"],
        "applicability": lambda p: p.title_iv_participant,
        "requirements": [...],
    },
    "coppa": {
        "id": "COPPA",
        "citations": ["16 CFR Part 312"],
        "applicability": lambda p: p.serves_minors,
        "requirements": [...],
    },
}
```

### Files to Create
- `src/regulatory/federal_catalog.py` - Federal regulation bundles

---

## Feature 5: Standards Change Detector + Diff

### Diff Output
```json
{
  "old_version": "20240101",
  "new_version": "20250101",
  "summary": {
    "added": 3,
    "removed": 1,
    "modified": 7
  },
  "changes": [
    {
      "type": "added",
      "standard_id": "VII.A.4.c",
      "title": "Online Refund Disclosure",
      "text": "..."
    },
    {
      "type": "modified",
      "standard_id": "V.A.3",
      "title": "Attendance Requirements",
      "old_text": "...",
      "new_text": "...",
      "diff_summary": "Changed from 80% to 85% attendance threshold"
    }
  ]
}
```

### Files to Create
- `src/regulatory/standards_diff.py` - Tree comparison algorithm

---

## Feature 6: Impact Analyzer Agent

### Purpose
For each changed requirement, identify affected documents and create remediation tasks.

### Agent Output
```json
{
  "institution_id": "inst_abc123",
  "standards_update": "ACCSC 20240101 → 20250101",
  "impacted_requirements": [
    {
      "standard_id": "VII.A.4.c",
      "change_type": "added",
      "risk_level": "high",
      "documents_to_check": [
        {"doc_id": "doc_123", "doc_type": "enrollment_agreement", "confidence": 0.85}
      ],
      "evidence_found": [
        {"doc_id": "doc_456", "page": 14, "snippet": "...refund policy...", "score": 0.72}
      ],
      "recommended_actions": [
        {"action": "add_disclosure", "description": "Add online refund disclosure to EA"},
        {"action": "audit", "description": "Audit catalog for consistency"}
      ]
    }
  ]
}
```

### Files to Create
- `src/agents/standards_impact_agent.py` - New agent

---

## Feature 7: Regulation Update Watch

### Scheduled Tasks
| Frequency | Check |
|-----------|-------|
| Daily | Accreditor standards sources |
| Weekly | State regulation sources |
| Monthly | Federal bundle refresh (manual trigger list) |

### Event Store
```
workspace/_updates/events.jsonl

{"source_type": "accreditor", "source_id": "ACCSC", "old_hash": "abc", "new_hash": "def", "detected_at": "2025-01-15T10:00:00Z", "status": "pending"}
```

### Dashboard Integration
- "Updates Detected" badge on nav
- Updates page with actions: View Diff, Run Impact Analysis

---

## Feature 8: Applicability Overrides

### Institution Settings
```json
{
  "conflict_policy": "strictest",
  "manual_overrides": {
    "refund_days": {
      "chosen_value": "3",
      "chosen_source": "FL",
      "notes": "Using strictest (Florida) for all states"
    }
  },
  "include_exclude_overrides": {
    "COPPA": {
      "action": "exclude",
      "notes": "We don't collect data from minors"
    }
  }
}
```

---

## Implementation Order

| Phase | Features | Dependencies |
|-------|----------|--------------|
| 1 | Standards Web Harvester | None |
| 2 | Standards Diff + Viewer | Harvester |
| 3 | Multi-State Stack Builder | Institution model update |
| 4 | Federal Regs Library | Stack Builder |
| 5 | Impact Analyzer Agent | Diff + Semantic Search |
| 6 | Requirement Explainer | Standards Store |
| 7 | Update Watch | Harvester + Task Queue |
| 8 | Applicability Overrides | Stack Builder |

---

## ACCSC First Implementation

Since ACCSC is your primary accreditor, start with:

### ACCSC Standards Source
```python
ACCSC_SOURCES = {
    "substantive_standards": {
        "url": "https://www.accsc.org/UploadedDocuments/Accreditation/Substantive-Standards-and-Reports.pdf",
        "format": "pdf",
        "parser": "accsc_standards_parser",
    },
    "enrollment_agreement_checklist": {
        "url": "https://www.accsc.org/UploadedDocuments/Accreditation/Enrollment-Agreement-Checklist.pdf",
        "format": "pdf",
        "parser": "accsc_checklist_parser",
    },
    "catalog_checklist": {
        "url": "https://www.accsc.org/UploadedDocuments/Accreditation/School-Catalog-Checklist.pdf",
        "format": "pdf",
        "parser": "accsc_checklist_parser",
    }
}
```

### ACCSC Section Structure
```
Section I - Rules of Process and Procedure
Section II - Governance, Management, and Administration
Section III - Relations with Students
Section IV - Faculty and Staff Qualifications
Section V - Educational Program and Outcomes
Section VI - Student Progress, Attendance, Records
Section VII - Financial Practices
...
```

---

---

## Feature 9: Accreditor Package System

### Purpose
Repeatable onboarding for any accreditor (institutional or programmatic).

### Package Structure
```
src/accreditors/<accreditor_id>/
├── manifest.json    # id, name, type, scope
├── sources.py       # Official URLs, fetch cadence
├── parser.py        # Normalize to StandardsTree
└── mappings.py      # Crosswalk seeds (optional)
```

### Recognized Institutional Accreditors (USDE)
**Regional-equivalent:** HLC, MSCHE, NECHE, NWCCU, SACSCOC, WSCUC, ACCJC
**National-equivalent:** ACCSC, ACCET, ACICS, COE, DEAC, ABHE, TRACS, AARTS, AIJS, NYSED

---

## Feature 10: Accreditor Switch Planner

### Purpose
Gap analysis when exploring accreditor change (A → B).

### Workflow
```
Current Accreditor Stack → Crosswalk → Target Accreditor Stack
                              ↓
                      Gap Analysis
                              ↓
            net_new_requirements[]
            evidence_gaps[]
            governance_changes[]
            transition_timeline[]
```

---

## Feature 11: Accreditation Calendar + Letter Extraction

### Purpose
Track deadlines from cycles, visits, and sanction/monitoring letters.

### Letter Extraction Agent
Input: Uploaded accreditor letter (PDF/DOCX)
Output: Extracted deadlines, deliverables, cited standards, inferred tasks

### Event Types
- visit, report, sanction, monitoring, rfi, internal

---

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /api/standards/{accreditor}/fetch-latest | Trigger harvest |
| GET | /api/standards/{accreditor}/versions | List versions |
| GET | /api/standards/{accreditor}/versions/{date} | Get specific version |
| GET | /api/standards/{accreditor}/diff/{old}/{new} | Get diff |
| POST | /api/standards/explain | Get requirement explanation |
| POST | /api/regulatory/build-stack | Build institution stack |
| GET | /api/regulatory/stack/latest | Get current stack |
| POST | /api/standards/{accreditor}/analyze-impact | Run impact analysis |
| GET | /api/updates/events | Get update events |
