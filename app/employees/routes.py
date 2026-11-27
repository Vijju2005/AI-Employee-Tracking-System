"""
EBT System – Employee Routes (Admin only)
"""

import os
import uuid
from datetime import datetime, date
from functools import wraps
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Employee, Department, WorkSchedule, User, UserRole, AccountStatus,
    Designation, EmployeeSalary, Attendance, LeaveRequest,
    EmployeeDocument, CompanyPolicy, EmployeeProfile, CalendarYear
)
from app.utils.crypto import mask_aadhaar, mask_pan, mask_bank_account
import io
import csv

employees_bp = Blueprint("employees", __name__, url_prefix="/employees")


def get_upload_dir(subfolder="documents"):
    """
    Get safe storage directory.
    If PERSISTENT_UPLOAD_DIR is configured, verify the mount path exists and is accessible.
    If PERSISTENT_UPLOAD_DIR is specified but does not exist on disk, raise an explicit
    RuntimeError so that uploads are NEVER silently saved to ephemeral container storage.
    """
    base_dir = os.environ.get("PERSISTENT_UPLOAD_DIR")
    if base_dir:
        if not os.path.exists(base_dir):
            raise RuntimeError(
                f"PERSISTENT STORAGE ERROR: Configured persistent disk path '{base_dir}' is not mounted. "
                "Upload aborted to prevent silent data loss on ephemeral storage."
            )
        target = os.path.join(base_dir, subfolder)
    else:
        # If running in production on Render without PERSISTENT_UPLOAD_DIR, prevent silent ephemeral storage
        is_prod = (
            os.environ.get("FLASK_ENV") == "production"
            or os.environ.get("RENDER") == "true"
            or os.environ.get("ENVIRONMENT") == "production"
        )
        if is_prod:
            raise RuntimeError(
                "PERSISTENT STORAGE ERROR: PERSISTENT_UPLOAD_DIR is not configured in production. "
                "Uploads must be backed by persistent storage."
            )
        target = os.path.join(current_app.root_path, "static", "uploads", subfolder)

    os.makedirs(target, exist_ok=True)
    return target


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
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
    calendar_year_filter = request.args.get("calendar_year", "")
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
    if calendar_year_filter:
        try:
            cy_obj = CalendarYear.query.get(int(calendar_year_filter))
            if cy_obj:
                start_dt = datetime.combine(cy_obj.start_date, datetime.min.time())
                end_dt = datetime.combine(cy_obj.end_date, datetime.max.time())
                query = query.filter(Employee.date_joined >= start_dt, Employee.date_joined <= end_dt)
        except (ValueError, TypeError):
            pass

    employees = query.order_by(Employee.full_name).paginate(page=page, per_page=12 if view_mode == 'grid' else 15, error_out=False)
    departments = Department.query.order_by(Department.name).all()
    calendar_years = CalendarYear.query.order_by(CalendarYear.start_date.desc()).all()

    # Dynamic metrics calculation for Summary Cards
    total_employees_count = Employee.query.count()
    active_employees_count = Employee.query.filter_by(status=AccountStatus.ACTIVE).count()
    active_pct = round((active_employees_count / total_employees_count * 100)) if total_employees_count > 0 else 0
    now_year = datetime.now().year
    ytd_start = datetime(now_year, 1, 1)
    new_joinees_count = Employee.query.filter(Employee.date_joined >= ytd_start).count()
    departments_count = len(departments)

    return render_template(
        "employees/list.html",
        employees=employees,
        departments=departments,
        calendar_years=calendar_years,
        view_mode=view_mode,
        total_employees_count=total_employees_count,
        active_employees_count=active_employees_count,
        active_pct=active_pct,
        new_joinees_count=new_joinees_count,
        departments_count=departments_count
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
    """Employee personal profile view and admin self-view with self-service capabilities."""
    employee = current_user.employee
    profile_obj = None
    docs = []
    salary = None

    if employee:
        profile_obj = employee.profile
        if not profile_obj:
            profile_obj = EmployeeProfile(employee_id=employee.id)
            db.session.add(profile_obj)
            db.session.commit()
        docs = EmployeeDocument.query.filter_by(employee_id=employee.id).order_by(EmployeeDocument.created_at.desc()).all()
        salary = EmployeeSalary.query.filter_by(employee_id=employee.id).first()

    active_tab = request.args.get("tab", "personal")
    return render_template(
        "employees/profile.html",
        employee=employee,
        user=current_user,
        profile=profile_obj,
        salary=salary,
        recent_docs=docs,
        active_tab=active_tab
    )


@employees_bp.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    """
    Allow authenticated employees to update permitted personal details only:
    - phone
    - bio / personal notes (if provided)
    - profile photo upload (PNG, JPG, WEBP, max 2MB)
    Strictly forbids modifying employee_id, role, salary, department, designation, or status.
    """
    employee = current_user.employee
    phone = request.form.get("phone", "").strip()

    # Update permitted phone on employee and user records
    if employee:
        employee.phone = phone or None
    current_user.phone = phone or None

    # Handle profile avatar image upload if provided
    file = request.files.get("avatar")
    if file and file.filename:
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            flash("Invalid photo format. Please upload a PNG, JPG, or WEBP image.", "danger")
            return redirect(url_for("employees.profile"))

        # Check file length/size (max 2MB)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > 2 * 1024 * 1024:
            flash("Image file too large. Maximum allowed size is 2MB.", "danger")
            return redirect(url_for("employees.profile"))

        unique_name = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
        upload_folder = get_upload_dir("avatars")
        save_path = os.path.join(upload_folder, unique_name)
        file.save(save_path)

        # Store web path
        web_path = f"/static/uploads/avatars/{unique_name}"
        if hasattr(current_user, "avatar_url"):
            current_user.avatar_url = web_path

    db.session.commit()
    flash("Personal contact profile updated successfully.", "success")
    return redirect(url_for("employees.profile"))


# ── Employee Self-Service: My Documents ─────────────────────
ALLOWED_DOC_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}
MAX_DOC_SIZE = 5 * 1024 * 1024  # 5MB


