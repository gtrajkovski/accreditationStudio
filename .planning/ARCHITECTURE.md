# AccreditationStudio Agent Architecture

## Core Philosophy

**Agents that run accreditation workflows**, not just agents that write documents.

Evidence mapping, crosswalks, readiness assessment, site visit prep, substantive change analysis, continuous compliance monitoring.

---

## System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                              │
│  Intent interpretation → Plan generation → Task dispatch         │
│  Checkpoint enforcement → Session logging → Artifact assembly    │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   EVIDENCE    │    │   DOCUMENT    │    │  COMPLIANCE   │
│   STANDARDS   │    │ INTELLIGENCE  │    │    AUDIT      │
│    LAYER      │    │    LAYER      │    │    LAYER      │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                 ┌─────────────────────┐
                 │  OUTPUT GENERATION  │
                 │       LAYER         │
                 └─────────────────────┘
                              │
                              ▼
                 ┌─────────────────────┐
                 │    OPERATIONAL      │
                 │       LAYER         │
                 └─────────────────────┘
```

---

## Agent Inventory

### 1. Orchestrator Agent
**Role:** Workflow coordination and task dispatch

**Responsibilities:**
- Interpret user intent (annual report, self-study, site visit, new program)
- Generate task plan (DAG with dependencies)
- Dispatch tasks to specialist agents
- Enforce human checkpoints
- Maintain session log and artifacts

**Inputs:** Institution profile, regulatory stack, document index, truth index

**Outputs:** Task graph, progress events, final deliverables

---

### Evidence & Standards Layer

### 2. Standards Librarian Agent
**Role:** Standards corpus and checklist management

**Responsibilities:**
- Parse accreditor standards into hierarchical tree
- Manage versions (year/edition)
- Create checklist packs per deliverable type
- Support ACCSC, HLC, SACSCOC, ABHES, COE presets

**Outputs:** Standards tree, checklist packs, requirement extracts

---

### 3. Evidence Mapper Agent
**Role:** Build "Standard → Evidence" mappings

**Responsibilities:**
- For each requirement, fetch candidate evidence from doc index
- Rank evidence quality, identify gaps
- Propose exhibit labels
- Generate crosswalk tables for self-studies

**Outputs:** `evidence_map.json`, `crosswalk_table.csv`

---

### 4. Crosswalk Builder Agent
**Role:** Map overlapping requirements across regulatory bodies

**Responsibilities:**
- Accreditor ↔ DOE Title IV ↔ State regs ↔ Programmatic
- Cluster similar obligations
- Recommend evidence reuse

**Outputs:** `regulatory_crosswalk.json`, reuse recommendations

---

### Document Intelligence Layer

### 5. Ingestion Agent ✅ IMPLEMENTED
**Role:** Document upload, parsing, indexing

**Responsibilities:**
- Document type classification
- Section detection (refund policy, attendance, etc.)
- PII redaction
- Chunking and embedding
- Flag missing required sections

**Outputs:** Parsed text, redaction report, chunk index, metadata

---

### 6. Policy Consistency Agent
**Role:** Detect contradictions across documents

**Checks:**
- Refund periods, cancellation terms, grievance procedures
- Tuition amounts, program lengths, contact info
- Cross-document consistency (catalog/handbook/agreement/website)

**Outputs:** `consistency_report.json`, remediation suggestions

---

### 7. Truth Index Curator Agent
**Role:** Maintain canonical institutional facts

**Responsibilities:**
- Propose updates from authoritative documents
- Require approval before changing canonical values
- Propagate changes into remediation tasks

**Outputs:** Updated truth index with audit trail

---

### Compliance & Audit Layer

### 8. Compliance Audit Agent
**Role:** Multi-pass compliance auditing

**Passes:**
1. Completeness check
2. Standard-by-standard matching
3. Internal consistency
4. Risk/severity grading
5. Remediation guidance

**Outputs:** Findings with severity, confidence, citations, evidence pointers

---

### 9. Risk Scorer Agent
**Role:** Risk prioritization and scoring

**Signals:**
- Severity counts
- Evidence gaps
- Contradictions
- Standards with repeated issues

**Outputs:** Top 10 risks, readiness score, trend analysis

---

### 10. Substantive Change Agent
**Role:** Change approval determination

**Analyzes:**
- New program/location/online/ownership changes
- Accreditor + state + DOE requirements
- Required approvals and timelines

**Outputs:** Determination, required forms, evidence list, timeline

**Checkpoint:** Always requires human approval

---

### Output Generation Layer

### 11. Remediation Agent
**Role:** Generate redlines and finals

**Rules:**
- Never modify originals
- Use truth index as source
- Link every clause to finding and standard
- Generate clean final + redline versions

**Outputs:** Redline DOCX, clean final DOCX, crossref DOCX

---

### 12. Narrative Agent
**Role:** Write issue narratives for responses and self-studies

**Inputs:** Findings, evidence map, institutional voice guidelines

**Outputs:** Issue response sections with citations

**Checkpoint:** Required for final submission narratives

---

### 13. Packet Assembler Agent
**Role:** Create submission packages

**Generates:**
- Cover page, TOC
- Crosswalk table
- Exhibit list
- Narrative sections
- Attachments manifest

**Outputs:** DOCX, PDF, ZIP packet

---

### Operational Layer

### 14. Calendar & Deadline Agent
**Role:** Deadline tracking and reminders

**Tracks:**
- Annual report timelines
- Renewal site visit schedules
- Substantive change deadlines
- Escalating warnings

**Outputs:** Calendar events, "due next" dashboard

---

### 15. Site Visit Prep Agent
**Role:** On-site preparation materials

**Produces:**
- Exhibit binder map
- Likely reviewer questions + evidence pointers
- Role-based prep lists (registrar, financial aid, program chair)

**Outputs:** Site visit binder ZIP, Q&A playbook

---

## Shared Infrastructure

### Session Runtime
Each workflow runs as a session with:
- State snapshot
- Queued tasks (DAG)
- Checkpoint gating
- Progress stream (SSE)
- Artifact registry

### Artifacts-First Design
Every agent writes artifacts to workspace:
```
workspace/{institution_id}/
├── evidence_maps/
├── crosswalks/
├── audits/
├── consistency_reports/
├── redlines/
├── finals/
├── packets/
└── agent_sessions/
```

### Confidence + Citations
No claim accepted without:
- Confidence score (0-1)
- Evidence pointers (document_id, chunk_id, page)
- Standard citations

### Human Checkpoints
Triggered by:
- Low confidence (< 0.7)
- Legal/compliance determinations
- Final submissions
- Truth index changes

---

## Standard Workflows

### 1. Audit Enrollment Agreement (ACCSC)
```
Ingestion → Standards Librarian → Evidence Mapper →
Compliance Audit → Remediation → Packet Assembly
```

### 2. Self-Study Preparation
```
Standards Librarian → Evidence Mapper → Crosswalk Builder →
Compliance Audit → Narrative → Packet Assembly
```

### 3. Site Visit Prep
```
Evidence Mapper → Compliance Audit → Risk Scorer →
Site Visit Prep
```

### 4. Substantive Change Filing
```
Substantive Change → Evidence Mapper → Narrative →
Packet Assembly
```

### 5. Annual Compliance Check
```
Ingestion (new docs) → Policy Consistency →
Compliance Audit → Risk Scorer → Calendar Update
```

---

## Build Order (Recommended)

| Priority | Agent | Value |
|----------|-------|-------|
| 1 | Ingestion ✅ | Document parsing + search |
| 2 | Evidence Mapper | Standard → Evidence crosswalk |
| 3 | Compliance Audit | Multi-pass with citations |
| 4 | Remediation | Redlines + finals |
| 5 | Packet Assembler | Submission packages |
| 6 | Policy Consistency | Ongoing maintenance |
| 7 | Truth Index Curator | Canonical facts |
| 8 | Site Visit Prep | Daily operational value |
| 9 | Calendar & Deadline | Reminders |
| 10 | Substantive Change | Advanced workflows |
| 11 | Crosswalk Builder | Multi-body compliance |
| 12 | Risk Scorer | Executive dashboard |

---

## Accreditor Priority

**Primary:** ACCSC (career colleges, detailed checklists)

**Next tier:**
- SACSCOC (regional, Southern states)
- HLC (regional, Midwest/West)
- ABHES (allied health)
- COE (distance education)

**Future:**
- ABET (engineering)
- State-specific (CA BPPE, TX TWC, FL CIE)
- Programmatic (nursing, business, etc.)
