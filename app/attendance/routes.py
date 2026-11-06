"""
EBT System – Attendance Routes
"""

from datetime import date, datetime, timezone, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Employee, Attendance, Break, AttendanceStatus, UserRole, Department, WorkSchedule
from app.time_utils import (
    utc_now, local_today, local_now, format_hours_mins,
    parse_iso_date,
)

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@attendance_bp.route("/")
@login_required
def index():
    today = date.today()
    from_date = parse_iso_date(request.args.get("from_date"))
    to_date = parse_iso_date(request.args.get("to_date"))
    dept_filter = request.args.get("dept")

    query = Attendance.query.join(Employee)

    if not current_user.is_admin:
        if current_user.employee:
            query = query.filter(Attendance.employee_id == current_user.employee.id)
        else:
            query = query.filter(db.false())

    if from_date:
        query = query.filter(Attendance.date >= from_date)
    if to_date:
        query = query.filter(Attendance.date <= to_date)
    if dept_filter and current_user.is_admin:
        query = query.filter(Employee.department_id == int(dept_filter))

    records = query.order_by(Attendance.date.desc()).limit(200).all()
    departments = Department.query.order_by(Department.name).all() if current_user.is_admin else []

    return render_template("attendance/index.html", records=records, departments=departments, today=today)


@attendance_bp.route("/history")
@login_required
def history():
    return redirect(url_for("attendance.index"))


@attendance_bp.route("/checkin", methods=["POST"])
@login_required
def checkin():
    if current_user.is_admin:
        flash("Admins cannot check in.", "warning")
        return redirect(url_for("dashboard.admin_dashboard"))

    employee = current_user.employee
    if not employee:
        flash("No employee record linked to your account.", "danger")
        return redirect(url_for("dashboard.employee_dashboard"))

    today = local_today()
    # Check for active (non-checked-out) attendance session first
    active_att = Attendance.query.filter_by(employee_id=employee.id, check_out=None).first()
    if active_att:
        flash("You already have an active check-in session.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    existing = Attendance.query.filter_by(employee_id=employee.id, date=today).first()
    if existing:
        flash("You have already completed attendance for today.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    attendance = Attendance(
        employee_id=employee.id,
        date=today,
        check_in=utc_now(),
        status=AttendanceStatus.PRESENT,
    )
    db.session.add(attendance)
    db.session.commit()
    flash("Checked in successfully!", "success")
    return redirect(url_for("dashboard.employee_dashboard"))


@attendance_bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    employee = current_user.employee
    if not employee:
        flash("No employee record linked to your account.", "danger")
        return redirect(url_for("dashboard.employee_dashboard"))

    today = local_today()
    # Prefer finding an active attendance session (without checkout), fallback to today's record
    attendance = Attendance.query.filter_by(employee_id=employee.id, check_out=None).order_by(Attendance.created_at.desc()).first()
    if not attendance:
        attendance = Attendance.query.filter_by(employee_id=employee.id, date=today).first()

    if not attendance or not attendance.check_in:
        flash("You haven't checked in.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))
    if attendance.check_out:
        flash("You have already checked out.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    # Safely handle active/unfinished break if employee checks out during a break
    active_break = Break.query.filter_by(attendance_id=attendance.id, end_time=None).first()
    now = utc_now()
    if active_break:
        active_break.close(now)
        flash(f"Active {active_break.category.value} break ended upon checkout ({active_break.duration_minutes:.0f}m).", "info")

    attendance.check_out = now
    attendance.recalculate()
    db.session.commit()

    net_str = format_hours_mins(attendance.net_working_minutes)
    total_str = format_hours_mins(attendance.total_duration_minutes)
    flash(f"Checked out successfully! Total: {total_str}, Net Working Time: {net_str}.", "success")
    return redirect(url_for("dashboard.employee_dashboard"))


# ── Shift & Work Schedule Management ─────────────────────────────────────────

@attendance_bp.route("/schedules")
@login_required
def schedules_list():
    """View and configure company work schedules and shifts."""
    if not current_user.is_admin:
        abort(403)

    schedules = WorkSchedule.query.order_by(WorkSchedule.name.asc()).all()
    employees = Employee.query.order_by(Employee.full_name.asc()).all()
    return render_template("attendance/schedules.html", schedules=schedules, employees=employees)


@attendance_bp.route("/schedules/add", methods=["POST"])
@login_required
def add_schedule():
    """Create a new work shift schedule."""
    if not current_user.is_admin:
        abort(403)

    name = request.form.get("name", "").strip()
    start_time_str = request.form.get("start_time", "").strip()
    end_time_str = request.form.get("end_time", "").strip()
    description = request.form.get("description", "").strip()

    if not name or not start_time_str or not end_time_str:
        flash("Shift name, start time, and end time are required.", "danger")
        return redirect(url_for("attendance.schedules_list"))

    try:
        from datetime import time
        sh, sm = map(int, start_time_str.split(":")[:2])
        eh, em = map(int, end_time_str.split(":")[:2])
        start_time = time(sh, sm)
        end_time = time(eh, em)

        # Calculate total hours
        duration_hours = (eh + em/60.0) - (sh + sm/60.0)
        if duration_hours < 0:
            duration_hours += 24.0

        sched = WorkSchedule(
            name=name,
            start_time=start_time,
            end_time=end_time,
            total_hours=round(duration_hours, 2),
            description=description
        )
        db.session.add(sched)
        db.session.commit()
        flash(f"Shift schedule '{name}' created successfully.", "success")
    except Exception as e:
        flash(f"Error creating shift: {str(e)}", "danger")

    return redirect(url_for("attendance.schedules_list"))


@attendance_bp.route("/schedules/assign", methods=["POST"])
@login_required
def assign_schedule():
    """Assign an employee or group to a work shift schedule."""
    if not current_user.is_admin:
        abort(403)

    employee_id = request.form.get("employee_id", type=int)
    schedule_id = request.form.get("schedule_id", type=int)

    if not employee_id or not schedule_id:
        flash("Please select both an employee and a shift schedule.", "warning")
        return redirect(url_for("attendance.schedules_list"))

    emp = Employee.query.get_or_404(employee_id)
    sched = WorkSchedule.query.get_or_404(schedule_id)

    emp.work_schedule_id = sched.id
    db.session.commit()
    flash(f"Assigned {emp.full_name} to '{sched.name}' shift.", "success")
    return redirect(url_for("attendance.schedules_list"))

