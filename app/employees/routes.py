"""
EBT System – Employee Routes (Admin only)
"""

from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Employee, Department, WorkSchedule, User, UserRole, AccountStatus,
    Designation, EmployeeSalary, Attendance, LeaveRequest
)

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
    view_mode = request.args.get("view", "list")  # list or grid
    page = request.args.get("page", 1, type=int)

    query = Employee.query
    if q:
        query = query.filter(
            db.or_(
                Employee.full_name.ilike(f"%{q}%"),
                Employee.employee_id.ilike(f"%{q}%"),
                Employee.email.ilike(f"%{q}%"),
                Employee.designation.ilike(f"%{q}%"),
            )
        )
    if dept_filter:
        query = query.filter_by(department_id=int(dept_filter))
    if status_filter:
        status_val = AccountStatus.ACTIVE if status_filter == "active" else AccountStatus.INACTIVE
        query = query.filter_by(status=status_val)

    employees = query.order_by(Employee.full_name).paginate(page=page, per_page=12 if view_mode == 'grid' else 15, error_out=False)
    departments = Department.query.order_by(Department.name).all()
    return render_template(
        "employees/list.html",
        employees=employees,
        departments=departments,
        view_mode=view_mode
    )


def get_next_employee_id() -> str:
    """
    Generate next sequential employee ID (e.g. EMP001, EMP002, ...).
    Inspects all existing IDs in the format EMP<number> and picks max + 1.
    """
    import re
    all_emp_ids = [e.employee_id for e in Employee.query.with_entities(Employee.employee_id).all()]
    max_num = 0
    for emp_id in all_emp_ids:
        match = re.match(r"^EMP(\d+)$", (emp_id or "").strip(), re.IGNORECASE)
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    next_num = max_num + 1 if max_num > 0 else 1
    candidate = f"EMP{next_num:03d}"
    while Employee.query.filter_by(employee_id=candidate).first():
        next_num += 1
        candidate = f"EMP{next_num:03d}"
    return candidate


@employees_bp.route("/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_employee():
    departments = Department.query.order_by(Department.name).all()
    schedules = WorkSchedule.query.order_by(WorkSchedule.name).all()
    error = None

    if request.method == "POST":
        emp_id = request.form.get("employee_id", "").strip() or get_next_employee_id()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        dept_id = request.form.get("department_id") or None
        
        # Designation: handle dropdown + custom "Other"
        desig_choice = request.form.get("designation_choice", "").strip()
        custom_desig = request.form.get("custom_designation", "").strip()
        if desig_choice == "Other" and custom_desig:
            designation = custom_desig
        elif desig_choice and desig_choice != "Other":
            designation = desig_choice
        else:
            designation = request.form.get("designation", "").strip() or None

        company_name = request.form.get("company_name", "").strip() or "EBT System"
        role_choice = request.form.get("role", "Employee").strip().lower()
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

            account_role = UserRole.ADMIN if role_choice == "admin" else UserRole.EMPLOYEE

            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=account_role,
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
                "company_name": company_name,
                "work_schedule_id": int(schedule_id) if schedule_id else None,
                "status": status_val,
                "user_id": user.id,
            }
            if joined_dt:
                emp_kwargs["date_joined"] = joined_dt

            emp = Employee(**emp_kwargs)
            db.session.add(emp)
            db.session.commit()
            flash(f"Employee '{full_name}' ({account_role.value}) added successfully with ID {emp_id}.", "success")
            return redirect(url_for("employees.list_employees"))

    auto_emp_id = get_next_employee_id()
    return render_template("employees/form.html", departments=departments,
                           schedules=schedules, auto_emp_id=auto_emp_id, error=error)


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
        
        # Designation: handle dropdown + custom "Other"
        desig_choice = request.form.get("designation_choice", "").strip()
        custom_desig = request.form.get("custom_designation", "").strip()
        if desig_choice == "Other" and custom_desig:
            designation = custom_desig
        elif desig_choice and desig_choice != "Other":
            designation = desig_choice
        else:
            designation = request.form.get("designation", "").strip() or None

        company_name = request.form.get("company_name", "").strip() or "EBT System"
        role_choice = request.form.get("role", "").strip().lower()
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
            employee.company_name = company_name
            employee.work_schedule_id = int(schedule_id) if schedule_id else None
            employee.status = AccountStatus.ACTIVE if status == "active" else AccountStatus.INACTIVE

            # Sync user email, role, and active status if linked
            if employee.user:
                employee.user.email = email
                employee.user.is_active = (status == "active")
                if role_choice in ("admin", "employee"):
                    # Prevent admin from accidentally demoting themselves
                    if employee.user.id == current_user.id and role_choice == "employee":
                        pass
                    else:
                        employee.user.role = UserRole.ADMIN if role_choice == "admin" else UserRole.EMPLOYEE

            db.session.commit()
            flash(f"Employee '{full_name}' updated successfully.", "success")
            return redirect(url_for("employees.list_employees"))

    return render_template("employees/form.html", employee=employee,
                           departments=departments, schedules=schedules, error=error)


@employees_bp.route("/profile")
@login_required
def profile():
    """Employee personal profile view and admin self-view."""
    employee = current_user.employee
    return render_template("employees/profile.html", employee=employee, user=current_user)


