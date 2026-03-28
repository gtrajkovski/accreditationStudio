"""Scheduler Service for automated report generation.

Uses Flask-APScheduler to manage scheduled report jobs.
"""

import json
import logging
from datetime import datetime
from uuid import uuid4
from flask_apscheduler import APScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from src.config import Config
from src.db.connection import get_conn, get_db_path
from src.services.report_service import ReportService
from src.services.email_service import EmailService
# PDFExporter imported lazily to avoid WeasyPrint/GTK at startup

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = APScheduler()


def get_scheduler():
    """Get the scheduler instance."""
    return scheduler


def init_scheduler(app):
    """Initialize APScheduler with Flask app.

    Args:
        app: Flask application instance
    """
    db_path = get_db_path()
    app.config['SCHEDULER_JOBSTORES'] = {
        'default': SQLAlchemyJobStore(url=f'sqlite:///{db_path}')
    }
    app.config['SCHEDULER_API_ENABLED'] = False
    scheduler.init_app(app)
    scheduler.start()
    logger.info("Scheduler service initialized")

    # Load existing enabled schedules
    _load_existing_schedules()


def _load_existing_schedules():
    """Load enabled schedules from database on startup."""
    conn = get_conn()
    schedules = conn.execute("SELECT * FROM report_schedules WHERE enabled = 1").fetchall()

    for sched in schedules:
        try:
            _add_job_from_schedule(dict(sched))
            logger.info(f"Loaded schedule: {sched['id']}")
        except Exception as e:
            logger.error(f"Failed to load schedule {sched['id']}: {e}")


