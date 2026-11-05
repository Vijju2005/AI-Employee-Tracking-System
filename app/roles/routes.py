"""
EBT System — Roles & Permissions Blueprint (RBAC)
Enterprise User & Access Management:
- Dynamic Role Management (Super Admin, Admin, HR Manager, Team Lead, Employee)
- Permission Management (module-based permissions like users, attendance, payroll, reports)
- Role-Permission Matrix (Assign granular permissions to roles)
- User-Role Assignment
"""

from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Role, Permission, User, user_roles, role_permissions

roles_bp = Blueprint("roles", __name__, url_prefix="/roles")


def admin_or_rbac_required(permission_slug=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            # Super Admin has unrestricted access
            if current_user.is_superadmin:
                return f(*args, **kwargs)
            # Admin has management access
            if current_user.is_admin:
                return f(*args, **kwargs)
            # Granular check
            if permission_slug and current_user.has_permission(permission_slug):
                return f(*args, **kwargs)
            flash("You do not possess the required permissions to perform this operation.", "danger")
            abort(403)
        return decorated
    return decorator


# ── Roles Overview & List ──────────────────────────────────────────────────────

@roles_bp.route("/")
@login_required
@admin_or_rbac_required("manage_roles")
def index():
    roles = Role.query.order_by(Role.id.asc()).all()
    permissions = Permission.query.order_by(Permission.module.asc(), Permission.name.asc()).all()
    # Group permissions by module
    modules = {}
    for p in permissions:
        modules.setdefault(p.module.title(), []).append(p)

    return render_template("roles/index.html", roles=roles, permissions=permissions, modules=modules)


@roles_bp.route("/add", methods=["POST"])
@login_required
@admin_or_rbac_required("manage_roles")
def add_role():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    permission_ids = request.form.getlist("permission_ids", type=int)

    if not name:
        flash("Role name is required.", "danger")
        return redirect(url_for("roles.index"))

    if Role.query.filter_by(name=name).first():
        flash(f"Role '{name}' already exists.", "danger")
        return redirect(url_for("roles.index"))

    role = Role(name=name, description=description, is_system=False)
    if permission_ids:
        selected_perms = Permission.query.filter(Permission.id.in_(permission_ids)).all()
        role.permissions = selected_perms

    db.session.add(role)
    db.session.commit()
    flash(f"Role '{name}' created successfully.", "success")
    return redirect(url_for("roles.index"))


@roles_bp.route("/<int:role_id>/edit", methods=["POST"])
@login_required
@admin_or_rbac_required("manage_roles")
def edit_role(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        abort(404)

    description = request.form.get("description", "").strip()
    permission_ids = request.form.getlist("permission_ids", type=int)

    # Allow editing name only if not a system role
    if not role.is_system:
        name = request.form.get("name", "").strip()
        if name:
            role.name = name

    role.description = description
    selected_perms = Permission.query.filter(Permission.id.in_(permission_ids)).all() if permission_ids else []
    role.permissions = selected_perms

    db.session.commit()
    flash(f"Role '{role.name}' permissions updated successfully.", "success")
    return redirect(url_for("roles.index"))


# ── Permissions Management ─────────────────────────────────────────────────────

@roles_bp.route("/permissions")
@login_required
@admin_or_rbac_required("manage_permissions")
def permissions_list():
    permissions = Permission.query.order_by(Permission.module.asc(), Permission.name.asc()).all()
    modules = {}
    for p in permissions:
        modules.setdefault(p.module.title(), []).append(p)
    return render_template("roles/permissions.html", permissions=permissions, modules=modules)


@roles_bp.route("/permissions/add", methods=["POST"])
@login_required
@admin_or_rbac_required("manage_permissions")
def add_permission():
    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip().lower().replace(" ", "_")
    module = request.form.get("module", "general").strip().lower()
    description = request.form.get("description", "").strip()

    if not name or not slug:
        flash("Permission name and slug identifier are required.", "danger")
        return redirect(url_for("roles.permissions_list"))

    if Permission.query.filter_by(slug=slug).first():
        flash(f"Permission identifier '{slug}' already exists.", "danger")
        return redirect(url_for("roles.permissions_list"))

    perm = Permission(name=name, slug=slug, module=module, description=description)
    db.session.add(perm)
    db.session.commit()
    flash(f"Permission '{name}' added successfully.", "success")
    return redirect(url_for("roles.permissions_list"))


# ── User Role Assignments ──────────────────────────────────────────────────────

@roles_bp.route("/users")
@login_required
@admin_or_rbac_required("manage_users")
def user_roles_list():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        query = query.filter(
            db.or_(
                User.username.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
            )
        )
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(User.id.asc()).paginate(page=page, per_page=15, error_out=False)
    roles = Role.query.order_by(Role.name.asc()).all()

    return render_template(
        "roles/user_assignments.html",
        pagination=pagination,
        users=pagination.items,
        roles=roles,
        search_q=q,
    )


@roles_bp.route("/users/<int:user_id>/assign", methods=["POST"])
@login_required
@admin_or_rbac_required("manage_users")
def assign_user_roles(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    role_ids = request.form.getlist("role_ids", type=int)
    selected_roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
    user.roles = selected_roles

    # Optional 2FA switch toggle per user
    user.two_factor_enabled = request.form.get("two_factor_enabled") == "on"

    db.session.commit()
    flash(f"Roles updated for user '{user.username}'.", "success")
    return redirect(url_for("roles.user_roles_list"))
