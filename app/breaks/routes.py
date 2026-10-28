"""
EBT System – Break Routes
"""

from datetime import datetime, timezone, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Attendance, Break, BreakCategory, Employee, UserRole
from app.time_utils import utc_now, local_today, format_mins

breaks_bp = Blueprint("breaks", __name__, url_prefix="/breaks")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@breaks_bp.route("/")
@login_required
def index():
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    category_filter = request.args.get("category")

    query = Break.query

    if not current_user.is_admin:
        if current_user.employee:
            query = query.filter(Break.employee_id == current_user.employee.id)
        else:
            query = query.filter(db.false())

    if from_date:
        query = query.filter(Break.start_time >= from_date)
    if to_date:
        query = query.filter(Break.start_time <= (to_date + " 23:59:59"))
    if category_filter:
        query = query.filter(Break.category == category_filter)

    breaks = query.order_by(Break.start_time.desc()).limit(200).all()
    return render_template("breaks/index.html", breaks=breaks)


@breaks_bp.route("/start", methods=["POST"])
@login_required
def start():
    employee = current_user.employee
    if not employee:
        flash("No employee record linked.", "danger")
        return redirect(url_for("dashboard.employee_dashboard"))

    today = local_today()
    # Find active attendance session (without checkout), fallback to today
    attendance = Attendance.query.filter_by(employee_id=employee.id, check_out=None).order_by(Attendance.created_at.desc()).first()
    if not attendance:
        attendance = Attendance.query.filter_by(employee_id=employee.id, date=today).first()

    if not attendance or attendance.check_out:
        flash("You must be checked in to start a break.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    # Check for existing active break
    active = Break.query.filter_by(attendance_id=attendance.id, end_time=None).first()
    if active:
        flash(f"You already have an active {active.category.value} break in progress. End it first.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    category_val = request.form.get("category", "Other")
    try:
        cat = BreakCategory(category_val)
    except ValueError:
        cat = BreakCategory.OTHER

    now = utc_now()
    brk = Break(
        attendance_id=attendance.id,
        employee_id=employee.id,
        category=cat,
        start_time=now,
    )
    db.session.add(brk)
    db.session.commit()
    flash(f"{cat.value} break started.", "success")
    return redirect(url_for("dashboard.employee_dashboard"))


@breaks_bp.route("/<int:break_id>/end", methods=["POST"])
@login_required
def end(break_id):
    brk = Break.query.get_or_404(break_id)
    employee = current_user.employee

    if not employee or brk.employee_id != employee.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("dashboard.employee_dashboard"))

    if brk.end_time:
        flash("Break already ended.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    now = utc_now()
    brk.close(now)

    # Recalculate attendance
    attendance = brk.attendance
    if attendance:
        attendance.recalculate()
    db.session.commit()

    duration_str = format_mins(brk.duration_minutes)
    flash(f"{brk.category.value} break ended. Actual duration: {duration_str}.", "success")
    return redirect(url_for("dashboard.employee_dashboard"))
