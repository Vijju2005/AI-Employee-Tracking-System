"""
EBT System — Super Admin Blueprint
Enterprise SaaS Administration:
- Multi-tenant Super Admin Dashboard & KPIs
- Companies Management (create, view, edit, suspend, activate)
- Packages Management (tier configuration, limits, monthly/yearly pricing)
- Subscriptions Management (tenant subscriptions, renewal, status tracking)
"""

from functools import wraps
import io
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Company, Package, Subscription, User, Employee, UserRole,
    CompanyLocation
)

superadmin_bp = Blueprint("superadmin", __name__, url_prefix="/superadmin")


def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            flash("Super Administrator privileges required.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Super Admin Dashboard ──────────────────────────────────────────────────────

@superadmin_bp.route("/")
@superadmin_bp.route("/dashboard")
@login_required
@superadmin_required
def dashboard():
    total_companies = Company.query.count()
    active_companies = Company.query.filter_by(status="active").count()
    total_packages = Package.query.count()
    active_subscriptions = Subscription.query.filter_by(status="active").count()
    total_users = User.query.count()
    total_revenue = db.session.query(db.func.coalesce(db.func.sum(Subscription.amount), 0.0)).filter(
        Subscription.status == "active"
    ).scalar()

    recent_companies = Company.query.order_by(Company.id.desc()).limit(6).all()
    recent_subscriptions = Subscription.query.order_by(Subscription.id.desc()).limit(6).all()

    return render_template(
        "superadmin/dashboard.html",
        total_companies=total_companies,
        active_companies=active_companies,
        total_packages=total_packages,
        active_subscriptions=active_subscriptions,
        total_users=total_users,
        total_revenue=total_revenue,
        recent_companies=recent_companies,
        recent_subscriptions=recent_subscriptions,
    )


# ── Companies Management ───────────────────────────────────────────────────────

@superadmin_bp.route("/companies")
@login_required
@superadmin_required
def companies_list():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    plan_filter = request.args.get("plan_id", type=int)

    query = Company.query
    if q:
        query = query.filter(
            db.or_(
                Company.name.ilike(f"%{q}%"),
                Company.code.ilike(f"%{q}%"),
                Company.email.ilike(f"%{q}%"),
                Company.registration_number.ilike(f"%{q}%"),
                Company.country.ilike(f"%{q}%"),
            )
        )
    if status:
        query = query.filter(Company.status == status)
    if plan_filter:
        query = query.filter(Company.package_id == plan_filter)

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Company.id.desc()).paginate(page=page, per_page=15, error_out=False)
    packages = Package.query.filter_by(is_active=True).all()

    # Pre-gather latest active subscription expiry per company
    company_expiries = {}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for c in pagination.items:
        latest_sub = Subscription.query.filter_by(company_id=c.id).order_by(Subscription.id.desc()).first()
        company_expiries[c.id] = latest_sub.expires_at if latest_sub else None

    # Counts
    total_companies = Company.query.count()
    active_count = Company.query.filter_by(status="active").count()
    suspended_count = Company.query.filter_by(status="suspended").count()
    archived_count = Company.query.filter_by(status="archived").count()

    return render_template(
        "superadmin/companies.html",
        pagination=pagination,
        companies=pagination.items,
        packages=packages,
        company_expiries=company_expiries,
        search_q=q,
        status_filter=status,
        plan_filter=plan_filter,
        total_companies=total_companies,
        active_count=active_count,
        suspended_count=suspended_count,
        archived_count=archived_count,
        now=now,
    )


@superadmin_bp.route("/companies/create", methods=["GET", "POST"])
@superadmin_bp.route("/companies/add", methods=["POST"])
@login_required
@superadmin_required
def company_create():
    packages = Package.query.filter_by(is_active=True).all()
    if request.method == "GET":
        return render_template("superadmin/company_form.html", company=None, packages=packages)

    # POST: Handle Add Company
    return _save_company(company=None)