@employees_bp.route("/documents")
@login_required
def documents_list():
    """
    Self-Service My Documents portal:
    - Employees can view and download their own corporate & personal records.
    - Admins can filter by employee or view full document repository.
    """
    selected_emp_id = request.args.get("emp_id", type=int)
    doc_type = request.args.get("type", "").strip()

    if current_user.is_admin:
        query = EmployeeDocument.query
        if selected_emp_id:
            query = query.filter_by(employee_id=selected_emp_id)
        if doc_type:
            query = query.filter_by(document_type=doc_type)
        documents = query.order_by(EmployeeDocument.created_at.desc()).all()
        employees = Employee.query.order_by(Employee.full_name).all()
        target_employee = Employee.query.get(selected_emp_id) if selected_emp_id else None
    else:
        # Standard employee: strictly limited to own documents
        if not current_user.employee:
            flash("No employee record linked to your account.", "warning")
            return redirect(url_for("dashboard.employee_dashboard"))
        query = EmployeeDocument.query.filter_by(employee_id=current_user.employee.id)
        if doc_type:
            query = query.filter_by(document_type=doc_type)
        documents = query.order_by(EmployeeDocument.created_at.desc()).all()
        employees = []
        target_employee = current_user.employee

    return render_template(
        "employees/documents.html",
        documents=documents,
        employees=employees,
        target_employee=target_employee,
        doc_type=doc_type
    )


