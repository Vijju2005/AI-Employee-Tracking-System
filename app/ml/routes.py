"""
EBT System – ML Prediction Routes
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Employee, UserRole, Break, Attendance, WorkSchedule

ml_bp = Blueprint("ml", __name__, url_prefix="/ml")


@ml_bp.route("/")
@login_required
def index():
    employees = Employee.query.order_by(Employee.full_name).all() if current_user.is_admin else []
    return render_template("ml/index.html", employees=employees, prediction=None)


@ml_bp.route("/predict", methods=["POST"])
@login_required
def predict():
    from datetime import datetime, date
    import math

    employee_id = request.form.get("employee_id")
    break_category = request.form.get("break_category", "Lunch")

    # Resolve employee
    if current_user.is_admin:
        if not employee_id:
            flash("Please select an employee.", "warning")
            return redirect(url_for("ml.index"))
        employee = Employee.query.get(int(employee_id))
    else:
        employee = current_user.employee

    if not employee:
        flash("Employee not found.", "danger")
        return redirect(url_for("ml.index"))

    # Get all completed breaks for this employee in this category
    breaks = (
        Break.query
        .filter_by(employee_id=employee.id, category=break_category)
        .filter(Break.end_time.isnot(None))
        .filter(Break.duration_minutes > 0)
        .all()
    )

    prediction_result = None
    mae, rmse, model_used = None, None, "Historical Average"

    if len(breaks) == 0:
        # Global average fallback
        all_breaks = Break.query.filter(
            Break.category == break_category,
            Break.end_time.isnot(None),
            Break.duration_minutes > 0,
        ).all()
        durations = [b.duration_minutes for b in all_breaks]
        avg_duration = sum(durations) / len(durations) if durations else 30.0
        model_used = "Global Average (no personal history)"
    else:
        durations = [b.duration_minutes for b in breaks]
        avg_duration = sum(durations) / len(durations)
        model_used = "Historical Average (personal)"

        # Try Random Forest if 20+ records
        if len(breaks) >= 20:
            try:
                avg_duration, mae, rmse, model_used = _train_and_predict(
                    employee, break_category, breaks, avg_duration
                )
            except Exception as e:
                flash(f"ML model training error (using average): {e}", "warning")

    # Scheduled working hours
    sched_hours = 8.0
    if employee.work_schedule:
        sched_hours = employee.work_schedule.total_hours

    available_minutes = max(0.0, (sched_hours * 60) - avg_duration)

    class PredictionResult:
        pass

    p = PredictionResult()
    p.employee_id = employee.id
    p.category = break_category
    p.predicted_break_minutes = round(avg_duration, 1)
    p.predicted_available_minutes = round(available_minutes, 1)
    p.model_used = model_used
    p.mae = round(mae, 2) if mae is not None else None
    p.rmse = round(rmse, 2) if rmse is not None else None

    employees = Employee.query.order_by(Employee.full_name).all() if current_user.is_admin else []
    return render_template("ml/index.html", employees=employees, prediction=p)


def _train_and_predict(employee, category, breaks, fallback):
    """Train Random Forest and return (predicted_duration, mae, rmse, model_name)."""
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    cat_map = {"Lunch": 0, "Tea": 1, "Coffee": 2, "Personal": 3, "Other": 4}
    cat_enc = cat_map.get(category, 4)
    sched_hours = employee.work_schedule.total_hours if employee.work_schedule else 8.0

    X, y = [], []
    for b in sorted(breaks, key=lambda x: x.start_time):
        X.append([
            b.start_time.weekday(),
            b.start_time.hour,
            cat_enc,
            sched_hours,
        ])
        y.append(b.duration_minutes)

    X = np.array(X)
    y = np.array(y)

    split = max(1, int(len(X) * 0.8))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)

    # Evaluation
    mae, rmse = None, None
    if len(X_test) > 0:
        preds = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, preds))
        from math import sqrt
        rmse = float(sqrt(mean_squared_error(y_test, preds)))

    # Predict for now
    from datetime import datetime
    now = datetime.now()
    pred_features = np.array([[now.weekday(), now.hour, cat_enc, sched_hours]])
    predicted = float(model.predict(pred_features)[0])
    predicted = max(1.0, predicted)

    return predicted, mae, rmse, "Random Forest"
