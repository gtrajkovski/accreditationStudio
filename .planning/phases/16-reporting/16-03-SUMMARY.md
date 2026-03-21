---
phase: 16-reporting
plan: 03
subsystem: reporting
tags: [scheduling, email, automation, apscheduler, flask-mail]
dependency_graph:
  requires:
    - "16-01 (ReportService, PDFExporter)"
    - "16-02 (Dashboard UI)"
  provides:
    - "SchedulerService (cron job management)"
    - "EmailService (report delivery)"
    - "Schedule management API (8 endpoints)"
    - "Schedule management UI"
  affects:
    - "app.py (service initialization)"
    - "reports_bp (scheduling endpoints)"
tech_stack:
  added:
    - "Flask-Mail 0.10.0"
    - "Flask-APScheduler 1.13.0"
    - "SQLAlchemyJobStore"
  patterns:
    - "Cron-based scheduling (daily/weekly/monthly)"
    - "Email attachments with PDF reports"
    - "Delivery logging for audit trail"
    - "Job persistence via SQLite"
key_files:
  created:
    - "src/services/email_service.py (87 lines)"
    - "src/services/scheduler_service.py (302 lines)"
    - "src/db/migrations/0027_scheduled_reports.sql (37 lines)"
  modified:
    - "requirements.txt (+2 dependencies)"
    - "src/config.py (+6 email settings)"
    - "src/api/reports.py (+358 lines, 8 endpoints)"
    - "app.py (+5 lines, service init)"
    - "templates/pages/reports.html (+102 lines, modal + table)"
    - "static/js/reports.js (+311 lines, schedule management)"
    - "src/i18n/en-US.json (+29 keys)"
    - "src/i18n/es-PR.json (+29 keys)"
decisions:
  - decision: "Use Flask-APScheduler with SQLAlchemyJobStore"
    rationale: "Provides persistent job storage in SQLite, survives app restarts, integrates cleanly with Flask lifecycle"
    alternatives: ["Celery (too heavy)", "cron (no programmatic control)", "threading.Timer (not persistent)"]
  - decision: "Separate email_delivery_log table for audit trail"
    rationale: "Tracks every send attempt (success/failure) independently from schedule execution, supports compliance reporting on notification delivery"
    alternatives: ["Store in schedule last_status only (loses history)", "External logging service (added complexity)"]
  - decision: "Day 1-28 for monthly schedules"
    rationale: "Avoids edge cases with short months (Feb 29, April 31), ensures schedule always runs on target day"
    alternatives: ["Support 1-31 with fallback logic", "Use last day of month"]
  - decision: "Modal-based schedule creation (not inline form)"
    rationale: "Conditional fields (day_of_week, day_of_month) fit better in modal, reduces clutter in main UI"
    alternatives: ["Inline form with show/hide", "Separate page"]
metrics:
  duration_minutes: 9.4
  completed_at: "2026-03-21T15:33:31Z"
  task_count: 3
  files_modified: 10
  lines_added: 1220
  commits: 3
---

# Phase 16 Plan 03: Scheduled Report Delivery Summary

**One-liner:** Automated compliance report generation with cron scheduling and email delivery using Flask-APScheduler and Flask-Mail.

## What Was Built

### 1. Email Service (`src/services/email_service.py`)
- Flask-Mail integration with SMTP configuration (Gmail defaults)
- `EmailService.send_report_email()`: Sends PDF as attachment
- `EmailService.log_delivery()`: Logs every send attempt to `email_delivery_log` table
- `init_mail(app)`: Configures mail service from Config class

### 2. Scheduler Service (`src/services/scheduler_service.py`)
- Flask-APScheduler with SQLAlchemyJobStore (persists jobs in SQLite)
- `schedule_report()`: Creates schedule record + APScheduler cron job
- `_execute_scheduled_report()`: Background job executor (generate PDF → email → log)
- `pause_schedule()`, `resume_schedule()`, `remove_schedule()`: Job lifecycle management
- `list_schedules()`, `get_schedule()`, `get_delivery_logs()`: Query helpers
- `_load_existing_schedules()`: Restores enabled schedules on app startup

