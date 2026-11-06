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
    User, Employee, Attendance, Break, LeaveRequest, Holiday,
    Department, AttendanceStatus, LeaveStatus, UserRole, AccountStatus,
    JobOpening, JobCandidate
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

    # Core workforce counts
    total_employees = Employee.query.count()
    present_today = Attendance.query.filter_by(date=today).count()
    absent_today = max(0, total_employees - present_today)
    active_breaks = Break.query.filter(Break.end_time.is_(None)).count()
    pending_leaves = LeaveRequest.query.filter_by(status=LeaveStatus.PENDING).count()

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

    # Holidays overview
    upcoming_holidays = (
        Holiday.query.filter(Holiday.holiday_date >= today)
        .order_by(Holiday.holiday_date.asc())
        .limit(5)
        .all()
    )
    total_holidays_2026 = (
        Holiday.query.filter(func.extract('year', Holiday.holiday_date) == 2026).count()
    )

    # Recent workforce activity timeline (combining latest attendance and break events)
    recent_activities = []
    latest_attendances = (
        Attendance.query.order_by(Attendance.created_at.desc())
        .limit(6)
        .all()
    )
    for att in latest_attendances:
        if att.employee:
            action_type = "Check Out" if att.check_out else "Check In"
            recent_activities.append({
                "type": "attendance",
                "employee": att.employee.full_name,
                "dept": att.employee.department.name if att.employee.department else "General",
                "action": action_type,
                "time": att.check_out or att.check_in or att.created_at,
                "badge": "badge-success" if action_type == "Check In" else "badge-info"
            })

    latest_breaks = (
        Break.query.order_by(Break.created_at.desc())
        .limit(6)
        .all()
    )
    for brk in latest_breaks:
        if brk.employee:
            action_type = f"{brk.category.value} Break Ended" if brk.end_time else f"{brk.category.value} Break Started"
            recent_activities.append({
                "type": "break",
                "employee": brk.employee.full_name,
                "dept": brk.employee.department.name if brk.employee.department else "General",
                "action": action_type,
                "time": brk.end_time or brk.start_time or brk.created_at,
                "badge": "badge-warning" if not brk.end_time else "badge-secondary"
            })

    recent_activities.sort(key=lambda x: x["time"] or datetime.min, reverse=True)
    recent_activities = recent_activities[:6]

    return render_template(
        "dashboard/admin.html",
        today=today,
        total_employees=total_employees,
        present_today=present_today,
        absent_today=absent_today,
        pending_leaves=pending_leaves,
        active_breaks=active_breaks,
        attendance_labels=labels,
        attendance_present=present_list,
        attendance_absent=absent_list,
        dept_labels=dept_labels,
        dept_counts=dept_counts,
        recent_leaves=recent_leaves,
        upcoming_holidays=upcoming_holidays,
        total_holidays_2026=total_holidays_2026,
        recent_activities=recent_activities,
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

    # Compute current dynamic elapsed times for immediate render
    elapsed_net = 0.0
    total_break_min = 0.0
    total_gross_min = 0.0
    if attendance and attendance.check_in:
        now_u = utc_now()
        total_gross_min = attendance.get_elapsed_working_minutes(now_u)
        total_break_min = attendance.get_total_break_minutes(now_u)
        elapsed_net = attendance.get_net_working_minutes(now_u)

    # Compute AI Prediction if employee exists
    prediction = None
    if employee:
        past_breaks = (
            Break.query
            .filter_by(employee_id=employee.id)
            .filter(Break.end_time.isnot(None))
            .filter(Break.duration_minutes > 0)
            .all()
        )
        if past_breaks:
            durations = [b.duration_minutes for b in past_breaks]
            avg_break = round(sum(durations) / len(durations), 1)
        else:
            avg_break = 25.0
        sched_hours = employee.work_schedule.total_hours if employee.work_schedule else 8.0
        sched_minutes = sched_hours * 60.0
        avail_mins = max(0.0, sched_minutes - avg_break)
        prediction = {
            "break_min": f"{avg_break:.0f}",
            "avail_h": f"{avail_mins / 60.0:.1f}",
            "model_used": "Random Forest / Historical Baseline",
        }

    # Recent leave requests for this employee
    my_leaves = []
    if employee:
        my_leaves = (
            LeaveRequest.query.filter_by(employee_id=employee.id)
            .order_by(LeaveRequest.created_at.desc())
            .limit(3)
            .all()
        )

    # Holiday checks for employee
    today_holiday = Holiday.query.filter_by(holiday_date=today).first()
    upcoming_holidays = (
        Holiday.query.filter(Holiday.holiday_date >= today)
        .order_by(Holiday.holiday_date.asc())
        .limit(5)
        .all()
    )

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
        today_holiday=today_holiday,
        upcoming_holidays=upcoming_holidays,
        my_leaves=my_leaves,
    )


# ── Dedicated HR Analytics Dashboard ─────────────────────────────────────────

