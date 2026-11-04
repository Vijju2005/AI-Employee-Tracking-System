"""
EBT System – Enterprise Reports Module
Implements 7 Comprehensive Reports:
1. Expense Report – Employee expenses, categories, amounts, receipts and dates
2. User Report – User details, roles, emails, and account status
3. Employee Report – Employee ID, name, department, designation and employment details
4. Payslip Report – Salary, allowances, deductions, net salary, and payment status
5. Attendance Report – Check-in, check-out, break duration, working hours and status
6. Leave Report – Leave type, dates, reason, approval status and employee details
7. Daily Report – Daily attendance, employee availability, breaks and leave summary
"""

import os
import io
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for, abort
from flask_login import login_required, current_user
import sqlalchemy as sa
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Attendance, Break, LeaveRequest, Employee, User, UserRole,
    Payslip, EmployeeSalary, Expense, ExpenseCategory, ExpenseStatus,
    Department, AccountStatus, LeaveStatus, AttendanceStatus
)
from app.time_utils import format_local_time, format_local_date, parse_iso_date

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

REPORT_CONFIGS = {
    "expense": {
        "title": "Expense Report",
        "description": "Employee business expenses, claim categories, disbursement amounts and dates.",
        "icon": "receipt",
        "admin_only": False,
    },
    "user": {
        "title": "User Report",
        "description": "System user credentials, security roles, permissions and account activity status.",
        "icon": "shield-check",
        "admin_only": True,
    },
    "employee": {
        "title": "Employee Report",
        "description": "Complete corporate personnel roster, department assignments, designations and joining details.",
        "icon": "users",
        "admin_only": True,
    },
    "payslip": {
        "title": "Payslip Report",
        "description": "Monthly payroll disbursement summaries, gross earnings, statutory deductions, net take-home and status.",
        "icon": "banknote",
        "admin_only": False,
    },
    "attendance": {
        "title": "Attendance Report",
        "description": "Daily employee check-in, check-out, duration, break totals, and attendance status flags.",
        "icon": "calendar-check",
        "admin_only": False,
    },
    "leave": {
        "title": "Leave Report",
        "description": "Leave requests, duration, categories, manager approval statuses, and employee explanations.",
        "icon": "calendar-days",
        "admin_only": False,
    },
    "daily": {
        "title": "Daily Report",
        "description": "Single-day cross-functional operational briefing combining attendance, breaks, availability, and active leaves.",
        "icon": "clipboard-list",
        "admin_only": False,
    },
}


@reports_bp.route("/")
@reports_bp.route("/<report_type>")
@login_required
def index(report_type="expense"):
    if report_type not in REPORT_CONFIGS:
        report_type = "expense"

    # Enforce role permissions
    if REPORT_CONFIGS[report_type]["admin_only"] and not current_user.is_admin:
        flash("Access restricted to administrators.", "warning")
        return redirect(url_for("reports.index", report_type="attendance"))

    # Fetch filter options
    departments = Department.query.order_by(Department.name).all() if current_user.is_admin else []
    employees = Employee.query.order_by(Employee.full_name).all() if current_user.is_admin else []

    # Get filter query parameters
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()
    target_date_str = request.args.get("target_date", "").strip()
    selected_emp_id = request.args.get("employee_id", "").strip()
    selected_dept_id = request.args.get("dept_id", "").strip()
    status_filter = request.args.get("status", "").strip()
    category_filter = request.args.get("category", "").strip()
    search_q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 15

    from_date = parse_iso_date(from_date_str) if from_date_str else None
    to_date = parse_iso_date(to_date_str) if to_date_str else None
    target_date = parse_iso_date(target_date_str) if target_date_str else date.today()

    # Query report records based on type
    result = _fetch_report_data(
        report_type=report_type,
        from_date=from_date,
        to_date=to_date,
        target_date=target_date,
        employee_id=selected_emp_id,
        dept_id=selected_dept_id,
        status=status_filter,
        category=category_filter,
        search_q=search_q,
        page=page,
        per_page=per_page,
    )

    return render_template(
        "reports/index.html",
        active_report=report_type,
        report_configs=REPORT_CONFIGS,
        departments=departments,
        employees=employees,
        from_date=from_date_str,
        to_date=to_date_str,
        target_date=target_date.isoformat(),
        selected_emp_id=selected_emp_id,
        selected_dept_id=selected_dept_id,
        status_filter=status_filter,
        category_filter=category_filter,
        search_q=search_q,
        headers=result["headers"],
        rows=result["rows"],
        total_count=result["total_count"],
        summary_stats=result["summary_stats"],
        page=page,
        total_pages=result["total_pages"],
        has_next=result["has_next"],
        has_prev=result["has_prev"],
    )


