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


def send_verification_email(user, verify_url: str) -> bool:
    """
    Send account verification email with secure activation link.
    """
    if not user or not user.email:
        return False

    subject = f"Verify Your Account — {current_app.config.get('APP_NAME', 'EBT System')}"
    body = f"""Hello {user.username},

Thank you for registering on {current_app.config.get('APP_NAME', 'EBT System')}.

Please verify and activate your account by clicking the link below:
{verify_url}

This verification link will expire in 24 hours.

If you did not register for this account, please ignore this email.

Regards,
Security & Identity Team
{current_app.config.get('APP_NAME', 'EBT System')}
"""
    msg = Message(subject=subject, recipients=[user.email], body=body)
    try:
        mail.send(msg)
        return True
    except Exception as exc:
        logger.warning("Failed to send verification email to %s: %s", user.email, exc)
        return False


def send_password_reset_email(user, reset_url: str) -> bool:
    """
    Send password reset instructions with secure time-limited token link.
    """
    if not user or not user.email:
        return False

    subject = f"Password Reset Request — {current_app.config.get('APP_NAME', 'EBT System')}"
    body = f"""Hello {user.username},

We received a request to reset the password for your account on {current_app.config.get('APP_NAME', 'EBT System')}.

To choose a new password, click the link below:
{reset_url}

This link is valid for 1 hour. If you did not make this request, you can safely ignore this email and your password will remain unchanged.

Regards,
Security Team
{current_app.config.get('APP_NAME', 'EBT System')}
"""
    msg = Message(subject=subject, recipients=[user.email], body=body)
    try:
        mail.send(msg)
        return True
    except Exception as exc:
        logger.warning("Failed to send password reset email to %s: %s", user.email, exc)
        return False


def send_otp_email(user, otp_code: str) -> bool:
    """
    Send 2-Factor Authentication OTP code to user's registered email.
    """
    if not user or not user.email:
        return False

    subject = f"Your Login Verification Code: {otp_code} — {current_app.config.get('APP_NAME', 'EBT System')}"
    body = f"""Hello {user.username},

Your two-step verification code for signing in to {current_app.config.get('APP_NAME', 'EBT System')} is:

    {otp_code}

This one-time passcode is valid for 10 minutes. Do not share this code with anyone.

If you did not attempt to sign in, please secure your account immediately.

Regards,
Security & Identity Team
{current_app.config.get('APP_NAME', 'EBT System')}
"""
    msg = Message(subject=subject, recipients=[user.email], body=body)
    try:
        mail.send(msg)
        return True
    except Exception as exc:
        logger.warning("Failed to send OTP email to %s: %s", user.email, exc)
        return False

