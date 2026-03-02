# AccreditAI Agent Architecture

## Core Idea
- **Engines** do reusable work (ingestion, search, standards, audit, remediation, packets, translation)
- **Agents** are thin coordinators that call engines and produce artifacts
- **Orchestrator** routes requests, sequences tasks, enforces checkpoints, logs everything

---

## Tier 0: Runtime & Governance

### 1) Orchestrator Agent
- **Job**: Turn any user goal into a plan, spawn tasks, coordinate specialists
- **Inputs**: goal, institution/program, available docs, current findings, language
- **Outputs**: task plan, artifacts, session log, progress events
- **Must**: enforce confidence thresholds and human approval checkpoints

### 2) Policy & Safety Agent
- **Job**: Enforce "no fabrication," evidence requirements, privacy rules, "do not embed PII"
- **Runs**: before results are presented or exported
- **Outputs**: pass/fail gate + remediation instructions if violations

### 3) Evidence Guardian Agent
- **Job**: Validate every claim has citation to standard + document snippet pointer
- **Outputs**: evidence completeness score; blocks compliance claims without evidence

---

## Tier 1: Intake, Organization & Retrieval

### 4) Document Intake Agent
- **Job**: Guide upload, classify doc types, detect missing key documents
- **Outputs**: document inventory, missing-doc list, ingestion queue

### 5) Parsing & Structure Agent
- **Job**: Validate parse quality, sectioning, headings, page mapping
- **Outputs**: parse diagnostics; "needs re-parse" actions

### 6) PII Redaction Agent
- **Job**: Detect sensitive fields; ensure redacted text used for embeddings
- **Outputs**: redaction report + approval checkpoint if heavy redaction affects meaning

### 7) Retrieval Tuning Agent
- **Job**: Improve chunking, retrieval filters (program, doc type, language), query rewriting
- **Outputs**: retrieval evaluation report; recommended settings

---

## Tier 2: Standards & Regulatory Stack

### 8) Standards Curator Agent
- **Job**: Import standards, build tree, maintain versions, map to checklists
- **Outputs**: standards library integrity report, checklist mappings

### 9) Regulatory Stack Agent
- **Job**: Build institution-specific stack (accreditor + federal + state + licensure)
- **Outputs**: regulatory_stack.json snapshot + rationale + citations

### 10) Standards Translator Agent
- **Job**: Translate standards/checklists to user-selected language using glossaries
- **Outputs**: translated views + quality flags + terminology updates

---

## Tier 3: Compliance Analysis & Quality

### 11) Compliance Audit Agent
- **Job**: Run multi-pass audits per document type and checklist
- **Passes**: completeness → clause checks → contradictions → risk scoring → summary
- **Outputs**: findings with severity, confidence, evidence refs, standard refs

### 12) Consistency Agent
- **Job**: Cross-document consistency checks using truth index and extracted values
- **Outputs**: mismatches, impact radius, suggested truth index updates

### 13) Risk Scoring Agent
- **Job**: Compute readiness score and risk heatmaps from findings + evidence coverage
- **Outputs**: readiness score breakdown and alerts

### 14) Gap Finder Agent
- **Job**: Identify missing evidence coverage for standards and checklist items
- **Outputs**: "missing evidence" tasks and recommended documents/sections to create

---

## Tier 4: Remediation & Authoring

### 15) Remediation Agent
- **Job**: Generate redlines/finals/crossrefs tied to findings and truth index
- **Outputs**: doc versions + change notes + citations
- **Checkpoint**: always require approval for writing to finals/exports

### 16) Policy Author Agent
- **Job**: Draft missing policy sections (not full policies), templates, clauses
- **Outputs**: insert-ready text with citations + warnings where institution-specific input required

### 17) Exhibit Builder Agent
- **Job**: Assemble exhibits list, label exhibits, ensure they match references
- **Outputs**: exhibit register + packaged folders

### 18) Change Impact Agent
- **Job**: When truth index value changes, find every dependent reference and propose edits
- **Outputs**: impact report + remediation batch

---

## Tier 5: Submission & Audit Defense

