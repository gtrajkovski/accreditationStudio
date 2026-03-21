"""Email Service for scheduled report delivery.

Uses Flask-Mail to send compliance reports via email.
"""

import json
import logging
from uuid import uuid4
from flask_mail import Mail, Message

from src.config import Config
from src.db.connection import get_conn

logger = logging.getLogger(__name__)

# Global mail instance
mail = Mail()


def init_mail(app):
    """Initialize Flask-Mail with app configuration.

    Args:
        app: Flask application instance
    """
    app.config['MAIL_SERVER'] = Config.MAIL_SERVER
    app.config['MAIL_PORT'] = Config.MAIL_PORT
    app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
    app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
    app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
    app.config['MAIL_DEFAULT_SENDER'] = Config.MAIL_DEFAULT_SENDER
    mail.init_app(app)
    logger.info(f"Mail service initialized: {Config.MAIL_SERVER}:{Config.MAIL_PORT}")


class EmailService:
    """Service for sending report emails and logging delivery attempts."""

    def send_report_email(self, recipients, subject, body, pdf_bytes, filename):
        """Send email with PDF attachment.

        Args:
            recipients: List of email addresses
            subject: Email subject line
            body: Email body text
            pdf_bytes: PDF file content as bytes
            filename: Attachment filename

        Raises:
            Exception: If email sending fails
        """
        msg = Message(
            subject=subject,
            recipients=recipients,
            body=body
        )
        msg.attach(filename, "application/pdf", pdf_bytes)
        mail.send(msg)
        logger.info(f"Email sent: {subject} to {recipients}")

    def log_delivery(self, schedule_id, report_id, recipients, subject, status, error=None):
        """Log email delivery attempt to database.

        Args:
            schedule_id: Schedule ID that triggered email (or None)
            report_id: Report ID that was sent (or None)
            recipients: List of email addresses
            subject: Email subject
            status: 'sent' or 'failed'
            error: Error message if failed
        """
        conn = get_conn()
        log_id = f"edl_{uuid4().hex[:12]}"

        conn.execute(
            """
            INSERT INTO email_delivery_log (id, schedule_id, report_id, recipients, subject, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, schedule_id, report_id, json.dumps(recipients), subject, status, error)
        )
        conn.commit()
        logger.info(f"Email delivery logged: {log_id} ({status})")