@employees_bp.route("/<int:emp_id>/view")
@login_required
def view_employee(emp_id):
    """Complete employee profile view showing personal, job, salary, attendance, and leave details."""
    employee = Employee.query.get_or_404(emp_id)

    # Permission check: Standard employees can only view their own profile
    if not current_user.is_admin:
        if not current_user.employee or current_user.employee.id != employee.id:
            abort(403)

    # Sensitive salary details (Admin only)
    salary = None
    if current_user.is_admin:
        salary = EmployeeSalary.query.filter_by(employee_id=employee.id).first()

    recent_attendance = (
        Attendance.query.filter_by(employee_id=employee.id)
        .order_by(Attendance.date.desc())
        .limit(10)
        .all()
    )
    recent_leaves = (
        LeaveRequest.query.filter_by(employee_id=employee.id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "employees/view.html",
        employee=employee,
        salary=salary,
        recent_attendance=recent_attendance,
        recent_leaves=recent_leaves
    )


# ── Department Management ───────────────────────────────────────────────────

@employees_bp.route("/departments")
@login_required
@admin_required
def departments_list():
    """List, search, and manage organizational departments."""
    q = request.args.get("q", "").strip()
    query = Department.query
    if q:
        query = query.filter(
            db.or_(
                Department.name.ilike(f"%{q}%"),
                Department.description.ilike(f"%{q}%")
            )
        )
    departments = query.order_by(Department.name.asc()).all()
    return render_template("employees/departments.html", departments=departments, q=q)


@employees_bp.route("/departments/add", methods=["POST"])
@login_required
@admin_required
def add_department():
    """Create a new department."""
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name:
        flash("Department name is required.", "danger")
        return redirect(url_for("employees.departments_list"))

    if Department.query.filter_by(name=name).first():
        flash(f"Department '{name}' already exists.", "warning")
        return redirect(url_for("employees.departments_list"))

    dept = Department(name=name, description=description)
    db.session.add(dept)
    db.session.commit()
    flash(f"Department '{name}' created successfully.", "success")
    return redirect(url_for("employees.departments_list"))


@employees_bp.route("/departments/<int:dept_id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_department(dept_id):
    """Edit department details."""
    dept = Department.query.get_or_404(dept_id)
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name:
        flash("Department name is required.", "danger")
        return redirect(url_for("employees.departments_list"))

    existing = Department.query.filter_by(name=name).first()
    if existing and existing.id != dept_id:
        flash(f"Another department with name '{name}' already exists.", "warning")
        return redirect(url_for("employees.departments_list"))

    dept.name = name
    dept.description = description
    db.session.commit()
    flash(f"Department '{name}' updated successfully.", "success")
    return redirect(url_for("employees.departments_list"))


@employees_bp.route("/departments/<int:dept_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_department(dept_id):
    """Safely delete department if no employees are currently assigned."""
    dept = Department.query.get_or_404(dept_id)
    assigned_count = Employee.query.filter_by(department_id=dept.id).count()
    if assigned_count > 0:
        flash(f"Cannot delete department '{dept.name}' because {assigned_count} employee(s) are assigned to it.", "danger")
        return redirect(url_for("employees.departments_list"))

    db.session.delete(dept)
    db.session.commit()
    flash(f"Department '{dept.name}' deleted successfully.", "info")
    return redirect(url_for("employees.departments_list"))


# ── Designation Management ───────────────────────────────────────────────────

@employees_bp.route("/designations")
@login_required
@admin_required
def designations_list():
    """List and manage designations associated with departments."""
    q = request.args.get("q", "").strip()
    dept_id = request.args.get("dept", type=int)

    query = Designation.query
    if q:
        query = query.filter(Designation.name.ilike(f"%{q}%"))
    if dept_id:
        query = query.filter_by(department_id=dept_id)

    designations = query.order_by(Designation.name.asc()).all()
    departments = Department.query.order_by(Department.name.asc()).all()
    return render_template(
        "employees/designations.html",
        designations=designations,
        departments=departments,
        selected_dept=dept_id,
        q=q
    )


@employees_bp.route("/designations/add", methods=["POST"])
@login_required
@admin_required
def add_designation():
    """Add new designation."""
    name = request.form.get("name", "").strip()
    dept_id = request.form.get("department_id", type=int)
    description = request.form.get("description", "").strip()

    if not name:
        flash("Designation title is required.", "danger")
        return redirect(url_for("employees.designations_list"))

    if Designation.query.filter_by(name=name).first():
        flash(f"Designation '{name}' already exists.", "warning")
        return redirect(url_for("employees.designations_list"))

    desig = Designation(name=name, department_id=dept_id or None, description=description)
    db.session.add(desig)
    db.session.commit()
    flash(f"Designation '{name}' created successfully.", "success")
    return redirect(url_for("employees.designations_list"))


@employees_bp.route("/designations/<int:desig_id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_designation(desig_id):
    """Edit designation details."""
    desig = Designation.query.get_or_404(desig_id)
    name = request.form.get("name", "").strip()
    dept_id = request.form.get("department_id", type=int)
    description = request.form.get("description", "").strip()

    if not name:
        flash("Designation title is required.", "danger")
        return redirect(url_for("employees.designations_list"))

    existing = Designation.query.filter_by(name=name).first()
    if existing and existing.id != desig_id:
        flash(f"Another designation with name '{name}' already exists.", "warning")
        return redirect(url_for("employees.designations_list"))

    desig.name = name
    desig.department_id = dept_id or None
    desig.description = description
    db.session.commit()
    flash(f"Designation '{name}' updated successfully.", "success")
    return redirect(url_for("employees.designations_list"))


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
