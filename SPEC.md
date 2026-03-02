# AccreditAI — Full Specification

This document contains the complete technical specification for AccreditAI.

---

## Project Overview

**AccreditAI** is an AI-powered platform that helps post-secondary educational institutions manage their **entire accreditation lifecycle** — from initial self-evaluation through document preparation, exhibit collection, on-site visit readiness, and post-visit response. It works with **any accrediting body** and always audits against the **full regulatory stack**: accreditor standards + federal regulations + state/territory requirements + professional licensure body expectations.

Standalone Flask app, single-user localhost tool (same deployment model as Course Builder Studio).

### Target Users
- **Accreditation Director / Compliance Officer** — manages findings, evidence, responses, deadlines, final packets
- **Accreditation Consultant** — audits documents for multiple institutions, prepares OSE materials, reviews submissions
- **Campus President / Executive** — sees dashboards, risk, and readiness scores
- **Department Owners** (Admissions, Financial Aid, Academics, Career Services) — upload documents, fix gaps, complete action items

### Success Metrics
- **Time saved**: 80%+ reduction in manual document auditing time (hours per EA audit: ~40 manual → ~4 with AI)
- **Gaps closed**: Zero undiscovered compliance gaps at visit time
- **Consistency**: Zero cross-document mismatches in submission packages
- **Readiness score**: Institution can measure visit-readiness at any point (0-100%)
- **Response time**: Finding letter → complete response package in days, not weeks

### Non-Goals (explicitly out of scope)
- NOT a student information system (SIS) — doesn't manage enrollment, grades, or attendance
- NOT a learning management system (LMS) — doesn't deliver instruction
- NOT a financial management system — doesn't process payments or financial aid disbursements
- NOT a multi-tenant SaaS (yet) — runs locally, single-user, per the Course Builder model
- NOT replacing human judgment for final compliance determinations — AI assists, humans decide

**The application is agentic to the highest degree possible.** Rather than requiring the user to click through every step manually, the system uses autonomous AI agents that can chain tasks, call tools, invoke each other, and complete multi-step workflows with minimal human intervention. The user sets the goal ("audit this enrollment agreement" or "prepare the ACCSC renewal submission"), and the agents do the work — asking the user only when they need a decision, approval, or information that can't be inferred.

---

## Agentic Architecture — The Brain

AccreditAI runs on a **multi-agent orchestration system** where specialized agents handle different domains. Agents can invoke each other, use tools (file I/O, document parsing, web lookup, .docx generation), and chain operations into complex workflows. The user interacts through a **command interface** (chat-style or task-based) and the agents execute.

### Agent Design Principles

1. **Agents are autonomous within their domain.** The Audit Agent doesn't wait for the user to tell it to check Item 14 — it checks all items, multi-pass, and reports results.
2. **Agents invoke each other.** The Audit Agent calls the Consistency Agent to cross-check catalog values. The Packet Agent calls the Narrative Agent to draft responses. The Orchestrator routes complex requests to the right specialist.
3. **Agents use tools.** Every agent has access to: file read/write in the workspace, document parsing (docx/pdf), document generation (.docx builder), truth index read/write, web search (for license verification), and the Claude API for reasoning.
4. **Agents never fabricate.** Every claim is backed by a citation to a specific document + page/section + standard ID. If evidence is missing, the agent says what it needs — it never invents policy text or compliance claims.
5. **Agents report confidence.** Every finding, mapping, and draft includes a confidence score. Below threshold → flagged for human review. Above threshold → auto-approved (configurable).
6. **Human-in-the-loop at decision points.** Agents execute autonomously but pause at configured checkpoints: compliance status determinations, document approval, submission finalization, and any action with institutional consequences.

### The Agents

```
┌─────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR AGENT                     │
│  Routes requests, decomposes complex tasks, manages      │
│  multi-agent workflows, reports progress to user         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  INGESTION   │  │  STANDARDS   │  │    AUDIT     │  │
│  │    AGENT     │  │    AGENT     │  │    AGENT     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  EVIDENCE    │  │ CONSISTENCY  │  │ REMEDIATION  │  │
│  │    AGENT     │  │    AGENT     │  │    AGENT     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  FINDINGS    │  │  NARRATIVE   │  │   PACKET     │  │
│  │    AGENT     │  │    AGENT     │  │    AGENT     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  CHECKLIST   │  │  INTERVIEW   │  │   CATALOG    │  │
│  │    AGENT     │  │  PREP AGENT  │  │    AGENT     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │  FACULTY     │  │ ACHIEVEMENT  │                     │
│  │    AGENT     │  │    AGENT     │                     │
│  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

#### Orchestrator Agent
**Role**: The traffic controller. Receives user requests, decomposes them into sub-tasks, dispatches to specialist agents, aggregates results, and reports back.

**Capabilities**:
- Parse natural language requests: "Prepare everything for our ACCSC renewal" → decomposes into 15+ sub-tasks across multiple agents
- Manage agent pipelines: Ingestion → Audit → Consistency Check → Remediation → Deliverables → Packet Assembly
- Track progress across multi-step workflows
- Handle errors and retries
- Present results to user with options for next steps

**Example workflow — "Audit this enrollment agreement"**:
1. Orchestrator receives the request + uploaded file
2. Calls **Ingestion Agent**: parse document, extract text, detect language, classify as enrollment agreement, extract metadata (program name, costs, credits)
3. Calls **Standards Agent**: load applicable checklist (ACCSC EA Checklist 35 items) + full standards + regulatory stack
4. Calls **Audit Agent**: run multi-pass audit (5 passes) → returns findings
5. Calls **Consistency Agent**: cross-check extracted values against truth index and catalog
6. Calls **Remediation Agent**: generate redline, final clean, cross-reference versions
7. Calls **Checklist Agent**: fill official checklist with page numbers from generated docs
8. All results saved to workspace, user notified with summary

**The user did not have to click through 8 steps. They uploaded a file and said "audit this."**

#### Ingestion Agent
**Role**: Processes any uploaded document into usable data.

**Tools**: PDF parser, DOCX parser, OCR engine, language detector, Claude API for classification

**Capabilities**:
- **Auto-classify** document type: enrollment agreement, catalog, student handbook, admissions manual, faculty handbook, policy manual, state approval, federal PPA, accreditor letter/report, finding letter, deferral letter, on-site evaluation report, financial statements, advisory committee minutes, etc.
- **Extract text** preserving structure (sections, tables, headers, signature blocks)
- **Extract metadata**: effective dates, program names, clock/credit hours, dollar amounts, campus locations, approval numbers, expiration dates, signatory names
- **Detect language** (English, Spanish, bilingual)
- **Generate embeddings** for semantic search
- **Store** original file + extracted text + metadata + embeddings in workspace
- **Flag** PII for redaction (SSNs, DOBs, student names) — never store PII in embeddings

#### Standards Agent
**Role**: Manages the standards knowledge base. Parses standards documents into structured trees. Answers "where is this required?" questions.

**Tools**: Standards store, Claude API for parsing and mapping

**Capabilities**:
- **Parse** uploaded standards documents (PDF/DOCX) into structured hierarchy: Sections → Subsections → Requirements → Checklist Items
- **Build standards tree** with cross-references between sections
- **Map** checklist items to standards sections (e.g., EA Checklist Item 14 → ACCSC §VI(B)(6)(a-b))
- **Answer** natural language queries: "What does ACCSC require about refund policies?" → returns all applicable sections with citations
- **Determine applicability**: given institution characteristics, which standards/requirements apply?
- **Detect** when standards have been updated and flag affected documents

#### Audit Agent
**Role**: The core auditor. Takes a document + standards + context and produces compliance findings.

**Tools**: Document parser, Standards Agent (for lookups), Consistency Agent (for cross-checks), Claude API for analysis

**Capabilities**:
- **Multi-pass audit** (5+ passes):
  - Pass 1: Initial item-by-item review against checklist/standards
  - Pass 2: Re-verify compliant items (catch false positives)
  - Pass 3: Re-verify non-compliant/partial items (catch false negatives)
  - Pass 4: Beyond-checklist findings (standards requirements not in the checklist)
  - Pass 5: Math/consistency verification (tuition calculations, dates, cross-document checks via Consistency Agent)
- **Multi-regulatory audit**: every finding tagged with ALL applicable regulatory sources (accreditor + federal + state + professional body)
- **Specific regulatory citations**: "34 CFR §99.7" not just "federal requirement"
- **Formatting compliance**: checks "large and conspicuous" requirements, signature block completeness, pagination
- **Output**: structured findings with status, severity, evidence, recommendation, confidence score

#### Evidence Agent
**Role**: Validates exhibits and evidence items. Checks completeness, relevance, currency.

**Tools**: Document parser, Standards Agent, workspace file system, Claude API

**Capabilities**:
- **For each standard/finding**, identify what evidence is required
- **Check uploaded evidence** for: completeness (does it contain what's needed?), currency (is it dated within required timeframe?), relevance (does it actually address the requirement?), authenticity (does it have required signatures/approvals?)
- **Cross-check** evidence claims against actual document content (if the SER says "our catalog discloses graduation rates" — does the catalog actually contain graduation rates?)
- **Flag** missing evidence, stale evidence, contradictory evidence
- **Suggest** what additional evidence would strengthen compliance
- **Build exhibit index** mapping each piece of evidence to the standards it supports

#### Consistency Agent
**Role**: The single-source-of-truth enforcer. Cross-checks values across all documents.

**Tools**: Truth index, workspace file system, document parser, Claude API

**Capabilities**:
- **Extract comparable values** from all documents in finals/ (tuition, credits, hours, fees, refund percentages, contact info, school IDs, program names, etc.)
- **Compare** against truth index — flag any mismatch
- **Compare** documents against each other — even without truth index entries
- **Detect specific inconsistencies**:
  - Program clock hours/credit hours mismatch: catalog vs. state approvals vs. accreditor conversion letter
  - Tuition amounts: EA vs. catalog vs. website
  - Refund policy language: EA vs. catalog vs. student handbook
  - Contact info/addresses across all documents
  - Program names/credential levels across all documents
  - Faculty qualifications: SER claims vs. actual credential files
  - Student achievement rates: disclosed rates vs. reported rates vs. annual report
- **Propagate fixes**: when truth index changes, identify all affected documents and generate update instructions for Remediation Agent

#### Remediation Agent
**Role**: Fixes documents. Generates redlines, clean versions, cross-references, policy drafts.

**Tools**: DOCX builder, document parser, Standards Agent, truth index, Claude API

**Capabilities**:
- **Generate redline/tracked changes** from audit findings + original document
- **Generate final clean version** with all fixes applied (per language)
- **Generate cross-reference version** with superscript tags at checklist item locations
- **Section-level editing**: "fix just the FERPA section" — rewrites one section in context of whole document
- **Document drafting from scratch**: complete enrollment agreements, handbooks, policies, catalog sections from institution profile + regulatory stack + truth index
- **Catalog rebuilding**: parse existing catalog → apply fixes → generate updated version
- **Translation**: generate the other language version natively (not machine translation)
- **Apply truth index values**: when regenerating, pull all authoritative values from truth index

#### Findings Agent
**Role**: Parses accreditor letters and reports into structured issues. This is for when the institution has ALREADY received findings (deferral letters, on-site reports, show-cause letters).

**Tools**: Document parser, Standards Agent, Claude API

**Capabilities**:
- **Upload** a finding letter, deferral letter, or on-site evaluation report
- **AI extracts** each discrete finding/issue into structured records:
  - Issue title
  - Narrative summary (what the accreditor is saying)
  - Standard citation(s)
  - Risk level (critical / major / minor)
  - Required evidence to address the finding
  - Suggested corrective actions
  - Suggested owner / responsible department
  - Deadline (from the letter)
- **Map** each finding to affected documents in the workspace
- **Create** action items automatically in the action plan
- **Track** response status per finding

#### Narrative Agent
**Role**: Drafts compliance narratives, SER sections, response statements, and corrective action descriptions.

**Tools**: Evidence Agent (for citations), Standards Agent (for requirements), workspace files, Claude API

**Capabilities**:
- **Two writing modes**:
  - **Draft mode**: fast iteration, conversational, good for internal review
  - **Submission mode**: formal, citation-heavy, audit-proof, accreditor-facing
- **Narrative types**:
  - "How we comply" statements (for SER sections)
  - "Corrective action taken" statements (for response to findings)
  - "Sustainment/monitoring" statements (for ongoing compliance plans)
  - Cover letters for submissions
  - Executive summaries
- **Every claim is cited**: links to specific document + page/section + standard ID
- **Never fabricates**: if evidence is missing, the narrative says what's needed, not what exists
- **Context-aware**: reads the institution's actual documents, audit findings, faculty data, achievement data to produce accurate narratives

#### Packet Agent
**Role**: Assembles submission-ready response packages and exhibit binders.

**Tools**: DOCX builder, PDF builder, workspace file system, Narrative Agent, Evidence Agent

**Capabilities**:
- **Build submission packets** with:
  - Cover page (institution name, accreditor, submission type, date)
  - Table of contents
  - Issue-by-issue narrative response (calls Narrative Agent for each)
  - Corrective action plan table
  - Exhibit list with labels and page references
  - Cross-walk table mapping each standard to evidence
  - Appendices
- **Build exhibit binders** for on-site visits:
  - Organized by exhibit number/category
  - Table of contents
  - Tab dividers
  - Cross-referenced to standards
- **Export** as: structured .docx, PDF, zipped folder with folder hierarchy, or all of the above
- **Version management**: track submission versions, maintain history

#### Checklist Agent
**Role**: Builds, fills, and validates any type of checklist.

**Tools**: Document parser, Standards Agent, workspace files, DOCX builder

**Capabilities**:
- **Auto-fill** official accreditor checklists from document content (page numbers, Y/N, evidence citations)
- **Build** verification checklists from audit findings for on-site visits
- **Build** custom compliance checklists for any purpose
- **Validate** checklists against actual documents (is what's claimed in the checklist actually in the document?)

#### Interview Prep Agent
**Role**: Generates role-specific interview preparation documents for on-site visits.

**Tools**: Standards Agent, Audit findings, SER content, Claude API, DOCX builder

**Capabilities**:
- Generate tailored question sets per role (Director, Academic Dean, Faculty, Financial Aid, Registrar, Admissions, Career Services, Students, DE Administrator)
- Include likely questions based on standards + specific institutional findings
- Generate talking points from institutional evidence
- Flag red flag areas with honest response guidance

#### Catalog Agent
**Role**: Builds, audits, and maintains institutional catalogs.

**Tools**: Document parser, Standards Agent, truth index, DOCX builder, Consistency Agent

**Capabilities**:
- Generate complete catalogs from scratch (wizard-driven or fully autonomous)
- Audit existing catalogs against catalog checklist + full regulatory stack
- Rebuild outdated catalogs with all fixes applied
- Section-level editing with full context awareness
- Multi-language generation

#### Faculty Agent
**Role**: Manages faculty credential compliance.

**Tools**: Faculty store, web search (license verification), Standards Agent

**Capabilities**:
- Cross-check qualifications against teaching assignments
- Track license expirations and alert
- Attempt web verification of licenses (state licensing board portals)
- Generate faculty compliance reports

#### Achievement Agent
**Role**: Validates and analyzes student outcome data.

**Tools**: Achievement store, Claude API for analysis

**Capabilities**:
- Validate rate calculations (population base × rate = count)
- Detect declining trends (5-year analysis)
- Compare against accreditor benchmarks
- Verify disclosure language includes required elements
- Generate achievement reports and disclosures

### Agent Communication Protocol

Agents communicate through a structured message format:

```python
@dataclass
class AgentMessage:
    from_agent: str               # e.g., "orchestrator"
    to_agent: str                 # e.g., "audit_agent"
    task_id: str                  # unique task identifier
    parent_task_id: str           # nullable — for sub-tasks
    action: str                   # e.g., "audit_document", "check_consistency"
    payload: dict                 # task-specific parameters
    context: dict                 # shared context (institution_id, program_id, etc.)
    priority: str                 # "critical", "normal", "background"