### 3. Database Migration (`0027_scheduled_reports.sql`)
- `report_schedules` table: Stores schedule configuration (type, hour, day_of_week, day_of_month, recipients JSON, enabled, last_run_at, last_status, last_error)
- `email_delivery_log` table: Audit trail for every email send attempt (status, error_message, sent_at)
- Indexes on `institution_id`, `enabled`, `schedule_id`, `status`

### 4. API Endpoints (`src/api/reports.py`)
Added 8 scheduling endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/reports/schedules` | POST | Create schedule (validates email, schedule type, timing) |
| `/api/reports/schedules?institution_id=X` | GET | List schedules for institution |
| `/api/reports/schedules/<id>` | GET | Get single schedule details |
| `/api/reports/schedules/<id>` | PATCH | Update schedule (recipients, hour, enabled) |
| `/api/reports/schedules/<id>/pause` | POST | Pause schedule (sets enabled=0, pauses job) |
| `/api/reports/schedules/<id>/resume` | POST | Resume schedule (sets enabled=1, resumes job) |
| `/api/reports/schedules/<id>` | DELETE | Delete schedule and remove job |
| `/api/reports/schedules/<id>/logs` | GET | Get email delivery logs for schedule |

**Validation:**
- Email regex validation (`validate_email_list()`)
- Schedule type: `daily`, `weekly`, `monthly`
- Hour: 0-23
- Day of week: 0-6 (Monday-Sunday)
- Day of month: 1-28 (avoids end-of-month issues)

### 5. UI Components (`templates/pages/reports.html`, `static/js/reports.js`)

**Scheduled Reports Section:**
- Table with columns: Schedule Type, Time, Recipients, Last Run, Status, Actions
- Empty state with clock icon: "No scheduled reports yet"
- "New Schedule" button opens modal

**Schedule Modal:**
- Form fields: Schedule Type (dropdown), Hour (0-23 input), Recipients (comma-separated emails)
- Conditional fields: Day of Week (shown for weekly), Day of Month (shown for monthly)
- Help text for each field (24-hour format, comma-separated emails, day 1-28)
- Cancel/Save buttons

**Schedule Management:**
- Status badges: Active (green), Paused (gray), Failed (red)
- Action buttons: Pause/Resume (toggle based on state), Delete (with confirmation)
- Recipients display: First email + "+N" with full list in tooltip

**JavaScript Methods:**
- `loadSchedules()`: Fetch and display schedules
- `createSchedule(formData)`: POST new schedule, refresh table
- `pauseSchedule(id)`, `resumeSchedule(id)`, `deleteSchedule(id)`: API calls with toast feedback
- `showScheduleModal()`, `closeScheduleModal()`: Modal visibility
- `formatScheduleDescription()`: "Daily", "Weekly on Monday", "Monthly on day 15"
- Schedule type change handler: Shows/hides conditional fields

### 6. Configuration (`src/config.py`)
Added 6 email settings with environment variable defaults:
- `MAIL_SERVER` (default: smtp.gmail.com)
- `MAIL_PORT` (default: 587)
- `MAIL_USE_TLS` (default: true)
- `MAIL_USERNAME`, `MAIL_PASSWORD` (default: empty)
- `MAIL_DEFAULT_SENDER` (default: noreply@accreditai.local)

### 7. Internationalization
Added 29 i18n keys to `en-US.json` and `es-PR.json`:
- `scheduled_reports`, `new_schedule`, `create_schedule`, `save_schedule`
- `schedule_type`, `daily`, `weekly`, `monthly`
- `time`, `hour`, `hour_help`
- `day_of_week`, `day_of_month`, `day_of_month_help`
- `monday`-`sunday` (day names)
- `recipients`, `recipients_help`, `last_run`, `actions`
- `pause`, `resume`, `enabled`, `disabled`, `success`, `failed`
- `confirm_delete_schedule`, `no_schedules`

## Deviations from Plan

None - plan executed exactly as written.

## Technical Decisions

### APScheduler vs Celery
**Chosen:** Flask-APScheduler with SQLAlchemyJobStore

**Why:**
- Lightweight (no broker required)
- Jobs persist in existing SQLite database
- Native Flask integration (`init_app()` pattern)
- Sufficient for scheduled report generation (not high-throughput queue processing)

### Email Delivery Logging
**Implemented:** Separate `email_delivery_log` table with full audit trail

**Why:**
- Compliance requirement: Must prove reports were delivered
- Supports debugging (error_message column)
- Allows querying delivery history per schedule
- Doesn't pollute `report_schedules` table with historical data

### Day 1-28 for Monthly Schedules
**Restriction:** Monthly schedules only allow day 1-28, not 29-31

**Why:**
- Avoids edge cases: February 29 (leap years), April 31 (doesn't exist)
- Simple validation (no "last day of month" logic)
- Clear UX (form help text explains restriction)

### Modal-based Schedule Creation
**Chosen:** Modal dialog with conditional fields

**Why:**
- Day-of-week and day-of-month fields are mutually exclusive
- Modal keeps main page clean (no always-visible empty form)
- Standard pattern for creation workflows in existing UI

## Verification Steps

To test scheduled report generation:

1. **Start Flask app:** `python app.py`
2. **Navigate to Reports page** (with institution selected)
3. **Create a schedule:**
   - Click "New Schedule"
   - Select "Daily" schedule
   - Set hour (e.g., 9)
   - Enter email: `test@example.com`
   - Click "Save Schedule"
4. **Verify schedule appears** in table with "Active" status
5. **Pause schedule:** Click pause icon, verify status changes to "Paused"
6. **Resume schedule:** Click resume icon, verify status returns to "Active"
7. **Delete schedule:** Click delete icon, confirm, verify removal

**Note:** Email delivery requires valid SMTP configuration in `.env`:
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@accreditai.local
```