### 19) Narrative Agent
- **Job**: Write issue-by-issue narratives using findings + evidence crosswalk
- **Outputs**: narrative sections with evidence links and standard citations

### 20) Crosswalk Agent
- **Job**: Generate standard-to-evidence tables suitable for submission
- **Outputs**: crosswalk tables, evidence index, references

### 21) Packet Agent
- **Job**: Build submission packets (DOCX/PDF/ZIP) from selected components
- **Checkpoint**: approval before export

### 22) Site Visit Coach Agent
- **Job**: Prepare Q&A, evidence drill-down, staff briefing, likely auditor questions
- **Outputs**: site visit playbook + rapid evidence links

---

## Tier 6: Product Experience

### 23) Workflow Coach Agent
- **Job**: Suggest next best action
- **Outputs**: prioritized task list (fix critical, fill evidence gaps, rerun audit)

### 24) Localization QA Agent
- **Job**: Ensure Spanish views reflect source meaning and preserve legal terms
- **Outputs**: translation quality flags + glossary improvements

---

## Default Pipelines

### A) First-time Setup
```
Document Intake → Parsing/PII → Regulatory Stack → Standards Curator → Audit → Risk Scoring
```

### B) Fix Cycle
```
Compliance Audit → Consistency → Remediation → Re-audit → Readiness Score Update
```

### C) Submission
```
Gap Finder → Narrative → Crosswalk → Packet Agent → Human Approval → Export
```

### D) Multilingual Support
```
Standards Translator → Document Translation → Localization QA → Enable Bilingual Viewing
```

---

## Checkpoints (Require Human Approval)

1. Low confidence findings below threshold
2. Any "compliant/non-compliant" determinations without strong evidence
3. Any final document generation
4. Any submission export
5. Any deletion or rename of institution artifacts
6. Any translation flagged "needs review" for legally sensitive sections

---

## Implementation Prompt

```
Implement the AccreditationStudio agent architecture as a registry of specialized agents coordinated by an Orchestrator.

Requirements:
1) Create src/agents/registry.py listing agents and their capabilities.
2) Create src/agents/base_agent.py defining:
   - run(context) -> AgentResult
   - AgentResult: status, confidence, citations, artifacts, checkpoints
3) Add agents as separate modules:
   - orchestrator_agent.py
   - evidence_guardian_agent.py
   - compliance_audit_agent.py
   - consistency_agent.py
   - remediation_agent.py
   - packet_agent.py
   - standards_translator_agent.py
   - risk_scoring_agent.py
   - workflow_coach_agent.py
   Keep other agents stubbed but registered.
4) Orchestrator:
   - routes user goals to an executable plan (tasks with dependencies)
   - calls agents via registry
   - emits progress events
   - enforces checkpoints (confidence threshold, export gating, evidence gating)
5) Add an API:
   - POST /api/agents/orchestrate { goal, institution_id, program_id?, locale? }
   - GET /api/agents/sessions/<id>
   - GET /api/agents/sessions/<id>/stream (SSE)
   - POST /api/agents/sessions/<id>/approve
6) Add tests for:
   - registry loads
   - orchestrator routes a simple goal into tasks
   - evidence guardian blocks missing citations

Start with base_agent + registry + orchestrator skeleton and register the top 8 agents.
```

---

## Agent Count: 24 Total

| Tier | Count | Agents |
|------|-------|--------|
| 0 - Governance | 3 | Orchestrator, Policy/Safety, Evidence Guardian |
| 1 - Intake | 4 | Document Intake, Parsing, PII Redaction, Retrieval Tuning |
| 2 - Standards | 3 | Standards Curator, Regulatory Stack, Standards Translator |
| 3 - Compliance | 4 | Compliance Audit, Consistency, Risk Scoring, Gap Finder |
| 4 - Remediation | 4 | Remediation, Policy Author, Exhibit Builder, Change Impact |
| 5 - Submission | 4 | Narrative, Crosswalk, Packet, Site Visit Coach |
| 6 - Experience | 2 | Workflow Coach, Localization QA |
