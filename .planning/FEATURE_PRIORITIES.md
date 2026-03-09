# AccreditAI Feature Priorities

## Top 5 Category-Leader Features

### 1. Accreditation Readiness Score
Single number institutions can track. Consultants love this.
```
Accreditation Readiness: 82%

Breakdown:
  Documents           90%
  Compliance          74%
  Evidence Coverage   81%
  Consistency         88%
```

### 2. Evidence Explorer
Standard → Evidence crosswalk with coverage visualization.
```
Standard Coverage

ACCSC 1 Governance      ██████████ 100%
ACCSC 2 Faculty         ████████░░ 80%
ACCSC 3 Admissions      ██████░░░░ 60%
```

### 3. Accreditation Simulation
Run mock audit, predict findings.
```
Likely Findings:
  Critical: Refund policy missing pro-rata clause
  Moderate: Faculty credentials incomplete
  Minor: Catalog formatting inconsistent
```

### 4. Bulk Remediation Engine
"Fix Everything" workflow - generate all redlines at once.

### 5. Submission Packet Studio
Visual workflow: Select Standards → Evidence → Narratives → Preview → Export

---

## Full Feature List (20 Items)

### Dashboards & Visualization
1. **Flight Deck** - Mission control with readiness score ✅
2. **Evidence Coverage Map** - Standard coverage percentages
3. **Compliance Heatmap** - Matrix: documents × requirements
4. **Compliance History** - Track readiness over time (graph) ✅
5. **Risk Alerts** - Real-time warnings banner ✅

### AI-Powered Features
6. **Explain This Standard** - Plain English + required evidence
7. **Accreditation Simulation** - Mock audit with predicted findings
8. **AI Accreditation Assistant** - Persistent chat for compliance Q&A
9. **Evidence Assistant** - "Show evidence for X" chat interface

### Remediation & Workflow
10. **Fix Everything Workflow** - Bulk remediation mode
11. **Impact Analysis** - Change one fact, see all affected documents
12. **Institutional Knowledge Graph** - Facts as nodes, documents reference them

### Planning & Timeline
13. **Accreditation Timeline Planner** - Self Study → Audit → Remediation → Submission
14. **Site Visit Mode** - Fast search during auditor visits

### Submission
15. **Submission Packet Studio** - Visual packet builder with preview

### Multi-User
16. **Multi-Institution Mode** - Consultant dashboard for 20-50 schools

### Document Tools
17. **Document Workbench IDE** - Panels: Document, Findings, Evidence, Fixes, Compare
18. **Evidence Highlighting** - Highlight exact sentence used as evidence

### Navigation
19. **Global Search** - Search standards, documents, findings, evidence
20. **Quick Actions FAB** - Upload, Audit, Fix, Create Packet ✅

---

## UX Principles

Every screen must answer:
1. **What** is wrong?
2. **Why** is it wrong?
3. **Where** is the evidence?
4. **How** do I fix it?

### UI Polish
- Skeleton loaders (not spinners)
- Severity badges: Critical (red), Moderate (yellow), Minor (blue), Compliant (green)
- Keyboard shortcuts: `/` search, `A` audit, `F` fix, `G+D` dashboard, `G+C` compliance ✅

---

## Implementation Order

| Phase | Features | Impact |
|-------|----------|--------|
| 3.1 | Readiness Score + Evidence Coverage Map | Core value prop |
| 3.2 | Compliance Heatmap + Risk Alerts | Fast problem finding |
| 3.3 | Explain Standard + AI Assistant | User education |
| 3.4 | Accreditation Simulation | Early warning |
| 3.5 | Bulk Remediation | Time savings |
| 3.6 | Submission Packet Studio | End-to-end workflow |
| 4.1 | Knowledge Graph + Impact Analysis | Consistency |
| 4.2 | Timeline Planner | Project management |
| 4.3 | Site Visit Mode | Visit support |
| 5.1 | Multi-Institution Mode | Consultant scale |

---

## Agent Architecture (15 Agents)

Already implemented in src/agents/:
1. OrchestratorAgent - Coordinates multi-agent workflows
2. StandardsLibrarianAgent - Standards lookup and interpretation
3. EvidenceMapperAgent - Standard → Evidence crosswalk
4. CrosswalkBuilderAgent - Build compliance matrices
5. IngestionAgent - Document upload and processing
6. PolicyConsistencyAgent - Detect contradictions
7. TruthIndexCuratorAgent - Maintain institutional facts
8. ComplianceAuditAgent - Multi-pass audit with citations
9. RiskScorerAgent - Calculate readiness score
10. SubstantiveChangeAgent - Detect reportable changes
11. RemediationAgent - Generate fixes and redlines
12. NarrativeAgent - Write self-study narratives
13. PacketAssemblerAgent - Build submission packets
14. CalendarDeadlineAgent - Track deadlines
15. SiteVisitPrepAgent - Generate interview prep
