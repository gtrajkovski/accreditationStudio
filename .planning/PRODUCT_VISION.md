# AccreditAI Product Vision

## Core Value Proposition

Transform AccreditAI from a "document generator" into an **Accreditation Operating System** that accreditation teams use **every week**, not just before site visits.

## Three Pillars

| Pillar | What It Means |
|--------|---------------|
| **Workflow Clarity** | Users always know where they are in the accreditation cycle |
| **Decision Support** | System answers "Are we compliant?" instantly with confidence |
| **Evidence Traceability** | Every claim links to document, page, and standard |

---

## Game-Changer Features (Priority Order)

### 1. Compliance Command Center (Home Screen)

**Purpose:** Situational awareness at a glance

```
┌─────────────────────────────────────────────────────┐
│  ACCSC Accreditation Health: 76%                    │
│  ████████████████░░░░░░                             │
├─────────────────────────────────────────────────────┤
│  Critical Issues (2)                                │
│  ⚠ Refund policy missing pro-rata clause           │
│  ⚠ Catalog hours mismatch with program outline     │
├─────────────────────────────────────────────────────┤
│  Upcoming Deadlines                                 │
│  📅 Annual Report due in 21 days                   │
│  📅 Catalog review due in 45 days                  │
├─────────────────────────────────────────────────────┤
│  Documents                                          │
│  ✔ Catalog uploaded                                │
│  ✔ Enrollment Agreement uploaded                   │
│  ⚠ Policy manual incomplete                        │
└─────────────────────────────────────────────────────┘
```

**Agent Integration:** RiskScorerAgent computes health score, CalendarDeadlineAgent provides deadlines, ComplianceAuditAgent provides findings.

---

### 2. Evidence Explorer

**Purpose:** Answer "Where is the evidence?" instantly

```
┌─────────────────────────────────────────────────────┐
│  Standard: ACCSC Section VII.A.4                    │
│  "Refund policy shall be clearly disclosed..."      │
├─────────────────────────────────────────────────────┤
│  Evidence Found:                                    │
│  ✔ Catalog, page 14, "Refund Policy" section       │
│  ✔ Enrollment Agreement, section 2, paragraph 3    │
│  ⚠ Student Handbook - weak match (0.62)            │
├─────────────────────────────────────────────────────┤
│  Gap: Missing pro-rata calculation example         │
│  [Generate Fix] [Mark as Addressed]                │
└─────────────────────────────────────────────────────┘
```

**Agent Integration:** EvidenceMapperAgent builds Standard → Evidence mappings using semantic search.

---

### 3. Accreditation Simulation

**Purpose:** Early warning system - simulate an auditor review

```
┌─────────────────────────────────────────────────────┐
│  🔍 Running Accreditation Simulation...             │
├─────────────────────────────────────────────────────┤
│  Likely Findings:                                   │
│  CRITICAL: Refund policy missing pro-rata clause   │
│  SIGNIFICANT: Catalog hours ≠ program outline      │
│  ADVISORY: Instructor CVs need updating            │
├─────────────────────────────────────────────────────┤
│  Mock Questions Reviewers May Ask:                  │
│  • "How do you calculate refunds for withdrawals?" │
│  • "Show me faculty qualification documentation"   │
│  • "Where is your attendance tracking policy?"     │
└─────────────────────────────────────────────────────┘
```

**Agent Integration:** ComplianceAuditAgent + SiteVisitPrepAgent simulate review process.

---

### 4. Fix It For Me

**Purpose:** One-click remediation with approval

```
┌─────────────────────────────────────────────────────┐
│  Finding: Missing cancellation clause              │
│  Standard: ACCSC VII.A.3                           │
├─────────────────────────────────────────────────────┤
│  [Generate Fix]                                     │
├─────────────────────────────────────────────────────┤
│  Suggested Text:                                    │
│  "Students may cancel enrollment within three      │
│   calendar days of signing without penalty..."     │
│                                                     │
│  Citation: ACCSC VII.A.3.a                         │
│  Confidence: 0.92                                   │
│                                                     │
│  [Approve] [Edit] [Reject]                         │
└─────────────────────────────────────────────────────┘
```

**Agent Integration:** RemediationAgent generates redline, NarrativeAgent provides citation.

---

### 5. Submission Packet Builder

**Purpose:** Guided packet assembly with preview

```
Step 1: Select Standards          [✔]
Step 2: Map Evidence              [✔]
Step 3: Generate Narratives       [In Progress]
Step 4: Review & Edit             [ ]
Step 5: Export Packet             [ ]

[Preview Packet] [Continue →]
```