@dataclass
class AgentResult:
    agent: str
    task_id: str
    status: str                   # "completed", "needs_human_input", "failed", "partial"
    result: dict                  # task-specific output
    confidence: float             # 0.0 to 1.0
    citations: list[dict]         # [{document, page, section, standard_id}]
    human_review_needed: bool
    next_suggested_actions: list[str]  # what should happen next
    artifacts_created: list[str]  # file paths created in workspace
```

### Agent Tool Registry

Every agent has access to these tools:

```python
AGENT_TOOLS = {
    # File operations
    "read_file": "Read a file from the workspace",
    "write_file": "Write a file to the workspace",
    "list_files": "List files in a workspace directory",
    "read_truth_index": "Read values from truth_index.json",
    "write_truth_index": "Update a value in truth_index.json",

    # Document operations
    "parse_docx": "Extract text + structure from a .docx file",
    "parse_pdf": "Extract text from a PDF (with OCR fallback)",
    "generate_docx": "Build a .docx file from structured content",
    "generate_pdf": "Convert a .docx to PDF",

    # AI operations
    "call_claude": "Make a Claude API call with structured output",
    "generate_embeddings": "Generate vector embeddings for text chunks",
    "semantic_search": "Search workspace documents by meaning",

    # Agent operations
    "call_agent": "Invoke another agent with a task",
    "get_task_status": "Check status of a running agent task",

    # Web operations (limited)
    "web_search": "Search the web (for license verification, etc.)",
    "web_fetch": "Fetch a specific URL",

    # Standards operations
    "search_standards": "Search standards library by keyword or section",
    "get_checklist": "Get checklist items for a document type",
    "get_regulatory_stack": "Get all applicable regulations for this institution",
}
```

### Agentic Workflow Examples

**Example 1: "Prepare our ACCSC renewal submission"**
```
User: "Prepare our ACCSC renewal submission"

Orchestrator:
├── 1. Reads institution profile + regulatory stack
├── 2. Identifies all required programs and document types
├── 3. For each program:
│   ├── Ingestion Agent: extract text from all uploaded originals
│   ├── Audit Agent: audit each document (EA, catalog sections, etc.)
│   ├── Consistency Agent: cross-check all values
│   ├── Remediation Agent: generate redlines + finals + crossrefs
│   ├── Checklist Agent: fill all applicable checklists
│   └── Evidence Agent: validate all exhibits
├── 4. Faculty Agent: verify all faculty credentials
├── 5. Achievement Agent: validate student outcome data
├── 6. Narrative Agent: draft all SER sections
├── 7. Consistency Agent: final cross-document consistency check
├── 8. Packet Agent: assemble complete submission package
├── 9. Interview Prep Agent: generate prep docs for all roles
└── 10. Reports readiness score + outstanding items to user

User interaction required:
- Approve compliance determinations (batch review)
- Provide missing information (agent asks specific questions)
- Review and approve final submission package
- Everything else is autonomous
```

**Example 2: "We just got a deferral letter from ACCSC"**
```
User: uploads deferral_letter.pdf

Orchestrator:
├── 1. Ingestion Agent: classify as "accreditor finding letter", extract text
├── 2. Findings Agent: parse into individual issues with citations + deadlines
├── 3. For each finding:
│   ├── Standards Agent: map to specific standards sections
│   ├── Evidence Agent: check what evidence exists in workspace
│   ├── Audit Agent: re-audit affected documents against the specific finding
│   └── Remediation Agent: generate fixes for affected documents
├── 4. Narrative Agent: draft response narratives for each finding
├── 5. Packet Agent: assemble response package
└── 6. Present to user: "Here are the 7 findings, here's the current evidence,
       here's what's missing, here are draft responses. Review and approve."

User interaction required:
- Confirm finding interpretations
- Provide any missing evidence
- Review response narratives
- Approve final response package
```

**Example 3: "Check if our catalog is consistent with our enrollment agreements"**
```
User: "Check consistency between catalog and all EAs"

Orchestrator:
├── 1. Consistency Agent:
│   ├── Read catalog from workspace
│   ├── Read all EA finals from workspace
│   ├── Extract: tuition, credits, hours, fees, refund policy, contact info,
│   │   program names, credential levels, attendance policy, SAP policy
│   ├── Compare every value
│   └── Report mismatches with exact locations
└── 2. Present: "Found 4 mismatches: [details with document, page, current value,
       expected value]. Fix all? Fix individually?"

