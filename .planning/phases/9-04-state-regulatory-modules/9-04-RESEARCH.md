---
phase: 9-04
type: research
created: 2026-03-27
---

# Phase 9-04: State Regulatory Modules - Research

## Current State

### Existing Infrastructure
- `RegulatoryStack` model has `state_regulations: List[Dict]` (empty, unused)
- `Institution.state_code` and `Institution.state_authority` exist but unused
- `RegulatorySource.STATE` enum defined but not integrated
- Calendar event type `STATE_DEADLINE` exists but unused
- No state requirement data, no state auditing

### Gap Summary
| Feature | Current | Needed |
|---------|---------|--------|
| State Authorization | None | SARA + individual state tracking |
| Catalog Requirements | None | State-specific disclosure checklist |
| Program Licensing | None | Board approvals, exam pass rates |
| Compliance Scoring | None | Per-state readiness (0-100) |
| Calendar Integration | Partial | State deadline auto-population |

## Technical Approach

### Database Schema (Migration 0039)

```sql
CREATE TABLE state_authorizations (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  state_code TEXT NOT NULL,
  authorization_status TEXT NOT NULL,  -- authorized, pending, restricted, denied
  sara_member BOOLEAN DEFAULT FALSE,
  effective_date TEXT,
  renewal_date TEXT,
  contact_agency TEXT,
  contact_url TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(institution_id, state_code)
);

CREATE TABLE state_catalog_requirements (
  id TEXT PRIMARY KEY,
  state_code TEXT NOT NULL,
  requirement_key TEXT NOT NULL,  -- hours_of_operation, refund_policy, etc.
  requirement_name TEXT NOT NULL,
  requirement_text TEXT,
  category TEXT,  -- disclosure, consumer_info, completion_rates
  required BOOLEAN DEFAULT TRUE,
  created_at TEXT NOT NULL,
  UNIQUE(state_code, requirement_key)
);

CREATE TABLE state_catalog_compliance (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  state_code TEXT NOT NULL,
  requirement_id TEXT NOT NULL REFERENCES state_catalog_requirements(id),
  status TEXT NOT NULL,  -- satisfied, partial, missing
  evidence_doc_id TEXT,
  page_reference TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(institution_id, requirement_id)
);

CREATE TABLE state_program_approvals (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  program_id TEXT NOT NULL,
  state_code TEXT NOT NULL,
  board_name TEXT NOT NULL,
  board_url TEXT,
  approved BOOLEAN DEFAULT FALSE,
  approval_date TEXT,
  expiration_date TEXT,
  license_exam TEXT,
  min_pass_rate REAL,
  current_pass_rate REAL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(institution_id, program_id, state_code)
);
```

### Data Models (src/core/models/state_regulations.py)

```python
@dataclass
class StateAuthorization:
    id: str
    institution_id: str
    state_code: str
    authorization_status: str  # authorized, pending, restricted, denied
    sara_member: bool
    effective_date: Optional[str]
    renewal_date: Optional[str]
    contact_agency: Optional[str]
    contact_url: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str

@dataclass
class StateCatalogRequirement:
    id: str
    state_code: str
    requirement_key: str
    requirement_name: str
    requirement_text: Optional[str]
    category: str
    required: bool
    created_at: str

@dataclass
class StateCatalogCompliance:
    id: str
    institution_id: str
    state_code: str
    requirement_id: str
    status: str  # satisfied, partial, missing
    evidence_doc_id: Optional[str]
    page_reference: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str

@dataclass
class StateProgramApproval:
    id: str
    institution_id: str
    program_id: str
    state_code: str
    board_name: str
    board_url: Optional[str]
    approved: bool
    approval_date: Optional[str]
    expiration_date: Optional[str]
    license_exam: Optional[str]
    min_pass_rate: float
    current_pass_rate: float
    notes: Optional[str]
    created_at: str
    updated_at: str
```

