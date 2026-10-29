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
    """Self-service employee registration."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    error = None
    form_data = None

    if request.method == "POST":
        username    = request.form.get("username", "").strip()
        full_name   = request.form.get("full_name", "").strip()
        email       = request.form.get("email", "").strip().lower()
        password    = request.form.get("password", "")
        confirm     = request.form.get("confirm_password", "")

        # Preserve entered values so user doesn't retype everything on error
        form_data = {"username": username, "full_name": full_name, "email": email}

        if not all([username, full_name, email, password, confirm]):
            error = "All fields are required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken. Please choose another."
        elif User.query.filter_by(email=email).first():
            error = "An account with that email already exists."
        else:
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
            db.session.add(new_user)
            db.session.flush()   # get new_user.id before commit

            # Generate a sequential employee ID (EMP001, EMP002, …)
            from app.models import Employee
            count      = Employee.query.count() + 1
            emp_id     = f"EMP{count:03d}"
            # Ensure uniqueness in the unlikely event of a collision
            while Employee.query.filter_by(employee_id=emp_id).first():
                count += 1
                emp_id = f"EMP{count:03d}"

            new_emp = Employee(
                employee_id=emp_id,
                full_name=full_name,
                email=email,
                user_id=new_user.id,
            )
            db.session.add(new_emp)
            db.session.commit()

            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html", error=error, form_data=form_data)


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
