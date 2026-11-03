"""
Payroll Blueprint & Routes.
Handles:
1. Executive Payroll Dashboard matching the attached screenshot
2. Employee Salary Management (View, Add, Edit salary structures)
3. Payslip Generation, History, and PDF Downloads
4. Payroll Items / Pay Components (Earnings & Deductions)
"""

from datetime import datetime, date
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    send_file, abort, jsonify, make_response
)
from flask_login import login_required, current_user
import io

from app.extensions import db
from app.models import (
    Employee, UserRole, EmployeeSalary, PayrollRun,
    PayrollItem, PayrollItemType, StatutoryCompliance, Payslip
)
from app.payroll.seeder import seed_default_payroll_items
from app.payroll.pdf_generator import generate_payslip_pdf


payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── 1. Payroll Dashboard (Executive View matching screenshot) ──────────────────

@payroll_bp.route("/")
@payroll_bp.route("/dashboard")
@login_required
def index():
    """
    Main Executive Payroll Dashboard.
    Matches the reference screenshot layout:
    - 4 KPI cards (Total Employees, Total Salary Cost, Net Payout, Avg CTC)
    - Salary Cost Summary Donut Chart (Amount / % view)
    - Statutory Compliance card (PF, ESI, TDS, PT, LWF with real recorded status)
    - Payslip Progress circular donut tracker
    - Recent Payroll Runs Table (Searchable)
    - Deductions Overview Bar Chart
    """
    # Auto-seed items if table is freshly created
    seed_default_payroll_items(db.session)

    # Active view mode: 'dashboard' (default) or 'list'
    view_mode = request.args.get("view", "dashboard").strip().lower()
    if view_mode not in ["dashboard", "list"]:
        view_mode = "dashboard"

    # Filter parameters
    selected_month = request.args.get("month", "").strip()
    selected_emp = request.args.get("employee", "").strip()
    selected_dept = request.args.get("dept", "").strip()
    selected_status = request.args.get("status", "").strip()
    search_q = request.args.get("q", "").strip()

    # Available payroll runs
    all_runs = PayrollRun.query.order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).all()

    current_run = None
    if selected_month:
        current_run = PayrollRun.query.filter_by(payroll_month=selected_month).first()
        if not current_run:
            current_run = PayrollRun.query.filter_by(month_code=selected_month).first()

    if not current_run and all_runs:
        current_run = all_runs[0]

    # Current month label for display
    active_month_label = current_run.payroll_month if current_run else datetime.now().strftime("%B %Y")
    active_month_code = current_run.month_code if current_run else datetime.now().strftime("%Y-%m")

    # If a specific run exists, use its historical metrics
    if current_run:
        total_employees = current_run.total_employees
        total_salary_cost = current_run.total_salary_cost
        net_payout = current_run.net_payout
        avg_ctc = current_run.average_ctc

        # Cost summary breakdown
        cost_summary = {
            "basic": current_run.total_basic,
            "hra": current_run.total_hra,
            "special": current_run.total_special,
            "other_allow": current_run.total_other_allowances,
            "employer_contrib": current_run.total_employer_contributions,
            "other_payments": current_run.total_other_payments,
        }

        # Deductions breakdown
        deductions_summary = {
            "pf": current_run.total_pf,
            "tds": current_run.total_tds,
            "esi": current_run.total_esi,
            "prof_tax": current_run.total_prof_tax,
            "lwf": current_run.total_lwf,
            "other": current_run.total_other_deductions,
        }

        # Payslip progress
        payslip_stats = {
            "generated": current_run.payslips_generated,
            "in_progress": current_run.payslips_in_progress,
            "yet_to_start": current_run.payslips_yet_to_start,
            "total": total_employees,
            "percentage": round((current_run.payslips_generated / total_employees * 100) if total_employees > 0 else 0),
        }
    else:
        # Compute dynamically from live active employee salary structures
        active_employees = Employee.query.filter_by(status="active").all()
        total_employees = len(active_employees)

        salaries = [e.salary_structure for e in active_employees if e.salary_structure]

        if salaries:
            total_salary_cost = sum(s.ctc / 12.0 for s in salaries)
            net_payout = sum(s.net_salary for s in salaries)
            avg_ctc = (sum(s.ctc for s in salaries) / len(salaries)) if salaries else 0.0

            cost_summary = {
                "basic": sum(s.basic_salary for s in salaries),
                "hra": sum(s.hra for s in salaries),
                "special": sum(s.special_allowance for s in salaries),
                "other_allow": sum(s.other_allowances for s in salaries),
                "employer_contrib": sum(s.employer_contributions for s in salaries),
                "other_payments": sum(s.other_payments for s in salaries),
            }

            deductions_summary = {
                "pf": sum(s.pf_deduction for s in salaries),
                "tds": sum(s.tds_deduction for s in salaries),
                "esi": sum(s.esi_deduction for s in salaries),
                "prof_tax": sum(s.prof_tax for s in salaries),
                "lwf": sum(s.lwf_deduction for s in salaries),
                "other": sum(s.other_deductions for s in salaries),
            }

            # Check existing payslips for active month
            gen_count = Payslip.query.filter_by(month_code=active_month_code, status="Generated").count()
            prog_count = Payslip.query.filter_by(month_code=active_month_code, status="In Progress").count()
            yet_count = max(0, total_employees - gen_count - prog_count)
            pct = round((gen_count / total_employees * 100) if total_employees > 0 else 0)

            payslip_stats = {
                "generated": gen_count,
                "in_progress": prog_count,
                "yet_to_start": yet_count,
                "total": total_employees,
                "percentage": pct,
            }
        else:
            total_salary_cost = 0.0
            net_payout = 0.0
            avg_ctc = 0.0
            cost_summary = {"basic": 0.0, "hra": 0.0, "special": 0.0, "other_allow": 0.0, "employer_contrib": 0.0, "other_payments": 0.0}
            deductions_summary = {"pf": 0.0, "tds": 0.0, "esi": 0.0, "prof_tax": 0.0, "lwf": 0.0, "other": 0.0}
            payslip_stats = {"generated": 0, "in_progress": 0, "yet_to_start": total_employees, "total": total_employees, "percentage": 0}

    # Statutory Compliance items (actual recorded status)
    compliance_items = StatutoryCompliance.query.filter(
        StatutoryCompliance.period.ilike(f"%{active_month_label[:3]}%") |
        StatutoryCompliance.period.ilike(f"%{active_month_label}%")
    ).all()

    if not compliance_items:
        # Fallback to all recent records
        compliance_items = StatutoryCompliance.query.order_by(StatutoryCompliance.id.desc()).limit(5).all()

    # Recent runs table (top 5)
    recent_runs = all_runs[:6]

    # Distinct payroll months from payslips and payroll runs for filters
    payslip_months = [m[0] for m in db.session.query(Payslip.payroll_month).distinct().all() if m[0]]
    run_months = [r.payroll_month for r in all_runs]
    distinct_months = sorted(list(set(run_months + payslip_months + [active_month_label])), reverse=True)

    # Departments list for filter dropdown
    from app.models import Department
    all_departments = Department.query.order_by(Department.name).all()

    # Active employees list for filter dropdown
    filter_employees = Employee.query.order_by(Employee.full_name).all()

    # Build List View dataset from actual database records (Payslips prioritized, fallback to Salary Structure)
    list_query = db.session.query(
        Employee,
        EmployeeSalary,
        Payslip
    ).outerjoin(EmployeeSalary, Employee.id == EmployeeSalary.employee_id)\
     .outerjoin(Payslip, db.and_(
         Employee.id == Payslip.employee_id,
         db.or_(Payslip.payroll_month == active_month_label, Payslip.month_code == active_month_code)
     ))

    # Apply filters
    if selected_emp:
        if selected_emp.isdigit():
            list_query = list_query.filter(Employee.id == int(selected_emp))
        else:
            list_query = list_query.filter(
                db.or_(
                    Employee.full_name.ilike(f"%{selected_emp}%"),
                    Employee.employee_id.ilike(f"%{selected_emp}%")
                )
            )

    if selected_dept and selected_dept.isdigit():
        list_query = list_query.filter(Employee.department_id == int(selected_dept))

    if search_q:
        list_query = list_query.filter(
            db.or_(
                Employee.full_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
                Employee.email.ilike(f"%{search_q}%")
            )
        )

    employee_rows = list_query.order_by(Employee.full_name).all()

    list_items = []
    for emp, sal, slip in employee_rows:
        # Determine gross, deductions, net, and status
        if slip:
            gross = slip.gross_earnings
            deductions = slip.total_deductions
            net = slip.net_salary
            status = slip.status or "Generated"
            payslip_id = slip.id
            month_label = slip.payroll_month
        elif sal:
            gross = sal.gross_salary
            deductions = sal.total_deductions
            net = sal.net_salary
            status = "Ready to Generate"
            payslip_id = None
            month_label = active_month_label
        else:
            gross = 0.0
            deductions = 0.0
            net = 0.0
            status = "Structure Pending"
            payslip_id = None
            month_label = active_month_label

        # Filter by status if selected
        if selected_status and selected_status.lower() != status.lower():
            continue

        dept_name = emp.department.name if emp.department else (emp.department_id and f"Dept {emp.department_id}" or "General")

        list_items.append({
            "employee": emp,
            "employee_id": emp.employee_id,
            "employee_name": emp.full_name,
            "department": dept_name,
            "payroll_month": month_label,
            "gross_salary": gross,
            "total_deductions": deductions,
            "net_salary": net,
            "status": status,
            "payslip_id": payslip_id,
            "has_salary_structure": sal is not None,
        })

    return render_template(
        "payroll/dashboard.html",
        view_mode=view_mode,
        selected_month=selected_month or active_month_label,
        selected_emp=selected_emp,
        selected_dept=selected_dept,
        selected_status=selected_status,
        search_q=search_q,
        distinct_months=distinct_months,
        all_departments=all_departments,
        filter_employees=filter_employees,
        list_items=list_items,
        active_month_label=active_month_label,
        active_month_code=active_month_code,
        all_runs=all_runs,
        total_employees=total_employees,
        total_salary_cost=total_salary_cost,
        net_payout=net_payout,
        avg_ctc=avg_ctc,
        cost_summary=cost_summary,
        deductions_summary=deductions_summary,
        compliance_items=compliance_items,
        payslip_stats=payslip_stats,
        recent_runs=recent_runs,
    )


