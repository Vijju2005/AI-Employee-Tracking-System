"""
EBT System — Super Admin Blueprint
Enterprise SaaS Administration:
- Multi-tenant Super Admin Dashboard & KPIs
- Companies Management (create, view, edit, suspend, activate)
- Packages Management (tier configuration, limits, monthly/yearly pricing)
- Subscriptions Management (tenant subscriptions, renewal, status tracking)
"""

from functools import wraps
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Company, Package, Subscription, User, Employee, UserRole

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

    query = Company.query
    if q:
        query = query.filter(
            db.or_(
                Company.name.ilike(f"%{q}%"),
                Company.code.ilike(f"%{q}%"),
                Company.email.ilike(f"%{q}%"),
            )
        )
    if status:
        query = query.filter(Company.status == status)

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Company.id.desc()).paginate(page=page, per_page=15, error_out=False)
    packages = Package.query.filter_by(is_active=True).all()

    return render_template(
        "superadmin/companies.html",
        pagination=pagination,
        companies=pagination.items,
        packages=packages,
        search_q=q,
        status_filter=status,
    )


@superadmin_bp.route("/companies/add", methods=["POST"])
@login_required
@superadmin_required
def company_add():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    package_id = request.form.get("package_id", type=int)
    address = request.form.get("address", "").strip()

    if not name or not code or not email:
        flash("Company name, unique code, and official email are required.", "danger")
        return redirect(url_for("superadmin.companies_list"))

    if Company.query.filter_by(code=code).first():
        flash(f"Company code '{code}' is already registered.", "danger")
        return redirect(url_for("superadmin.companies_list"))

    company = Company(
        name=name,
        code=code,
        email=email,
        phone=phone,
        package_id=package_id,
        address=address,
        status="active",
    )
    db.session.add(company)
    db.session.flush()

    # Automatically create starter subscription if package selected
    if package_id:
        pkg = db.session.get(Package, package_id)
        if pkg:
            sub = Subscription(
                company_id=company.id,
                package_id=pkg.id,
                billing_cycle="monthly",
                amount=pkg.price_per_month,
                status="active",
                starts_at=datetime.now(timezone.utc).replace(tzinfo=None),
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30),
            )
            db.session.add(sub)

    db.session.commit()
    flash(f"Company '{name}' ({code}) registered successfully.", "success")
    return redirect(url_for("superadmin.companies_list"))


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
    return redirect(url_for("superadmin.companies_list"))


# ── Packages Management ────────────────────────────────────────────────────────

@superadmin_bp.route("/packages")
@login_required
@superadmin_required
def packages_list():
    packages = Package.query.order_by(Package.price_per_month.asc()).all()
    return render_template("superadmin/packages.html", packages=packages)


@superadmin_bp.route("/packages/save", methods=["POST"])
@login_required
@superadmin_required
def package_save():
    pkg_id = request.form.get("package_id", type=int)
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    price_mo = request.form.get("price_per_month", 0.0, type=float)
    price_yr = request.form.get("price_per_year", 0.0, type=float)
    max_emp = request.form.get("max_employees", 25, type=int)
    max_storage = request.form.get("max_storage_mb", 500, type=int)
    features = request.form.get("features_json", "").strip()

    if not name or not code:
        flash("Package name and unique code are required.", "danger")
        return redirect(url_for("superadmin.packages_list"))

    if pkg_id:
        pkg = db.session.get(Package, pkg_id)
        if not pkg:
            abort(404)
    else:
        if Package.query.filter_by(code=code).first():
            flash(f"Package code '{code}' already exists.", "danger")
            return redirect(url_for("superadmin.packages_list"))
        pkg = Package()
        db.session.add(pkg)

    pkg.name = name
    pkg.code = code
    pkg.price_per_month = price_mo
    pkg.price_per_year = price_yr
    pkg.max_employees = max_emp
    pkg.max_storage_mb = max_storage
    pkg.features_json = features
    pkg.is_active = True

    db.session.commit()
    flash(f"Package '{name}' saved successfully.", "success")
    return redirect(url_for("superadmin.packages_list"))


# ── Subscriptions Management ───────────────────────────────────────────────────

@superadmin_bp.route("/subscriptions")
@login_required
@superadmin_required
def subscriptions_list():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = Subscription.query.join(Company, Subscription.company_id == Company.id)
    if q:
        query = query.filter(
            db.or_(
                Company.name.ilike(f"%{q}%"),
                Company.code.ilike(f"%{q}%"),
            )
        )
    if status:
        query = query.filter(Subscription.status == status)

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Subscription.id.desc()).paginate(page=page, per_page=15, error_out=False)

    companies = Company.query.filter_by(status="active").all()
    packages = Package.query.filter_by(is_active=True).all()

    return render_template(
        "superadmin/subscriptions.html",
        pagination=pagination,
        subscriptions=pagination.items,
        companies=companies,
        packages=packages,
        search_q=q,
        status_filter=status,
    )


@superadmin_bp.route("/subscriptions/add", methods=["POST"])
@login_required
@superadmin_required
def subscription_add():
    company_id = request.form.get("company_id", type=int)
    package_id = request.form.get("package_id", type=int)
    cycle = request.form.get("billing_cycle", "monthly")
    amount = request.form.get("amount", type=float)

    if not company_id or not package_id:
        flash("Company and Package selection are required.", "danger")
        return redirect(url_for("superadmin.subscriptions_list"))

    pkg = db.session.get(Package, package_id)
    if not amount and pkg:
        amount = pkg.price_per_year if cycle == "yearly" else pkg.price_per_month

    days = 365 if cycle == "yearly" else 30
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    sub = Subscription(
        company_id=company_id,
        package_id=package_id,
        billing_cycle=cycle,
        amount=amount or 0.0,
        status="active",
        starts_at=now,
        expires_at=now + timedelta(days=days),
    )
    db.session.add(sub)
    db.session.commit()

    flash("Subscription generated and activated.", "success")
    return redirect(url_for("superadmin.subscriptions_list"))


@superadmin_bp.route("/subscriptions/<int:sub_id>/renew", methods=["POST"])
@login_required
@superadmin_required
def subscription_renew(sub_id):
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        abort(404)
    days = 365 if sub.billing_cycle == "yearly" else 30
    base_date = sub.expires_at if sub.expires_at and sub.expires_at > datetime.now(timezone.utc).replace(tzinfo=None) else datetime.now(timezone.utc).replace(tzinfo=None)
    sub.expires_at = base_date + timedelta(days=days)
    sub.status = "active"
    db.session.commit()
    flash(f"Subscription renewed until {sub.expires_at.strftime('%Y-%m-%d')}.", "success")
    return redirect(url_for("superadmin.subscriptions_list"))