**Agent Integration:** PacketAssemblerAgent orchestrates, NarrativeAgent writes sections.

---

## Additional High-Impact Features

### Accreditation Timeline
Visual project management for the accreditation cycle:
```
[Self Study] ✓ → [Audit] ✓ → [Remediation] 60% → [Submission] → [Site Visit]
```

### Risk Radar
Heat map visualization of compliance risk by document/area.

### Site Visit Mode
"Compliance Google" - instant evidence lookup during site visits.

### AI Accreditation Assistant
Persistent chat that answers questions using audit results + standards + evidence.

### Document Workbench
IDE-like interface showing document with findings, evidence highlights, and fix suggestions inline.

### Compliance History
Track readiness score over time with trend graphs.

### Knowledge Graph
Institutional facts (tuition, hours, policies) linked across all documents for consistency checking.

---

## Ideal User Workflow

```
1. Create Institution
        ↓
2. Upload Documents (catalog, agreement, policies)
        ↓
3. Run Full Compliance Audit [One Click]
        ↓
4. Review Findings (Critical → Advisory)
        ↓
5. Click "Fix It" → Approve Redlines
        ↓
6. Re-run Audit → Score Improves
        ↓
7. Generate Submission Packet
        ↓
8. Site Visit Prep with Evidence Explorer
```

---

## Implementation Prompts

### Prompt 1: Compliance Command Center UI
```
Build the Compliance Command Center as the institution home page.

Components:
- Accreditation Health Score (0-100%) with color-coded bar
- Critical/Significant/Advisory finding counts with expandable list
- Upcoming Deadlines from CalendarDeadlineAgent
- Document Status grid (uploaded/missing/needs-review)
- Recent Activity feed

API calls:
- GET /api/institutions/<id>/compliance-summary
- GET /api/institutions/<id>/deadlines
- GET /api/institutions/<id>/documents/status

Use existing dark theme (#1a1a2e), vanilla JS, Jinja2 templates.
```

### Prompt 2: Evidence Explorer Page
```
Build the Evidence Explorer UI.

Features:
- Standards tree on left (collapsible by section)
- Evidence panel on right showing:
  - Matched chunks with document/page/section
  - Relevance score (color-coded)
  - Gap indicator if evidence weak/missing
- Click chunk → opens document at location
- [Generate Fix] button for gaps

API:
- GET /api/standards/<id>/sections
- POST /api/institutions/<id>/evidence/search { standard_id }
- GET /api/documents/<id>/chunks/<chunk_id>

Uses EvidenceMapperAgent.search_evidence tool.
```

### Prompt 3: Fix It Wizard
```
Implement the Fix It workflow.

Flow:
1. User clicks "Fix It" on a finding
2. System calls RemediationAgent.generate_fix
3. Shows suggested text with:
   - Diff against current
   - Standard citation
   - Confidence score
4. User approves/edits/rejects
5. If approved, creates redline in workspace

API:
- POST /api/findings/<id>/generate-fix
- POST /api/findings/<id>/apply-fix { approved_text }

Checkpoint: Fixes require human approval before applying.
```

### Prompt 4: Accreditation Simulation
```
Implement mock auditor simulation.

Workflow:
1. User clicks "Run Simulation"
2. Orchestrator runs:
   - ComplianceAuditAgent (all passes)
   - SiteVisitPrepAgent (generate questions)
   - RiskScorerAgent (compute score)
3. Returns:
   - Predicted findings with severity
   - Likely reviewer questions
   - Overall readiness score

API:
- POST /api/institutions/<id>/simulate
- GET /api/simulations/<id>/stream (SSE for progress)

UI shows results as mock "auditor report".
```

---

## Technical Prerequisites

Before building these features, ensure:

1. ✅ 15-agent architecture (DONE)
2. ✅ Semantic search infrastructure (DONE)
3. ✅ Standards library with presets (DONE)
4. 🔶 Search API blueprint (needs registration)
5. 🔶 Ingestion auto-indexing (needs update)

---

## Metrics That Matter

| Metric | Target |
|--------|--------|
| Time to first audit | < 10 minutes after upload |
| Evidence search latency | < 2 seconds |
| Fix generation time | < 30 seconds |
| Readiness score accuracy | > 85% vs actual audit |

---

## Build Order (Recommended)

| Phase | Features | Value |
|-------|----------|-------|
| 3.1 | Evidence Explorer + Search API | Core evidence traceability |
| 3.2 | Compliance Command Center | Situational awareness |
| 3.3 | Fix It Wizard | Remediation efficiency |
| 3.4 | Accreditation Simulation | Early warning |
| 3.5 | Submission Packet Builder | End-to-end workflow |
