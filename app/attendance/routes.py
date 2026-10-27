"""
EBT System – Attendance Routes
"""

from datetime import date, datetime, timezone, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Employee, Attendance, AttendanceStatus, UserRole, Department

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@attendance_bp.route("/")
@login_required
def index():
    today = date.today()
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
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

    today = date.today()
    existing = Attendance.query.filter_by(employee_id=employee.id, date=today).first()
    if existing:
        flash("You have already checked in today.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    attendance = Attendance(
        employee_id=employee.id,
        date=today,
        check_in=_utcnow(),
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

    today = date.today()
    attendance = Attendance.query.filter_by(employee_id=employee.id, date=today).first()
    if not attendance:
        flash("You haven't checked in today.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))
    if attendance.check_out:
        flash("You have already checked out.", "warning")
        return redirect(url_for("dashboard.employee_dashboard"))

    attendance.check_out = _utcnow()
    attendance.recalculate()
    db.session.commit()
    flash(f"Checked out. Net working time: {attendance.net_working_minutes:.0f} minutes.", "success")
    return redirect(url_for("dashboard.employee_dashboard"))
