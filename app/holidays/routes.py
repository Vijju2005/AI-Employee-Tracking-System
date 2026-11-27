"""
Holiday Management Blueprint for Employee Break Tracking System.
Provides 2026 Interactive Calendar, Holiday CRUD for Admins, and read-only views for Employees.
"""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import extract, or_
from app.extensions import db
from app.models import Holiday, CalendarYear, Employee
from app.time_utils import local_today

holidays_bp = Blueprint("holidays", __name__, url_prefix="/holidays")


@holidays_bp.route("/")
@login_required
def index():
    """
    Main Holiday Management and Calendar view.
    Displays the interactive 2026 calendar, list of holidays, search, and upcoming holidays.
    """
    today = local_today()
    current_year = 2026

    # Query all holidays ordered by date
    holidays = Holiday.query.order_by(Holiday.holiday_date.asc()).all()

    # Upcoming holidays (today or later)
    upcoming_holidays = [h for h in holidays if h.holiday_date >= today][:6]

    # Count of 2026 holidays
    holidays_2026_count = sum(1 for h in holidays if h.holiday_date.year == 2026)

    # Check if today is a holiday
    today_holiday = next((h for h in holidays if h.holiday_date == today), None)

    return render_template(
        "holidays/index.html",
        holidays=holidays,
        upcoming_holidays=upcoming_holidays,
        holidays_2026_count=holidays_2026_count,
        today=today,
        today_holiday=today_holiday,
        current_year=current_year,
    )


@holidays_bp.route("/api/events")
@login_required
def api_events():
    """
    Returns holiday events as JSON for dynamic calendar rendering.
    """
    year = request.args.get("year", type=int)
    query = Holiday.query
    if year:
        query = query.filter(extract("year", Holiday.holiday_date) == year)
    holidays = query.order_by(Holiday.holiday_date.asc()).all()

    data = [
        {
            "id": h.id,
            "title": h.holiday_name,
            "holiday_name": h.holiday_name,
            "date": h.holiday_date.isoformat(),
            "description": h.description or "",
            "is_past": h.holiday_date < local_today(),
        }
        for h in holidays
    ]
    return jsonify({"success": True, "holidays": data})


@holidays_bp.route("/add", methods=["POST"])
@login_required
def add_holiday():
    """
    Admin-only: Add a new holiday. Validates name, date, and uniqueness.
    """
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("holidays.index"))

    name = request.form.get("holiday_name", "").strip()
    date_str = request.form.get("holiday_date", "").strip()
    description = request.form.get("description", "").strip()

    if not name or not date_str:
        flash("Please provide both holiday name and holiday date.", "danger")
        return redirect(url_for("holidays.index"))

    try:
        holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format. Please select a valid date (YYYY-MM-DD).", "danger")
        return redirect(url_for("holidays.index"))

    # Check for duplicate date
    existing = Holiday.query.filter_by(holiday_date=holiday_date).first()
    if existing:
        flash(f"A holiday already exists on {holiday_date.strftime('%d %B %Y')} ({existing.holiday_name}).", "danger")
        return redirect(url_for("holidays.index"))

    try:
        new_holiday = Holiday(
            holiday_name=name,
            holiday_date=holiday_date,
            description=description or None,
            created_by=current_user.id,
        )
        db.session.add(new_holiday)
        db.session.commit()
        flash(f"Holiday '{name}' on {holiday_date.strftime('%d %b %Y')} added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding holiday: {str(e)}", "danger")

    return redirect(url_for("holidays.index"))


@holidays_bp.route("/<int:holiday_id>/edit", methods=["POST"])
@login_required
def edit_holiday(holiday_id):
    """
    Admin-only: Edit an existing holiday.
    """
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("holidays.index"))

    holiday = Holiday.query.get_or_404(holiday_id)

    name = request.form.get("holiday_name", "").strip()
    date_str = request.form.get("holiday_date", "").strip()
    description = request.form.get("description", "").strip()

    if not name or not date_str:
        flash("Holiday name and date are required.", "danger")
        return redirect(url_for("holidays.index"))

    try:
        new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for("holidays.index"))

    # Check if duplicate date on a different record
    duplicate = Holiday.query.filter(Holiday.holiday_date == new_date, Holiday.id != holiday_id).first()
    if duplicate:
        flash(f"Another holiday already exists on {new_date.strftime('%d %B %Y')} ({duplicate.holiday_name}).", "danger")
        return redirect(url_for("holidays.index"))

    try:
        holiday.holiday_name = name
        holiday.holiday_date = new_date
        holiday.description = description or None
        db.session.commit()
        flash(f"Holiday '{name}' updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating holiday: {str(e)}", "danger")

    return redirect(url_for("holidays.index"))


@holidays_bp.route("/<int:holiday_id>/delete", methods=["POST"])
@login_required
def delete_holiday(holiday_id):
    """
    Admin-only: Delete a holiday with confirmation.
    """
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("holidays.index"))

    holiday = Holiday.query.get_or_404(holiday_id)
    name = holiday.holiday_name
    date_formatted = holiday.holiday_date.strftime("%d %b %Y")

    try:
        db.session.delete(holiday)
        db.session.commit()
        flash(f"Holiday '{name}' ({date_formatted}) deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting holiday: {str(e)}", "danger")

    return redirect(url_for("holidays.index"))


# ── Calendar Year Management ───────────────────────────────────────────────────

