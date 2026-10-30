"""
Holiday Management Blueprint for Employee Break Tracking System.
Provides 2026 Interactive Calendar, Holiday CRUD for Admins, and read-only views for Employees.
"""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import extract
from app.extensions import db
from app.models import Holiday
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