@reports_bp.route("/export/<report_type>")
@login_required
def export_report(report_type):
    if report_type not in REPORT_CONFIGS:
        abort(404)

    if REPORT_CONFIGS[report_type]["admin_only"] and not current_user.is_admin:
        abort(403)

    fmt = request.args.get("format", "pdf").lower()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()
    target_date_str = request.args.get("target_date", "").strip()
    selected_emp_id = request.args.get("employee_id", "").strip()
    selected_dept_id = request.args.get("dept_id", "").strip()
    status_filter = request.args.get("status", "").strip()
    category_filter = request.args.get("category", "").strip()
    search_q = request.args.get("q", "").strip()

    from_date = parse_iso_date(from_date_str) if from_date_str else None
    to_date = parse_iso_date(to_date_str) if to_date_str else None
    target_date = parse_iso_date(target_date_str) if target_date_str else date.today()

    # Query all matching records without pagination for clean full-dataset export
    result = _fetch_report_data(
        report_type=report_type,
        from_date=from_date,
        to_date=to_date,
        target_date=target_date,
        employee_id=selected_emp_id,
        dept_id=selected_dept_id,
        status=status_filter,
        category=category_filter,
        search_q=search_q,
        page=1,
        per_page=10000,
    )

    title = REPORT_CONFIGS[report_type]["title"]
    headers = result["headers"]
    data = result["export_data"]
    timestamp = date.today().strftime("%Y%m%d")

    try:
        if fmt == "excel":
            output = _generate_excel(title, headers, data)
            filename = f"ebt_{report_type}_report_{timestamp}.xlsx"
            return send_file(
                io.BytesIO(output), as_attachment=True, download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            output = _generate_pdf(title, headers, data)
            filename = f"ebt_{report_type}_report_{timestamp}.pdf"
            return send_file(
                io.BytesIO(output), as_attachment=True, download_name=filename,
                mimetype="application/pdf"
            )
    except Exception as e:
        flash(f"Report export failed: {e}", "danger")
        return redirect(url_for("reports.index", report_type=report_type))


# ── Report Data Builders ───────────────────────────────────────────────────────

def _fetch_report_data(report_type, from_date, to_date, target_date, employee_id, dept_id, status, category, search_q, page, per_page):
    """Executes filtered queries and prepares tabular rows and export records."""
    if report_type == "expense":
        return _build_expense_report(from_date, to_date, employee_id, dept_id, status, category, search_q, page, per_page)
    elif report_type == "user":
        return _build_user_report(status, search_q, page, per_page)
    elif report_type == "employee":
        return _build_employee_report(dept_id, status, search_q, page, per_page)
    elif report_type == "payslip":
        return _build_payslip_report(from_date, to_date, employee_id, dept_id, status, search_q, page, per_page)
    elif report_type == "attendance":
        return _build_attendance_report(from_date, to_date, employee_id, dept_id, status, search_q, page, per_page)
    elif report_type == "leave":
        return _build_leave_report(from_date, to_date, employee_id, dept_id, status, category, search_q, page, per_page)
    elif report_type == "daily":
        return _build_daily_report(target_date, dept_id, search_q, page, per_page)
    else:
        return {"headers": [], "rows": [], "export_data": [], "total_count": 0, "summary_stats": {}, "total_pages": 1, "has_next": False, "has_prev": False}


def _build_expense_report(from_date, to_date, employee_id, dept_id, status, category, search_q, page, per_page):
    query = Expense.query.join(Employee, Expense.employee_id == Employee.id)

    if not current_user.is_admin and current_user.employee:
        query = query.filter(Expense.employee_id == current_user.employee.id)
    elif employee_id and current_user.is_admin:
        query = query.filter(Expense.employee_id == int(employee_id))

    if dept_id and current_user.is_admin:
        query = query.filter(Employee.department_id == int(dept_id))

    if from_date:
        query = query.filter(Expense.expense_date >= from_date)
    if to_date:
        query = query.filter(Expense.expense_date <= to_date)
    if status:
        query = query.filter(Expense.status == status)
    if category:
        query = query.filter(Expense.category == category)
    if search_q:
        query = query.filter(
            sa.or_(
                Expense.expense_number.ilike(f"%{search_q}%"),
                Expense.merchant.ilike(f"%{search_q}%"),
                Expense.description.ilike(f"%{search_q}%"),
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
            )
        )

    total_count = query.count()
    all_matched = query.all()
    total_amount = sum(e.amount for e in all_matched)
    approved_amount = sum(e.amount for e in all_matched if e.status in [ExpenseStatus.APPROVED, ExpenseStatus.REIMBURSED])

    pagination = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    headers = ["Expense Ref", "Employee", "Department", "Category", "Merchant", "Amount (INR)", "Expense Date", "Status"]
    rows = []
    export_data = []

    for r in records:
        emp_name = r.employee.full_name if r.employee else "—"
        dept_name = r.employee.department.name if (r.employee and r.employee.department) else "—"
        cat_str = r.category.value.replace("_", " ").title() if hasattr(r.category, "value") else str(r.category)
        status_str = r.status.value.title() if hasattr(r.status, "value") else str(r.status)

        rows.append({
            "cols": [
                r.expense_number,
                f"{emp_name} ({r.employee.employee_id})" if r.employee else "—",
                dept_name,
                cat_str,
                r.merchant or "—",
                f"₹ {r.amount:,.2f}",
                format_local_date(r.expense_date),
                status_str,
            ],
            "status": status_str,
        })

    for r in all_matched:
        emp_name = r.employee.full_name if r.employee else "—"
        dept_name = r.employee.department.name if (r.employee and r.employee.department) else "—"
        cat_str = r.category.value.replace("_", " ").title() if hasattr(r.category, "value") else str(r.category)
        status_str = r.status.value.title() if hasattr(r.status, "value") else str(r.status)
        export_data.append([
            r.expense_number,
            f"{emp_name} ({r.employee.employee_id})" if r.employee else "—",
            dept_name,
            cat_str,
            r.merchant or "—",
            f"{r.amount:.2f}",
            str(r.expense_date),
            status_str,
        ])

    return {
        "headers": headers,
        "rows": rows,
        "export_data": export_data,
        "total_count": total_count,
        "summary_stats": {
            "Total Expenses": total_count,
            "Total Claimed": f"₹ {total_amount:,.2f}",
            "Total Approved": f"₹ {approved_amount:,.2f}",
        },
        "total_pages": pagination.pages or 1,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _build_user_report(status, search_q, page, per_page):
    query = User.query.outerjoin(Employee, User.id == Employee.user_id)

    if status:
        is_active_val = status.lower() in ["active", "true", "1"]
        query = query.filter(User.is_active == is_active_val)
    if search_q:
        query = query.filter(
            sa.or_(
                User.username.ilike(f"%{search_q}%"),
                User.email.ilike(f"%{search_q}%"),
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
            )
        )

    total_count = query.count()
    all_matched = query.all()
    active_count = sum(1 for u in all_matched if u.is_active)
    admin_count = sum(1 for u in all_matched if u.role == UserRole.ADMIN)

    pagination = query.order_by(User.id.asc()).paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    headers = ["User ID", "Username", "Email", "Linked Employee", "Role", "Status", "Created On"]
    rows = []
    export_data = []

    for u in records:
        emp_str = f"{u.employee.full_name} ({u.employee.employee_id})" if u.employee else "No Link"
        role_str = u.role.value.title() if hasattr(u.role, "value") else str(u.role)
        status_str = "Active" if u.is_active else "Inactive"
        created_str = u.created_at.strftime("%Y-%m-%d") if u.created_at else "—"

        rows.append({
            "cols": [
                f"USR-{u.id:04d}",
                u.username,
                u.email,
                emp_str,
                role_str,
                status_str,
                created_str,
            ],
            "status": status_str,
        })

    for u in all_matched:
        emp_str = f"{u.employee.full_name} ({u.employee.employee_id})" if u.employee else "No Link"
        role_str = u.role.value.title() if hasattr(u.role, "value") else str(u.role)
        status_str = "Active" if u.is_active else "Inactive"
        created_str = u.created_at.strftime("%Y-%m-%d") if u.created_at else "—"
        export_data.append([
            f"USR-{u.id:04d}",
            u.username,
            u.email,
            emp_str,
            role_str,
            status_str,
            created_str,
        ])

    return {
        "headers": headers,
        "rows": rows,
        "export_data": export_data,
        "total_count": total_count,
        "summary_stats": {
            "Total Users": total_count,
            "Active Accounts": active_count,
            "Administrators": admin_count,
        },
        "total_pages": pagination.pages or 1,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _build_employee_report(dept_id, status, search_q, page, per_page):
    query = Employee.query

    if dept_id:
        query = query.filter(Employee.department_id == int(dept_id))
    if status:
        query = query.filter(Employee.status == status)
    if search_q:
        query = query.filter(
            sa.or_(
                Employee.employee_id.ilike(f"%{search_q}%"),
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.email.ilike(f"%{search_q}%"),
                Employee.designation.ilike(f"%{search_q}%"),
            )
        )

    total_count = query.count()
    all_matched = query.all()
    active_count = sum(1 for e in all_matched if e.status == AccountStatus.ACTIVE)

    pagination = query.order_by(Employee.employee_id.asc()).paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    headers = ["Employee ID", "Full Name", "Email", "Department", "Designation", "Employment Status", "Date Joined"]
    rows = []
    export_data = []

    for e in records:
        dept_name = e.department.name if e.department else "—"
        status_str = e.status.value.title() if hasattr(e.status, "value") else str(e.status)
        joined_str = e.date_joined.strftime("%Y-%m-%d") if e.date_joined else "—"

        rows.append({
            "cols": [
                e.employee_id,
                e.full_name,
                e.email,
                dept_name,
                e.designation or "—",
                status_str,
                joined_str,
            ],
            "status": status_str,
        })

    for e in all_matched:
        dept_name = e.department.name if e.department else "—"
        status_str = e.status.value.title() if hasattr(e.status, "value") else str(e.status)
        joined_str = e.date_joined.strftime("%Y-%m-%d") if e.date_joined else "—"
        export_data.append([
            e.employee_id,
            e.full_name,
            e.email,
            dept_name,
            e.designation or "—",
            status_str,
            joined_str,
        ])

    return {
        "headers": headers,
        "rows": rows,
        "export_data": export_data,
        "total_count": total_count,
        "summary_stats": {
            "Total Employees": total_count,
            "Active Roster": active_count,
        },
        "total_pages": pagination.pages or 1,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _build_payslip_report(from_date, to_date, employee_id, dept_id, status, search_q, page, per_page):
    query = Payslip.query.join(Employee, Payslip.employee_id == Employee.id)

    if not current_user.is_admin and current_user.employee:
        query = query.filter(Payslip.employee_id == current_user.employee.id)
    elif employee_id and current_user.is_admin:
        query = query.filter(Payslip.employee_id == int(employee_id))

    if dept_id and current_user.is_admin:
        query = query.filter(Employee.department_id == int(dept_id))

    if status:
        query = query.filter(Payslip.status == status)

    if search_q:
        query = query.filter(
            sa.or_(
                Payslip.payslip_number.ilike(f"%{search_q}%"),
                Payslip.payroll_month.ilike(f"%{search_q}%"),
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
            )
        )

    total_count = query.count()
    all_matched = query.all()
    total_gross = sum(p.gross_earnings for p in all_matched)
    total_deductions = sum(p.total_deductions for p in all_matched)
    total_net = sum(p.net_salary for p in all_matched)

    pagination = query.order_by(Payslip.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    headers = ["Payslip Ref", "Employee", "Payroll Month", "Basic Salary (INR)", "Allowances (INR)", "Total Deductions (INR)", "Net Payout (INR)", "Payment Status"]
    rows = []
    export_data = []

    for p in records:
        emp_name = p.employee.full_name if p.employee else "—"
        allowances = p.hra + p.special_allowance + p.other_allowances + p.bonus
        status_str = p.status or "Generated"

        rows.append({
            "cols": [
                p.payslip_number,
                f"{emp_name} ({p.employee.employee_id})" if p.employee else "—",
                p.payroll_month,
                f"₹ {p.basic_salary:,.2f}",
                f"₹ {allowances:,.2f}",
                f"₹ {p.total_deductions:,.2f}",
                f"₹ {p.net_salary:,.2f}",
                status_str,
            ],
            "status": status_str,
        })

    for p in all_matched:
        emp_name = p.employee.full_name if p.employee else "—"
        allowances = p.hra + p.special_allowance + p.other_allowances + p.bonus
        status_str = p.status or "Generated"
        export_data.append([
            p.payslip_number,
            f"{emp_name} ({p.employee.employee_id})" if p.employee else "—",
            p.payroll_month,
            f"{p.basic_salary:.2f}",
            f"{allowances:.2f}",
            f"{p.total_deductions:.2f}",
            f"{p.net_salary:.2f}",
            status_str,
        ])

    return {
        "headers": headers,
        "rows": rows,
        "export_data": export_data,
        "total_count": total_count,
        "summary_stats": {
            "Total Payslips": total_count,
            "Total Gross": f"₹ {total_gross:,.2f}",
            "Total Net Disbursed": f"₹ {total_net:,.2f}",
        },
        "total_pages": pagination.pages or 1,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _build_attendance_report(from_date, to_date, employee_id, dept_id, status, search_q, page, per_page):
    query = Attendance.query.join(Employee, Attendance.employee_id == Employee.id)

    if not current_user.is_admin and current_user.employee:
        query = query.filter(Attendance.employee_id == current_user.employee.id)
    elif employee_id and current_user.is_admin:
        query = query.filter(Attendance.employee_id == int(employee_id))

    if dept_id and current_user.is_admin:
        query = query.filter(Employee.department_id == int(dept_id))

    if from_date:
        query = query.filter(Attendance.date >= from_date)
    if to_date:
        query = query.filter(Attendance.date <= to_date)
    if status:
        query = query.filter(Attendance.status == status)
    if search_q:
        query = query.filter(
            sa.or_(
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
            )
        )

    total_count = query.count()
    all_matched = query.all()
    total_net_hrs = sum(a.net_working_minutes for a in all_matched) / 60.0
    total_break_mins = sum(a.break_duration_minutes for a in all_matched)

    pagination = query.order_by(Attendance.date.desc(), Attendance.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    headers = ["Date", "Employee", "Department", "Check In", "Check Out", "Break (mins)", "Net Working (hrs)", "Status"]
    rows = []
    export_data = []

    for a in records:
        emp_name = a.employee.full_name if a.employee else "—"
        dept_name = a.employee.department.name if (a.employee and a.employee.department) else "—"
        status_str = a.status.value.title() if hasattr(a.status, "value") else str(a.status)

        rows.append({
            "cols": [
                format_local_date(a.date),
                f"{emp_name} ({a.employee.employee_id})" if a.employee else "—",
                dept_name,
                format_local_time(a.check_in, "%I:%M %p") if a.check_in else "—",
                format_local_time(a.check_out, "%I:%M %p") if a.check_out else "Active",
                f"{a.break_duration_minutes:.0f}",
                f"{a.net_working_minutes / 60.0:.2f} hrs",
                status_str,
            ],
            "status": status_str,
        })

    for a in all_matched:
        emp_name = a.employee.full_name if a.employee else "—"
        dept_name = a.employee.department.name if (a.employee and a.employee.department) else "—"
        status_str = a.status.value.title() if hasattr(a.status, "value") else str(a.status)
        export_data.append([
            str(a.date),
            f"{emp_name} ({a.employee.employee_id})" if a.employee else "—",
            dept_name,
            a.check_in.strftime("%H:%M") if a.check_in else "—",
            a.check_out.strftime("%H:%M") if a.check_out else "Active",
            f"{a.break_duration_minutes:.0f}",
            f"{a.net_working_minutes / 60.0:.2f}",
            status_str,
        ])

    return {
        "headers": headers,
        "rows": rows,
        "export_data": export_data,
        "total_count": total_count,
        "summary_stats": {
            "Total Sessions": total_count,
            "Total Net Hours": f"{total_net_hrs:,.1f} hrs",
            "Total Breaks": f"{total_break_mins:,.0f} mins",
        },
        "total_pages": pagination.pages or 1,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _build_leave_report(from_date, to_date, employee_id, dept_id, status, category, search_q, page, per_page):
    query = LeaveRequest.query.join(Employee, LeaveRequest.employee_id == Employee.id)

    if not current_user.is_admin and current_user.employee:
        query = query.filter(LeaveRequest.employee_id == current_user.employee.id)
    elif employee_id and current_user.is_admin:
        query = query.filter(LeaveRequest.employee_id == int(employee_id))

    if dept_id and current_user.is_admin:
        query = query.filter(Employee.department_id == int(dept_id))

    if from_date:
        query = query.filter(LeaveRequest.start_date >= from_date)
    if to_date:
        query = query.filter(LeaveRequest.end_date <= to_date)
    if status:
        query = query.filter(LeaveRequest.status == status)
    if category:
        query = query.filter(LeaveRequest.leave_type == category)
    if search_q:
        query = query.filter(
            sa.or_(
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
                LeaveRequest.reason.ilike(f"%{search_q}%"),
            )
        )

    total_count = query.count()
    all_matched = query.all()
    approved_count = sum(1 for l in all_matched if l.status == LeaveStatus.APPROVED)
    pending_count = sum(1 for l in all_matched if l.status == LeaveStatus.PENDING)

    pagination = query.order_by(LeaveRequest.start_date.desc(), LeaveRequest.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    headers = ["Leave Ref", "Employee", "Department", "Leave Type", "Start Date", "End Date", "Approval Status", "Reason"]
    rows = []
    export_data = []

    for l in records:
        emp_name = l.employee.full_name if l.employee else "—"
        dept_name = l.employee.department.name if (l.employee and l.employee.department) else "—"
        type_str = l.leave_type.value.replace("_", " ").title() if hasattr(l.leave_type, "value") else str(l.leave_type)
        status_str = l.status.value.title() if hasattr(l.status, "value") else str(l.status)

        rows.append({
            "cols": [
                f"LV-{l.id:04d}",
                f"{emp_name} ({l.employee.employee_id})" if l.employee else "—",
                dept_name,
                type_str,
                format_local_date(l.start_date),
                format_local_date(l.end_date),
                status_str,
                (l.reason or "—")[:40],
            ],
            "status": status_str,
        })

    for l in all_matched:
        emp_name = l.employee.full_name if l.employee else "—"
        dept_name = l.employee.department.name if (l.employee and l.employee.department) else "—"
        type_str = l.leave_type.value.replace("_", " ").title() if hasattr(l.leave_type, "value") else str(l.leave_type)
        status_str = l.status.value.title() if hasattr(l.status, "value") else str(l.status)
        export_data.append([
            f"LV-{l.id:04d}",
            f"{emp_name} ({l.employee.employee_id})" if l.employee else "—",
            dept_name,
            type_str,
            str(l.start_date),
            str(l.end_date),
            status_str,
            l.reason or "—",
        ])

    return {
        "headers": headers,
        "rows": rows,
        "export_data": export_data,
        "total_count": total_count,
        "summary_stats": {
            "Total Requests": total_count,
            "Approved": approved_count,
            "Pending": pending_count,
        },
        "total_pages": pagination.pages or 1,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _build_daily_report(target_date, dept_id, search_q, page, per_page):
    """
    Daily Comprehensive Briefing:
    Cross-references each employee on the selected date to display check-in/out,
    break duration, live availability, and active leave status.
    """
    query = Employee.query.filter_by(status=AccountStatus.ACTIVE)

    if not current_user.is_admin and current_user.employee:
        query = query.filter(Employee.id == current_user.employee.id)

    if dept_id and current_user.is_admin:
        query = query.filter(Employee.department_id == int(dept_id))

    if search_q:
        query = query.filter(
            sa.or_(
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
            )
        )

    total_count = query.count()
    all_employees = query.order_by(Employee.full_name).all()

    # Pre-fetch attendance and leaves for target_date to avoid N+1 queries
    emp_ids = [e.id for e in all_employees]
    attendance_map = {}
    if emp_ids:
        att_list = Attendance.query.filter(Attendance.date == target_date, Attendance.employee_id.in_(emp_ids)).all()
        attendance_map = {a.employee_id: a for a in att_list}

    # Pre-fetch active leaves spanning target_date
    leave_map = {}
    if emp_ids:
        leaves = LeaveRequest.query.filter(
            LeaveRequest.employee_id.in_(emp_ids),
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= target_date,
            LeaveRequest.end_date >= target_date,
        ).all()
        leave_map = {l.employee_id: l for l in leaves}

    # Pagination
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_employees = all_employees[start_idx:end_idx]

    present_count = len(attendance_map)
    on_leave_count = len(leave_map)

    headers = ["Employee ID", "Employee Name", "Department", "Attendance Status", "Check In", "Check Out", "Total Breaks", "Work Hours", "Availability Status"]
    rows = []
    export_data = []

    for e in page_employees:
        att = attendance_map.get(e.id)
        lv = leave_map.get(e.id)
        dept_name = e.department.name if e.department else "—"

        if lv:
            att_status = f"On Leave ({lv.leave_type.value.replace('_', ' ').title()})"
            check_in_str = "—"
            check_out_str = "—"
            break_str = "0 m"
            work_str = "0.0 h"
            avail_status = "On Leave"
        elif att:
            att_status = att.status.value.title() if hasattr(att.status, "value") else str(att.status)
            check_in_str = format_local_time(att.check_in, "%I:%M %p") if att.check_in else "—"
            check_out_str = format_local_time(att.check_out, "%I:%M %p") if att.check_out else "Active"
            break_str = f"{att.break_duration_minutes:.0f} m"
            work_str = f"{att.net_working_minutes / 60.0:.1f} h"
            avail_status = "Checked Out" if att.check_out else "Available / Working"
        else:
            att_status = "Absent / Not Checked In"
            check_in_str = "—"
            check_out_str = "—"
            break_str = "0 m"
            work_str = "0.0 h"
            avail_status = "Off Duty"

        rows.append({
            "cols": [
                e.employee_id,
                e.full_name,
                dept_name,
                att_status,
                check_in_str,
                check_out_str,
                break_str,
                work_str,
                avail_status,
            ],
            "status": avail_status,
        })

    for e in all_employees:
        att = attendance_map.get(e.id)
        lv = leave_map.get(e.id)
        dept_name = e.department.name if e.department else "—"

        if lv:
            att_status = f"On Leave ({lv.leave_type.value.replace('_', ' ').title()})"
            check_in_str = "—"
            check_out_str = "—"
            break_str = "0 m"
            work_str = "0.0 h"
            avail_status = "On Leave"
        elif att:
            att_status = att.status.value.title() if hasattr(att.status, "value") else str(att.status)
            check_in_str = att.check_in.strftime("%H:%M") if att.check_in else "—"
            check_out_str = att.check_out.strftime("%H:%M") if att.check_out else "Active"
            break_str = f"{att.break_duration_minutes:.0f} m"
            work_str = f"{att.net_working_minutes / 60.0:.1f} h"
            avail_status = "Checked Out" if att.check_out else "Available"
        else:
            att_status = "Not Checked In"
            check_in_str = "—"
            check_out_str = "—"
            break_str = "0 m"
            work_str = "0.0 h"
            avail_status = "Off Duty"

        export_data.append([
            e.employee_id,
            e.full_name,
            dept_name,
            att_status,
            check_in_str,
            check_out_str,
            break_str,
            work_str,
            avail_status,
        ])

    return {
        "headers": headers,
        "rows": rows,
        "export_data": export_data,
        "total_count": total_count,
        "summary_stats": {
            "Total Workforce": total_count,
            "Logged In Today": present_count,
            "On Approved Leave": on_leave_count,
        },
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


# ── PDF & Excel Exporters ──────────────────────────────────────────────────────

def _generate_excel(title, headers, data):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]

    navy = "0B192C"
    blue = "2563EB"

    col_count = max(len(headers), 1)

    # Title row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_count)
    title_cell = ws.cell(row=1, column=1, value=f"{title.upper()} — ENTERPRISE AUDIT")
    title_cell.font = Font(bold=True, size=13, color="FFFFFF", name="Arial")
    title_cell.fill = PatternFill("solid", fgColor=navy)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    # Subtitle with timestamp
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=col_count)
    sub_cell = ws.cell(row=2, column=1, value=f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Confidential")
    sub_cell.font = Font(size=9, color="64748B", italic=True, name="Arial")
    sub_cell.fill = PatternFill("solid", fgColor="F8FAFC")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18

    # Header row
    thin_border = Border(
        left=Side(style='thin', color="CBD5E1"),
        right=Side(style='thin', color="CBD5E1"),
        top=Side(style='thin', color="CBD5E1"),
        bottom=Side(style='thin', color="CBD5E1")
    )

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.font = Font(bold=True, color="FFFFFF", size=10, name="Arial")
        cell.fill = PatternFill("solid", fgColor=blue)
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = thin_border
    ws.row_dimensions[3].height = 24

    # Data rows
    for row_idx, row in enumerate(data, 4):
        bg_color = "FFFFFF" if row_idx % 2 == 0 else "F8FAFC"
        for col_idx, val in enumerate(row, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = Font(size=9, color="0F172A", name="Arial")
            cell.fill = PatternFill("solid", fgColor=bg_color)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            cell.border = thin_border
        ws.row_dimensions[row_idx].height = 20

    # Auto-adjust column widths
    from openpyxl.utils import get_column_letter
    for col_idx in range(1, len(headers) + 1):
        letter = get_column_letter(col_idx)
        max_len = len(str(headers[col_idx - 1]))
        for row_idx in range(4, len(data) + 4):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[letter].width = min(max_len + 4, 38)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _generate_pdf(title, headers, data):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=0.4 * inch,
        bottomMargin=0.4 * inch,
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0B192C")
    blue = colors.HexColor("#2563EB")

    elements = []
    # Title
    elements.append(Paragraph(title, ParagraphStyle(
        "ReportTitle", parent=styles["Heading1"],
        fontSize=15, textColor=navy, spaceAfter=2, fontName="Helvetica-Bold"
    )))
    # Subtitle
    elements.append(Paragraph(
        f"Employee Break Tracking & Availability Prediction System &bull; Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        ParagraphStyle("ReportSub", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#64748B"), spaceAfter=10)
    ))

    # Wrap strings in paragraphs for multi-line auto-wrap in ReportLab
    cell_style = ParagraphStyle("CellText", fontSize=7.5, leading=9.5, textColor=colors.HexColor("#0F172A"))
    header_style = ParagraphStyle("HeaderCell", fontSize=7.5, leading=9.5, textColor=colors.white, fontName="Helvetica-Bold")

    wrapped_headers = [Paragraph(str(h), header_style) for h in headers]
    wrapped_data = []
    for row in data:
        wrapped_data.append([Paragraph(str(val if val is not None else ""), cell_style) for val in row])

    table_data = [wrapped_headers] + wrapped_data
    col_count = max(len(headers), 1)
    available_width = landscape(A4)[0] - (0.8 * inch)
    col_width = available_width / col_count

    t = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]))
    elements.append(t)
    doc.build(elements)
    return buf.getvalue()
