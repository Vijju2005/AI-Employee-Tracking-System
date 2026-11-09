"""
EBT System — Auth Routes
Comprehensive Authentication Suite:
- Multi-role Login (Super Admin, Admin, Employee) with remember-me
- User Registration with optional Email Verification token dispatch
- Email Verification route
- Forgot Password & Token-based Secure Reset Password
- Two-Step Verification (OTP over Email with 10-minute validity)
- Session Lock Screen & Unlock
- First-run initial administrator setup
"""

import secrets
from datetime import datetime, timedelta, timezone
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session, current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User, UserRole, Employee, AccountStatus
from app.email import (
    send_verification_email,
    send_password_reset_email,
    send_otp_email
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _get_serializer():
    secret = current_app.config.get("SECRET_KEY", "dev-secret-key")
    return URLSafeTimedSerializer(secret)


def _redirect_by_role(user):
    if user.is_superadmin:
        return redirect(url_for("superadmin.dashboard"))
    if user.role == UserRole.ADMIN:
        return redirect(url_for("dashboard.admin_dashboard"))
    return redirect(url_for("dashboard.employee_dashboard"))


# ── Login & 2-Factor OTP ───────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        # Check if session is locked
        if session.get("is_locked"):
            return redirect(url_for("auth.lock_screen"))
        return _redirect_by_role(current_user)

    error = None
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        if not identifier or not password:
            error = "Please enter both username/email and password."
        else:
            user = (
                User.query.filter_by(username=identifier).first()
                or User.query.filter_by(email=identifier).first()
            )
            if user and check_password_hash(user.password_hash, password):
                if not user.is_active:
                    error = "Your account is disabled. Contact an administrator."
                elif hasattr(user, "is_verified") and not user.is_verified:
                    error = "Your email address has not been verified. Please check your inbox or verify your account."
                elif hasattr(user, "two_factor_enabled") and user.two_factor_enabled:
                    # 2-Step Verification required
                    otp = f"{secrets.randbelow(900000) + 100000:06d}"
                    user.otp_code = otp
                    user.otp_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)
                    db.session.commit()

                    # Save intermediate auth session
                    session["2fa_user_id"] = user.id
                    session["2fa_remember"] = remember
                    session["2fa_next"] = request.args.get("next")

                    # Dispatch OTP email
                    send_otp_email(user, otp)

                    flash(f"A 6-digit verification code has been sent to {user.email}.", "info")
                    return redirect(url_for("auth.verify_otp"))
                else:
                    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.session.commit()
                    session.pop("is_locked", None)
                    from app.time_utils import get_current_session_cycle_id
                    session["login_cycle_id"] = get_current_session_cycle_id()
                    login_user(user, remember=remember)

                    next_page = request.args.get("next")
                    if next_page and next_page.startswith("/") and not next_page.startswith("//") and not next_page.startswith("/\\"):
                        return redirect(next_page)
                    return _redirect_by_role(user)
            else:
                error = "Invalid username/email or password."

    return render_template("auth/login.html", error=error)


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """Verify 2-Factor Authentication OTP code."""
    user_id = session.get("2fa_user_id")
    if not user_id:
        flash("Login session expired. Please sign in again.", "warning")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user:
        session.pop("2fa_user_id", None)
        return redirect(url_for("auth.login"))

    error = None
    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if not otp or len(otp) != 6:
            error = "Please enter the complete 6-digit verification code."
        elif not user.otp_code or user.otp_code != otp:
            error = "Invalid verification code. Please try again."
        elif user.otp_expires_at and user.otp_expires_at < now:
            error = "Verification code has expired. Please request a new one."
        else:
            # Code verified successfully
            user.otp_code = None
            user.otp_expires_at = None
            user.last_login = now
            db.session.commit()

            remember = session.pop("2fa_remember", False)
            next_page = session.pop("2fa_next", None)
            session.pop("2fa_user_id", None)
            session.pop("is_locked", None)
            from app.time_utils import get_current_session_cycle_id
            session["login_cycle_id"] = get_current_session_cycle_id()

            login_user(user, remember=remember)
            flash("Two-step verification successful. Welcome back!", "success")

            if next_page and next_page.startswith("/") and not next_page.startswith("//") and not next_page.startswith("/\\"):
                return redirect(next_page)
            return _redirect_by_role(user)

    return render_template("auth/verify_otp.html", user=user, error=error)


@auth_bp.route("/resend-otp")
def resend_otp():
    """Resend a fresh OTP to the user's email."""
    user_id = session.get("2fa_user_id")
    if not user_id:
        flash("Session expired. Please sign in again.", "warning")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for("auth.login"))

    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)
    db.session.commit()

    send_otp_email(user, otp)
    flash(f"A new verification code has been dispatched to {user.email}.", "info")
    return redirect(url_for("auth.verify_otp"))


