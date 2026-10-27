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
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        dept_id = request.form.get("department_id") or None
        designation = request.form.get("designation", "").strip()
        schedule_id = request.form.get("work_schedule_id") or None
        status = request.form.get("status", "active")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not all([emp_id, full_name, email, username, password]):
            error = "Employee ID, name, email, username, and password are required."
        elif Employee.query.filter_by(employee_id=emp_id).first():
            error = f"Employee ID '{emp_id}' already exists."
        elif Employee.query.filter_by(email=email).first():
            error = "An employee with this email already exists."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        else:
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()

            status_val = AccountStatus.ACTIVE if status == "active" else AccountStatus.INACTIVE
            emp = Employee(
                employee_id=emp_id,
                full_name=full_name,
                email=email,
                phone=phone or None,
                department_id=int(dept_id) if dept_id else None,
                designation=designation or None,
                work_schedule_id=int(schedule_id) if schedule_id else None,
                status=status_val,
                user_id=user.id,
            )
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
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        dept_id = request.form.get("department_id") or None
        designation = request.form.get("designation", "").strip()
        schedule_id = request.form.get("work_schedule_id") or None
        status = request.form.get("status", "active")

        existing = Employee.query.filter(
            Employee.email == email, Employee.id != emp_id
        ).first()
        if existing:
            error = "Another employee already has this email."
        else:
            employee.full_name = full_name
            employee.email = email
            employee.phone = phone or None
            employee.department_id = int(dept_id) if dept_id else None
            employee.designation = designation or None
            employee.work_schedule_id = int(schedule_id) if schedule_id else None
            employee.status = AccountStatus.ACTIVE if status == "active" else AccountStatus.INACTIVE
            db.session.commit()
            flash("Employee updated successfully.", "success")
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
