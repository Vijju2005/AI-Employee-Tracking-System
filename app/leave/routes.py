"""
EBT System – Leave Routes
"""

from datetime import date, datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import LeaveRequest, LeaveType, LeaveDayType, LeaveStatus, Employee, UserRole
from app.email import send_leave_status_email

leave_bp = Blueprint("leave", __name__, url_prefix="/leave")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@leave_bp.route("/")
@login_required
def index():
    status_filter = request.args.get("status")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

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