# ── User Registration & Email Verification ─────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Enterprise self-registration for new platform users.
    Creates user account, auto-generates associated Employee profile,
    and dispatches account verification email.
    Can be toggled via ENABLE_SELF_REGISTRATION config.
    """
    if not current_app.config.get("ENABLE_SELF_REGISTRATION", True):
        flash("Public registration is disabled. Please contact your administrator for your account credentials.", "info")
        return redirect(url_for("auth.login"))

    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    error = None
    form_data = {}

    if request.method == "POST":
        form_data = request.form.to_dict()
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([username, full_name, email, password, confirm_password]):
            error = "All fields are required."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters in length."
        elif User.query.filter_by(username=username).first():
            error = "Username is already taken. Please choose another."
        elif User.query.filter_by(email=email).first() or Employee.query.filter_by(email=email).first():
            error = "An account or employee profile is already registered with this email address."
        else:
            # Auto-generate next employee ID
            last_emp = Employee.query.order_by(Employee.id.desc()).first()
            next_num = 1
            if last_emp and last_emp.employee_id and last_emp.employee_id.startswith("EMP"):
                try:
                    next_num = int(last_emp.employee_id.replace("EMP", "")) + 1
                except ValueError:
                    next_num = (last_emp.id or 1) + 1
            emp_code = f"EMP{next_num:03d}"

            # Create User
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=False,  # pending email verification
                two_factor_enabled=False,
            )
            db.session.add(new_user)
            db.session.flush()

            # Create Employee Record
            new_emp = Employee(
                employee_id=emp_code,
                full_name=full_name,
                email=email,
                company_name="EBT Enterprise",
                designation="Team Member",
                status=AccountStatus.ACTIVE,
                user_id=new_user.id,
            )
            db.session.add(new_emp)
            db.session.commit()

            # Generate Verification Token
            s = _get_serializer()
            token = s.dumps({"user_id": new_user.id}, salt="email-verification")
            verify_url = url_for("auth.verify_email", token=token, _external=True)

            send_verification_email(new_user, verify_url)

            flash(
                "Account created successfully! We sent a verification email with an activation link. "
                "You can also log in once verified.",
                "success"
            )
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html", error=error, form_data=form_data)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    """Activates account when user clicks verification link in email."""
    s = _get_serializer()
    try:
        data = s.loads(token, salt="email-verification", max_age=86400)  # 24 hours
        user_id = data.get("user_id")
        user = db.session.get(User, user_id)
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("auth.login"))

        if user.is_verified:
            flash("Your email is already verified. Please sign in.", "info")
            return redirect(url_for("auth.login"))

        user.is_verified = True
        db.session.commit()
        flash("Email successfully verified! Your account is active. Please log in.", "success")
        return redirect(url_for("auth.login"))
    except SignatureExpired:
        flash("Verification link has expired. Please request a new activation email or log in.", "warning")
        return redirect(url_for("auth.login"))
    except BadSignature:
        flash("Invalid verification link token.", "danger")
        return redirect(url_for("auth.login"))


# ── Forgot & Reset Password ────────────────────────────────────────────────────

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Form to initiate password recovery via email."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            error = "Please enter your registered email address."
        else:
            user = User.query.filter_by(email=email).first()
            if user:
                s = _get_serializer()
                token = s.dumps({"user_id": user.id}, salt="password-reset")
                reset_url = url_for("auth.reset_password", token=token, _external=True)
                send_password_reset_email(user, reset_url)

            # Generic success message for privacy/anti-enumeration
            flash(
                "If an account exists with that email address, password reset instructions have been dispatched.",
                "info"
            )
            return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", error=error)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Set a new password using verified reset token."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    s = _get_serializer()
    try:
        data = s.loads(token, salt="password-reset", max_age=3600)  # 1 hour
        user_id = data.get("user_id")
        user = db.session.get(User, user_id)
        if not user:
            flash("User account not found.", "danger")
            return redirect(url_for("auth.login"))
    except SignatureExpired:
        flash("Password reset link has expired. Please submit a new request.", "warning")
        return redirect(url_for("auth.forgot_password"))
    except BadSignature:
        flash("Invalid or corrupted password reset link.", "danger")
        return redirect(url_for("auth.forgot_password"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not password or not confirm:
            error = "Please fill in all password fields."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        else:
            user.password_hash = generate_password_hash(password)
            user.is_verified = True  # reset also validates ownership of email
            db.session.commit()
            flash("Your password has been reset successfully. Please log in with your new credentials.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token, error=error)


# ── Lock Screen ────────────────────────────────────────────────────────────────

@auth_bp.route("/lock", methods=["GET", "POST"])
@login_required
def lock_screen():
    """Puts session in locked state until user re-enters password."""
    session["is_locked"] = True
    error = None

    if request.method == "POST":
        password = request.form.get("password", "")
        if not password:
            error = "Please enter your password to unlock the screen."
        elif check_password_hash(current_user.password_hash, password):
            session.pop("is_locked", None)
            flash("Session unlocked. Welcome back!", "success")
            return _redirect_by_role(current_user)
        else:
            error = "Incorrect password. Please try again."

    return render_template("auth/lock_screen.html", user=current_user, error=error)


@auth_bp.route("/unlock", methods=["POST"])
@login_required
def unlock():
    password = request.form.get("password", "")
    if check_password_hash(current_user.password_hash, password):
        session.pop("is_locked", None)
        flash("Session unlocked.", "success")
        return _redirect_by_role(current_user)
    flash("Incorrect password.", "danger")
    return redirect(url_for("auth.lock_screen"))


# ── Logout & Initial Setup ─────────────────────────────────────────────────────

@auth_bp.route("/logout")
@login_required
def logout():
    session.pop("is_locked", None)
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run: create the initial admin or superadmin account."""
    if User.query.filter(User.role.in_([UserRole.ADMIN, UserRole.SUPERADMIN])).first():
        flash("Admin account already exists. Please log in.", "info")
        return redirect(url_for("auth.login"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not all([username, email, password, confirm]):
            error = "All fields are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken."
        elif User.query.filter_by(email=email).first():
            error = "Email already registered."
        else:
            admin = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.session.add(admin)
            db.session.commit()
            flash("Admin account created. Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/setup.html", error=error)
