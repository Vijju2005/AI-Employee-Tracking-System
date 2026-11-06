"""
EBT System – Leave Routes
"""

from datetime import date, datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import LeaveRequest, LeaveType, LeaveDayType, LeaveStatus, Employee, UserRole, LeaveTypePolicy
from app.email import send_leave_status_email
from app.time_utils import parse_iso_date

leave_bp = Blueprint("leave", __name__, url_prefix="/leave")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@leave_bp.route("/")
@login_required
def index():
    status_filter = request.args.get("status")
    from_date = parse_iso_date(request.args.get("from_date"))
    to_date = parse_iso_date(request.args.get("to_date"))

    query = LeaveRequest.query

    if not current_user.is_admin:
        emp = current_user.employee
        if emp:
            query = query.filter_by(employee_id=emp.id)
        else:
            query = query.filter(db.false())

    if status_filter:
        try:
            query = query.filter_by(status=LeaveStatus(status_filter))
        except ValueError:
            pass
    if from_date:
        query = query.filter(LeaveRequest.start_date >= from_date)
    if to_date:
        query = query.filter(LeaveRequest.end_date <= to_date)

    leave_requests = query.order_by(LeaveRequest.created_at.desc()).limit(200).all()
    return render_template("leave/index.html", leave_requests=leave_requests)


@leave_bp.route("/apply", methods=["GET", "POST"])
@login_required
def apply():
    if current_user.is_admin:
        flash("Admins cannot apply for leave.", "warning")
        return redirect(url_for("dashboard.admin_dashboard"))

    error = None
    if request.method == "POST":
        leave_type_val = request.form.get("leave_type", "")
        start_date_str = request.form.get("start_date", "")
        end_date_str = request.form.get("end_date", "")
        day_type_val = request.form.get("day_type", "Full Day")
        reason = request.form.get("reason", "").strip()

        if not all([leave_type_val, start_date_str, end_date_str, reason]):
            error = "All required fields must be filled."
        else:
            try:
                leave_type = LeaveType(leave_type_val)
                day_type = LeaveDayType(day_type_val)
                start_date = date.fromisoformat(start_date_str)
                end_date = date.fromisoformat(end_date_str)
            except (ValueError, TypeError) as e:
                error = f"Invalid data: {e}"
            else:
                if end_date < start_date:
                    error = "End date cannot be before start date."
                else:
                    emp = current_user.employee
                    if not emp:
                        error = "No employee record linked to your account."
                    else:
                        lr = LeaveRequest(
                            employee_id=emp.id,
                            leave_type=leave_type,
                            day_type=day_type,
                            start_date=start_date,
                            end_date=end_date,
                            reason=reason,
                            status=LeaveStatus.PENDING,
                        )
                        db.session.add(lr)
                        db.session.commit()
                        flash("Leave request submitted successfully.", "success")
                        return redirect(url_for("leave.index"))

    return render_template("leave/apply.html", error=error)


@leave_bp.route("/<int:leave_id>/review", methods=["GET", "POST"])
@login_required
def review(leave_id):
    if not current_user.is_admin:
        abort(403)

    leave = LeaveRequest.query.get_or_404(leave_id)

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        admin_notes = request.form.get("admin_notes", "").strip()

        if leave.status != LeaveStatus.PENDING:
            flash(f"This leave request has already been processed as {leave.status.value}.", "warning")
            return redirect(url_for("leave.index"))

        if action == "approve":
            leave.status = LeaveStatus.APPROVED
            msg = f"Leave request for {leave.employee.full_name} has been approved."
        elif action == "reject":
            leave.status = LeaveStatus.REJECTED
            msg = f"Leave request for {leave.employee.full_name} has been rejected."
        else:
            flash("Invalid action.", "danger")
            return redirect(url_for("leave.review", leave_id=leave_id))

        leave.reviewed_by_id = current_user.id
        leave.reviewed_at = _utcnow()
        leave.admin_notes = admin_notes or None
        db.session.commit()

        # Send email notification to employee
        send_leave_status_email(leave)

        flash(msg, "success")
        return redirect(url_for("leave.index"))

    return render_template("leave/review.html", leave=leave)


# ── Leave Policy Settings ───────────────────────────────────────────────────

@leave_bp.route("/policies")
@login_required
def policies_list():
    """List and manage corporate leave policies and allocation allowances."""
    if not current_user.is_admin:
        abort(403)

    # Seed default baseline policies idempotently if empty
    if LeaveTypePolicy.query.count() == 0:
        default_policies = [
            {"name": "Paid Annual Leave", "code": "ANNUAL", "annual_allocation_days": 18, "carry_forward_max_days": 5, "is_paid": True, "description": "Standard earned annual vacation"},
            {"name": "Sick & Medical Leave", "code": "SICK", "annual_allocation_days": 10, "carry_forward_max_days": 0, "is_paid": True, "description": "Medical recuperation and illness recovery"},
            {"name": "Casual Personal Leave", "code": "CASUAL", "annual_allocation_days": 8, "carry_forward_max_days": 0, "is_paid": True, "description": "Urgent personal affairs and family matters"},
            {"name": "Unpaid Leave of Absence", "code": "UNPAID", "annual_allocation_days": 0, "carry_forward_max_days": 0, "is_paid": False, "description": "Extended time off without compensation"},
        ]
        for p in default_policies:
            db.session.add(LeaveTypePolicy(**p))
        db.session.commit()

    policies = LeaveTypePolicy.query.order_by(LeaveTypePolicy.name.asc()).all()
    return render_template("leave/policies.html", policies=policies)


@leave_bp.route("/policies/add", methods=["POST"])
@login_required
def add_policy():
    """Create a new leave policy rule."""
    if not current_user.is_admin:
        abort(403)

    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    allocation = request.form.get("annual_allocation_days", 12, type=int)
    carry_forward = request.form.get("carry_forward_max_days", 0, type=int)
    is_paid = request.form.get("is_paid") in ["1", "on", "true", "True"]
    description = request.form.get("description", "").strip()

    if not name or not code:
        flash("Policy name and code identifier are required.", "danger")
        return redirect(url_for("leave.policies_list"))

    if LeaveTypePolicy.query.filter((LeaveTypePolicy.name == name) | (LeaveTypePolicy.code == code)).first():
        flash("A leave policy with this name or code already exists.", "warning")
        return redirect(url_for("leave.policies_list"))

    pol = LeaveTypePolicy(
        name=name,
        code=code,
        annual_allocation_days=allocation,
        carry_forward_max_days=carry_forward,
        is_paid=is_paid,
        description=description
    )
    db.session.add(pol)
    db.session.commit()
    flash(f"Leave policy '{name}' configured successfully.", "success")
    return redirect(url_for("leave.policies_list"))