For Gmail, generate an App Password (not account password) if 2FA is enabled.

## Integration Points

**Requires:**
- `ReportService.generate_compliance_report_data()` (from 16-01)
- `PDFExporter.generate_compliance_report()` (from 16-01)
- Institution ID (from dashboard context)

**Provides:**
- Scheduled report generation (accessible via `/api/reports/schedules`)
- Email delivery service (reusable for future features)
- Delivery audit trail (queryable via `/api/reports/schedules/<id>/logs`)

**Future Extensions:**
- Add more schedule types: bi-weekly, quarterly, yearly
- Support multiple report types (compliance, faculty, exhibits)
- Email template customization (HTML body with institution branding)
- Delivery retry logic with exponential backoff
- Admin dashboard for all schedules across institutions

## Commits

1. **fab34c1** - `feat(16-03): create email and scheduler services with database migration`
   - Added Flask-Mail and Flask-APScheduler dependencies
   - Created EmailService and SchedulerService
   - Created migration 0027_scheduled_reports.sql

2. **cca033c** - `feat(16-03): add scheduling API endpoints and initialize services in app`
   - 8 scheduling endpoints with validation
   - Email regex validation helper
   - Initialized mail and scheduler services in app.py

3. **227da60** - `feat(16-03): add scheduling UI to reports page`
   - Schedule modal with conditional fields
   - Schedule table with status badges and actions
   - JavaScript schedule management methods
   - Full i18n support (29 keys)

## Self-Check: PASSED

**Files verified:**
- [x] `src/services/email_service.py` exists
- [x] `src/services/scheduler_service.py` exists
- [x] `src/db/migrations/0027_scheduled_reports.sql` exists
- [x] `src/api/reports.py` contains scheduling endpoints
- [x] `app.py` initializes mail and scheduler services
- [x] `templates/pages/reports.html` contains schedule modal
- [x] `static/js/reports.js` contains schedule management methods
- [x] `src/i18n/en-US.json` contains `scheduled_reports` key
- [x] `src/i18n/es-PR.json` contains `scheduled_reports` key

**Commits verified:**
- [x] fab34c1 exists
- [x] cca033c exists
- [x] 227da60 exists