@superadmin_bp.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
@login_required
@superadmin_required
def company_edit(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        abort(404)
    packages = Package.query.filter_by(is_active=True).all()
    if request.method == "GET":
        return render_template("superadmin/company_form.html", company=company, packages=packages)

    # POST: Handle Edit Company
    return _save_company(company=company)


def _save_company(company=None):
    from app.employees.routes import get_upload_dir
    is_edit = company is not None

    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    reg_no = request.form.get("registration_number", "").strip()
    gstin = request.form.get("gstin", "").strip().upper()
    pan = request.form.get("pan", "").strip().upper()
    industry = request.form.get("industry", "").strip()
    website = request.form.get("website", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    country = request.form.get("country", "India").strip()
    state = request.form.get("state", "").strip()
    city = request.form.get("city", "").strip()
    pincode = request.form.get("pincode", "").strip()
    package_id = request.form.get("package_id", type=int)
    emp_limit = request.form.get("employee_limit", type=int)
    user_limit = request.form.get("user_limit", type=int)
    sub_start_str = request.form.get("subscription_start", "").strip()
    sub_end_str = request.form.get("subscription_end", "").strip()

    # Initial admin fields (for new company)
    admin_name = request.form.get("admin_name", "").strip()
    admin_email = request.form.get("admin_email", "").strip().lower()
    admin_phone = request.form.get("admin_mobile", "").strip()

    # Validations
    if not name or not code or not email:
        flash("Company Name, Unique Code, and Official Email are required.", "danger")
        return render_template("superadmin/company_form.html", company=company, packages=Package.query.filter_by(is_active=True).all())

    # Unique code check
    existing_code = Company.query.filter_by(code=code).first()
    if existing_code and (not is_edit or existing_code.id != company.id):
        flash(f"Company Code '{code}' is already assigned to another organization.", "danger")
        return render_template("superadmin/company_form.html", company=company, packages=Package.query.filter_by(is_active=True).all())

    # Date range validation
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sub_start = now
    sub_end = now + timedelta(days=365)
    if sub_start_str:
        try:
            sub_start = datetime.strptime(sub_start_str, "%Y-%m-%d")
        except ValueError:
            pass
    if sub_end_str:
        try:
            sub_end = datetime.strptime(sub_end_str, "%Y-%m-%d")
        except ValueError:
            pass

    if sub_end < sub_start:
        flash("Subscription End Date cannot precede Start Date.", "danger")
        return render_template("superadmin/company_form.html", company=company, packages=Package.query.filter_by(is_active=True).all())

    # Logo upload handling
    logo_filename = company.logo if is_edit else None
    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        sec_name = secure_filename(logo_file.filename)
        ext = os.path.splitext(sec_name)[1].lower()
        if ext in [".png", ".jpg", ".jpeg", ".svg", ".webp"]:
            import uuid
            new_logo_name = f"logo_{code}_{uuid.uuid4().hex[:6]}{ext}"
            try:
                upload_dir = get_upload_dir("avatars")
                logo_file.save(os.path.join(upload_dir, new_logo_name))
                logo_filename = new_logo_name
            except Exception as e:
                flash(f"Logo upload warning: {str(e)}", "warning")

    if not is_edit:
        company = Company()
        db.session.add(company)
        company.status = "active"

    company.name = name
    company.code = code
    company.registration_number = reg_no or None
    company.gstin = gstin or None
    company.pan = pan or None
    company.industry = industry or None
    company.website = website or None
    company.email = email
    company.phone = phone or None
    company.address = address or None
    company.country = country or "India"
    company.state = state or None
    company.city = city or None
    company.pincode = pincode or None
    company.package_id = package_id or None
    company.employee_limit = emp_limit or (Package.query.get(package_id).max_employees if package_id else None)
    company.user_limit = user_limit or (Package.query.get(package_id).max_users if package_id else None)
    if logo_filename:
        company.logo = logo_filename

    db.session.flush()

    # If new company or updated package, ensure active subscription
    if package_id and (not is_edit or not company.subscriptions.first()):
        pkg = db.session.get(Package, package_id)
        if pkg:
            sub = Subscription(
                company_id=company.id,
                package_id=pkg.id,
                billing_cycle="monthly",
                amount=pkg.price_per_month,
                status="active",
                starts_at=sub_start,
                expires_at=sub_end,
            )
            db.session.add(sub)

    # Initial admin creation if provided for new company
    if not is_edit and admin_email:
        existing_user = User.query.filter((User.username == admin_email) | (User.email == admin_email)).first()
        if not existing_user:
            uname = admin_email.split("@")[0] + f"_{company.code.lower()}"
            admin_user = User(
                username=uname,
                email=admin_email,
                password_hash=generate_password_hash("Admin@123"),
                role=UserRole.ADMIN,
                company_id=company.id,
                is_active=True,
                is_verified=True,
            )
            db.session.add(admin_user)
            db.session.flush()

            # Create employee record for this admin
            emp = Employee(
                employee_id=f"EMP_{company.code}_001",
                full_name=admin_name or name + " Admin",
                email=admin_email,
                phone=admin_phone or phone,
                company_name=company.name,
                designation="Administrator",
                user_id=admin_user.id,
            )
            db.session.add(emp)

    db.session.commit()

    action_label = "updated" if is_edit else "created"
    flash(f"Company '{name}' ({code}) {action_label} successfully.", "success")

    if request.form.get("action") == "save_and_add":
        return redirect(url_for("superadmin.company_create"))
    return redirect(url_for("superadmin.company_view", company_id=company.id))


@superadmin_bp.route("/companies/<int:company_id>/view")
@login_required
@superadmin_required
def company_view(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        abort(404)

    # Stats
    employee_count = Employee.query.filter_by(company_name=company.name).count()
    user_count = User.query.filter_by(company_id=company.id).count()
    subscriptions = Subscription.query.filter_by(company_id=company.id).order_by(Subscription.id.desc()).all()
    active_sub = Subscription.query.filter_by(company_id=company.id, status="active").order_by(Subscription.id.desc()).first()
    locations = CompanyLocation.query.filter_by(company_id=company.id).order_by(CompanyLocation.is_headquarters.desc(), CompanyLocation.id.asc()).all()
    packages = Package.query.filter_by(is_active=True).all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    return render_template(
        "superadmin/company_detail.html",
        company=company,
        employee_count=employee_count,
        user_count=user_count,
        subscriptions=subscriptions,
        active_sub=active_sub,
        locations=locations,
        packages=packages,
        now=now,
    )


@superadmin_bp.route("/companies/<int:company_id>/locations/add", methods=["POST"])
@login_required
@superadmin_required
def company_location_add(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        abort(404)

    loc_name = request.form.get("location_name", "").strip()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "").strip()
    country = request.form.get("country", "India").strip()
    pincode = request.form.get("pincode", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    is_hq = bool(request.form.get("is_headquarters"))

    if not loc_name:
        flash("Location name is required.", "danger")
        return redirect(url_for("superadmin.company_view", company_id=company.id))

    if is_hq:
        # Unset existing HQ
        CompanyLocation.query.filter_by(company_id=company.id, is_headquarters=True).update({"is_headquarters": False})

    loc = CompanyLocation(
        company_id=company.id,
        location_name=loc_name,
        address=address or None,
        city=city or None,
        state=state or None,
        country=country or "India",
        pincode=pincode or None,
        phone=phone or None,
        email=email or None,
        is_headquarters=is_hq,
    )
    db.session.add(loc)
    db.session.commit()
    flash(f"Location '{loc_name}' added to {company.name}.", "success")
    return redirect(url_for("superadmin.company_view", company_id=company.id))


@superadmin_bp.route("/companies/<int:company_id>/locations/<int:loc_id>/delete", methods=["POST"])
@login_required
@superadmin_required
def company_location_delete(company_id, loc_id):
    loc = db.session.get(CompanyLocation, loc_id)
    if not loc or loc.company_id != company_id:
        abort(404)
    name = loc.location_name
    db.session.delete(loc)
    db.session.commit()
    flash(f"Location '{name}' removed.", "info")
    return redirect(url_for("superadmin.company_view", company_id=company_id))


@superadmin_bp.route("/companies/<int:company_id>/toggle-status", methods=["POST"])
@login_required
@superadmin_required
def company_toggle_status(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        abort(404)
    company.status = "suspended" if company.status == "active" else "active"
    db.session.commit()
    flash(f"Company '{company.name}' status updated to {company.status.upper()}.", "info")
    # Redirect back to caller (view or list)
    ref = request.referrer
    if ref and f"/companies/{company_id}/view" in ref:
        return redirect(url_for("superadmin.company_view", company_id=company.id))
    return redirect(url_for("superadmin.companies_list"))


@superadmin_bp.route("/companies/<int:company_id>/archive", methods=["POST"])
@login_required
@superadmin_required
def company_archive(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        abort(404)
    company.status = "archived" if company.status != "archived" else "active"
    db.session.commit()
    state_str = "Archived" if company.status == "archived" else "Restored to Active"
    flash(f"Company '{company.name}' has been {state_str}.", "info")
    return redirect(url_for("superadmin.companies_list"))


@superadmin_bp.route("/companies/<int:company_id>/delete", methods=["POST"])
@login_required
@superadmin_required
def company_delete(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        abort(404)

    # Check dependent records
    user_count = User.query.filter_by(company_id=company.id).count()
    emp_count = Employee.query.filter_by(company_name=company.name).count()
    sub_count = Subscription.query.filter_by(company_id=company.id).count()

    if user_count > 0 or emp_count > 0 or sub_count > 0:
        flash(
            f"Cannot delete company '{company.name}' because it has {user_count} user(s), "
            f"{emp_count} employee(s), and {sub_count} subscription record(s). "
            f"Please suspend or archive the company instead to preserve operational data.",
            "danger"
        )
        return redirect(url_for("superadmin.companies_list"))

    db.session.delete(company)
    db.session.commit()
    flash(f"Company '{company.name}' deleted successfully.", "success")
    return redirect(url_for("superadmin.companies_list"))


@superadmin_bp.route("/companies/export/excel")
@login_required
@superadmin_required
def companies_export_excel():
    """Export companies directory to formatted Excel (.xlsx) spreadsheet."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    companies = Company.query.order_by(Company.id.asc()).all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Companies Directory"

    # Styling
    navy_fill = PatternFill(start_color="0B192C", end_color="0B192C", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    headers = [
        "Company ID", "Company Name", "Code", "Reg. Number", "Official Email",
        "Phone", "Country", "State", "City", "Subscription Plan",
        "Status", "Registered Date"
    ]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = navy_fill
        cell.font = header_font
        cell.alignment = align_center

    for c in companies:
        pkg_name = c.package.name if c.package else "None"
        created_str = c.created_at.strftime("%Y-%m-%d") if c.created_at else "—"
        row_data = [
            f"CMP-{c.id:04d}",
            c.name,
            c.code,
            c.registration_number or "—",
            c.email,
            c.phone or "—",
            c.country or "India",
            c.state or "—",
            c.city or "—",
            pkg_name,
            c.status.upper(),
            created_str,
        ]
        ws.append(row_data)

    # Format cells & column widths
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = thin_border
            cell.alignment = align_left

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"EBT System_Companies_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


# ── Packages & Subscription Plans Management ───────────────────────────────────

@superadmin_bp.route("/packages")
@login_required
@superadmin_required
def packages_list():
    packages = Package.query.order_by(Package.price_per_month.asc()).all()
    # Compute active subscriptions count per package
    sub_counts = {}
    for p in packages:
        sub_counts[p.id] = Subscription.query.filter_by(package_id=p.id).count()

    standard_features = [
        "Attendance Timesheets & GPS Check-in",
        "Break Tracking & Monitoring",
        "Leave Approvals & Policy Config",
        "Automated Payroll & Payslip PDF",
        "AI Availability Prediction & Telemetry",
        "Employee Self-Service (ESS) & Document Vault",
        "Corporate Reports & Excel Export",
        "Custom RBAC Roles & Permissions",
    ]

    return render_template(
        "superadmin/packages.html",
        packages=packages,
        sub_counts=sub_counts,
        standard_features=standard_features
    )


@superadmin_bp.route("/packages/save", methods=["POST"])
@login_required
@superadmin_required
def package_save():
    import json
    pkg_id = request.form.get("package_id", type=int)
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    description = request.form.get("description", "").strip()
    billing_cycle = request.form.get("billing_cycle", "monthly").strip()
    price_mo = request.form.get("price_per_month", 0.0, type=float)
    price_yr = request.form.get("price_per_year", 0.0, type=float)
    max_emp = request.form.get("max_employees", 25, type=int)
    max_users = request.form.get("max_users", 5, type=int)
    max_storage = request.form.get("max_storage_mb", 500, type=int)
    trial_days = request.form.get("trial_period_days", 14, type=int)

    # Collect selected module features
    selected_features = request.form.getlist("features[]")
    custom_features_str = request.form.get("custom_features", "").strip()
    if custom_features_str:
        for f in custom_features_str.split("\n"):
            f_clean = f.strip().strip("-•* ")
            if f_clean and f_clean not in selected_features:
                selected_features.append(f_clean)

    if not name or not code:
        flash("Package name and unique code are required.", "danger")
        return redirect(url_for("superadmin.packages_list"))

    if price_mo < 0 or price_yr < 0 or max_emp < 1:
        flash("Pricing must be non-negative and employee limit must be at least 1.", "warning")
        return redirect(url_for("superadmin.packages_list"))

    if pkg_id:
        pkg = db.session.get(Package, pkg_id)
        if not pkg:
            abort(404)
        # Check code uniqueness if changing code
        existing = Package.query.filter_by(code=code).first()
        if existing and existing.id != pkg.id:
            flash(f"Package code '{code}' is already used by another package.", "danger")
            return redirect(url_for("superadmin.packages_list"))
    else:
        if Package.query.filter_by(code=code).first():
            flash(f"Package code '{code}' already exists.", "danger")
            return redirect(url_for("superadmin.packages_list"))
        pkg = Package()
        db.session.add(pkg)

    pkg.name = name
    pkg.code = code
    pkg.description = description or None
    pkg.billing_cycle = billing_cycle
    pkg.price_per_month = price_mo
    pkg.price_per_year = price_yr
    pkg.max_employees = max_emp
    pkg.max_users = max(1, max_users)
    pkg.max_storage_mb = max_storage
    pkg.trial_period_days = max(0, trial_days)
    pkg.features_json = json.dumps(selected_features) if selected_features else None
    if pkg_id is None:
        pkg.is_active = True

    db.session.commit()
    flash(f"Package plan '{name}' saved successfully.", "success")
    return redirect(url_for("superadmin.packages_list"))


@superadmin_bp.route("/packages/<int:pkg_id>/duplicate", methods=["POST"])
@login_required
@superadmin_required
def package_duplicate(pkg_id):
    """Duplicate an existing plan into a new draft package."""
    orig = db.session.get(Package, pkg_id)
    if not orig:
        abort(404)

    import uuid
    suffix = uuid.uuid4().hex[:4].upper()
    new_code = f"{orig.code}_COPY_{suffix}"[:45]
    new_name = f"{orig.name} (Copy {suffix})"[:95]

    dup = Package(
        name=new_name,
        code=new_code,
        description=orig.description,
        billing_cycle=orig.billing_cycle,
        price_per_month=orig.price_per_month,
        price_per_year=orig.price_per_year,
        max_employees=orig.max_employees,
        max_users=orig.max_users,
        max_storage_mb=orig.max_storage_mb,
        trial_period_days=orig.trial_period_days,
        features_json=orig.features_json,
        is_active=False,  # default to inactive draft
    )
    db.session.add(dup)
    db.session.commit()
    flash(f"Package duplicated successfully as '{new_name}'. You may now customize its pricing and feature limits.", "success")
    return redirect(url_for("superadmin.packages_list"))


@superadmin_bp.route("/packages/<int:pkg_id>/toggle-status", methods=["POST"])
@login_required
@superadmin_required
def package_toggle_status(pkg_id):
    pkg = db.session.get(Package, pkg_id)
    if not pkg:
        abort(404)
    pkg.is_active = not pkg.is_active
    db.session.commit()
    status_label = "ACTIVATED" if pkg.is_active else "DEACTIVATED"
    flash(f"Package '{pkg.name}' is now {status_label}.", "info")
    return redirect(url_for("superadmin.packages_list"))


@superadmin_bp.route("/packages/<int:pkg_id>/delete", methods=["POST"])
@login_required
@superadmin_required
def package_delete(pkg_id):
    pkg = db.session.get(Package, pkg_id)
    if not pkg:
        abort(404)

    # Check references from both companies and subscriptions
    linked_subs = Subscription.query.filter_by(package_id=pkg.id).count()
    linked_companies = Company.query.filter_by(package_id=pkg.id).count()

    if linked_subs > 0 or linked_companies > 0:
        flash(
            f"Cannot delete package '{pkg.name}' because it has {linked_subs} subscription(s) "
            f"and {linked_companies} company assignment(s). You can deactivate it instead to retire the tier safely.",
            "danger"
        )
        return redirect(url_for("superadmin.packages_list"))

    db.session.delete(pkg)
    db.session.commit()
    flash(f"Package '{pkg.name}' deleted successfully.", "success")
    return redirect(url_for("superadmin.packages_list"))


# ── Subscriptions Management ───────────────────────────────────────────────────

@superadmin_bp.route("/subscriptions")
@login_required
@superadmin_required
def subscriptions_list():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    pkg_filter = request.args.get("package_id", type=int)
    sort_by = request.args.get("sort_by", "newest").strip()

    query = Subscription.query.join(Company, Subscription.company_id == Company.id)
    if q:
        query = query.filter(
            db.or_(
                Company.name.ilike(f"%{q}%"),
                Company.code.ilike(f"%{q}%"),
                Company.email.ilike(f"%{q}%"),
            )
        )
    if status:
        query = query.filter(Subscription.status == status)
    if pkg_filter:
        query = query.filter(Subscription.package_id == pkg_filter)

    # Sorting
    if sort_by == "expires_asc":
        query = query.order_by(Subscription.expires_at.asc())
    elif sort_by == "expires_desc":
        query = query.order_by(Subscription.expires_at.desc())
    elif sort_by == "amount_desc":
        query = query.order_by(Subscription.amount.desc())
    elif sort_by == "company_name":
        query = query.order_by(Company.name.asc())
    else:
        query = query.order_by(Subscription.id.desc())

    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=15, error_out=False)

    # Metric counts
    total_subs = Subscription.query.count()
    active_count = Subscription.query.filter_by(status="active").count()
    pending_count = Subscription.query.filter_by(status="pending").count()
    expired_count = Subscription.query.filter_by(status="expired").count()
    cancelled_count = Subscription.query.filter_by(status="cancelled").count()

    companies = Company.query.order_by(Company.name.asc()).all()
    packages = Package.query.order_by(Package.name.asc()).all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    return render_template(
        "superadmin/subscriptions.html",
        pagination=pagination,
        subscriptions=pagination.items,
        companies=companies,
        packages=packages,
        search_q=q,
        status_filter=status,
        pkg_filter=pkg_filter,
        sort_by=sort_by,
        total_subs=total_subs,
        active_count=active_count,
        pending_count=pending_count,
        expired_count=expired_count,
        cancelled_count=cancelled_count,
        now=now,
    )


@superadmin_bp.route("/subscriptions/add", methods=["POST"])
@login_required
@superadmin_required
def subscription_add():
    company_id = request.form.get("company_id", type=int)
    package_id = request.form.get("package_id", type=int)
    cycle = request.form.get("billing_cycle", "monthly")
    amount = request.form.get("amount", type=float)
    status = request.form.get("status", "active")

    if not company_id or not package_id:
        flash("Company and Package selection are required.", "danger")
        return redirect(url_for("superadmin.subscriptions_list"))

    company = db.session.get(Company, company_id)
    pkg = db.session.get(Package, package_id)
    if not company or not pkg:
        flash("Invalid Company or Package selected.", "danger")
        return redirect(url_for("superadmin.subscriptions_list"))

    # Compute accurate price if not explicitly overridden
    if amount is None or amount <= 0:
        amount = pkg.price_per_year if cycle == "yearly" else pkg.price_per_month

    days = 365 if cycle == "yearly" else 30
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # If activating new subscription, mark any currently active company subscriptions as superseded/cancelled
    if status == "active":
        active_subs = Subscription.query.filter_by(company_id=company_id, status="active").all()
        for old_sub in active_subs:
            old_sub.status = "expired" if old_sub.expires_at and old_sub.expires_at < now else "cancelled"
        # Sync company package_id
        company.package_id = package_id

    sub = Subscription(
        company_id=company_id,
        package_id=package_id,
        billing_cycle=cycle,
        amount=amount,
        status=status,
        starts_at=now,
        expires_at=now + timedelta(days=days),
    )
    db.session.add(sub)
    db.session.commit()

    flash(f"Subscription generated and activated for '{company.name}' with package '{pkg.name}' ({cycle.title()}).", "success")
    return redirect(url_for("superadmin.subscriptions_list"))


@superadmin_bp.route("/subscriptions/<int:sub_id>/renew", methods=["POST"])
@login_required
@superadmin_required
def subscription_renew(sub_id):
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        abort(404)

    extension_type = request.form.get("extension_type", "auto")  # auto, 30, 90, 365, custom
    custom_expiry_str = request.form.get("custom_expiry", "").strip()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    base_date = sub.expires_at if sub.expires_at and sub.expires_at > now else now

    if extension_type == "custom" and custom_expiry_str:
        try:
            from datetime import datetime as dt
            new_expiry = dt.strptime(custom_expiry_str, "%Y-%m-%d")
        except ValueError:
            flash("Invalid custom date format. Use YYYY-MM-DD.", "warning")
            return redirect(url_for("superadmin.subscriptions_list"))
    elif extension_type in ["30", "90", "365"]:
        new_expiry = base_date + timedelta(days=int(extension_type))
    else:
        # Default based on billing cycle
        days = 365 if sub.billing_cycle == "yearly" else 30
        new_expiry = base_date + timedelta(days=days)

    # Create a renewal record preserving full history
    new_sub = Subscription(
        company_id=sub.company_id,
        package_id=sub.package_id,
        billing_cycle=sub.billing_cycle,
        amount=sub.amount,
        status="active",
        starts_at=base_date,
        expires_at=new_expiry,
    )
    # Mark old subscription as completed/renewed
    sub.status = "expired" if sub.expires_at and sub.expires_at <= now else "cancelled"
    db.session.add(new_sub)
    db.session.commit()

    flash(f"Subscription renewed until {new_expiry.strftime('%Y-%m-%d')} for '{sub.company.name}'.", "success")
    return redirect(url_for("superadmin.subscriptions_list"))


@superadmin_bp.route("/subscriptions/<int:sub_id>/change-plan", methods=["POST"])
@login_required
@superadmin_required
def subscription_change_plan(sub_id):
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        abort(404)

    new_pkg_id = request.form.get("new_package_id", type=int)
    cycle = request.form.get("billing_cycle", sub.billing_cycle)
    new_pkg = db.session.get(Package, new_pkg_id)
    if not new_pkg:
        flash("Selected package does not exist.", "danger")
        return redirect(url_for("superadmin.subscriptions_list"))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    days = 365 if cycle == "yearly" else 30
    amount = new_pkg.price_per_year if cycle == "yearly" else new_pkg.price_per_month

    # Retire current subscription preserving history
    sub.status = "cancelled"

    # Create new subscription
    new_sub = Subscription(
        company_id=sub.company_id,
        package_id=new_pkg.id,
        billing_cycle=cycle,
        amount=amount,
        status="active",
        starts_at=now,
        expires_at=now + timedelta(days=days),
    )
    # Sync company package
    if sub.company:
        sub.company.package_id = new_pkg.id

    db.session.add(new_sub)
    db.session.commit()

    flash(f"Plan changed to '{new_pkg.name}' for company '{sub.company.name}'.", "success")
    return redirect(url_for("superadmin.subscriptions_list"))


@superadmin_bp.route("/subscriptions/<int:sub_id>/update-status", methods=["POST"])
@login_required
@superadmin_required
def subscription_update_status(sub_id):
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        abort(404)

    new_status = request.form.get("status", sub.status).strip()
    starts_at_str = request.form.get("starts_at", "").strip()
    expires_at_str = request.form.get("expires_at", "").strip()

    if new_status in ["active", "pending", "expired", "cancelled"]:
        sub.status = new_status

    if starts_at_str:
        try:
            from datetime import datetime as dt
            sub.starts_at = dt.strptime(starts_at_str, "%Y-%m-%d")
        except ValueError:
            pass

    if expires_at_str:
        try:
            from datetime import datetime as dt
            sub.expires_at = dt.strptime(expires_at_str, "%Y-%m-%d")
        except ValueError:
            pass

    db.session.commit()
    flash(f"Subscription #{sub.id} updated successfully.", "success")
    return redirect(url_for("superadmin.subscriptions_list"))


@superadmin_bp.route("/subscriptions/<int:sub_id>/cancel", methods=["POST"])
@login_required
@superadmin_required
def subscription_cancel(sub_id):
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        abort(404)

    sub.status = "cancelled"
    db.session.commit()
    flash(f"Subscription #{sub.id} for '{sub.company.name}' has been cancelled.", "info")
    return redirect(url_for("superadmin.subscriptions_list"))


@superadmin_bp.route("/companies/<int:company_id>/subscriptions-history")
@login_required
@superadmin_required
def company_subscriptions_history(company_id):
    """View full chronological subscription history for a given company."""
    company = db.session.get(Company, company_id)
    if not company:
        abort(404)

    history = Subscription.query.filter_by(company_id=company.id).order_by(Subscription.id.desc()).all()
    packages = Package.query.filter_by(is_active=True).all()

    return render_template(
        "superadmin/subscription_history.html",
        company=company,
        history=history,
        packages=packages
    )