@employees_bp.route("/documents/upload", methods=["POST"])
@login_required
def upload_document():
    """
    Upload a secure employee document.
    - Standard employees can upload documents for themselves.
    - Admins can upload official letters/documents for any designated employee.
    """
    # Determine target employee
    if current_user.is_admin:
        emp_id = request.form.get("employee_id", type=int)
        if not emp_id and current_user.employee:
            emp_id = current_user.employee.id
    else:
        if not current_user.employee:
            abort(403)
        emp_id = current_user.employee.id

    employee = Employee.query.get_or_404(emp_id)

    file = request.files.get("document_file")
    doc_name = request.form.get("document_name", "").strip()
    doc_type = request.form.get("document_type", "Other").strip()
    notes = request.form.get("notes", "").strip()

    if not file or not file.filename:
        flash("Please select a document file to upload.", "danger")
        return redirect(url_for("employees.documents_list"))

    orig_filename = secure_filename(file.filename)
    ext = os.path.splitext(orig_filename)[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        flash(f"Invalid document format '{ext}'. Allowed types: PDF, JPG, PNG, DOCX.", "danger")
        return redirect(url_for("employees.documents_list"))

    # File size check
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_DOC_SIZE:
        flash("Document file too large. Maximum allowed size is 5MB.", "danger")
        return redirect(url_for("employees.documents_list"))

    safe_title = doc_name or os.path.splitext(orig_filename)[0]
    unique_filename = f"doc_emp{employee.id}_{uuid.uuid4().hex[:10]}{ext}"
    try:
        upload_dir = get_upload_dir("documents")
        abs_path = os.path.join(upload_dir, unique_filename)
        file.save(abs_path)
    except RuntimeError as re:
        flash(f"Upload failed: {str(re)}", "danger")
        return redirect(url_for("employees.documents_list"))

    # Determine status: auto-approve for admins, pending/approved for employees
    status = "Approved" if current_user.is_admin else "Submitted"

    doc = EmployeeDocument(
        employee_id=employee.id,
        document_name=safe_title,
        document_type=doc_type,
        file_path=unique_filename,
        file_size=size,
        mime_type=file.content_type or "application/octet-stream",
        status=status,
        notes=notes or None,
        uploaded_by_id=current_user.id
    )
    db.session.add(doc)
    db.session.commit()

    flash(f"Document '{safe_title}' uploaded successfully.", "success")
    return redirect(url_for("employees.documents_list"))


@employees_bp.route("/documents/<int:doc_id>/download")
@login_required
def download_document(doc_id):
    """
    Secure document download with authorization checks:
    - Standard employees can only download their own documents.
    - Admins can download all company employee documents.
    """
    doc = EmployeeDocument.query.get_or_404(doc_id)

    # Privacy verification
    if not current_user.is_admin:
        if not current_user.employee or current_user.employee.id != doc.employee_id:
            abort(403)

    upload_dir = get_upload_dir("documents")
    # Clean filename without path traversal
    filename = os.path.basename(doc.file_path)
    file_on_disk = os.path.join(upload_dir, filename)

    if not os.path.isfile(file_on_disk):
        flash("The requested document file could not be found on the server storage.", "warning")
        return redirect(url_for("employees.documents_list"))

    # Determine friendly download filename
    ext = os.path.splitext(filename)[1]
    download_name = f"{secure_filename(doc.document_name)}{ext}"

    return send_from_directory(
        upload_dir,
        filename,
        as_attachment=True,
        download_name=download_name
    )


@employees_bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    """Delete document (admin or document owner)."""
    doc = EmployeeDocument.query.get_or_404(doc_id)
    if not current_user.is_admin and (not current_user.employee or current_user.employee.id != doc.employee_id):
        abort(403)

    # Remove physical file if present
    upload_dir = get_upload_dir("documents")
    file_path = os.path.join(upload_dir, os.path.basename(doc.file_path))
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    name = doc.document_name
    db.session.delete(doc)
    db.session.commit()
    flash(f"Document '{name}' deleted.", "success")
    return redirect(url_for("employees.documents_list"))


# ── Employee Self-Service: Company Policies ─────────────────
@employees_bp.route("/policies")
@login_required
def policies_list():
    """
    Company Policies and HR Guidelines:
    - All employees can view and download guidelines.
    - Admins can add, edit, or delete policy guidelines.
    """
    cat_filter = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()

    query = CompanyPolicy.query
    if cat_filter:
        query = query.filter_by(category=cat_filter)
    if q:
        query = query.filter(
            db.or_(
                CompanyPolicy.title.ilike(f"%{q}%"),
                CompanyPolicy.description.ilike(f"%{q}%")
            )
        )

    policies = query.order_by(CompanyPolicy.category.asc(), CompanyPolicy.title.asc()).all()
    categories = [
        "General HR",
        "Leave & Attendance",
        "Code of Conduct",
        "POSH & Workplace Safety",
        "IT & Data Security",
        "Compensation & Benefits",
        "Travel & Expense"
    ]
    return render_template(
        "employees/policies.html",
        policies=policies,
        categories=categories,
        cat_filter=cat_filter,
        q=q
    )


@employees_bp.route("/policies/add", methods=["POST"])
@login_required
@admin_required
def add_policy():
    """Add a new company policy (Admin only)."""
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "General HR").strip()
    description = request.form.get("description", "").strip()
    version = request.form.get("version", "1.0").strip()
    eff_date_str = request.form.get("effective_date", "").strip()

    if not title:
        flash("Policy title is required.", "danger")
        return redirect(url_for("employees.policies_list"))

    eff_date = None
    if eff_date_str:
        from datetime import datetime
        try:
            eff_date = datetime.strptime(eff_date_str, "%Y-%m-%d").date()
        except ValueError:
            eff_date = None

    file_name = None
    file = request.files.get("policy_file")
    if file and file.filename:
        orig = secure_filename(file.filename)
        ext = os.path.splitext(orig)[1].lower()
        if ext not in [".pdf", ".docx", ".txt"]:
            flash("Policy document must be a PDF or DOCX file.", "danger")
            return redirect(url_for("employees.policies_list"))
        file_name = f"policy_{uuid.uuid4().hex[:8]}{ext}"
        try:
            save_dir = get_upload_dir("policies")
            file.save(os.path.join(save_dir, file_name))
        except RuntimeError as re:
            flash(f"Policy upload failed: {str(re)}", "danger")
            return redirect(url_for("employees.policies_list"))

    policy = CompanyPolicy(
        title=title,
        category=category,
        description=description or None,
        file_path=file_name,
        version=version or "1.0",
        effective_date=eff_date,
        created_by_id=current_user.id
    )
    db.session.add(policy)
    db.session.commit()
    flash(f"Company policy '{title}' published successfully.", "success")
    return redirect(url_for("employees.policies_list"))