If user says "fix all":
├── Orchestrator dispatches Remediation Agent for each affected document
├── New versions saved to workspace
└── Consistency Agent re-runs to verify fixes
```

### AI Safety Guardrails

```
ABSOLUTE RULES FOR ALL AGENTS:

1. NEVER fabricate evidence, policy text, or compliance claims.
   - If evidence is missing, say "Evidence not found — [what is needed]"
   - If a standard is not met, say "Non-compliant — [what is missing]"
   - NEVER generate fake document content that claims to represent what the institution does

2. ALWAYS cite sources for every claim.
   - Format: {document_name, page/section, standard_id}
   - If a claim cannot be cited, it must be flagged as "unverified"

3. ALWAYS label uncertainty.
   - Confidence < 0.7 → "LOW CONFIDENCE — requires human review"
   - Confidence < 0.5 → "UNABLE TO DETERMINE — insufficient evidence"

4. REQUIRE human confirmation for:
   - Compliance status determinations (compliant / non-compliant)
   - Submission of any document to an accreditor
   - Changes to the truth index that affect multiple documents
   - Deletion of any document or finding

5. NEVER store student PII in embeddings or AI context.
   - SSNs, DOBs, student names → redact before processing
   - Flag documents containing PII for redaction workflow

6. ALWAYS preserve original documents.
   - Originals are read-only in the workspace
   - All modifications create new versions in the appropriate folder

7. WORK WITHOUT AI when AI is unavailable.
   - Every feature must have a manual fallback
   - Standards mapping, evidence tagging, checklist filling can all be done manually
   - AI enhances but never gates the workflow
   - When API key is missing: app starts, all CRUD works, uploads work, workspace works
   - When API key is present but rate-limited: queue tasks, retry with backoff, notify user
   - Health endpoint: /api/health reports {ai_enabled: true/false, agents_available: [...]}
```

### Prompt Templates

Store prompt templates as versioned, editable files in `src/agents/prompts/`:

```
src/agents/prompts/
├── orchestrator/
│   └── task_decomposition.prompt
├── ingestion/
│   ├── document_classification.prompt
│   └── metadata_extraction.prompt
├── standards/
│   ├── standards_parsing.prompt
│   └── standards_mapping.prompt
├── audit/
│   ├── initial_audit.prompt
│   ├── verification_pass.prompt
│   ├── beyond_checklist.prompt
│   └── consistency_check.prompt
├── evidence/
│   ├── evidence_validation.prompt
│   └── exhibit_completeness.prompt
├── findings/
│   └── findings_extraction.prompt
├── narrative/
│   ├── how_we_comply.prompt
│   ├── corrective_action.prompt
│   └── sustainment_monitoring.prompt
├── remediation/
│   ├── redline_generation.prompt
│   ├── document_fix.prompt
│   └── section_edit.prompt
├── checklist/
│   └── checklist_fill.prompt
├── interview/
│   └── role_questions.prompt
└── catalog/
    ├── catalog_section.prompt
    └── catalog_audit.prompt
