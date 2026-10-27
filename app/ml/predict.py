"""
EBT System — ML Prediction
Makes predictions for a given employee/category/context.
"""

from datetime import datetime, timezone
import numpy as np
import pandas as pd

from app.ml.preprocessing import FEATURE_COLS, MIN_SAMPLES_FOR_RF


def predict_break_duration(
    train_result: dict,
    category: str,
    weekday: int,
    hour_of_day: int,
    scheduled_hours: float,
    prior_breaks_today: int,
    rolling_avg: float | None = None,
) -> dict:
    """
    Returns a prediction dict:
      - predicted_break_minutes
      - model_used
      - baseline_mae, baseline_rmse
      - rf_mae, rf_rmse (if RF was used)
      - is_demo: True if prediction is based on insufficient data
    """
    cat_map = {"Lunch": 0, "Tea": 1, "Coffee": 2, "Personal": 3, "Other": 4}
    cat_encoded = cat_map.get(category, 4)

    cat_avg = train_result.get("category_averages", {})
    n_samples = train_result.get("n_samples", 0)
    rf_model = train_result.get("model")

    # Fallback rolling avg
    if rolling_avg is None:
        rolling_avg = cat_avg.get(category, 15.0)
    if rolling_avg == 0:
        rolling_avg = 15.0

    is_demo = n_samples < 5

    if rf_model is not None and n_samples >= MIN_SAMPLES_FOR_RF:
        features = pd.DataFrame([{
            "weekday": weekday,
            "hour_of_day": hour_of_day,
            "category_encoded": cat_encoded,
            "scheduled_hours": scheduled_hours,
            "prior_breaks_today": prior_breaks_today,
            "rolling_avg": rolling_avg,
        }])
        pred = float(rf_model.predict(features[FEATURE_COLS])[0])
        model_used = "Random Forest"
    else:
        # Baseline: category average from training
        pred = float(cat_avg.get(category, rolling_avg or 15.0))
        model_used = "Historical Average Baseline"

    pred = max(1.0, round(pred, 1))

    return {
        "predicted_break_minutes": pred,
        "model_used": model_used,
        "baseline_mae": train_result.get("baseline_mae"),
        "baseline_rmse": train_result.get("baseline_rmse"),
        "rf_mae": train_result.get("rf_mae"),
        "rf_rmse": train_result.get("rf_rmse"),
        "n_samples": n_samples,
        "is_demo": is_demo,
        "status": train_result.get("status", ""),
    }


def calculate_available_time(
    scheduled_end_time,  # datetime
    current_time: datetime,
    already_elapsed_break_minutes: float,
    predicted_future_break_minutes: float,
) -> float:
    """
    Estimated available working time (minutes) from now until end of shift,
    minus predicted future breaks only (already-elapsed breaks are NOT subtracted again).
    
    Returns 0 if past end of shift.
    """
    if scheduled_end_time is None:
        return None

    remaining_shift = (scheduled_end_time - current_time).total_seconds() / 60
    if remaining_shift <= 0:
        return 0.0

    available = remaining_shift - max(0.0, predicted_future_break_minutes)
    return max(0.0, round(available, 1))