@dashboard_bp.route("/dashboard/hr")
@login_required
@admin_required
def hr_dashboard():
    """Enterprise HR Analytics Dashboard."""
    total_employees = Employee.query.count()
    active_employees = Employee.query.filter_by(status=AccountStatus.ACTIVE).count()
    inactive_employees = total_employees - active_employees

    # Department distribution
    dept_distribution = (
        db.session.query(Department.name, func.count(Employee.id))
        .outerjoin(Employee, Employee.department_id == Department.id)
        .group_by(Department.id)
        .all()
    )
    dept_labels = [r[0] for r in dept_distribution]
    dept_counts = [r[1] for r in dept_distribution]

    # Leave requests breakdown
    pending_leaves = LeaveRequest.query.filter_by(status=LeaveStatus.PENDING).count()
    approved_leaves = LeaveRequest.query.filter_by(status=LeaveStatus.APPROVED).count()
    rejected_leaves = LeaveRequest.query.filter_by(status=LeaveStatus.REJECTED).count()

    # Recent workforce joins
    recent_joins = (
        Employee.query.order_by(Employee.date_joined.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "dashboard/hr.html",
        total_employees=total_employees,
        active_employees=active_employees,
        inactive_employees=inactive_employees,
        dept_labels=dept_labels,
        dept_counts=dept_counts,
        pending_leaves=pending_leaves,
        approved_leaves=approved_leaves,
        rejected_leaves=rejected_leaves,
        recent_joins=recent_joins
    )


# ── Dedicated Attendance Dashboard ───────────────────────────────────────────

@dashboard_bp.route("/dashboard/attendance")
@login_required
@admin_required
def attendance_dashboard():
    """Enterprise Attendance Analytics & Roster Dashboard."""
    today = local_today()
    total_employees = Employee.query.count()

    today_records = Attendance.query.filter_by(date=today).all()
    present_today = len(today_records)
    absent_today = max(0, total_employees - present_today)

    # Approved leaves for today
    on_leave_today = (
        LeaveRequest.query.filter(
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today
        ).count()
    )

    attendance_pct = round((present_today / total_employees * 100), 1) if total_employees > 0 else 0.0

    # Total net work hours & breaks logged today
    total_work_minutes = sum(r.net_working_minutes or 0.0 for r in today_records)
    total_break_minutes = sum(r.break_duration_minutes or 0.0 for r in today_records)

    # 7-day trend
    trend_labels = []
    trend_present = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        trend_labels.append(d.strftime("%d %b"))
        count = Attendance.query.filter_by(date=d).count()
        trend_present.append(count)

    recent_logs = (
        Attendance.query.order_by(Attendance.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "dashboard/attendance.html",
        today=today,
        total_employees=total_employees,
        present_today=present_today,
        absent_today=absent_today,
        on_leave_today=on_leave_today,
        attendance_pct=attendance_pct,
        total_work_hours=round(total_work_minutes / 60.0, 1),
        total_break_hours=round(total_break_minutes / 60.0, 1),
        trend_labels=trend_labels,
        trend_present=trend_present,
        recent_logs=recent_logs
    )


# ── Dedicated Recruitment Dashboard ─────────────────────────────────────────

@dashboard_bp.route("/dashboard/recruitment")
@login_required
@admin_required
def recruitment_dashboard():
    """Enterprise Talent Acquisition & Recruitment Pipeline Dashboard."""
    # Seed sample baseline job postings idempotently if empty
    if JobOpening.query.count() == 0:
        it_dept = Department.query.filter(Department.name.ilike("%tech%")).first() or Department.query.first()
        dept_id = it_dept.id if it_dept else None

        job1 = JobOpening(
            title="Senior Full-Stack Python Engineer",
            department_id=dept_id,
            positions=2,
            status="open",
            job_type="Full-Time",
            experience_level="Senior",
            description="Lead backend architecture and web dashboard services."
        )
        job2 = JobOpening(
            title="HR & Payroll Operations Specialist",
            department_id=dept_id,
            positions=1,
            status="open",
            job_type="Full-Time",
            experience_level="Mid-Level",
            description="Manage corporate employee payroll and attendance compliance."
        )
        db.session.add_all([job1, job2])
        db.session.commit()

        cand1 = JobCandidate(
            job_opening_id=job1.id,
            full_name="Aarav Sharma",
            email="aarav.sharma@example.com",
            phone="+91 98765 43210",
            status="interviewing",
            rating=4,
            interview_notes="Strong algorithmic background and Flask/MySQL expertise."
        )
        cand2 = JobCandidate(
            job_opening_id=job1.id,
            full_name="Pooja Rao",
            email="pooja.rao@example.com",
            phone="+91 98123 45678",
            status="applied",
            rating=3
        )
        db.session.add_all([cand1, cand2])
        db.session.commit()

    total_openings = JobOpening.query.filter_by(status="open").count()
    total_candidates = JobCandidate.query.count()

    applied_count = JobCandidate.query.filter_by(status="applied").count()
    interviewing_count = JobCandidate.query.filter_by(status="interviewing").count()
    offered_count = JobCandidate.query.filter_by(status="offered").count()
    hired_count = JobCandidate.query.filter_by(status="hired").count()

    openings = JobOpening.query.order_by(JobOpening.created_at.desc()).all()
    candidates = JobCandidate.query.order_by(JobCandidate.created_at.desc()).limit(10).all()

    return render_template(
        "dashboard/recruitment.html",
        total_openings=total_openings,
        total_candidates=total_candidates,
        applied_count=applied_count,
        interviewing_count=interviewing_count,
        offered_count=offered_count,
        hired_count=hired_count,
        openings=openings,
        candidates=candidates
    )