```

Every prompt template MUST:
- Explicitly forbid hallucination
- Require citations to standard IDs and document locations
- Request structured JSON output
- Include confidence scores
- Specify what to do when evidence is insufficient

### RAG Pipeline — How Agents Access Documents

Agents don't read raw files every time. The system maintains a **vector index** of all workspace documents for fast semantic retrieval.

**Ingestion pipeline** (runs when any document enters the workspace):
```
1. EXTRACT text (docx_parser / pdf_parser / OCR)
2. CHUNK into semantic segments (~500 tokens each, overlapping)
   - Preserve section headers and page numbers in chunk metadata
   - Keep tables as complete chunks (don't split mid-table)
3. REDACT PII before embedding (SSNs, DOBs, student names → [REDACTED])
   - PII regex patterns + Claude API for ambiguous cases
   - Original text stored separately in PII-protected storage
   - Redacted text used for all AI context and embeddings
4. EMBED each chunk using Claude embeddings (or local model for speed)
5. STORE in SQLite + vector extension (sqlite-vss) or pgvector if Postgres
   - Columns: chunk_id, document_id, page_number, section_header,
     text, text_redacted, embedding, metadata_json
6. INDEX metadata: document type, program, language, effective date,
   approval status, last modified
```

**Retrieval** (when an agent needs document context):
```python
def retrieve_context(query: str, filters: dict = None, top_k: int = 10) -> list[Chunk]:
    """
    Semantic search across all workspace documents.

    filters can include:
      document_type: "enrollment_agreement"
      program_id: "bsn-nursing"
      language: "es"
      date_after: "2024-01-01"

    Returns chunks with:
      - text (redacted)
      - source document path
      - page number
      - section header
      - similarity score
    """
```

**RAG-only rule**: When an agent makes a claim about what a document says, it MUST:
1. Retrieve relevant chunks via semantic search
2. Quote or paraphrase from the retrieved text
3. Cite the source: `{document: "catalog_final_es.docx", page: 14, section: "Política de Reembolso"}`
4. If no relevant chunks found → say "Not found in available documents"
5. NEVER synthesize information that isn't in the retrieved chunks

### Chat Interface — Natural Language Agent Interaction

The primary user interface is a **chat panel** (persistent sidebar or full-screen mode) where the user talks to the Orchestrator Agent in natural language. The chat is always available from any page.

**How it works**:
```
User: "I just uploaded our enrollment agreement for the BSN program.
       Audit it against ACCSC and let me know what's wrong."

Orchestrator: "Got it. I'll run a full audit. Here's what I'm doing:
  ✅ Step 1/6: Parsing document... (BSN Enrollment Agreement, Spanish, 6 pages)
  ✅ Step 2/6: Loading ACCSC EA Checklist (35 items) + full standards + federal/state regs
  🔄 Step 3/6: Running initial audit (Pass 1 of 5)...
  ⏳ Step 4/6: Verification passes
  ⏳ Step 5/6: Cross-document consistency check
  ⏳ Step 6/6: Generating deliverables

[Progress bar: 35%]"

...

Orchestrator: "Audit complete. Here's the summary:
  📊 19 Compliant | 8 Partial | 3 Non-Compliant | 5 N/A

  🔴 Critical findings:
  1. Item 6: Per-period tuition not disclosed ($4,320/cuatrimestre missing)
  2. Item 14: No FERPA/privacy section
  3. Item 19: School official signature block missing name and title

  📁 Files saved to workspace:
  - programs/bsn-nursing/audits/ea_audit_report_5pass.docx
  - programs/bsn-nursing/audits/ea_audit_findings.json

  What would you like to do next?
  [Generate fixes] [View detailed findings] [Run consistency check against catalog]"
```

**Chat capabilities**:
- Natural language commands: "audit this", "fix the FERPA section", "prepare our renewal"
- Follow-up questions: "what does ACCSC say about refund policies?" → Standards Agent answers with citations
- Status checks: "how's the audit going?" → Orchestrator reports progress
- Approval workflow: "approve all findings except #7, that one is actually compliant" → updates findings
- Multi-turn context: chat maintains conversation history for follow-ups
- **Slash commands** for power users: `/audit`, `/consistency-check`, `/generate-packet`, `/search standards refund`, `/fix document section`

**Chat message types** (rendered differently in UI):
- `user_message` — what the user typed
- `agent_thinking` — what the agent is doing (collapsible, shows progress)
- `agent_result` — the final output (formatted with tables, badges, links)
- `agent_question` — agent needs input (renders as a form/buttons)
- `file_link` — clickable link to a workspace file
- `approval_request` — renders approve/reject buttons
- `progress` — renders a progress bar with step descriptions

### Agent Session Management

Every complex workflow creates an **AgentSession** that tracks the full execution:

```python
@dataclass
class AgentSession:
    id: str
    parent_session_id: str        # nullable — for sub-tasks
    orchestrator_request: str     # the original user request
    status: str                   # "running", "waiting_for_human", "completed", "failed"
    agents_involved: list[str]    # which agents were called
    tasks: list[AgentTask]        # individual task executions
    checkpoints: list[HumanCheckpoint]  # where human input was requested
    artifacts_created: list[str]  # file paths created
    started_at: str
    completed_at: str             # nullable
    total_ai_tokens_used: int     # cost tracking
    total_ai_calls: int

@dataclass
class AgentTask:
    id: str
    session_id: str
    agent: str                    # e.g., "audit_agent"
    action: str                   # e.g., "run_audit_pass_1"
    status: str                   # "queued", "running", "completed", "failed"
    input_summary: str            # what was sent to the agent
    output_summary: str           # what came back
    confidence: float
    duration_ms: int
    ai_tokens_used: int
    started_at: str
    completed_at: str

@dataclass
class HumanCheckpoint:
    id: str
    session_id: str
    agent: str
    question: str                 # what the agent is asking
    options: list[str]            # choices presented to user
    user_response: str            # nullable — pending until answered
    answered_at: str              # nullable
```

**Session log** is stored in `workspace/{institution}/agent_sessions/` as JSON files — full audit trail of every agent action, every AI call, every human decision.

### Real-Time Progress Streaming

Long-running agent tasks stream progress to the UI via **Server-Sent Events (SSE)**:

```
GET /api/sessions/{session_id}/stream

event: progress
data: {"step": 3, "total": 6, "agent": "audit_agent", "message": "Running Pass 1..."}

event: progress
data: {"step": 3, "total": 6, "agent": "audit_agent", "message": "Pass 1 complete. 35 items evaluated."}

event: checkpoint
data: {"id": "cp-123", "question": "Item 7 rated as N/A — this is a conditional item. Is this program offered via distance education?", "options": ["Yes", "No"]}

event: complete
data: {"summary": {...}, "files_created": [...]}
```

The UI renders these events in real-time in both the chat panel and any active workspace views (audit workspace, deliverables page, etc.).

### PII Redaction Pipeline

Institutional documents contain student PII (names, SSNs, DOBs, addresses). The system MUST handle this safely.

**Detection** (runs during ingestion):
- Regex patterns: SSN (`\d{3}-\d{2}-\d{4}`), DOB formats, phone numbers
- Claude API call with low-token prompt: "Identify any student PII in this chunk" → returns spans
- Named entity recognition for student names (when surrounded by enrollment/grade context)

**Redaction levels**:
- **Level 0 — Raw**: original text, only stored in encrypted local files, NEVER sent to AI
- **Level 1 — Redacted**: PII replaced with tokens (`[SSN-001]`, `[STUDENT-042]`), used for all AI operations
- **Level 2 — Anonymized**: all identifying info removed, used for embeddings and vector index

**Rules**:
- AI agents ONLY see Level 1 (redacted) text
- Embeddings use Level 2 (anonymized) text
- Original files in `originals/` are never modified (PII stays in the file)
- Generated documents (finals, deliverables) preserve PII only when regenerating from templates with institution-provided data
- Session logs never contain PII
- Export packages can optionally include a PII redaction pass

### Two Writing Modes

All narrative-generating agents (Narrative Agent, Remediation Agent, Catalog Agent, SER drafting) support two modes:

**Draft Mode** — fast iteration, conversational:
- Less formal tone
- Shorter narratives
- Inline notes: "⚠️ Need to confirm this date with registrar"
- Placeholder markers: `[VERIFY: exact clock hours from state approval]`
- Good for internal review and iteration

**Submission Mode** — formal, audit-proof, citation-heavy:
- Formal compliance language
- Every claim cited: "(See Exhibit 4, pg. 12, Section III.A.2)"
- No placeholders — anything unverified is flagged as a gap, not glossed over
- Follows accreditor's preferred narrative structure
- Headers match the accreditor's response format exactly

User can toggle between modes globally or per-document. Draft mode is default. Submission mode is used for final packet generation.

### Fix-It Wizard

When the Audit Agent or Consistency Agent finds an issue, the system doesn't just report it — it offers a **guided fix workflow**:

```
┌─────────────────────────────────────────────┐
│  🔴 Finding: Item 14 — FERPA/Privacy        │
│  Missing from enrollment agreement           │
├─────────────────────────────────────────────┤
│                                              │
│  📍 WHERE to add it:                         │
│     After Section 8 (Financial Aid),         │
│     before Complaint Procedure               │
│                                              │
│  📝 SUGGESTED TEXT:                           │
│     "POLÍTICA DE PRIVACIDAD                  │
│      De acuerdo con la Ley de Derechos       │
│      Educativos y Privacidad de la Familia   │
│      (FERPA)..." [full text shown]           │
│                                              │
│  ✅ WHO should approve:                      │
│     Academic Director + Compliance Officer    │
│                                              │
│  📎 WHAT exhibit to include:                 │
│     FERPA notification template,             │
│     Student acknowledgment form              │
│                                              │
│  🔗 STANDARDS CITATION:                      │
│     ACCSC §VI(B)(6)(a-b), 34 CFR §99.7     │
│                                              │
│  [Apply Fix] [Edit First] [Skip] [Reject]   │
└─────────────────────────────────────────────┘
```

The "Apply Fix" button:
1. Calls the Remediation Agent to insert the text at the correct location
2. Saves new version of the document in workspace
3. Updates the truth index if applicable
4. Marks the finding as "remediated — pending verification"
5. Creates an action item for the approver

### Observability & Audit Logging

Every agent action is logged for compliance auditability:

```python
@dataclass
class AuditLogEntry:
    timestamp: str
    session_id: str
    agent: str
    action: str                   # "audit_pass_1", "generate_redline", "update_truth_index"
    target: str                   # document/finding/exhibit affected
    input_hash: str               # hash of input data (for reproducibility)
    output_hash: str              # hash of output data
    ai_model: str                 # which model was used
    ai_tokens: int                # how many tokens consumed
    confidence: float
    human_approved: bool          # was this action human-approved?
    user_id: str                  # who was logged in
    details: dict                 # action-specific metadata
```

Stored in `workspace/{institution}/audit_log.jsonl` (append-only).

Dashboard view: `/admin/audit-log` — searchable, filterable log of every system action.

---

## Local Workspace — The Project Folder

**Every institution gets a persistent local folder** that mirrors the full state of everything being built. This is NOT just a database — it's a real folder structure on disk that the user can browse, open files from, and share. The application reads from and writes to this folder in real time.

```
workspace/
└── {institution_slug}/                    # e.g., "cem-college" or "cftc"
    ├── institution.json                   # Profile, campuses, school IDs, regulatory stack config
    ├── programs/
    │   ├── {program_slug}/                # e.g., "bsn-nursing", "emt-basic"
    │   │   ├── program.json              # Program details (credits, cost, duration, etc.)
    │   │   ├── originals/                # Uploaded original documents (never modified)
    │   │   │   ├── contrato_original_es.docx
    │   │   │   └── enrollment_agreement_original_en.docx
    │   │   ├── audits/                   # Audit reports and findings
    │   │   │   ├── ea_audit_report.docx
    │   │   │   ├── ea_audit_findings.json
    │   │   │   └── ea_audit_report_5pass.docx
    │   │   ├── redlines/                 # Tracked changes versions
    │   │   │   ├── ea_redline_es.docx
    │   │   │   └── ea_redline_en.docx
    │   │   ├── finals/                   # Clean final versions (the working truth)
    │   │   │   ├── ea_final_es.docx
    │   │   │   └── ea_final_en.docx
    │   │   ├── crossrefs/                # Cross-reference versions with tags
    │   │   │   ├── ea_crossref_es.docx
    │   │   │   └── ea_crossref_en.docx
    │   │   ├── checklists/               # Filled accreditor checklists
    │   │   │   ├── ea_checklist_es.docx
    │   │   │   └── ea_checklist_en.docx
    │   │   └── action_plan.json
    │   └── ...
    ├── catalog/                           # Institution-wide catalog
    │   ├── originals/
    │   │   └── catalog_original.pdf
    │   ├── audit/
    │   │   └── catalog_audit_report.docx
    │   ├── redlines/
    │   │   ├── catalog_redline_es.docx
    │   │   └── catalog_redline_en.docx
    │   ├── finals/
    │   │   ├── catalog_final_es.docx     # THE catalog — single source of truth
    │   │   └── catalog_final_en.docx
    │   └── extracted_data.json            # Parsed catalog data (tuition, fees, policies, etc.)
    ├── policies/                          # Institution-wide policies
    │   ├── ferpa_policy.docx
    │   ├── complaint_procedure.docx
    │   ├── refund_policy.docx
    │   ├── title_ix_policy.docx
    │   ├── drug_free_policy.docx
    │   ├── ada_504_policy.docx
    │   └── ...
    ├── exhibits/                          # Organized by exhibit number
    │   ├── exhibit_02_faculty/
    │   │   ├── faculty_credentials.xlsx
    │   │   └── review_notes.json
    │   ├── exhibit_17_admissions/
    │   │   ├── admissions_manual.docx
    │   │   └── review_notes.json
    │   └── ...
    ├── faculty/
    │   ├── faculty_registry.json          # All faculty/staff credentials
    │   └── verification_log.json          # License verification attempts and results
    ├── achievements/
    │   ├── achievement_data.json          # Student outcome data by program and year
    │   └── trend_analysis.json
    ├── visit_prep/
    │   ├── interview_prep_director.docx
    │   ├── interview_prep_faculty.docx
    │   ├── interview_prep_students.docx
    │   ├── interview_prep_financial_aid.docx
    │   ├── mock_evaluation_report.docx
    │   ├── ose_form_prefilled.docx
    │   └── visit_day_schedule.docx
    ├── responses/                         # Post-visit response documents
    │   ├── team_report_original.pdf
    │   ├── response_draft.docx
    │   └── corrective_action_plan.docx
    ├── submissions/                       # Packaged submission bundles
    │   ├── accsc_renewal_2026/
    │   │   ├── table_of_contents.docx
    │   │   └── ... (organized by accreditor requirements)
    │   └── accsc_renewal_2026.zip
    ├── calendar.json                      # All compliance deadlines
    ├── action_plan.json                   # Master action plan across all areas
    ├── regulatory_stack.json              # Computed regulatory requirements
    └── truth_index.json                   # Single Source of Truth index (see below)
```

### Key Principles

1. **Originals are sacred.** Uploaded files go into `originals/` and are NEVER modified. Everything else is generated or edited.

2. **Finals are the truth.** The `finals/` folder for each program and the catalog contains THE current authoritative version. When the cross-document consistency engine runs, it reads from these files.

3. **Everything is a real file.** The user can open any file in Word, browse the folder in Finder/Explorer, and share files directly. The app generates real .docx and .pdf files, not just database records.

4. **The workspace persists.** Between sessions, between restarts, the workspace is always there. The app picks up where it left off.

5. **Document versions are tracked.** Each document edit creates a new version. The previous version moves to a `_versions/` subfolder with a timestamp.

---

## Single Source of Truth — Cross-Document Consistency Engine

This is one of the most critical features. Accreditation evaluators specifically look for **inconsistencies between documents** — and they WILL find them. The system must enforce a single source of truth.

### The Truth Index

The `truth_index.json` file maintains a registry of authoritative values that must be consistent across ALL documents:

```json
{
  "institution": {
    "name": "CEM College",
    "accreditor_school_ids": {"main": "M055215", "branch": "B055216"},
    "campuses": [
      {"name": "San Juan", "address": "Calle 13 #1206, Urb. Ext. San Agustín, Río Piedras, PR 00926", "type": "main"},
      {"name": "Humacao", "address": "...", "type": "branch"}
    ],
    "state_authority": {"name": "CEPR", "address": "...", "phone": "...", "url": "..."},
    "accsc_contact": {"address": "...", "phone": "...", "url": "..."},
    "complaint_official": {"title": "Director(a) de Asuntos Estudiantiles", "title_en": "Director of Student Affairs"}
  },
  "programs": {
    "bsn-nursing": {
      "name_es": "Bachillerato en Ciencias de Enfermería",
      "name_en": "Bachelor of Science in Nursing",
      "total_credits": 131,
      "total_cost": 38880.00,
      "duration_months": 36,
      "academic_periods": 9,
      "cost_per_period": 4320.00,
      "book_cost": 3641.00,
      "uniform_cost": 575.00,
      "materials_cost": 115.00,
      "modality": "hybrid"
    }
  },
  "policies": {
    "refund_table": [...],
    "cancellation_period_days": 3,
    "admin_fee": 150.00,
    "institutional_refund_window_days": 90,
    "title_iv_return_days": 45,
    "ferpa_opt_out_days": 30,
    "fee_schedule": {...}
  }
}
```

### Consistency Check Engine

When triggered (manually or after any document update), the engine:

1. **Reads the truth index** — the authoritative values
2. **Scans every document in `finals/`** across all programs and the catalog
3. **Extracts comparable values** — tuition amounts, credit counts, fee schedules, refund percentages, policy language, contact info, school IDs, program names, etc.
4. **Compares against the truth index** — flags any mismatch
5. **Compares documents against each other** — even without a truth index entry, if the catalog says tuition is $4,100 but the EA says $4,320, that's flagged
6. **Produces a Consistency Report** showing:
   - ✅ Consistent values (verified across N documents)
   - ❌ Mismatches (with exact location in each document, current value, expected value)
   - ⚠ Values found in some documents but not others (potential gaps)

### Automatic Truth Propagation

When the user updates a value in the truth index (e.g., changes tuition from $4,320 to $4,100), the system can:
- Show which documents would be affected
- Offer to update all affected documents automatically
- Regenerate affected deliverables (checklists, cross-references, etc.)

---

## Document Workspace — Edit, Fix, Draft, Rebuild Any Document

The system is not just an auditor — it's a **document workbench**. Users need to:

### Work on a Single Document
- Open any document in the workspace
- View it rendered (HTML preview or PDF embed)
- AI-assisted editing: "Fix the FERPA section to include identity verification language"
- Find-and-replace across the document
- Insert/modify specific sections
- Track what was changed and why
- Save new version to workspace

### Draft a New Document from Scratch
The system can **generate a complete first draft** of any institutional document type:

- **Enrollment Agreement** — from program data + regulatory stack + institution profile
- **Institutional Catalog** — from institution profile + all program data + policies
- **Student Handbook** — from policies + institutional context
- **Admissions Manual** — from admissions policies + regulatory requirements
- **Faculty Handbook** — from faculty policies + PD requirements
- **Any Policy Document** — from regulatory requirements + institutional context
- **Self-Evaluation Report (SER)** — section-by-section from institutional data
- **Team Report Response** — from evaluator findings + institutional evidence

### Rebuild an Existing Document
When a document is outdated, the system can:
1. Parse the existing document to extract current content
2. Audit it against current standards
3. Identify what needs to change
4. Generate an updated version that:
   - Preserves what's still valid
   - Fixes what's broken
   - Adds what's missing
   - Updates all data values from the truth index
   - Maintains the institution's voice and formatting style
5. Produce a redline showing what changed and why

---

## Catalog Builder

Catalogs are the **most complex document** an institution maintains. They're typically 50-100+ pages and must satisfy requirements from every regulatory body simultaneously.

### Catalog Builder Features

**From-scratch generation:**
- Wizard collects: institution profile, all programs, policies, staff/faculty, calendar
- AI generates a complete catalog structure following the accreditor's catalog checklist
- Fills all sections with institution-specific content
- Cross-references against the accreditor's catalog checklist
- Applies federal requirements (FERPA disclosure, Clery, drug-free campus, gainful employment, etc.)
- Applies state requirements (CEPR, CIE, BPPE, etc.)
- Generates in requested language(s)

**Catalog audit:**
- Upload existing catalog (PDF or DOCX)
- AI audits against full regulatory stack
- Produces findings per catalog checklist item
- Flags missing sections, outdated information, inconsistencies with EAs

**Catalog update/rebuild:**
- Parse existing catalog
- Apply changes from truth index (updated tuition, new programs, revised policies)
- Insert missing required sections
- Fix identified issues
- Regenerate table of contents
- Produce redline showing changes + clean updated version

**Section-level editing:**
- Work on individual catalog sections without regenerating the whole thing
- "Update the refund policy section to match the new ACCSC requirements"
- "Add the new Pet Grooming program to the catalog"
- "Update all tuition tables to reflect the 2026-2027 rates"

---

## Checklist Builder

The system builds **any type of checklist** — not just the accreditor's official checklists, but custom verification checklists for any purpose.

### Types of Checklists

**Accreditor checklists** (filled from document data):
- Enrollment Agreement Checklist (e.g., ACCSC's 35-item checklist with page numbers)
- Catalog Checklist (e.g., ACCSC's ~60-item catalog requirements)
- On-Site Evaluation Checklist
- Annual Report Checklist

**On-site visit verification checklists** (AI-generated from audit findings):
- Items to verify on-site grouped by area
- Priority-coded (critical → high → medium → informational)
- Checkbox format for evaluator use
- Cross-referenced to specific standards, SER sections, and documents
- Pre-visit action items (e.g., "Request Canvas LMS login from DE Director")

**Custom compliance checklists:**
- Per-program compliance status checklists
- Policy completeness checklists
- Exhibit readiness checklists
- Faculty credential checklists
- Document review due-date checklists

**Pre-visit preparation checklists:**
- Room setup checklist
- Document room organization checklist
- Staff notification and briefing checklist
- Technology/equipment verification checklist

### Checklist Generation Logic

1. AI reads the relevant standards/requirements
2. AI reads the institutional context (audit findings, documents, exhibits)
3. AI generates checklist items with:
   - Checkbox
   - Description
   - Priority/severity badge
   - Regulatory citation
   - Where to find evidence
   - Cross-reference to audit finding (if applicable)
4. System formats as .docx with the institution's branding

---

## Interview Preparation — Role-Specific Questions for On-Site Visits

Accreditation visits involve interviews with **every role in the institution**. The system generates tailored interview preparation documents for each role, based on:
- The accreditor's standards (what they're required to ask about)
- The institution's specific audit findings (what evaluators will probe)
- Common evaluator questions per role
- Areas of concern flagged in the SER or prior correspondence

### Roles and Question Areas

**School Director / President:**
- Mission and strategic planning
- Governance and decision-making
- Financial stability and resource allocation
- Knowledge of accreditation standards
- Enrollment management
- Response to any prior findings or concerns
- Substantive changes since last visit

**Academic Director / Dean:**
- Curriculum development and review process
- Program Advisory Committee involvement
- Faculty hiring, evaluation, and development
- SAP policy administration
- Student complaint handling
- Distance education oversight (if applicable)
- How student achievement data informs decisions

**Faculty Members (per program):**
- Their qualifications for the courses they teach
- How they develop and update curriculum
- Student assessment methods
- How they provide feedback to students
- Professional development activities
- Awareness of student outcome data
- Distance education delivery methods (if applicable)
- Resources available for instruction

**Financial Aid Director:**
- Title IV administration procedures
- R2T4 calculation process
- Student eligibility verification
- Loan counseling procedures
- Cohort default rate management
- FAFSA processing timeline
- Communication with students about aid status

**Registrar:**
- Student records management
- FERPA compliance procedures
- Transcript evaluation process
- Transfer credit policies
- Attendance tracking
- SAP monitoring and notification
- Grade change procedures

**Admissions Representatives:**
- Admissions criteria and process
- How they present the school to prospective students
- What disclosures they provide before enrollment
- How they handle questions about outcomes/employment
- Training they receive on advertising/representation rules
- Their understanding of the enrollment agreement

**Career Services / Placement Officer:**
- Employment verification methodology
- How they assist graduates with job placement
- Employer relationship development
- Employment rate calculation (population base, timeframe)
- Documentation of placement efforts
- Follow-up with graduates

**Students (current):**
- Why they chose this school
- Their experience with admissions (were they pressured?)
- Are they aware of complaint procedures?
- Do they have access to the catalog?
- Is instruction quality consistent?
- Are resources (library, labs, equipment) adequate?
- Do they receive timely feedback on assignments?
- Are they aware of student achievement rates?

**Students (graduates):**
- Did the program prepare them for employment?
- Were they assisted with job placement?
- Were they satisfied with the education received?
- Would they recommend the school?
- Was the training consistent with what was represented at enrollment?

### Interview Prep Document Format

Each role gets a .docx document containing:
1. **Role title and who typically interviews them**
2. **General guidance** (be truthful, specific, refer to documentation)
3. **Likely questions** organized by standards area
4. **Suggested talking points** based on institutional evidence
5. **Red flag areas** — specific topics where the institution has known weaknesses (from audit findings) with guidance on honest, constructive responses
6. **DO NOT** list — things to avoid saying (don't guess, don't overcommit, don't contradict the SER)

---

## The Full Accreditation Lifecycle (What This Tool Covers)

### Phase 1: KNOW YOUR REQUIREMENTS

**1.1 — Standards Ingestion & Regulatory Stack Builder**
- Upload/configure the accreditor's standards document (ACCSC, SACSCOC, HLC, ABHES, COE, etc.)
- AI parses standards into structured, searchable sections with checklist items
- System identifies which federal regulations apply based on institution characteristics:
  - **Title IV** (34 CFR §668) — if the school accepts federal financial aid
  - **FERPA** (34 CFR §99) — student privacy (virtually all schools)
  - **Title IX** — sex discrimination protections
  - **Clery Act** — campus security and crime reporting
  - **ADA / Section 504** — disability accommodations
  - **Gainful Employment** (34 CFR §668.402-414) — for certificate/diploma programs at for-profit schools
  - **Veterans Benefits** (38 USC §3679, PL 115-407 §103) — if the school enrolls VA beneficiaries
  - **FTC Act §5** — truth in advertising for educational programs
  - **Reg Z / TILA** — if the school offers payment plans with >4 installments
  - **COPPA** — if the school serves minors in online settings
  - **CARES Act / HEERF** — pandemic-era fund compliance (if applicable)
- System identifies state/territory requirements based on institution location:
  - **Puerto Rico**: CEPR (Consejo de Educación de Puerto Rico) — Ley 212-2018, Reglamento 9272
  - **Florida**: CIE (Commission for Independent Education) — Florida Statutes §1005
  - **California**: BPPE (Bureau for Private Postsecondary Education) — Ed. Code §94800-94950
  - **New York**: BPSS (Bureau of Proprietary School Supervision)
- System identifies professional/programmatic requirements
- **Output**: A unified **Regulatory Stack** showing ALL requirements

**1.2 — Exhibit Registry**
- Every accreditor requires specific exhibits for their visit
- The system maintains an **Exhibit Checklist** per accreditor
- **AI functionality**: When an exhibit document is uploaded, the system automatically audits it against ALL applicable requirements

### Phase 2: ASSESS CURRENT STATE

**2.1 — Document Audit Engine**
- Upload institutional documents
- AI audits each document against the FULL regulatory stack
- Multi-pass verification (5+ passes for comprehensive coverage)
- Beyond-checklist findings
- Cross-document consistency checks

**2.2 — Policy Gap Analysis**
- Checks which required policies exist, which are missing, and which are incomplete
- Maps each policy to which regulation(s) require it

**2.3 — Faculty & Staff Credential Tracker**
- Faculty/Staff Registry with credentials, licenses, qualifications
- Cross-check qualifications against teaching assignments
- Expiration alerts
- Web verification of licenses

**2.4 — Student Achievement Data Validator**
- Track graduation, employment, licensure pass rates
- Trend analysis (5-year trends)
- Benchmark comparisons
- Mathematical accuracy verification

**2.5 — Advertising & Marketing Compliance Scanner**
- Review website, brochures, social media
- Check against accreditor + FTC + state advertising requirements

### Phase 3: FIX AND PREPARE

**3.1 — Document Remediation & Deliverable Generation**
- Audit Report (.docx)
- Tracked Changes / Redline (.docx, per language)
- Final Clean Version (.docx, per language)
- Cross-Reference Version (.docx, per language)
- Filled Checklist (.docx, per language)
- Action Plan

**3.2 — Self-Evaluation Report (SER) Assistant**
- Parse accreditor's SER template into structured outline
- Draft narrative responses with evidence citations
- Cross-reference SER claims against actual document content

**3.3 — Exhibit Collector & Validator**
- Track every required exhibit
- AI reviews for completeness, currency, accuracy

**3.4 — Policy Generator**
- Draft missing policies based on regulatory requirements

**3.5 — Action Plan Manager**
- Aggregate all issues into unified action plan
- Kanban board view and table view
- Progress tracking

### Phase 4: VISIT PREPARATION & EXECUTION

**4.1 — On-Site Evaluation (OSE) Prep Kit**
- Visit preparation checklist
- Room/space setup requirements
- Staff interview preparation
- Day-by-day schedule template

**4.2 — Mock Visit / Readiness Assessment**
- AI-powered simulation of an evaluator's review
- Mock Team Report with predicted findings
- Readiness score

**4.3 — Evaluator Form Pre-Filler**
- Pre-fill evaluation form templates based on SER data

### Phase 5: POST-VISIT RESPONSE

**5.1 — Team Report Response Writer**
- Parse findings from team report
- Draft responses with evidence citations
- Track corrective actions

**5.2 — Corrective Action Plan Generator**
- Formal corrective action plan in accreditor's format
- Implementation tracking

### Phase 6: ONGOING COMPLIANCE

**6.1 — Compliance Calendar**
- Track ALL deadlines across ALL regulatory bodies
- Countdown timers and automated reminders

**6.2 — Annual Report Preparation**
- Pre-fill annual report templates
- Validate data consistency

**6.3 — Substantive Change Monitor**
- Track institution changes that require notification

**6.4 — Document Review Scheduler**
- Track when documents were last reviewed
- Flag overdue documents

---

## Architecture

**Follow the same layered structure as Course Builder Studio (`src/`):**

- **`src/core/`** — Framework-agnostic domain layer
  - `models.py` — All dataclasses and enums
  - `workspace.py` — The local workspace manager
  - `project_store.py` — Institution/audit persistence
  - `standards_store.py` — Standards library persistence
  - `document_store.py` — Document file storage
  - `truth_engine.py` — Single Source of Truth engine
  - `vector_store.py` — Embeddings and semantic search
  - `exhibit_store.py` — Exhibit registry
  - `faculty_store.py` — Faculty/staff credential tracking
  - `achievement_store.py` — Student achievement data
  - `calendar_store.py` — Compliance calendar
  - `regulatory_stack.py` — Regulatory stack builder
  - `pii_redactor.py` — PII detection and redaction

- **`src/agents/`** — The agentic brain
  - `orchestrator.py` — Routes requests, manages workflows
  - `ingestion_agent.py` — Document parsing, classification
  - `standards_agent.py` — Standards tree management
  - `audit_agent.py` — Multi-pass auditing
  - `evidence_agent.py` — Exhibit validation
  - `consistency_agent.py` — Cross-document truth enforcement
  - `remediation_agent.py` — Document fixing, redlines
  - `findings_agent.py` — Accreditor letter parsing
  - `narrative_agent.py` — Compliance narrative drafting
  - `packet_agent.py` — Submission package assembly
  - `checklist_agent.py` — Checklist building
  - `interview_agent.py` — Interview prep generation
  - `catalog_agent.py` — Catalog generation/audit
  - `faculty_agent.py` — Faculty credential checking
  - `achievement_agent.py` — Student outcome validation
  - `base_agent.py` — Abstract base class
  - `session_manager.py` — AgentSession lifecycle
  - `tool_registry.py` — Agent tool definitions
  - `prompts/` — Versioned prompt templates

- **`src/api/`** — Flask Blueprints (each using `init_*_bp(stores...)` DI pattern)
  - `institutions.py` — Institution + program CRUD
  - `workspace.py` — Browse workspace, truth index CRUD
  - `documents.py` — Upload, extraction, preview
  - `document_editor.py` — AI-assisted editing
  - `audits.py` — Run audits, findings, overrides
  - `deliverables.py` — Generate, preview, download
  - `standards.py` — Browse, search, import standards
  - `exhibits.py` — Exhibit registry
  - `faculty.py` — Faculty registry
  - `achievements.py` — Student achievement data
  - `policies.py` — Policy gap analysis
  - `catalog.py` — Catalog builder
  - `checklists.py` — Checklist builder
  - `interview_prep.py` — Interview prep generator
  - `submissions.py` — Submission package organization
  - `action_plans.py` — Remediation tracking
  - `calendar.py` — Compliance calendar
  - `ser.py` — Self-evaluation report drafting
  - `responses.py` — Post-visit team report response
  - `advertising.py` — Marketing compliance review
  - `readiness.py` — Mock visit / readiness assessment
  - `consistency.py` — Cross-document consistency checks
  - `chat.py` — Chat interface API
  - `sessions.py` — Agent session API
  - `search.py` — Semantic search API

- **`src/generators/`** — Document generation
  - `base_generator.py` — Abstract BaseGenerator[T]
  - `schemas/` — Pydantic models for each output type

- **`src/validators/`** — Validation logic
  - `document_validator.py`
  - `standards_validator.py`
  - `consistency_validator.py`
  - `faculty_validator.py`
  - `achievement_validator.py`
  - `exhibit_validator.py`
  - `pii_validator.py`

- **`src/regulatory/`** — Regulatory knowledge base
  - `federal.py` — Federal regulation definitions
  - `states/` — State-specific modules
  - `professional.py` — Professional body requirements
  - `stack_builder.py` — Assembles full regulatory stack

- **`src/exporters/`** — Document generation
  - `docx_builder.py`
  - `pdf_builder.py`
  - `submission_packager.py`
  - `calendar_exporter.py`
  - `ser_exporter.py`

- **`src/importers/`** — Document ingestion
  - `docx_parser.py`
  - `pdf_parser.py`
  - `standards_importer.py`
  - `exhibit_importer.py`
  - `csv_importer.py`
  - `chunker.py` — Semantic chunking for RAG

- **`src/ai/`** — AI infrastructure
  - `client.py` — AIClient wraps Anthropic SDK
  - `embeddings.py` — Embedding generation
  - `retriever.py` — RAG retriever

- **`src/tasks/`** — Background task queue
  - `queue.py` — SQLite-backed task queue
  - `worker.py` — Background worker process

- **`src/config.py`** — Configuration

- **`src/auth/`** — Authentication

**Entry point:** `app.py`

**Frontend:** Jinja2 templates + vanilla JS, dark theme (#1a1a2e)

---

## Data Model

### Enums

```python
class AccreditingBody(str, Enum):
    ACCSC = "ACCSC"
    SACSCOC = "SACSCOC"
    HLC = "HLC"
    WASC = "WASC"
    ABHES = "ABHES"
    COE = "COE"
    DEAC = "DEAC"
    CUSTOM = "CUSTOM"

class DocumentType(str, Enum):
    ENROLLMENT_AGREEMENT = "enrollment_agreement"
    CATALOG = "catalog"
    STUDENT_HANDBOOK = "student_handbook"
    ADMISSIONS_MANUAL = "admissions_manual"
    FACULTY_HANDBOOK = "faculty_handbook"
    POLICY_MANUAL = "policy_manual"
    SELF_EVALUATION_REPORT = "self_evaluation_report"
    CANVAS_MANUAL = "canvas_manual"
    FINANCIAL_AID_POLICY = "financial_aid_policy"
    COMPLAINT_POLICY = "complaint_policy"
    SAFETY_PLAN = "safety_plan"
    DRUG_FREE_POLICY = "drug_free_policy"
    TITLE_IX_POLICY = "title_ix_policy"
    ADA_POLICY = "ada_policy"
    FACULTY_PD_PROTOCOL = "faculty_pd_protocol"
    ADVISORY_COMMITTEE_MINUTES = "advisory_committee_minutes"
    ORGANIZATIONAL_CHART = "organizational_chart"
    FINANCIAL_STATEMENTS = "financial_statements"
    OTHER = "other"

class Language(str, Enum):
    EN = "en"
    ES = "es"
    BILINGUAL = "bilingual"

class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NA = "na"

class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    SIGNIFICANT = "significant"
    ADVISORY = "advisory"
    INFORMATIONAL = "informational"

class RegulatorySource(str, Enum):
    ACCREDITOR = "accreditor"
    FEDERAL_TITLE_IV = "federal_title_iv"
    FEDERAL_FERPA = "federal_ferpa"
    FEDERAL_TITLE_IX = "federal_title_ix"
    FEDERAL_CLERY = "federal_clery"
    FEDERAL_ADA = "federal_ada"
    FEDERAL_VA = "federal_va"
    FEDERAL_FTC = "federal_ftc"
    FEDERAL_REG_Z = "federal_reg_z"
    FEDERAL_GAINFUL_EMPLOYMENT = "federal_gainful_employment"
    FEDERAL_DRUG_FREE = "federal_drug_free"
    STATE = "state"
    PROFESSIONAL = "professional"
    INSTITUTIONAL = "institutional"

class AuditStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    APPROVED = "approved"

class DeliverableType(str, Enum):
    AUDIT_REPORT = "audit_report"
    REDLINE = "redline"
    FINAL_CLEAN = "final_clean"
    CROSS_REFERENCE = "cross_reference"
    CHECKLIST = "checklist"
    ACTION_PLAN = "action_plan"
    SER_DRAFT = "ser_draft"
    TEAM_RESPONSE = "team_response"
    POLICY_DRAFT = "policy_draft"
    EXHIBIT_REPORT = "exhibit_report"
    FACULTY_REPORT = "faculty_report"
    ACHIEVEMENT_REPORT = "achievement_report"
    READINESS_REPORT = "readiness_report"
    ADVERTISING_REPORT = "advertising_report"

class ExhibitStatus(str, Enum):
    NOT_STARTED = "not_started"
    COLLECTING = "collecting"
    UPLOADED = "uploaded"
    AI_REVIEWED = "ai_reviewed"
    FLAGGED = "flagged"
    APPROVED = "approved"

class ActionItemStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"

class CredentialLevel(str, Enum):
    DIPLOMA = "diploma"
    CERTIFICATE = "certificate"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORAL = "doctoral"

class Modality(str, Enum):
    ON_GROUND = "on_ground"
    HYBRID = "hybrid"
    ONLINE = "online"
    MIXED = "mixed"

class CalendarEventType(str, Enum):
    ACCREDITOR_DEADLINE = "accreditor_deadline"
    FEDERAL_DEADLINE = "federal_deadline"
    STATE_DEADLINE = "state_deadline"
    VISIT_DATE = "visit_date"
    LICENSE_EXPIRATION = "license_expiration"
    DOCUMENT_REVIEW_DUE = "document_review_due"
    ANNUAL_REPORT_DUE = "annual_report_due"
    INTERNAL_DEADLINE = "internal_deadline"

class ReadinessLevel(str, Enum):
    READY = "ready"
    MOSTLY_READY = "mostly_ready"
    SIGNIFICANT_GAPS = "significant_gaps"
    NOT_READY = "not_ready"
```

### Core Dataclasses

```python
@dataclass
class Institution:
    id: str
    name: str
    accrediting_body: AccreditingBody
    school_ids: dict                      # {"main": "M055215", "branch": "B055216"}
    campuses: list[dict]                  # [{name, address, city, state, zip, type}]
    state_authority: dict                 # {name, address, phone, url}
    federal_characteristics: dict         # {title_iv: True, va_approved: True, ...}
    state_code: str                       # "PR", "FL", "CA"
    programs: list[Program]
    created_at: str
    updated_at: str

@dataclass
class Program:
    id: str
    name_en: str
    name_es: str
    credential_level: CredentialLevel
    total_credits: int
    total_cost: float
    duration_months: int
    academic_periods: int
    cost_per_period: float
    book_cost: float
    other_costs: dict
    modality: Modality
    licensure_required: bool
    licensure_exam: str
    professional_body: str
    programmatic_accreditor: str

@dataclass
class RegulatoryStack:
    id: str
    institution_id: str
    accreditor_standards: StandardsLibrary
    federal_regulations: list[FederalRegulation]
    state_regulations: list[StateRegulation]
    professional_requirements: list[ProfessionalRequirement]
    built_at: str

@dataclass
class FederalRegulation:
    code: RegulatorySource
    name: str
    citation: str
    applies_because: str
    key_requirements: list[str]
    document_types_affected: list[DocumentType]
    full_text_excerpt: str

@dataclass
class StateRegulation:
    state_code: str
    authority_name: str
    law_citation: str
    key_requirements: list[str]
    document_types_affected: list[DocumentType]

@dataclass
class ProfessionalRequirement:
    program_id: str
    body_name: str
    requirements: list[str]
    credential_requirements: list[str]

@dataclass
class StandardsLibrary:
    id: str
    accrediting_body: AccreditingBody
    name: str
    version: str
    effective_date: str
    checklist_items: list[ChecklistItem]
    sections: list[StandardsSection]
    full_text: str
    is_system_preset: bool
    created_at: str

@dataclass
class ChecklistItem:
    number: str
    category: str
    description: str
    section_reference: str
    applies_to: list[DocumentType]

@dataclass
class StandardsSection:
    id: str
    number: str
    title: str
    text: str
    parent_section: str

@dataclass
class Document:
    id: str
    institution_id: str
    program_id: str
    doc_type: DocumentType
    language: Language
    original_filename: str
    file_path: str
    extracted_text: str
    extracted_structure: dict
    page_count: int
    version: int
    status: str
    last_reviewed_date: str
    review_cycle_months: int
    uploaded_at: str
    updated_at: str

@dataclass
class Audit:
    id: str
    document_id: str
    program_id: str
    standards_library_id: str
    regulatory_stack_id: str
    audit_type: str
    status: AuditStatus
    summary: dict
    summary_by_source: dict
    findings: list[AuditFinding]
    passes_completed: int
    ai_model_used: str
    started_at: str
    completed_at: str

@dataclass
class AuditFinding:
    id: str
    audit_id: str
    item_number: str
    item_description: str
    status: ComplianceStatus
    severity: FindingSeverity
    regulatory_source: RegulatorySource
    regulatory_citation: str
    evidence_in_document: str
    finding_detail: str
    recommendation: str
    page_numbers: str
    ai_confidence: float
    human_override_status: str
    human_notes: str
    pass_discovered: int

@dataclass
class Exhibit:
    id: str
    institution_id: str
    exhibit_number: str
    title: str
    description: str
    required_by: list[str]
    status: ExhibitStatus
    documents: list[str]
    issues: list[ExhibitIssue]
    assignee: str
    due_date: str
    notes: str

@dataclass
class ExhibitIssue:
    id: str
    exhibit_id: str
    description: str
    severity: FindingSeverity
    regulatory_source: RegulatorySource
    regulatory_citation: str
    recommendation: str
    status: ActionItemStatus

@dataclass
class FacultyMember:
    id: str
    institution_id: str
    name: str
    title: str
    role: str
    employment_start_date: str
    employment_type: str
    academic_credentials: list[dict]
    professional_licenses: list[dict]
    work_experience: list[dict]
    foreign_credential_eval: dict
    teaching_assignments: list[dict]
    professional_development: list[dict]
    compliance_status: str
    issues: list[str]

@dataclass
class StudentAchievementData:
    id: str
    program_id: str
    reporting_year: str
    cohort_start_date: str
    population_base: int
    graduation_count: int
    graduation_rate: float
    employment_count: int
    employment_rate: float
    licensure_exam_name: str
    licensure_attempts: int
    licensure_passes: int
    licensure_pass_rate: float
    retention_rate: float
    data_source: str

@dataclass
class ComplianceCalendarEvent:
    id: str
    institution_id: str
    event_type: CalendarEventType
    title: str
    description: str
    regulatory_source: RegulatorySource
    due_date: str
    reminder_days: list[int]
    recurring: bool
    recurrence_months: int
    status: str
    completed_at: str
    notes: str

@dataclass
class SubmissionPackage:
    id: str
    institution_id: str
    name: str
    accrediting_body: AccreditingBody
    visit_date: str
    programs_included: list[str]
    folders: list[dict]
    exhibits: list[str]
    status: str
    created_at: str
    packaged_at: str
    zip_file_path: str

@dataclass
class ActionPlan:
    id: str
    institution_id: str
    name: str
    items: list[ActionItem]
    overall_status: str
    visit_date: str
    created_at: str

@dataclass
class ActionItem:
    id: str
    action_plan_id: str
    source_type: str
    source_id: str
    phase: int
    description: str
    regulatory_source: RegulatorySource
    regulatory_citation: str
    assignee: str
    due_date: str
    status: ActionItemStatus
    evidence_of_completion: str
    completed_at: str

@dataclass
class ReadinessAssessment:
    id: str
    institution_id: str
    assessment_date: str
    overall_level: ReadinessLevel
    area_scores: dict
    predicted_findings: list[dict]
    recommendations: list[str]
    days_until_visit: int

# Agent System Models

@dataclass
class AgentSession:
    id: str
    institution_id: str
    parent_session_id: str
    orchestrator_request: str
    status: str
    agents_involved: list[str]
    tasks: list[AgentTask]
    checkpoints: list[HumanCheckpoint]
    artifacts_created: list[str]
    chat_history: list[dict]
    started_at: str
    completed_at: str
    total_ai_tokens_used: int
    total_ai_calls: int
    error_message: str

@dataclass
class AgentTask:
    id: str
    session_id: str
    agent: str
    action: str
    status: str
    input_summary: str
    output_summary: str
    confidence: float
    citations: list[dict]
    duration_ms: int
    ai_model: str
    ai_tokens_used: int
    started_at: str
    completed_at: str

@dataclass
class HumanCheckpoint:
    id: str
    session_id: str
    task_id: str
    agent: str
    checkpoint_type: str
    question: str
    context: str
    options: list[str]
    user_response: str
    answered_at: str

@dataclass
class ChatMessage:
    id: str
    session_id: str
    institution_id: str
    role: str
    message_type: str
    content: str
    metadata: dict
    agent: str
    timestamp: str

# Vector Store / RAG Models

@dataclass
class DocumentChunk:
    id: str
    document_id: str
    chunk_index: int
    page_number: int
    section_header: str
    text_original: str
    text_redacted: str
    text_anonymized: str
    embedding: list[float]
    metadata: dict
    created_at: str

@dataclass
class SemanticSearchResult:
    chunk: DocumentChunk
    similarity_score: float
    document_path: str
    document_type: str
    highlight_text: str

# Audit Log

@dataclass
class AuditLogEntry:
    id: str
    timestamp: str
    session_id: str
    agent: str
    action: str
    target_type: str
    target_id: str
    input_hash: str
    output_hash: str
    ai_model: str
    ai_tokens: int
    confidence: float
    human_approved: bool
    user_id: str
    details: dict
```

---

## Application Pages

### Dashboard (`/`)
- Compliance Score gauge
- Regulatory Stack Overview cards
- Countdown to next visit/deadline
- Top 10 action items
- Consistency status
- Agent activity feed
- Recent activity
- Quick actions

### Chat Panel (persistent sidebar)
- Slide-out from any page
- Natural language + slash commands
- Real-time progress streaming
- Inline file links and approval requests
- Conversation history

### Agent Sessions (`/sessions`)
- List of all sessions
- Task breakdown per session
- Human checkpoint responses
- Token usage tracking
- Audit log viewer

### Semantic Search (`/search`)
- Full-text semantic search
- Filter by document type, program, language, date
- Click results to open source

### Workspace Browser (`/workspace`)
- File tree view
- Status badges
- Version history
- Open in OS file manager

### Institution Setup (`/institutions/:id`)
- Institution profile
- Regulatory Stack Builder wizard
- Programs list
- Documents library

### Standards Library (`/standards`)
- System presets + custom
- Import wizard
- Browse and search

### Document Manager (`/documents`)
- Upload with drag-and-drop
- Text extraction preview
- Version history
- Review scheduler

### Document Editor (`/documents/:id/edit`)
- Split-pane: rendered doc + AI editing panel
- Section editor, find & fix, insert section
- Apply audit findings
- Translate
- Truth check button

### Catalog Builder (`/catalog`)
- Build from scratch or rebuild existing
- Section navigator
- Program editor
- Consistency badge
- Preview and export

### Checklist Builder (`/checklists`)
- Template gallery
- Auto-fill mode
- Custom builder
- Verification checklist generator

### Interview Prep (`/interview-prep`)
- Role selector
- Generate button
- Preview and edit
- Red flag mode toggle
- Batch generate

### Consistency Center (`/consistency`)
- Run check button
- Green/red/yellow cards
- Truth index editor
- Propagate button
- History

### Audit Workspace (`/audits/:id`)
- Split-pane: document + findings
- Regulatory source badges
- Fix-It wizard
- Filter and override controls
- Writing mode toggle

### Exhibit Manager (`/exhibits`)
- Exhibit checklist grid
- Upload evidence
- AI review results

### Faculty Dashboard (`/faculty`)
- Credential status table
- Verification tools
- Expiration alerts

### Student Achievement (`/achievements`)
- Per-program data tables with trends
- Benchmark comparisons
- Data import

### Policy Center (`/policies`)
- Required policies checklist
- Upload and AI draft generation
- Review scheduler

### Deliverables (`/audits/:id/deliverables`)
- Card grid with language selector
- Generate/preview/download

### Submission Organizer (`/submissions/:id`)
- Drag-and-drop folder builder
- Auto-organize
- TOC generator
- Download as zip

### Action Plan (`/action-plans/:id`)
- Kanban board
- Filter controls
- Progress dashboard

### Compliance Calendar (`/calendar`)
- Monthly/weekly/list view
- Color-coded by regulatory source
- Add/edit events

### SER Assistant (`/ser`)
- Section-by-section drafting
- Data auto-fill
- Export

### Readiness Assessment (`/readiness`)
- Mock evaluation
- Readiness gauge
- Area scores
- Predicted findings

### Post-Visit Response (`/responses/:id`)
- Upload team report
- AI-parsed findings
- Draft responses
- Track corrective actions

---

## AI Engine Design Principles

1. **Zero Hallucination Tolerance.** Every claim must be grounded in actual document text.

2. **Cite Everything.** Every finding links to specific standard ID + document + page/section.

3. **Two-Way Verification.** Compliant items are re-checked for false positives; non-compliant items are re-checked for false negatives.

4. **Multi-Regulatory Awareness.** Findings cite all applicable regulatory sources.

5. **Confidence Scoring.** AI reports confidence 0.0-1.0; < 0.7 requires human review.

6. **Writing Modes.** Draft mode for iteration; submission mode for audit-proof output.

7. **Human-Reviewable Output.** All AI outputs are structured for human verification.

8. **Graceful Degradation.** App fully works without AI; AI is enhancement, not gate.

9. **Always audit against the full regulatory stack.** Not just accreditor requirements.

10. **Regulatory citations must be specific.** "34 CFR §668.43(a)(2)" not just "federal requirement".

11. **Cross-document consistency is critical.** Compare claims across all documents.

12. **Severity reflects regulatory risk.** Critical = loss of accreditation/Title IV eligibility.

13. **Never claim full compliance without evidence.** Flag limitations, not false passes.

---

## Frontend Style

```css
--bg-primary: #1a1a2e;
--bg-secondary: #16213e;
--bg-card: #0f3460;
--accent: #e94560;
--text-primary: #eee;
--text-secondary: #aaa;
--success: #4ade80;        /* compliant */
--warning: #fbbf24;        /* partial */
--danger: #ef4444;         /* non-compliant */
--info: #60a5fa;           /* N/A */

/* Regulatory source colors */
--accreditor: #a78bfa;     /* purple */
--federal: #f472b6;        /* pink */
--state: #fb923c;          /* orange */
--professional: #34d399;   /* teal */
```

---

## Commands

```bash
python app.py                # Flask dev server on port 5003
flask init-db                # Initialize database
pytest                       # Run all tests
pip install -r requirements.txt
```

## Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-sonnet-4-20250514
EMBEDDING_MODEL=claude-embed-1
MAX_TOKENS=8192
PORT=5003
WORKSPACE_DIR=./workspace
UPLOAD_DIR=./uploads
SECRET_KEY=...

# Agent configuration
AGENT_CONFIDENCE_THRESHOLD=0.7
AGENT_AUTO_APPROVE=false
AGENT_MAX_CONCURRENT_TASKS=3
AGENT_SESSION_LOG=true

# Vector store
VECTOR_STORE=sqlite-vss
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# PII
PII_DETECTION=regex+ai
PII_ENCRYPTION_KEY=...
```

## Dependencies

```
# Core
flask
flask-login
flask-sse
anthropic
python-dotenv
pydantic

# Document processing
python-docx
pdfplumber
mammoth
pytesseract
Pillow
openpyxl

# Vector store / RAG
sqlite-vss
numpy

# Security
bcrypt
cryptography

# External
requests
icalendar
```

---

## MVP Build Order

### Phase 1 — Foundation: Workspace + Agent Framework
1. Project scaffolding (match Course Builder structure exactly)
2. Workspace manager
3. Core models + stores
4. Agent framework (BaseAgent, tool registry, session manager)
5. Orchestrator Agent (shell)
6. Background task queue
7. Chat API + Chat Panel UI
8. Institution + Program CRUD
9. Dashboard shell

### Phase 2 — Ingestion + Standards + Vector Store
10. Ingestion Agent
11. Chunking + embedding pipeline
12. Semantic search API + UI
13. Standards Agent + ACCSC preset
14. Standards Library UI
15. Regulatory Stack Builder
16. Truth index

### Phase 3 — Audit Engine
17. Audit Agent (multi-pass, RAG-powered)
18. Audit Workspace UI
19. Fix-It wizard
20. Finding overrides + human checkpoints
21. Evidence Agent
22. Audit report generation

### Phase 4 — Remediation + Document Workbench
23. Remediation Agent
24. Document editor UI
25. Document drafter
26. Consistency Agent
27. Consistency Center UI
28. Checklist auto-filling

### Phase 5 — Findings + Narrative + Packets
29. Findings Agent
30. Narrative Agent
31. Packet Agent
32. Submission Organizer UI
33. Action plan generation + tracking

### Phase 6 — Catalog + Exhibits + Faculty
34. Catalog Agent + Builder UI
35. Exhibit registry + Evidence Agent
36. Faculty Agent
37. Achievement Agent

### Phase 7 — Visit Prep + Interview + Checklists
38. Checklist Agent
39. Interview Prep Agent
40. Mock visit / readiness assessment
41. Visit day schedule
42. SER drafting assistant

### Phase 8 — Post-Visit + Ongoing Compliance
43. Team report response writer
44. Corrective action plan generator
45. Compliance calendar
46. Annual report pre-filler
47. Document review scheduler

### Phase 9 — Polish + Advanced
48. Advertising/marketing compliance scanner
49. Cross-program comparison matrix
50. Standards importer for any accreditor
51. Additional state regulatory modules
52. Batch processing
53. Full observability dashboard

---

## Testing Strategy

- Mock `src.agents.base_agent.Anthropic` for all agent tests
- Use real ACCSC standards text as test fixtures
- CEM College BSN enrollment agreement as primary test document

**Agent framework tests:**
- Orchestrator decomposes requests correctly
- Agent-to-agent communication
- Session lifecycle
- Human checkpoint workflow
- SSE progress streaming
- Agent failure and retry
- Session logging

**RAG pipeline tests:**
- Chunking preserves section boundaries
- PII redaction catches all patterns
- Embeddings use anonymized text
- Semantic search returns correct citations

**Audit agent tests:**
- Multi-pass catches findings
- Findings include all regulatory sources
- Confidence scores are reasonable
- Fix-It wizard generates correct suggestions
- Beyond-checklist findings discovered

**Consistency agent tests:**
- Detects known mismatches
- Truth propagation updates documents
- Reads from actual .docx files

**Findings agent tests:**
- Parses accreditor letters correctly
- Maps to standards sections
- Extracts deadlines

**Narrative agent tests:**
- Draft mode produces informal text
- Submission mode produces cited text
- Every claim has citation

**Packet agent tests:**
- Contains all required sections
- Exhibit list references actual files
- Crosswalk table correct

**PII safety tests:**
- PII never in embeddings, logs, AI prompts
- PII preserved in originals and finals
- Encryption at rest

**Workspace tests:**
- Correct folder structure
- Document upload locations
- Version tracking
- Persistence across restarts
- Truth index CRUD

**Integration tests:**
- Full end-to-end workflows
- Consistency check → remediation → re-check
- Catalog audit → rebuild → re-audit

**Export/deliverable tests:**
- .docx files open without corruption
- Page numbers match
- Cross-reference tags correct
- Redline formatting correct
- Submission zip structure correct

**Manual fallback tests:**
- All features work with AI disabled
- Graceful degradation on rate limits