### Service Layer (state_regulatory_service.py)

```python
class StateRegulatoryService:
    # Authorization CRUD
    def add_authorization(inst_id, state_code, status, sara_member, ...)
    def get_authorizations(inst_id) -> List[StateAuthorization]
    def update_authorization(auth_id, **updates)
    def delete_authorization(auth_id)

    # Catalog requirements
    def get_requirements_for_state(state_code) -> List[StateCatalogRequirement]
    def get_compliance_status(inst_id, state_code) -> List[StateCatalogCompliance]
    def update_compliance(inst_id, requirement_id, status, evidence_doc_id, ...)

    # Program approvals
    def add_program_approval(inst_id, prog_id, state_code, board_name, ...)
    def get_program_approvals(inst_id, state_code=None) -> List[StateProgramApproval]
    def update_program_approval(approval_id, **updates)

    # Scoring
    def compute_state_readiness(inst_id, state_code) -> StateReadinessScore
    def get_all_states_summary(inst_id) -> List[StateSummary]
```

### API Endpoints (state_regulatory_bp.py)

```
# Authorizations
GET  /api/state-regulations                     # List all states for institution
POST /api/state-regulations                     # Add state authorization
GET  /api/state-regulations/<state_code>        # Get state details
PUT  /api/state-regulations/<state_code>        # Update authorization
DELETE /api/state-regulations/<state_code>      # Remove authorization

# Catalog Requirements
GET  /api/state-regulations/<state>/requirements    # List requirements
GET  /api/state-regulations/<state>/compliance      # Compliance status
PUT  /api/state-regulations/<state>/compliance/<id> # Update compliance

# Program Approvals
GET  /api/state-regulations/<state>/programs        # List program approvals
POST /api/state-regulations/<state>/programs        # Add approval
PUT  /api/state-regulations/<state>/programs/<id>   # Update approval

# Scoring
GET  /api/state-regulations/<state>/readiness       # State readiness score
GET  /api/state-regulations/summary                 # All states summary
```

### State Requirement Presets (5 States)

**California (CA)**
- BPPE approval required for private postsecondary
- School Performance Fact Sheet (SPFS) mandatory
- Completion rate disclosure
- Placement rate disclosure
- Salary and wage information

**Texas (TX)**
- TWC Career Schools and Colleges approval
- Student protection fund participation
- Refund policy state-mandated
- Completion/placement reporting

**New York (NY)**
- NYSED registration required
- Consumer information disclosure
- Program registration per degree level
- Foreign student authorization

**Florida (FL)**
- CIE licensure
- Surety bond requirements
- Agent registration
- Completion rate thresholds

**Illinois (IL)**
- IBHE authorization
- Private Business and Vocational Schools Act
- Student complaint disclosure
- Refund calculation method

## Files to Create

```
src/core/models/state_regulations.py     # Data models
src/services/state_regulatory_service.py # Business logic
src/api/state_regulatory_bp.py          # REST endpoints
src/db/migrations/0039_state_regulatory.sql
templates/state_regulations.html         # UI page
static/js/state-regulations.js
static/css/state-regulations.css
data/state_requirements/                 # JSON presets
  ca.json
  tx.json
  ny.json
  fl.json
  il.json
```

## Estimated Scope

| Component | Lines | Tasks |
|-----------|-------|-------|
| Models | 200 | 1 |
| Migration | 80 | 1 |
| Service | 350 | 1 |
| API | 300 | 1 |
| Presets (5 states) | 200 | 1 |
| UI Template | 350 | 1 |
| JavaScript | 400 | 1 |
| CSS | 150 | 1 |
| **Total** | **~2,000** | **8** |

## Plan Structure

- **Plan 9-04-01**: Models, Migration, Service (core backend)
- **Plan 9-04-02**: API Blueprint, State Presets (data layer)
- **Plan 9-04-03**: UI Template, JavaScript, CSS (frontend)