def schedule_report(institution_id, report_type, schedule_type, hour, recipients, day_of_week=None, day_of_month=None):
    """Create new scheduled report.

    Args:
        institution_id: Institution ID
        report_type: Type of report (e.g., 'compliance')
        schedule_type: 'daily', 'weekly', or 'monthly'
        hour: Hour of day to run (0-23)
        recipients: List of email addresses
        day_of_week: Day of week for weekly schedules (0=Monday, 6=Sunday)
        day_of_month: Day of month for monthly schedules (1-31)

    Returns:
        Schedule ID
    """
    schedule_id = f"rs_{uuid4().hex[:12]}"
    conn = get_conn()

    conn.execute(
        """
        INSERT INTO report_schedules (id, institution_id, report_type, schedule_type, schedule_hour, schedule_day_of_week, schedule_day_of_month, recipients)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (schedule_id, institution_id, report_type, schedule_type, hour, day_of_week, day_of_month, json.dumps(recipients))
    )
    conn.commit()

    # Add job to scheduler
    _add_job_from_schedule({
        'id': schedule_id,
        'institution_id': institution_id,
        'report_type': report_type,
        'schedule_type': schedule_type,
        'schedule_hour': hour,
        'schedule_day_of_week': day_of_week,
        'schedule_day_of_month': day_of_month,
        'recipients': json.dumps(recipients)
    })

    logger.info(f"Created schedule: {schedule_id} ({schedule_type} at {hour}:00)")
    return schedule_id


def _add_job_from_schedule(sched):
    """Add APScheduler job from schedule dict.

    Args:
        sched: Schedule dict with keys: id, institution_id, report_type, schedule_type, schedule_hour, etc.
    """
    trigger_kwargs = {'hour': sched['schedule_hour'], 'minute': 0}

    if sched['schedule_type'] == 'weekly':
        trigger_kwargs['day_of_week'] = sched['schedule_day_of_week'] or 0
    elif sched['schedule_type'] == 'monthly':
        trigger_kwargs['day'] = sched['schedule_day_of_month'] or 1

    recipients = json.loads(sched['recipients'])

    scheduler.add_job(
        id=sched['id'],
        func=_execute_scheduled_report,
        trigger='cron',
        args=[sched['id'], sched['institution_id'], sched['report_type'], recipients],
        replace_existing=True,
        **trigger_kwargs
    )


def _execute_scheduled_report(schedule_id, institution_id, report_type, recipients):
    """Background job to generate and email report.

    Args:
        schedule_id: Schedule ID
        institution_id: Institution ID
        report_type: Type of report
        recipients: List of email addresses
    """
    # Lazy import to avoid WeasyPrint/GTK dependency at app startup
    from src.exporters.pdf_exporter import PDFExporter

    conn = get_conn()

    try:
        logger.info(f"Executing scheduled report: {schedule_id}")

        # Generate report
        report_service = ReportService()
        data = report_service.generate_compliance_report_data(institution_id)
        pdf_bytes = PDFExporter().generate_compliance_report(data)
        report_id = report_service.save_report_metadata(
            institution_id,
            report_type,
            f"Scheduled {report_type} report",
            None,
            len(pdf_bytes),
            generated_by="scheduler"
        )

        # Send email
        email_service = EmailService()
        filename = f"compliance_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        subject = f"AccreditAI: {report_type.title()} Report - {data['institution']['name']}"
        body = f"Please find attached your scheduled {report_type} report generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

        email_service.send_report_email(
            recipients=recipients,
            subject=subject,
            body=body,
            pdf_bytes=pdf_bytes,
            filename=filename
        )
        email_service.log_delivery(schedule_id, report_id, recipients, f"{report_type} Report", 'sent')

        # Update schedule
        conn.execute(
            "UPDATE report_schedules SET last_run_at = datetime('now'), last_status = 'success', last_error = NULL WHERE id = ?",
            (schedule_id,)
        )
        conn.commit()

        logger.info(f"Scheduled report completed: {schedule_id}")

    except Exception as e:
        logger.error(f"Scheduled report failed: {schedule_id}: {e}")
        conn.execute(
            "UPDATE report_schedules SET last_run_at = datetime('now'), last_status = 'failed', last_error = ? WHERE id = ?",
            (str(e), schedule_id)
        )
        conn.commit()

        # Log failure
        EmailService().log_delivery(schedule_id, None, recipients, f"{report_type} Report", 'failed', str(e))


def pause_schedule(schedule_id):
    """Pause a schedule (disable and pause job).

    Args:
        schedule_id: Schedule ID
    """
    scheduler.pause_job(schedule_id)
    conn = get_conn()
    conn.execute(
        "UPDATE report_schedules SET enabled = 0, updated_at = datetime('now') WHERE id = ?",
        (schedule_id,)
    )
    conn.commit()
    logger.info(f"Paused schedule: {schedule_id}")


def resume_schedule(schedule_id):
    """Resume a paused schedule.

    Args:
        schedule_id: Schedule ID
    """
    scheduler.resume_job(schedule_id)
    conn = get_conn()
    conn.execute(
        "UPDATE report_schedules SET enabled = 1, updated_at = datetime('now') WHERE id = ?",
        (schedule_id,)
    )
    conn.commit()
    logger.info(f"Resumed schedule: {schedule_id}")


def remove_schedule(schedule_id):
    """Delete a schedule and remove its job.

    Args:
        schedule_id: Schedule ID
    """
    try:
        scheduler.remove_job(schedule_id)
    except Exception as e:
        logger.warning(f"Failed to remove scheduler job {schedule_id}: {e}")

    conn = get_conn()
    conn.execute("DELETE FROM report_schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    logger.info(f"Removed schedule: {schedule_id}")


def list_schedules(institution_id):
    """List all schedules for an institution.

    Args:
        institution_id: Institution ID

    Returns:
        List of schedule dicts
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM report_schedules WHERE institution_id = ? ORDER BY created_at DESC",
        (institution_id,)
    ).fetchall()

    schedules = []
    for row in rows:
        sched = dict(row)
        if sched.get('recipients'):
            sched['recipients'] = json.loads(sched['recipients'])
        schedules.append(sched)

    return schedules


def get_schedule(schedule_id):
    """Get a single schedule by ID.

    Args:
        schedule_id: Schedule ID

    Returns:
        Schedule dict or None
    """
    conn = get_conn()
    row = conn.execute("SELECT * FROM report_schedules WHERE id = ?", (schedule_id,)).fetchone()

    if not row:
        return None

    sched = dict(row)
    if sched.get('recipients'):
        sched['recipients'] = json.loads(sched['recipients'])

    return sched


def get_delivery_logs(schedule_id, limit=20):
    """Get email delivery logs for a schedule.

    Args:
        schedule_id: Schedule ID
        limit: Maximum number of logs to return

    Returns:
        List of log dicts
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM email_delivery_log WHERE schedule_id = ? ORDER BY sent_at DESC LIMIT ?",
        (schedule_id, limit)
    ).fetchall()

    logs = []
    for row in rows:
        log = dict(row)
        if log.get('recipients'):
            log['recipients'] = json.loads(log['recipients'])
        logs.append(log)

    return logs
