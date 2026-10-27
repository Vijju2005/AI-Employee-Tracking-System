"""
EBT System — Email Notification Services
Provides safe email dispatch for leave review workflows (approval/rejection)
using Flask-Mail. Reads SMTP configuration from environment variables.
"""

import logging
from flask import current_app
from flask_mail import Message
from app.extensions import mail

logger = logging.getLogger(__name__)


def send_leave_status_email(leave_request) -> bool:
    """
    Send an email notification to the employee when their leave request
    is approved or rejected.
    
    Safe by default:
    - If employee has no email, skips gracefully.
    - If mail is suppressed (MAIL_SUPPRESS_SEND=True, the default in dev/test),
      it does not attempt socket connections.
    - Catches all transport exceptions so user operations never fail due to email downtime.
    """
    if not leave_request or not leave_request.employee or not leave_request.employee.email:
        logger.info("Leave status email skipped: no recipient email found.")
        return False

    recipient = leave_request.employee.email
    emp_name = leave_request.employee.full_name
    status_text = leave_request.status.value if hasattr(leave_request.status, "value") else str(leave_request.status)
    leave_type = leave_request.leave_type.value if hasattr(leave_request.leave_type, "value") else str(leave_request.leave_type)
    
    subject = f"Leave Request Update: {status_text} - {current_app.config.get('APP_NAME', 'EBT System')}"
    
    body = f"""Hello {emp_name},

Your leave request for {leave_type} leave from {leave_request.start_date} to {leave_request.end_date} has been {status_text.upper()}.

Status: {status_text}
Reviewed Date: {leave_request.reviewed_at or 'N/A'}
Admin Notes: {leave_request.admin_notes or 'None'}

Please log into your employee portal to view updated leave records.

Regards,
HR Management Team
{current_app.config.get('APP_NAME', 'EBT System')}
"""

    msg = Message(
        subject=subject,
        recipients=[recipient],
        body=body,
    )

    try:
        mail.send(msg)
        logger.info("Leave status notification sent to %s for leave ID %s", recipient, leave_request.id)
        return True
    except Exception as exc:
        logger.warning("Failed to send leave status email to %s: %s", recipient, exc)
        return False