@employees_bp.route("/policies/<int:policy_id>/download")
@login_required
def download_policy(policy_id):
    """Download attached policy file."""
    policy = CompanyPolicy.query.get_or_404(policy_id)
    if not policy.file_path:
        flash("No downloadable document attached to this policy.", "warning")
        return redirect(url_for("employees.policies_list"))

    save_dir = get_upload_dir("policies")
    ext = os.path.splitext(policy.file_path)[1]
    filename = os.path.basename(policy.file_path)
    file_on_disk = os.path.join(save_dir, filename)

    if not os.path.isfile(file_on_disk):
        flash("The requested policy file could not be found on the server storage.", "warning")
        return redirect(url_for("employees.policies_list"))

    download_name = f"{secure_filename(policy.title)}_v{policy.version}{ext}"

    return send_from_directory(
        save_dir,
        filename,
        as_attachment=True,
        download_name=download_name
    )


@employees_bp.route("/policies/<int:policy_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_policy(policy_id):
    """Delete policy (Admin only)."""
    policy = CompanyPolicy.query.get_or_404(policy_id)
    if policy.file_path:
        save_dir = get_upload_dir("policies")
        target_path = os.path.join(save_dir, os.path.basename(policy.file_path))
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass

    title = policy.title
    db.session.delete(policy)
    db.session.commit()
    flash(f"Policy '{title}' deleted successfully.", "success")
    return redirect(url_for("employees.policies_list"))


@employees_bp.route("/<int:emp_id>/view")
@login_required
def view_employee(emp_id):
    """Complete employee profile view showing personal, job, salary, attendance, documents, and family details."""
    employee = Employee.query.get_or_404(emp_id)

    # Permission check: Standard employees can only view their own profile
    if not current_user.is_admin:
        if not current_user.employee or current_user.employee.id != employee.id:
            abort(403)

    # Sensitive salary details (Admin only)
    salary = None
    if current_user.is_admin:
        salary = EmployeeSalary.query.filter_by(employee_id=employee.id).first()

    profile = employee.profile
    if not profile:
        profile = EmployeeProfile(employee_id=employee.id)
        db.session.add(profile)
        db.session.commit()

    # Documents
    documents = EmployeeDocument.query.filter_by(employee_id=employee.id).order_by(EmployeeDocument.created_at.desc()).all()

    # Managers list for admin assignment
    managers = []
    if current_user.is_admin:
        managers = Employee.query.filter(Employee.id != employee.id, Employee.status == AccountStatus.ACTIVE).order_by(Employee.full_name).all()

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
        profile=profile,
        salary=salary,
        documents=documents,
        managers=managers,
        recent_attendance=recent_attendance,
        recent_leaves=recent_leaves
    )


