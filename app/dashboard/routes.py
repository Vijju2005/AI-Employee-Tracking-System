"""
EBT System – Dashboard Routes
Admin dashboard and Employee dashboard.
"""

from datetime import date, datetime, timedelta, timezone
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import (
    User, Employee, Attendance, Break, LeaveRequest,
    Department, AttendanceStatus, LeaveStatus, UserRole
)
from app.time_utils import local_today, local_now, utc_now

dashboard_bp = Blueprint("dashboard", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for("dashboard.admin_dashboard"))
    return redirect(url_for("dashboard.employee_dashboard"))


@dashboard_bp.route("/dashboard/admin")
@login_required
@admin_required
def admin_dashboard():
    today = local_today()

    # Stat cards
    total_employees = Employee.query.count()
    present_today = Attendance.query.filter_by(date=today).count()
    pending_leaves = LeaveRequest.query.filter_by(status=LeaveStatus.PENDING).count()
    active_breaks = Break.query.filter(Break.end_time.is_(None)).count()

    # Attendance trend – last 7 days
    labels, present_list, absent_list = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        labels.append(d.strftime("%d %b"))
        present_count = Attendance.query.filter_by(date=d).count()
        present_list.append(present_count)
        absent_list.append(max(0, total_employees - present_count))

    # Department distribution
    dept_data = (
        db.session.query(Department.name, func.count(Employee.id))
        .outerjoin(Employee, Employee.department_id == Department.id)
        .group_by(Department.id)
        .all()
    )
    dept_labels = [r[0] for r in dept_data]
    dept_counts = [r[1] for r in dept_data]

    # Recent pending leaves
    recent_leaves = (
        LeaveRequest.query.filter_by(status=LeaveStatus.PENDING)
        .order_by(LeaveRequest.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard/admin.html",
        today=today,
        total_employees=total_employees,
        present_today=present_today,
        pending_leaves=pending_leaves,
        active_breaks=active_breaks,
        attendance_labels=labels,
        attendance_present=present_list,
        attendance_absent=absent_list,
        dept_labels=dept_labels,
        dept_counts=dept_counts,
        recent_leaves=recent_leaves,
    )


@dashboard_bp.route("/dashboard/employee")
@login_required
def employee_dashboard():
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for("dashboard.admin_dashboard"))

    today = local_today()
    employee = current_user.employee

    attendance = None
    active_break = None
    if employee:
        # Prefer active (non-checked-out) attendance, fallback to today's record
        attendance = Attendance.query.filter_by(
            employee_id=employee.id, check_out=None
        ).order_by(Attendance.created_at.desc()).first()

        if not attendance:
            attendance = Attendance.query.filter_by(
                employee_id=employee.id, date=today
            ).first()

        if attendance:
            active_break = Break.query.filter_by(
                attendance_id=attendance.id, end_time=None
            ).first()

    prediction = None

    # Compute current dynamic elapsed times for immediate render
    elapsed_net = 0.0
    total_break_min = 0.0
    total_gross_min = 0.0
    if attendance and attendance.check_in:
        now_u = utc_now()
        total_gross_min = attendance.get_elapsed_working_minutes(now_u)
        total_break_min = attendance.get_total_break_minutes(now_u)
        elapsed_net = attendance.get_net_working_minutes(now_u)

    return render_template(
        "dashboard/employee.html",
        today=today,
        employee=employee,
        attendance=attendance,
        active_break=active_break,
        prediction=prediction,
        elapsed_net_minutes=elapsed_net,
        total_break_minutes=total_break_min,
        total_gross_minutes=total_gross_min,
    )
