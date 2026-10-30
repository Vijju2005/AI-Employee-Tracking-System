"""
EBT System — Auth Routes
Handles login, logout, and first-admin setup.
"""

from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User, UserRole

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
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
                else:
                    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.session.commit()
                    login_user(user, remember=remember)
                    next_page = request.args.get("next")
                    # Safe relative redirection check (prevent open redirects like //evil.com or /\evil.com)
                    if next_page and next_page.startswith("/") and not next_page.startswith("//") and not next_page.startswith("/\\"):
                        return redirect(next_page)
                    return _redirect_by_role(user)
            else:
                error = "Invalid username/email or password."

    return render_template("auth/login.html", error=error)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Public employee self-registration is disabled. Accounts are provisioned by Admin."""
    flash("Public registration is disabled. Please contact your administrator for your account credentials.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run: create the initial admin account."""
    if User.query.filter_by(role=UserRole.ADMIN).first():
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
            )
            db.session.add(admin)
            db.session.commit()
            flash("Admin account created. Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/setup.html", error=error)


def _redirect_by_role(user):
    if user.role == UserRole.ADMIN:
        return redirect(url_for("dashboard.admin_dashboard"))
    return redirect(url_for("dashboard.employee_dashboard"))
