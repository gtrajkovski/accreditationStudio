-- Phase 10: Timeline Planner
-- Migration for accreditation timeline management with Gantt visualization

-- Accreditation timelines (parent container)
CREATE TABLE IF NOT EXISTS accreditation_timelines (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    accreditor_code TEXT,
    process_type TEXT NOT NULL DEFAULT 'initial',
    target_date TEXT NOT NULL,
    start_date TEXT,
    status TEXT DEFAULT 'planning',
    progress_percentage INTEGER DEFAULT 0,
    created_from_template TEXT,
    color_code TEXT DEFAULT '#c9a84c',
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_timeline_institution
    ON accreditation_timelines(institution_id);
CREATE INDEX IF NOT EXISTS idx_timeline_status
    ON accreditation_timelines(status);
CREATE INDEX IF NOT EXISTS idx_timeline_target_date
    ON accreditation_timelines(target_date);

-- Timeline phases (groupings within a timeline)
CREATE TABLE IF NOT EXISTS timeline_phases (
    id TEXT PRIMARY KEY,
    timeline_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    phase_order INTEGER NOT NULL,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'pending',
    progress_percentage INTEGER DEFAULT 0,
    color_code TEXT,
    collapsed INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (timeline_id) REFERENCES accreditation_timelines(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_phase_timeline
    ON timeline_phases(timeline_id);
CREATE INDEX IF NOT EXISTS idx_phase_order
    ON timeline_phases(timeline_id, phase_order);

-- Timeline milestones (individual tasks within phases)
CREATE TABLE IF NOT EXISTS timeline_milestones (
    id TEXT PRIMARY KEY,
    timeline_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    milestone_order INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    start_date TEXT,
    status TEXT DEFAULT 'pending',
    priority TEXT DEFAULT 'normal',
    assigned_to TEXT,
    completion_percentage INTEGER DEFAULT 0,
    completed_at TEXT,
    depends_on TEXT,
    blocks TEXT,
    linked_calendar_event_id TEXT,
    linked_action_item_id TEXT,
    linked_document_ids TEXT,
    notes TEXT,
    checklist TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (timeline_id) REFERENCES accreditation_timelines(id) ON DELETE CASCADE,
    FOREIGN KEY (phase_id) REFERENCES timeline_phases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_milestone_timeline
    ON timeline_milestones(timeline_id);
CREATE INDEX IF NOT EXISTS idx_milestone_phase
    ON timeline_milestones(phase_id);
CREATE INDEX IF NOT EXISTS idx_milestone_due_date
    ON timeline_milestones(due_date);
CREATE INDEX IF NOT EXISTS idx_milestone_status
    ON timeline_milestones(status);

-- Timeline templates (reusable starting points)
CREATE TABLE IF NOT EXISTS timeline_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    accreditor_code TEXT,
    process_type TEXT NOT NULL,
    description TEXT,
    default_duration_days INTEGER DEFAULT 365,
    phases TEXT NOT NULL,
    milestones TEXT NOT NULL,
    is_system_template INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_template_accreditor
    ON timeline_templates(accreditor_code);
CREATE INDEX IF NOT EXISTS idx_template_process
    ON timeline_templates(process_type);

-- Seed system templates
INSERT OR IGNORE INTO timeline_templates (id, name, accreditor_code, process_type, description, default_duration_days, phases, milestones, is_system_template, created_at)
VALUES
(
    'tmpl_accsc_initial',
    'ACCSC Initial Accreditation',
    'ACCSC',
    'initial_accreditation',
    'Standard timeline for ACCSC initial accreditation process',
    365,
    '[{"order":1,"name":"Application Phase","days_before_end":365,"days_before_start":270,"color_code":"#a78bfa"},{"order":2,"name":"Self-Study Phase","days_before_end":270,"days_before_start":120,"color_code":"#60a5fa"},{"order":3,"name":"Site Visit Preparation","days_before_end":120,"days_before_start":30,"color_code":"#34d399"},{"order":4,"name":"Visit & Response","days_before_end":30,"days_before_start":0,"color_code":"#fbbf24"}]',
    '[{"phase_order":1,"order":1,"name":"Submit Application","days_before_target":365,"priority":"high"},{"phase_order":1,"order":2,"name":"Application Fee Payment","days_before_target":360,"priority":"high"},{"phase_order":1,"order":3,"name":"Application Review Complete","days_before_target":300,"priority":"normal"},{"phase_order":2,"order":1,"name":"Appoint Self-Study Committee","days_before_target":270,"priority":"high"},{"phase_order":2,"order":2,"name":"Gather Evidence Documents","days_before_target":210,"priority":"normal"},{"phase_order":2,"order":3,"name":"Draft Self-Study Report","days_before_target":180,"priority":"high"},{"phase_order":2,"order":4,"name":"Internal Review","days_before_target":150,"priority":"normal"},{"phase_order":2,"order":5,"name":"Submit Self-Study","days_before_target":120,"priority":"critical"},{"phase_order":3,"order":1,"name":"Team Chair Assignment","days_before_target":90,"priority":"normal"},{"phase_order":3,"order":2,"name":"Prepare Site Visit Materials","days_before_target":60,"priority":"high"},{"phase_order":3,"order":3,"name":"Staff Briefings","days_before_target":45,"priority":"normal"},{"phase_order":3,"order":4,"name":"Mock Interviews","days_before_target":30,"priority":"normal"},{"phase_order":4,"order":1,"name":"Site Visit","days_before_target":14,"priority":"critical"},{"phase_order":4,"order":2,"name":"Exit Interview","days_before_target":13,"priority":"high"},{"phase_order":4,"order":3,"name":"Team Report Response","days_before_target":0,"priority":"critical"}]',
    1,
    datetime('now')
),
(
    'tmpl_accsc_reaffirm',
    'ACCSC Reaffirmation',
    'ACCSC',
    'reaffirmation',
    'Standard timeline for ACCSC reaffirmation of accreditation',
    540,
    '[{"order":1,"name":"Planning Phase","days_before_end":540,"days_before_start":420,"color_code":"#a78bfa"},{"order":2,"name":"Self-Study Development","days_before_end":420,"days_before_start":180,"color_code":"#60a5fa"},{"order":3,"name":"Evidence Assembly","days_before_end":180,"days_before_start":90,"color_code":"#f472b6"},{"order":4,"name":"Site Visit Preparation","days_before_end":90,"days_before_start":30,"color_code":"#34d399"},{"order":5,"name":"Visit & Response","days_before_end":30,"days_before_start":0,"color_code":"#fbbf24"}]',
    '[{"phase_order":1,"order":1,"name":"Notification of Reaffirmation Cycle","days_before_target":540,"priority":"normal"},{"phase_order":1,"order":2,"name":"Form Self-Study Committee","days_before_target":500,"priority":"high"},{"phase_order":1,"order":3,"name":"Review Standards Changes","days_before_target":450,"priority":"normal"},{"phase_order":2,"order":1,"name":"Assign Section Writers","days_before_target":420,"priority":"high"},{"phase_order":2,"order":2,"name":"First Draft Complete","days_before_target":300,"priority":"high"},{"phase_order":2,"order":3,"name":"Internal Review Cycle","days_before_target":240,"priority":"normal"},{"phase_order":2,"order":4,"name":"Final Draft Complete","days_before_target":180,"priority":"critical"},{"phase_order":3,"order":1,"name":"Compile Evidence Appendices","days_before_target":150,"priority":"high"},{"phase_order":3,"order":2,"name":"Quality Check Evidence","days_before_target":120,"priority":"normal"},{"phase_order":3,"order":3,"name":"Submit Self-Study Package","days_before_target":90,"priority":"critical"},{"phase_order":4,"order":1,"name":"Coordinate Visit Logistics","days_before_target":60,"priority":"high"},{"phase_order":4,"order":2,"name":"Prepare Interview Teams","days_before_target":45,"priority":"normal"},{"phase_order":4,"order":3,"name":"Final Readiness Check","days_before_target":14,"priority":"high"},{"phase_order":5,"order":1,"name":"Site Visit","days_before_target":7,"priority":"critical"},{"phase_order":5,"order":2,"name":"Response to Team Report","days_before_target":0,"priority":"critical"}]',
    1,
    datetime('now')
),
(
    'tmpl_substantive_change',
    'Substantive Change',
    NULL,
    'substantive_change',
    'Timeline for substantive change notification and approval',
    180,
    '[{"order":1,"name":"Preparation","days_before_end":180,"days_before_start":90,"color_code":"#60a5fa"},{"order":2,"name":"Submission","days_before_end":90,"days_before_start":30,"color_code":"#34d399"},{"order":3,"name":"Review & Approval","days_before_end":30,"days_before_start":0,"color_code":"#fbbf24"}]',
    '[{"phase_order":1,"order":1,"name":"Identify Change Type","days_before_target":180,"priority":"high"},{"phase_order":1,"order":2,"name":"Draft Change Documentation","days_before_target":150,"priority":"normal"},{"phase_order":1,"order":3,"name":"Internal Approval","days_before_target":120,"priority":"high"},{"phase_order":1,"order":4,"name":"Prepare Supporting Evidence","days_before_target":90,"priority":"normal"},{"phase_order":2,"order":1,"name":"Submit Application","days_before_target":75,"priority":"critical"},{"phase_order":2,"order":2,"name":"Pay Applicable Fees","days_before_target":70,"priority":"high"},{"phase_order":2,"order":3,"name":"Respond to Questions","days_before_target":45,"priority":"normal"},{"phase_order":3,"order":1,"name":"Commission Review","days_before_target":30,"priority":"normal"},{"phase_order":3,"order":2,"name":"Address Conditions","days_before_target":14,"priority":"high"},{"phase_order":3,"order":3,"name":"Receive Approval","days_before_target":0,"priority":"critical"}]',
    1,
    datetime('now')
),
(
    'tmpl_team_response',
    'Team Visit Response',
    NULL,
    'team_visit_response',
    'Timeline for responding to team visit findings',
    60,
    '[{"order":1,"name":"Analysis","days_before_end":60,"days_before_start":40,"color_code":"#ef4444"},{"order":2,"name":"Response Development","days_before_end":40,"days_before_start":14,"color_code":"#f472b6"},{"order":3,"name":"Finalization","days_before_end":14,"days_before_start":0,"color_code":"#34d399"}]',
    '[{"phase_order":1,"order":1,"name":"Receive Team Report","days_before_target":60,"priority":"critical"},{"phase_order":1,"order":2,"name":"Categorize Findings","days_before_target":55,"priority":"high"},{"phase_order":1,"order":3,"name":"Assign Response Owners","days_before_target":50,"priority":"high"},{"phase_order":1,"order":4,"name":"Gather Evidence","days_before_target":40,"priority":"normal"},{"phase_order":2,"order":1,"name":"Draft Individual Responses","days_before_target":35,"priority":"high"},{"phase_order":2,"order":2,"name":"Internal Review","days_before_target":25,"priority":"normal"},{"phase_order":2,"order":3,"name":"Compile Supporting Documents","days_before_target":20,"priority":"normal"},{"phase_order":2,"order":4,"name":"Legal/Compliance Review","days_before_target":14,"priority":"high"},{"phase_order":3,"order":1,"name":"Final Editing","days_before_target":10,"priority":"high"},{"phase_order":3,"order":2,"name":"Executive Approval","days_before_target":7,"priority":"critical"},{"phase_order":3,"order":3,"name":"Submit Response Package","days_before_target":0,"priority":"critical"}]',
    1,
    datetime('now')
);