@holidays_bp.route("/calendar-years")
@login_required
def calendar_years_list():
    """
    List all configured Calendar Years with stats, active/inactive toggles,
    and associated employees count.
    """
    if not current_user.is_admin:
        flash("Admin privileges required to manage Calendar Years.", "danger")
        return redirect(url_for("holidays.index"))

    years = CalendarYear.query.order_by(CalendarYear.start_date.desc()).all()
    
    # Calculate employee count who joined in each calendar year
    all_employees = Employee.query.all()
    emp_count_map = {}
    for y in years:
        emp_count_map[y.id] = 0

    unassigned_count = 0
    for emp in all_employees:
        if emp.date_joined:
            d = emp.date_joined.date() if hasattr(emp.date_joined, "date") else emp.date_joined
            matched = False
            for y in years:
                if y.start_date <= d <= y.end_date:
                    emp_count_map[y.id] += 1
                    matched = True
                    break
            if not matched:
                unassigned_count += 1
        else:
            unassigned_count += 1

    return render_template(
        "holidays/calendar_years.html",
        years=years,
        emp_count_map=emp_count_map,
        unassigned_count=unassigned_count,
        total_employees=len(all_employees),
    )


@holidays_bp.route("/calendar-years/add", methods=["POST"])
@login_required
def add_calendar_year():
    """Add a new calendar year with validation."""
    if not current_user.is_admin:
        flash("Admin privileges required.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    name = request.form.get("name", "").strip()
    start_date_str = request.form.get("start_date", "").strip()
    end_date_str = request.form.get("end_date", "").strip()
    is_active = request.form.get("is_active") == "on" or request.form.get("is_active") == "true" or request.form.get("is_active") == "1"

    if not all([name, start_date_str, end_date_str]):
        flash("All fields (Calendar Name, Start Date, End Date) are required.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format. Please select valid calendar dates.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    if start_date >= end_date:
        flash("Start date must be strictly before end date.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    # Uniqueness check on Name
    if CalendarYear.query.filter(CalendarYear.name.ilike(name)).first():
        flash(f"A calendar year named '{name}' already exists.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    # Conflicting or overlapping periods check
    conflict = CalendarYear.query.filter(
        CalendarYear.start_date <= end_date,
        CalendarYear.end_date >= start_date
    ).first()
    if conflict:
        flash(f"Date range overlaps with existing '{conflict.name}' ({conflict.start_date} to {conflict.end_date}).", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    cy = CalendarYear(
        name=name,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
    )
    db.session.add(cy)
    try:
        db.session.commit()
        flash(f"Calendar Year '{name}' created successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving calendar year: {str(e)}", "danger")

    return redirect(url_for("holidays.calendar_years_list"))


@holidays_bp.route("/calendar-years/<int:year_id>/edit", methods=["POST"])
@login_required
def edit_calendar_year(year_id):
    """Edit an existing calendar year."""
    if not current_user.is_admin:
        flash("Admin privileges required.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    cy = CalendarYear.query.get_or_404(year_id)
    name = request.form.get("name", "").strip()
    start_date_str = request.form.get("start_date", "").strip()
    end_date_str = request.form.get("end_date", "").strip()
    is_active = request.form.get("is_active") == "on" or request.form.get("is_active") == "true" or request.form.get("is_active") == "1"

    if not all([name, start_date_str, end_date_str]):
        flash("All fields are required.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    if start_date >= end_date:
        flash("Start date must be strictly before end date.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    # Uniqueness check on Name excluding self
    existing_name = CalendarYear.query.filter(CalendarYear.id != cy.id, CalendarYear.name.ilike(name)).first()
    if existing_name:
        flash(f"Another calendar year named '{name}' already exists.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    # Conflicting or overlapping periods check excluding self
    conflict = CalendarYear.query.filter(
        CalendarYear.id != cy.id,
        CalendarYear.start_date <= end_date,
        CalendarYear.end_date >= start_date
    ).first()
    if conflict:
        flash(f"Date range overlaps with existing '{conflict.name}' ({conflict.start_date} to {conflict.end_date}).", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    cy.name = name
    cy.start_date = start_date
    cy.end_date = end_date
    cy.is_active = is_active
    try:
        db.session.commit()
        flash(f"Calendar Year '{name}' updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating calendar year: {str(e)}", "danger")

    return redirect(url_for("holidays.calendar_years_list"))


@holidays_bp.route("/calendar-years/<int:year_id>/toggle-status", methods=["POST"])
@login_required
def toggle_calendar_year_status(year_id):
    """Toggle Active/Inactive status of a calendar year."""
    if not current_user.is_admin:
        flash("Admin privileges required.", "danger")
        return redirect(url_for("holidays.calendar_years_list"))

    cy = CalendarYear.query.get_or_404(year_id)
    cy.is_active = not cy.is_active
    db.session.commit()
    state_str = "activated" if cy.is_active else "deactivated"
    flash(f"Calendar Year '{cy.name}' has been {state_str}.", "info")
    return redirect(url_for("holidays.calendar_years_list"))


@holidays_bp.route("/calendar-years/<int:year_id>/employees")
@login_required
def view_calendar_year_employees(year_id):
    """
    View employees who joined during a selected calendar year.
    """
    if not current_user.is_admin:
        flash("Admin privileges required.", "danger")
        return redirect(url_for("holidays.index"))

    cy = CalendarYear.query.get_or_404(year_id)
    start_dt = datetime.combine(cy.start_date, datetime.min.time())
    end_dt = datetime.combine(cy.end_date, datetime.max.time())

    employees = Employee.query.filter(
        Employee.date_joined >= start_dt,
        Employee.date_joined <= end_dt
    ).order_by(Employee.date_joined.asc()).all()

    return render_template(
        "holidays/calendar_year_employees.html",
        calendar_year=cy,
        employees=employees,
    )