# ── 2. Employee Salary Section (Manage & Edit Salary Structures) ───────────────

@payroll_bp.route("/salaries")
@login_required
@admin_required
def salaries_list():
    """Admin view of all employee salaries with search and department filtering."""
    q = request.args.get("q", "").strip()
    dept_id = request.args.get("dept", "").strip()

    query = Employee.query
    if q:
        query = query.filter(
            db.or_(
                Employee.full_name.ilike(f"%{q}%"),
                Employee.employee_id.ilike(f"%{q}%"),
                Employee.email.ilike(f"%{q}%"),
            )
        )
    if dept_id:
        query = query.filter_by(department_id=int(dept_id))

    employees = query.order_by(Employee.full_name).all()
    from app.models import Department
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        "payroll/salaries.html",
        employees=employees,
        departments=departments,
    )


@payroll_bp.route("/salaries/<int:emp_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_salary(emp_id):
    """View and edit an employee's salary structure with automatic total recalculation."""
    employee = Employee.query.get_or_404(emp_id)
    salary = employee.salary_structure

    if not salary:
        salary = EmployeeSalary(employee_id=employee.id)
        db.session.add(salary)

    error = None
    if request.method == "POST":
        try:
            salary.basic_salary = float(request.form.get("basic_salary", 0) or 0)
            salary.hra = float(request.form.get("hra", 0) or 0)
            salary.special_allowance = float(request.form.get("special_allowance", 0) or 0)
            salary.other_allowances = float(request.form.get("other_allowances", 0) or 0)
            salary.bonus = float(request.form.get("bonus", 0) or 0)
            salary.employer_contributions = float(request.form.get("employer_contributions", 0) or 0)
            salary.other_payments = float(request.form.get("other_payments", 0) or 0)

            # Deductions
            salary.pf_deduction = float(request.form.get("pf_employee") or request.form.get("pf_deduction", 0) or 0)
            salary.esi_deduction = float(request.form.get("esi_employee") or request.form.get("esi_deduction", 0) or 0)
            salary.tds_deduction = float(request.form.get("tds") or request.form.get("tds_deduction", 0) or 0)
            salary.prof_tax = float(request.form.get("professional_tax") or request.form.get("prof_tax", 0) or 0)
            salary.lwf_deduction = float(request.form.get("lwf") or request.form.get("lwf_deduction", 0) or 0)
            salary.other_deductions = float(request.form.get("other_deductions", 0) or 0)

            salary.payment_mode = request.form.get("payment_mode", "Bank Transfer").strip()
            salary.bank_name = request.form.get("bank_name", "").strip() or None
            salary.account_number = request.form.get("account_number", "").strip() or None
            salary.ifsc_code = request.form.get("ifsc_code", "").strip() or None

            eff_date_str = request.form.get("effective_date", "").strip()
            if eff_date_str:
                salary.effective_date = datetime.strptime(eff_date_str, "%Y-%m-%d").date()

            # Auto calculate gross, total deductions, net salary, and CTC
            salary.compute_totals()

            db.session.commit()
            flash(f"Salary structure for {employee.full_name} updated successfully. Net Pay: INR {salary.net_salary:,.2f}", "success")
            return redirect(url_for("payroll.salaries_list"))
        except Exception as e:
            db.session.rollback()
            error = f"Error saving salary: {str(e)}"

    return render_template(
        "payroll/salary_form.html",
        employee=employee,
        salary=salary,
        error=error,
    )


# ── 3. Payslip Section (Generation, History, and PDF Download) ─────────────────

@payroll_bp.route("/payslips")
@login_required
def payslips_list():
    """
    List payslips.
    - Admins see all employee payslips with search & month filter.
    - Standard employees only see their own payslips (Strict privacy protection).
    """
    month_filter = request.args.get("month", "").strip()
    q = request.args.get("q", "").strip()

    query = Payslip.query.join(Employee)

    if not current_user.is_admin:
        if current_user.employee:
            query = query.filter(Payslip.employee_id == current_user.employee.id)
        else:
            query = query.filter(db.false())
    else:
        if q:
            query = query.filter(
                db.or_(
                    Employee.full_name.ilike(f"%{q}%"),
                    Employee.employee_id.ilike(f"%{q}%"),
                    Payslip.payslip_number.ilike(f"%{q}%"),
                )
            )

    if month_filter:
        query = query.filter(
            db.or_(
                Payslip.payroll_month == month_filter,
                Payslip.month_code == month_filter
            )
        )

    payslips = query.order_by(Payslip.id.desc()).limit(150).all()

    # Distinct month options
    distinct_months = [
        r[0] for r in db.session.query(Payslip.payroll_month).distinct().all()
    ]

    return render_template(
        "payroll/payslips.html",
        payslips=payslips,
        distinct_months=distinct_months,
    )


@payroll_bp.route("/payslips/generate", methods=["GET", "POST"])
@login_required
@admin_required
def generate_payslip():
    """
    Admin payslip generation form:
    Select employee, choose month, automatically load current salary structure,
    customize if necessary, and create the verified payslip.
    """
    employees = Employee.query.filter_by(status="active").order_by(Employee.full_name).all()
    error = None

    if request.method == "POST":
        emp_id = request.form.get("employee_id")
        payroll_month = request.form.get("payroll_month", "").strip()  # e.g., "May 2025"
        month_code = request.form.get("month_code", "").strip()        # e.g., "2025-05"

        if not emp_id or not payroll_month:
            error = "Please select an employee and payroll month."
        else:
            employee = Employee.query.get(int(emp_id))
            if not employee:
                error = "Employee not found."
            else:
                if not month_code:
                    try:
                        # parse month code from "May 2025"
                        dt = datetime.strptime(payroll_month, "%B %Y")
                        month_code = dt.strftime("%Y-%m")
                    except Exception:
                        month_code = datetime.now().strftime("%Y-%m")

                # Check if payslip already exists for this employee in this month
                existing = Payslip.query.filter_by(employee_id=employee.id, month_code=month_code).first()
                if existing:
                    flash(f"A payslip for {employee.full_name} for {payroll_month} already exists (Ref: {existing.payslip_number}).", "warning")
                    return redirect(url_for("payroll.view_payslip", payslip_id=existing.id))

                sal = employee.salary_structure
                # Extract figures from form or salary structure
                basic = float(request.form.get("basic_pay") or request.form.get("basic_salary") or (sal.basic_salary if sal else 0.0) or 0.0)
                hra = float(request.form.get("hra") or (sal.hra if sal else 0.0) or 0.0)
                special = float(request.form.get("special_allowance") or (sal.special_allowance if sal else 0.0) or 0.0)
                other_allow = float(request.form.get("other_allowances") or (sal.other_allowances if sal else 0.0) or 0.0)
                bonus = float(request.form.get("bonus") or (sal.bonus if sal else 0.0) or 0.0)

                pf = float(request.form.get("pf_employee") or request.form.get("pf_deduction") or (sal.pf_deduction if sal else 0.0) or 0.0)
                esi = float(request.form.get("esi_employee") or request.form.get("esi_deduction") or (sal.esi_deduction if sal else 0.0) or 0.0)
                tds = float(request.form.get("tds") or request.form.get("tds_deduction") or (sal.tds_deduction if sal else 0.0) or 0.0)
                pt = float(request.form.get("professional_tax") or request.form.get("prof_tax") or (sal.prof_tax if sal else 0.0) or 0.0)
                lwf = float(request.form.get("lwf") or request.form.get("lwf_deduction") or (sal.lwf_deduction if sal else 0.0) or 0.0)
                other_ded = float(request.form.get("other_deductions") or (sal.other_deductions if sal else 0.0) or 0.0)

                gross = basic + hra + special + other_allow + bonus
                tot_ded = pf + esi + tds + pt + lwf + other_ded
                net = max(0.0, gross - tot_ded)

                working_days = int(request.form.get("working_days", 30) or 30)
                days_present = float(request.form.get("paid_days") or request.form.get("days_present") or 30.0)
                days_absent = float(request.form.get("lop_days") or max(0.0, working_days - days_present))

                # Generate reference number
                now_str = datetime.now().strftime("%y%m%d%H%M")
                slip_ref = f"PS-{employee.employee_id}-{now_str[-5:]}"

                payslip = Payslip(
                    payslip_number=slip_ref,
                    employee_id=employee.id,
                    payroll_month=payroll_month,
                    month_code=month_code,
                    working_days=working_days,
                    days_present=days_present,
                    days_absent=days_absent,
                    basic_salary=round(basic, 2),
                    hra=round(hra, 2),
                    special_allowance=round(special, 2),
                    other_allowances=round(other_allow, 2),
                    bonus=round(bonus, 2),
                    gross_earnings=round(gross, 2),
                    pf_deduction=round(pf, 2),
                    esi_deduction=round(esi, 2),
                    tds_deduction=round(tds, 2),
                    prof_tax=round(pt, 2),
                    lwf_deduction=round(lwf, 2),
                    other_deductions=round(other_ded, 2),
                    total_deductions=round(tot_ded, 2),
                    net_salary=round(net, 2),
                    status="Generated",
                )
                db.session.add(payslip)
                db.session.commit()

                flash(f"Payslip {slip_ref} generated successfully for {employee.full_name}!", "success")
                return redirect(url_for("payroll.view_payslip", payslip_id=payslip.id))

    return render_template(
        "payroll/generate_payslip.html",
        employees=employees,
        error=error,
    )


@payroll_bp.route("/payslips/<int:payslip_id>")
@login_required
def view_payslip(payslip_id):
    """View individual payslip details with earnings, deductions, and PDF export."""
    payslip = Payslip.query.get_or_404(payslip_id)

    # Permission check: Standard employees can only view their own payslips
    if not current_user.is_admin:
        if not current_user.employee or current_user.employee.id != payslip.employee_id:
            abort(403)

    return render_template("payroll/view_payslip.html", payslip=payslip)


@payroll_bp.route("/payslips/<int:payslip_id>/pdf")
@login_required
def download_payslip_pdf(payslip_id):
    """Download official PDF payslip document."""
    payslip = Payslip.query.get_or_404(payslip_id)

    # Permission check: Standard employees can only download their own payslips
    if not current_user.is_admin:
        if not current_user.employee or current_user.employee.id != payslip.employee_id:
            abort(403)

    employee = payslip.employee
    company = employee.company_name if employee and employee.company_name else "EBT Enterprise System"
    pdf_bytes = generate_payslip_pdf(payslip, employee, company_name=company)

    filename = f"Payslip_{employee.employee_id}_{payslip.month_code}.pdf"
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# ── 4. Payroll Items (Pay Components) ──────────────────────────────────────────

@payroll_bp.route("/components", methods=["GET"])
@login_required
@admin_required
def components_list():
    """Manage earning and deduction pay components."""
    seed_default_payroll_items(db.session)

    earnings = PayrollItem.query.filter_by(item_type=PayrollItemType.EARNING).order_by(PayrollItem.name).all()
    deductions = PayrollItem.query.filter_by(item_type=PayrollItemType.DEDUCTION).order_by(PayrollItem.name).all()

    return render_template(
        "payroll/components.html",
        earnings=earnings,
        deductions=deductions,
    )


@payroll_bp.route("/components", methods=["POST"])
@payroll_bp.route("/components/add", methods=["POST"])
@login_required
@admin_required
def add_component():
    """Add a new custom or statutory pay component."""
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    item_type_str = (request.form.get("type") or request.form.get("item_type") or "earning").strip().lower()
    description = request.form.get("description", "").strip()
    is_statutory = request.form.get("is_statutory") in ["on", "true", "1", "True"]

    if not name or not code:
        flash("Name and Component Code are required.", "danger")
        return redirect(url_for("payroll.components_list"))

    if PayrollItem.query.filter(db.or_(PayrollItem.name == name, PayrollItem.code == code)).first():
        flash(f"A payroll component with name '{name}' or code '{code}' already exists.", "warning")
        return redirect(url_for("payroll.components_list"))

    item_type = PayrollItemType.EARNING if item_type_str == "earning" else PayrollItemType.DEDUCTION
    p_item = PayrollItem(
        name=name,
        code=code,
        item_type=item_type,
        description=description,
        is_statutory=is_statutory,
        is_active=True,
    )
    db.session.add(p_item)
    db.session.commit()
    flash(f"Pay component '{name}' ({code}) created successfully.", "success")
    return redirect(url_for("payroll.components_list"))


@payroll_bp.route("/components/<int:item_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_component(item_id):
    """Activate or deactivate a pay component."""
    item = PayrollItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    status_str = "activated" if item.is_active else "deactivated"
    flash(f"Pay component '{item.name}' has been {status_str}.", "info")
    return redirect(url_for("payroll.components_list"))


# ── 5. Helper API for Salary Autofill ──────────────────────────────────────────

@payroll_bp.route("/api/employee-salary/<int:emp_id>")
@login_required
@admin_required
def api_employee_salary(emp_id):
    """Returns an employee's salary breakdown for instant form autofill."""
    emp = Employee.query.get_or_404(emp_id)
    sal = emp.salary_structure
    if not sal:
        return jsonify({
            "has_salary": False,
            "full_name": emp.full_name,
            "employee_id": emp.employee_id,
        })

    return jsonify({
        "has_salary": True,
        "full_name": emp.full_name,
        "employee_id": emp.employee_id,
        "basic_salary": sal.basic_salary,
        "hra": sal.hra,
        "special_allowance": sal.special_allowance,
        "other_allowances": sal.other_allowances,
        "bonus": sal.bonus,
        "pf_deduction": sal.pf_deduction,
        "esi_deduction": sal.esi_deduction,
        "tds_deduction": sal.tds_deduction,
        "prof_tax": sal.prof_tax,
        "lwf_deduction": sal.lwf_deduction,
        "other_deductions": sal.other_deductions,
        "gross_salary": sal.gross_salary,
        "total_deductions": sal.total_deductions,
        "net_salary": sal.net_salary,
    })
