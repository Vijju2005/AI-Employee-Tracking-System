"""
EBT System – Employee Routes (Admin only)
"""

from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Employee, Department, WorkSchedule, User, UserRole, AccountStatus

employees_bp = Blueprint("employees", __name__, url_prefix="/employees")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@employees_bp.route("/")
@login_required
@admin_required
def list_employees():
    q = request.args.get("q", "").strip()
    dept_filter = request.args.get("dept", "")
    status_filter = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)

    query = Employee.query
    if q:
        query = query.filter(
            db.or_(
                Employee.full_name.ilike(f"%{q}%"),
                Employee.employee_id.ilike(f"%{q}%"),
                Employee.email.ilike(f"%{q}%"),
            )
        )
    if dept_filter:
        query = query.filter_by(department_id=int(dept_filter))
    if status_filter:
        status_val = AccountStatus.ACTIVE if status_filter == "active" else AccountStatus.INACTIVE
        query = query.filter_by(status=status_val)

    employees = query.order_by(Employee.full_name).paginate(page=page, per_page=15, error_out=False)
    departments = Department.query.order_by(Department.name).all()
    return render_template("employees/list.html", employees=employees, departments=departments)


@employees_bp.route("/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_employee():
    departments = Department.query.order_by(Department.name).all()
    schedules = WorkSchedule.query.order_by(WorkSchedule.name).all()
    error = None

    if request.method == "POST":
        emp_id = request.form.get("employee_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        dept_id = request.form.get("department_id") or None
        designation = request.form.get("designation", "").strip()
        schedule_id = request.form.get("work_schedule_id") or None
        status = request.form.get("status", "active")
        date_joined_str = request.form.get("date_joined", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not all([emp_id, full_name, email, username, password]):
            error = "Employee ID, name, email, username, and password are required."
        elif Employee.query.filter_by(employee_id=emp_id).first():
            error = f"Employee ID '{emp_id}' already exists."
        elif Employee.query.filter_by(email=email).first() or User.query.filter_by(email=email).first():
            error = "An account/employee with this email already exists."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        else:
            from datetime import datetime
            joined_dt = None
            if date_joined_str:
                try:
                    joined_dt = datetime.strptime(date_joined_str, "%Y-%m-%d")
                except ValueError:
                    joined_dt = None

            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=UserRole.EMPLOYEE,
                is_active=(status == "active"),
            )
            db.session.add(user)
            db.session.flush()

            status_val = AccountStatus.ACTIVE if status == "active" else AccountStatus.INACTIVE
            emp_kwargs = {
                "employee_id": emp_id,
                "full_name": full_name,
                "email": email,
                "phone": phone or None,
                "department_id": int(dept_id) if dept_id else None,
                "designation": designation or None,
                "work_schedule_id": int(schedule_id) if schedule_id else None,
                "status": status_val,
                "user_id": user.id,
            }
            if joined_dt:
                emp_kwargs["date_joined"] = joined_dt

            emp = Employee(**emp_kwargs)
            db.session.add(emp)
            db.session.commit()
            flash(f"Employee '{full_name}' added successfully.", "success")
            return redirect(url_for("employees.list_employees"))

    return render_template("employees/form.html", departments=departments,
                           schedules=schedules, error=error)


@employees_bp.route("/<int:emp_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_employee(emp_id):
    employee = Employee.query.get_or_404(emp_id)
    departments = Department.query.order_by(Department.name).all()
    schedules = WorkSchedule.query.order_by(WorkSchedule.name).all()
    error = None

    if request.method == "POST":
        new_emp_id = request.form.get("employee_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        dept_id = request.form.get("department_id") or None
        designation = request.form.get("designation", "").strip()
        schedule_id = request.form.get("work_schedule_id") or None
        status = request.form.get("status", "active")
        date_joined_str = request.form.get("date_joined", "").strip()

        if not new_emp_id or not full_name or not email:
            error = "Employee ID, name, and email are required."
        elif Employee.query.filter(Employee.employee_id == new_emp_id, Employee.id != emp_id).first():
            error = f"Employee ID '{new_emp_id}' is already assigned to another employee."
        elif Employee.query.filter(Employee.email == email, Employee.id != emp_id).first():
            error = "Another employee already has this email."
        elif employee.user and User.query.filter(User.email == email, User.id != employee.user_id).first():
            error = "Another user account already has this email."
        else:
            from datetime import datetime
            if date_joined_str:
                try:
                    employee.date_joined = datetime.strptime(date_joined_str, "%Y-%m-%d")
                except ValueError:
                    pass

            employee.employee_id = new_emp_id
            employee.full_name = full_name
            employee.email = email
            employee.phone = phone or None
            employee.department_id = int(dept_id) if dept_id else None
            employee.designation = designation or None
            employee.work_schedule_id = int(schedule_id) if schedule_id else None
            employee.status = AccountStatus.ACTIVE if status == "active" else AccountStatus.INACTIVE

            # Sync user email and active status if linked
            if employee.user:
                employee.user.email = email
                employee.user.is_active = (status == "active")

            db.session.commit()
            flash(f"Employee '{full_name}' updated successfully.", "success")
            return redirect(url_for("employees.list_employees"))

    return render_template("employees/form.html", employee=employee,
                           departments=departments, schedules=schedules, error=error)


@employees_bp.route("/<int:emp_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_status(emp_id):
    employee = Employee.query.get_or_404(emp_id)
    if employee.status == AccountStatus.ACTIVE:
        employee.status = AccountStatus.INACTIVE
        if employee.user:
            employee.user.is_active = False
        msg = f"{employee.full_name} deactivated."
    else:
        employee.status = AccountStatus.ACTIVE
        if employee.user:
            employee.user.is_active = True
        msg = f"{employee.full_name} activated."
    db.session.commit()
    flash(msg, "success")
    return redirect(url_for("employees.list_employees"))
