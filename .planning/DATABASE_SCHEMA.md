# Database Schema for AccreditationStudio

## Architectural Note

Current state: **File-based JSON persistence** via WorkspaceManager
Future option: **SQLite/PostgreSQL** with this schema

This schema supports: institutions, programs, documents, standards, audits, evidence, consistency, remediation, submissions, agent sessions, multilingual UI, and document translations.

---

## Core Entities

### institutions
- `id` (uuid, pk)
- `name`, `legal_name`
- `accreditor_primary` (e.g., "ACCSC")
- `timezone`, `default_locale`, `supported_locales` (jsonb)
- `theme_preference` (light|dark|system)

### programs
- `id`, `institution_id` (fk)
- `name`, `credential_level`, `delivery_modes` (jsonb)
- `active` (bool)

### users + institution_memberships
- Multi-user with roles: admin|editor|reviewer|viewer|consultant

---

## Documents + Translations

### documents
- `id`, `institution_id`, `program_id` (nullable)
- `doc_type` (catalog|enrollment_agreement|refund_policy|...)
- `source_language`, `status` (uploaded|parsing|indexed|failed)
- `original_file_path`, `file_sha256`, `page_count`

### document_versions
- `version_type` (original|redline|final|crossref)
- `label`, `file_path`, `file_sha256`

### document_parses
- `parser_version`, `extracted_text_path`
- `structured_json_path`, `pii_redacted_text_path`
- `parse_warnings` (jsonb)

### document_chunks
- `chunk_index`, `page_start`, `page_end`
- `text_path`, `embedding_id`

### document_translations
- `source_language`, `target_language` (e.g., es-PR)
- `status` (queued|translating|complete|failed)
- `translated_text_path`, `quality_flags` (jsonb)

### document_chunk_translations
- Per-chunk translations for bilingual evidence display

### terminology_glossaries
- Institution + locale specific term mappings
- `entries` (jsonb): `{"Enrollment Agreement": "Acuerdo de Matrícula"}`

---

## Standards + Regulatory

### accreditors
- `code` (ACCSC, COE, etc.), `name`, `default_language`

### standards
- `accreditor_id`, `standard_code`, `title`, `body`
- `parent_id` (tree structure)

### standard_translations
- `target_language`, `title_translated`, `body_translated`

### checklists + checklist_items
- Per doc_type checklists with `mapped_standard_ids`

### regulatory_stacks
- `institution_id`, `accreditor_id`
- `snapshot` (jsonb): federal/state/licensure refs

---

## Audits + Evidence

### audit_runs
- `institution_id`, `program_id`, `checklist_id`
- `status` (queued|running|complete|failed)

### audit_findings
- `checklist_item_id`, `document_id`
- `status` (compliant|partial|non_compliant|na|needs_info)
- `severity`, `confidence`, `human_review_required`

### evidence_refs
- `finding_id`, `document_id`, `document_version_id`
- `page`, `locator` (jsonb), `snippet_hash`
- `language` (for multilingual evidence display)

### finding_standard_refs
- Links findings to standards

### human_checkpoints
- `checkpoint_type` (low_confidence|finalize_submission|policy_override|...)
- `status` (pending|approved|rejected)

---

## Consistency + Remediation

### truth_index
- `institution_id`, `key` (tuition_total, refund_days, ...)
- `value` (jsonb), `source_ref` (jsonb)

### consistency_checks + consistency_issues
- Track contradictions with `found_values` array

### remediation_jobs
- `document_id`, `audit_run_id`
- `outputs` (jsonb): paths to redline/final/crossref

---

## Submissions

### submission_packets
- `packet_type` (self-study|teach-out|response|follow-up)
- `status` (draft|building|ready|exported)
- `docx_path`, `pdf_path`, `zip_path`

### packet_items
- `type` (narrative|crosswalk|exhibit|cover|toc)
- `ref` (jsonb), `order_index`

---

## Agent Sessions

### agent_sessions
- `institution_id`, `user_id`, `goal`, `status`

### agent_events
- `session_id`, `agent`, `event_type`, `payload` (jsonb)

### plans + plan_tasks
- Task DAG with dependencies, checkpoints, artifacts

---

## Multilingual Implementation

### UI i18n
- User `locale` preference (BCP 47: en-US, es-PR, es-ES, fr-CA)
- Institution `default_locale` + `supported_locales`
- Theme: light|dark|system with CSS tokens

### Document Translation Pipeline
1. Document indexed → trigger translation job
2. Translate chunk-by-chunk with glossary injection
3. Store in `document_chunk_translations`
4. Generate full translated view

### Evidence Display
- `evidence_refs` always store source locator
- UI shows translated excerpt with "Show source" toggle
- Quality flags badge if translation issues detected

---

## Migration Path

Current file-based structure maps to this schema:
- `workspace/{institution_id}/institution.json` → `institutions` table
- `workspace/{institution_id}/programs/` → `programs` table
- `workspace/{institution_id}/**/*.json` → respective tables

SQLAlchemy models can coexist with WorkspaceManager during transition.