@employees_bp.route("/<int:emp_id>/profile/update", methods=["POST"])
@login_required
def update_employee_profile_sections(emp_id):
    """
    Update detailed sections of an employee profile.
    - Admins can update all sections (Personal, Identity, Family, Education, Employment, Banking).
    - Employees can update only permitted personal & emergency sections for their own profile.
    """
    employee = Employee.query.get_or_404(emp_id)

    if not current_user.is_admin and (not current_user.employee or current_user.employee.id != employee.id):
        abort(403)

    section = request.form.get("section", "personal").strip()
    profile = EmployeeProfile.query.filter_by(employee_id=employee.id).first()
    if not profile:
        profile = EmployeeProfile(employee_id=employee.id)
        db.session.add(profile)
        db.session.flush()
        db.session.add(profile)

    from datetime import datetime

    if section == "personal":
        # Permitted for both Employee and Admin
        dob_str = request.form.get("date_of_birth", "").strip()
        if dob_str:
            try:
                profile.date_of_birth = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        profile.gender = request.form.get("gender", profile.gender)
        profile.marital_status = request.form.get("marital_status", profile.marital_status)
        profile.personal_email = request.form.get("personal_email", "").strip() or None
        profile.personal_phone = request.form.get("personal_phone", "").strip() or None
        profile.blood_group = request.form.get("blood_group", "").strip() or None
        profile.nationality = request.form.get("nationality", "Indian").strip()
        profile.current_address = request.form.get("current_address", "").strip() or None
        profile.permanent_address = request.form.get("permanent_address", "").strip() or None

        # Also update employee primary phone if provided
        phone = request.form.get("phone", "").strip()
        if phone:
            employee.phone = phone
            if employee.user:
                employee.user.phone = phone

    elif section == "family":
        # Permitted for both Employee and Admin
        profile.father_name = request.form.get("father_name", "").strip() or None
        profile.mother_name = request.form.get("mother_name", "").strip() or None
        profile.spouse_name = request.form.get("spouse_name", "").strip() or None
        profile.dependents_info = request.form.get("dependents_info", "").strip() or None
        profile.emergency_contact_name = request.form.get("emergency_contact_name", "").strip() or None
        profile.emergency_contact_relation = request.form.get("emergency_contact_relation", "").strip() or None
        profile.emergency_contact_phone = request.form.get("emergency_contact_phone", "").strip() or None
        profile.emergency_contact_address = request.form.get("emergency_contact_address", "").strip() or None

    elif section == "identity":
        # Restricted to Admin
        if not current_user.is_admin:
            abort(403)
        aadhaar = request.form.get("aadhaar_number", "").strip()
        pan = request.form.get("pan_number", "").strip().upper()
        if aadhaar:
            profile.aadhaar_number = aadhaar
        if pan:
            profile.pan_number = pan
        profile.passport_number = request.form.get("passport_number", "").strip() or None
        passport_exp = request.form.get("passport_expiry", "").strip()
        if passport_exp:
            try:
                profile.passport_expiry = datetime.strptime(passport_exp, "%Y-%m-%d").date()
            except ValueError:
                pass
        profile.driving_licence = request.form.get("driving_licence", "").strip() or None
        profile.uan_number = request.form.get("uan_number", "").strip() or None
        profile.pf_account_number = request.form.get("pf_account_number", "").strip() or None
        profile.esic_number = request.form.get("esic_number", "").strip() or None

    elif section == "education":
        # Admin or Employee can update educational background
        profile.highest_qualification = request.form.get("highest_qualification", "").strip() or None
        profile.institution_university = request.form.get("institution_university", "").strip() or None
        grad_year = request.form.get("graduation_year", type=int)
        profile.graduation_year = grad_year or None
        profile.previous_company = request.form.get("previous_company", "").strip() or None
        profile.previous_designation = request.form.get("previous_designation", "").strip() or None
        tot_exp = request.form.get("total_experience_years", type=float)
        profile.total_experience_years = tot_exp if tot_exp is not None else profile.total_experience_years

    elif section == "employment":
        # Restricted to Admin
        if not current_user.is_admin:
            abort(403)
        profile.employment_type = request.form.get("employment_type", "Full-Time")
        profile.work_location = request.form.get("work_location", "Bengaluru")
        manager_id = request.form.get("manager_id", type=int)
        if manager_id and manager_id == employee.id:
            flash("An employee cannot be designated as their own reporting manager.", "warning")
            return redirect(url_for("employees.view_employee", emp_id=employee.id, tab="employment"))
        employee.manager_id = manager_id if manager_id else None

        prob_date = request.form.get("probation_end_date", "").strip()
        if prob_date:
            try:
                profile.probation_end_date = datetime.strptime(prob_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        conf_date = request.form.get("confirmation_date", "").strip()
        if conf_date:
            try:
                profile.confirmation_date = datetime.strptime(conf_date, "%Y-%m-%d").date()
            except ValueError:
                pass

    elif section == "banking":
        # Restricted to Admin
        if not current_user.is_admin:
            abort(403)
        profile.account_holder_name = request.form.get("account_holder_name", "").strip() or None
        profile.bank_branch = request.form.get("bank_branch", "").strip() or None
        bank_name = request.form.get("bank_name", "").strip() or None
        account_number = request.form.get("account_number", "").strip() or None
        ifsc_code = request.form.get("ifsc_code", "").strip().upper() or None

        if account_number:
            profile.bank_account_number = account_number
        elif request.form.get("clear_bank_account") == "true":
            profile.bank_account_number = ""

        salary = EmployeeSalary.query.filter_by(employee_id=employee.id).first()
        if not salary and (bank_name or account_number):
            salary = EmployeeSalary(employee_id=employee.id)
            db.session.add(salary)
        if salary:
            if bank_name:
                salary.bank_name = bank_name
            if account_number:
                salary.account_number = account_number
            if ifsc_code:
                salary.ifsc_code = ifsc_code

    db.session.commit()
    flash(f"Profile section '{section.capitalize()}' updated successfully.", "success")
    if current_user.is_admin and current_user.employee and current_user.employee.id != employee.id:
        return redirect(url_for("employees.view_employee", emp_id=employee.id, tab=section))
    return redirect(url_for("employees.profile", tab=section))


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


# ── Bulk Import & Export Routes ───────────────────────────────────────────────

@employees_bp.route("/export")
@login_required
@admin_required
def export_employees():
    """
    Export current filtered or full employee roster to Excel (.xlsx) or CSV.
    """
    from flask import Response, make_response
    q = request.args.get("q", "").strip()
    dept_filter = request.args.get("dept", "")
    status_filter = request.args.get("status", "")
    calendar_year_filter = request.args.get("calendar_year", "")
    fmt = request.args.get("format", "excel").lower()

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
    if calendar_year_filter:
        try:
            cy_obj = CalendarYear.query.get(int(calendar_year_filter))
            if cy_obj:
                start_dt = datetime.combine(cy_obj.start_date, datetime.min.time())
                end_dt = datetime.combine(cy_obj.end_date, datetime.max.time())
                query = query.filter(Employee.date_joined >= start_dt, Employee.date_joined <= end_dt)
        except (ValueError, TypeError):
            pass

    records = query.order_by(Employee.employee_id.asc()).all()

    if fmt == "csv":
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["Employee ID", "Full Name", "Email", "Department", "Designation", "Joining Year", "Joining Date", "Status"])
        for e in records:
            cw.writerow([
                e.employee_id,
                e.full_name,
                e.email,
                e.department.name if e.department else "—",
                e.designation or "—",
                e.joining_calendar_year.name if e.joining_calendar_year else "—",
                e.date_joined.strftime("%Y-%m-%d") if e.date_joined else "—",
                e.status.value.title() if hasattr(e.status, "value") else str(e.status).title()
            ])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = f"attachment; filename=Employee_Roster_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output

    # Excel Export using openpyxl
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from flask import send_file

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Employee Directory"
        ws.views.sheetView[0].showGridLines = True

        title_font = Font(name="Calibri", size=15, bold=True, color="0B192C")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1"),
        )

        ws.cell(row=1, column=1, value="EBT System — Workforce Personnel Directory").font = title_font
        ws.cell(row=2, column=1, value=f"Generated on {datetime.now().strftime('%d %B %Y at %I:%M %p')} | Total Records: {len(records)}").font = Font(size=9, color="64748B", italic=True)

        headers = ["Employee ID", "Full Name", "Email", "Department", "Designation", "Joining Year", "Joining Date", "Status"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center" if col_idx in [1, 6, 7, 8] else "left", vertical="center")
            cell.border = thin_border
        ws.row_dimensions[4].height = 26

        for r_idx, e in enumerate(records, start=5):
            ws.cell(row=r_idx, column=1, value=e.employee_id).alignment = Alignment(horizontal="center")
            ws.cell(row=r_idx, column=2, value=e.full_name)
            ws.cell(row=r_idx, column=3, value=e.email)
            ws.cell(row=r_idx, column=4, value=e.department.name if e.department else "—")
            ws.cell(row=r_idx, column=5, value=e.designation or "—")
            ws.cell(row=r_idx, column=6, value=e.joining_calendar_year.name if e.joining_calendar_year else "—").alignment = Alignment(horizontal="center")
            ws.cell(row=r_idx, column=7, value=e.date_joined.strftime("%d %b %Y") if e.date_joined else "—").alignment = Alignment(horizontal="center")
            
            st_cell = ws.cell(row=r_idx, column=8, value=e.status.value.title() if hasattr(e.status, "value") else str(e.status).title())
            st_cell.alignment = Alignment(horizontal="center")
            if (e.status.value if hasattr(e.status, "value") else str(e.status)).lower() == "active":
                st_cell.font = Font(color="047857", bold=True)
            else:
                st_cell.font = Font(color="B91C1C", bold=True)

            for col_idx in range(1, 9):
                ws.cell(row=r_idx, column=col_idx).border = thin_border
            ws.row_dimensions[r_idx].height = 20

        col_widths = {1: 16, 2: 26, 3: 32, 4: 20, 5: 24, 6: 22, 7: 18, 8: 16}
        for col_idx, width in col_widths.items():
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)

        filename = f"EBT System_Employees_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f"Excel export failed: {str(e)}. Falling back to CSV.", "warning")
        return redirect(url_for("employees.export_employees", format="csv", q=q, dept=dept_filter, status=status_filter, calendar_year=calendar_year_filter))


