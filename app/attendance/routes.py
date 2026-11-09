"""
EBT System – Attendance Routes
"""

from datetime import date, datetime, timezone, timedelta
import calendar
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Employee, Attendance, Break, AttendanceStatus, UserRole, Department, WorkSchedule, LeaveRequest, LeaveStatus
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
    today = local_today()
    from_date = parse_iso_date(request.args.get("from_date"))
    to_date = parse_iso_date(request.args.get("to_date"))
    dept_filter = request.args.get("dept")

    base_query = Attendance.query.join(Employee)

    if not current_user.is_admin:
        if current_user.employee:
            base_query = base_query.filter(Attendance.employee_id == current_user.employee.id)
        else:
            base_query = base_query.filter(db.false())

    if from_date:
        base_query = base_query.filter(Attendance.date >= from_date)
    if to_date:
        base_query = base_query.filter(Attendance.date <= to_date)
    if dept_filter and current_user.is_admin:
        base_query = base_query.filter(Employee.department_id == int(dept_filter))

    records = base_query.order_by(Attendance.date.desc()).limit(200).all()
    departments = Department.query.order_by(Department.name).all() if current_user.is_admin else []

    # ── Real Database-Backed Analytics Calculation ───────────────────────────
    # Reference target employee if employee user
    target_emp_id = current_user.employee.id if (not current_user.is_admin and current_user.employee) else None

    # Determine reference date for the 7-day trend (use to_date if provided, else today, or latest record date)
    if to_date:
        trend_end_date = to_date
    elif records:
        trend_end_date = max(today, records[0].date)
    else:
        trend_end_date = today

    # 1. Weekly Attendance Trend (Last 7 Days)
    weekly_dates = [trend_end_date - timedelta(days=i) for i in range(6, -1, -1)]
    trend_labels = [d.strftime("%a, %d %b") for d in weekly_dates]
    trend_present = []
    trend_absent = []
    trend_pct = []

    for d in weekly_dates:
        # Check approved leave for this date
        leave_q = LeaveRequest.query.filter(
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= d,
            LeaveRequest.end_date >= d
        )
        if target_emp_id:
            leave_q = leave_q.filter(LeaveRequest.employee_id == target_emp_id)
        leave_count = leave_q.count()

        att_q = Attendance.query.filter(Attendance.date == d)
        if target_emp_id:
            att_q = att_q.filter(Attendance.employee_id == target_emp_id)
        elif dept_filter and current_user.is_admin:
            att_q = att_q.join(Employee).filter(Employee.department_id == int(dept_filter))

        day_recs = att_q.all()
        # Count completed or present checkins
        p_count = sum(1 for r in day_recs if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.HALF_DAY))

        if target_emp_id:
            # For individual employee: 1 if present, else 0; absent if 0 and not weekend and not future
            total_target = 1
            a_count = 1 if (p_count == 0 and leave_count == 0 and d <= today and d.weekday() < 5) else 0
            rate = 100.0 if p_count > 0 else 0.0
        else:
            total_target = Employee.query.filter_by(status='Active').count() or len(day_recs) or 1
            a_count = max(0, total_target - p_count - leave_count) if d <= today else 0
            rate = round((p_count / total_target * 100), 1) if total_target > 0 else 0.0

        trend_present.append(p_count)
        trend_absent.append(a_count)
        trend_pct.append(rate)

    # 2. Working Hours vs Break Hours (Last 7 active days from filtered records or weekly window)
    hours_labels = []
    hours_gross = []
    hours_break = []
    hours_net = []

    # Get completed records with check_out for accurate calculation, up to 7 distinct days
    comp_recs_by_date = {}
    for r in sorted(records, key=lambda x: x.date):
        if r.check_out and r.check_in:
            d_key = r.date.strftime("%d %b")
            if d_key not in comp_recs_by_date:
                comp_recs_by_date[d_key] = {"gross": 0.0, "break": 0.0, "net": 0.0}
            
            # Gross hours: exact delta between check_in and check_out
            if r.check_out > r.check_in:
                gross_mins = max(0.0, (r.check_out - r.check_in).total_seconds() / 60.0)
            else:
                gross_mins = 0.0

            # Break hours: validated non-negative
            break_mins = max(0.0, r.break_duration_minutes or 0.0)

            # Net working hours: gross minus breaks, bounded
            net_mins = max(0.0, gross_mins - break_mins)

            comp_recs_by_date[d_key]["gross"] += round(gross_mins / 60.0, 2)
            comp_recs_by_date[d_key]["break"] += round(break_mins / 60.0, 2)
            comp_recs_by_date[d_key]["net"] += round(net_mins / 60.0, 2)

    # Take the latest 7 days for the chart
    recent_hour_days = list(comp_recs_by_date.keys())[-7:]
    for d_key in recent_hour_days:
        hours_labels.append(d_key)
        hours_gross.append(round(comp_recs_by_date[d_key]["gross"], 1))
        hours_break.append(round(comp_recs_by_date[d_key]["break"], 1))
        hours_net.append(round(comp_recs_by_date[d_key]["net"], 1))

    # 3. Attendance Status Distribution (Present, Absent, On Approved Leave)
    # Based on records in current view/filter
    status_present_count = 0
    status_absent_count = 0
    status_leave_count = 0

    for r in records:
        if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.HALF_DAY):
            status_present_count += 1
        elif r.status == AttendanceStatus.ABSENT:
            status_absent_count += 1
        elif r.status == AttendanceStatus.ON_LEAVE:
            status_leave_count += 1

    # Check leaves matching the date range or filtered records
    if records:
        earliest_rec_date = min(r.date for r in records)
        latest_rec_date = max(r.date for r in records)
    else:
        earliest_rec_date = from_date or today
        latest_rec_date = to_date or today

    leave_filter_q = LeaveRequest.query.filter(
        LeaveRequest.status == LeaveStatus.APPROVED,
        LeaveRequest.start_date <= latest_rec_date,
        LeaveRequest.end_date >= earliest_rec_date
    )
    if target_emp_id:
        leave_filter_q = leave_filter_q.filter(LeaveRequest.employee_id == target_emp_id)
    status_leave_count += leave_filter_q.count()

    # 4. Monthly Attendance Summary Metrics
    # Month reference: month of latest record or today
    ref_month = trend_end_date.month
    ref_year = trend_end_date.year
    month_name = calendar.month_name[ref_month]

    # Calculate standard working days in the month (excluding Saturdays and Sundays up to today/month end)
    _, num_days_in_month = calendar.monthrange(ref_year, ref_month)
    cutoff_day = min(num_days_in_month, today.day if (ref_year == today.year and ref_month == today.month) else num_days_in_month)
    month_working_days = sum(1 for day in range(1, cutoff_day + 1) if date(ref_year, ref_month, day).weekday() < 5)

    month_recs = [r for r in records if r.date.year == ref_year and r.date.month == ref_month]
    month_present_days = len(set(r.date for r in month_recs if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.HALF_DAY)))
    
    # Calculate absent days
    month_absent_days = max(0, month_working_days - month_present_days)

    # Calculate monthly gross, break, and net hours strictly on completed shifts
    month_gross_mins = 0.0
    month_break_mins = 0.0
    month_net_mins = 0.0

    for r in month_recs:
        if r.check_in and r.check_out and r.check_out > r.check_in:
            g_m = max(0.0, (r.check_out - r.check_in).total_seconds() / 60.0)
            b_m = max(0.0, r.break_duration_minutes or 0.0)
            n_m = max(0.0, g_m - b_m)
            month_gross_mins += g_m
            month_break_mins += b_m
            month_net_mins += n_m

    month_total_work_hours = round(month_net_mins / 60.0, 1)
    month_total_break_hours = round(month_break_mins / 60.0, 1)
    month_attendance_pct = round((month_present_days / month_working_days * 100), 1) if month_working_days > 0 else 0.0

    analytics = {
        "month_name": month_name,
        "month_year": ref_year,
        "working_days": month_working_days,
        "present_days": month_present_days,
        "absent_days": month_absent_days,
        "total_work_hours": month_total_work_hours,
        "total_break_hours": month_total_break_hours,
        "attendance_pct": month_attendance_pct,
        "trend_labels": trend_labels,
        "trend_present": trend_present,
        "trend_absent": trend_absent,
        "trend_pct": trend_pct,
        "hours_labels": hours_labels,
        "hours_gross": hours_gross,
        "hours_break": hours_break,
        "hours_net": hours_net,
        "status_present": status_present_count,
        "status_absent": status_absent_count,
        "status_leave": status_leave_count,
    }

    return render_template(
        "attendance/index.html",
        records=records,
        departments=departments,
        today=today,
        analytics=analytics
    )


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