@employees_bp.route("/import", methods=["POST"])
@login_required
@admin_required
def import_employees():
    """
    Bulk import workforce members via standard CSV file.
    Expected CSV columns:
    employee_id, full_name, email, department, designation, username, password, [date_joined]
    """
    file = request.files.get("csv_file")
    if not file or not file.filename:
        flash("Please select a CSV file to upload.", "danger")
        return redirect(url_for("employees.list_employees"))

    if not file.filename.lower().endswith(".csv"):
        flash("Invalid file type. Please upload a CSV formatted file.", "danger")
        return redirect(url_for("employees.list_employees"))

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)
        
        imported_count = 0
        skipped_count = 0
        errors = []

        for row_idx, row in enumerate(reader, start=2):
            # Normalize keys
            clean_row = {k.strip().lower() if k else "": (v.strip() if v else "") for k, v in row.items()}
            
            full_name = clean_row.get("full_name") or clean_row.get("name")
            email = clean_row.get("email", "").lower()
            emp_id = clean_row.get("employee_id") or clean_row.get("id") or get_next_employee_id()
            username = clean_row.get("username") or email.split("@")[0] or emp_id.lower()
            password = clean_row.get("password") or "EmployeePass123!"
            dept_name = clean_row.get("department")
            designation = clean_row.get("designation")
            date_joined_str = clean_row.get("date_joined") or clean_row.get("joining_date")

            if not full_name or not email:
                skipped_count += 1
                errors.append(f"Row {row_idx}: Missing Full Name or Email.")
                continue

            if Employee.query.filter_by(email=email).first() or User.query.filter_by(email=email).first():
                skipped_count += 1
                continue

            if Employee.query.filter_by(employee_id=emp_id).first():
                emp_id = get_next_employee_id()

            if User.query.filter_by(username=username).first():
                username = f"{username}_{uuid.uuid4().hex[:4]}"

            # Department lookup or creation
            dept = None
            if dept_name:
                dept = Department.query.filter(Department.name.ilike(dept_name)).first()
                if not dept:
                    dept = Department(name=dept_name.title())
                    db.session.add(dept)
                    db.session.flush()

            joined_dt = datetime.now()
            if date_joined_str:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        joined_dt = datetime.strptime(date_joined_str, fmt)
                        break
                    except ValueError:
                        pass

            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            db.session.add(user)
            db.session.flush()

            emp = Employee(
                employee_id=emp_id,
                full_name=full_name,
                email=email,
                department_id=dept.id if dept else None,
                designation=designation or "Team Member",
                status=AccountStatus.ACTIVE,
                user_id=user.id,
                date_joined=joined_dt
            )
            db.session.add(emp)
            imported_count += 1

        db.session.commit()
        if imported_count > 0:
            flash(f"Successfully imported {imported_count} employees.", "success")
        if skipped_count > 0:
            flash(f"Skipped {skipped_count} duplicate or invalid records.", "info")

    except Exception as e:
        db.session.rollback()
        flash(f"Import failed: {str(e)}", "danger")

    return redirect(url_for("employees.list_employees"))

