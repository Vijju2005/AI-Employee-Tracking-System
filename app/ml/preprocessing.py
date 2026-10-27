"""
EBT System — ML Preprocessing
Prepares historical break records as features for prediction.
"""

import pandas as pd
import numpy as np
from datetime import date


def build_feature_dataframe(breaks_with_attendance):
    """
    Accepts a list of (Break, Attendance, Employee) tuples from SQLAlchemy
    and returns a cleaned Pandas DataFrame with ML-ready features.
    
    Features (no target leakage — only info available at prediction time):
      - weekday (0=Mon … 6=Sun)
      - hour_of_day (hour break started)
      - category_encoded (label-encoded break category)
      - scheduled_hours (from work schedule)
      - prior_breaks_today (how many breaks the employee already had that day)
      - rolling_avg_duration (emp's 7-day rolling avg break duration by category)
    
    Target:
      - duration_minutes (actual break duration)
    """
    records = []
    for brk, att, emp in breaks_with_attendance:
        if brk.end_time is None or brk.duration_minutes is None:
            continue
        if brk.duration_minutes <= 0:
            continue

        sched_hours = 8.0
        if emp.work_schedule:
            sched_hours = emp.work_schedule.total_hours or 8.0

        records.append({
            "employee_id": emp.id,
            "break_id": brk.id,
            "attendance_id": att.id,
            "date": att.date,
            "start_time": brk.start_time,
            "category": brk.category.value if brk.category else "Other",
            "duration_minutes": brk.duration_minutes,
            "weekday": att.date.weekday() if att.date else 0,
            "hour_of_day": brk.start_time.hour if brk.start_time else 9,
            "scheduled_hours": sched_hours,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.sort_values(["employee_id", "date", "start_time"]).reset_index(drop=True)

    # Category encoding
    cat_map = {"Lunch": 0, "Tea": 1, "Coffee": 2, "Personal": 3, "Other": 4}
    df["category_encoded"] = df["category"].map(cat_map).fillna(4).astype(int)

    # Prior breaks today per employee
    df["prior_breaks_today"] = df.groupby(["employee_id", "date"]).cumcount()

    # Rolling 7-day average duration per employee+category
    df["rolling_avg"] = (
        df.groupby(["employee_id", "category"])["duration_minutes"]
        .transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
        .fillna(df["duration_minutes"].mean())
    )

    # Drop rows with NaN in key columns
    df = df.dropna(subset=["duration_minutes", "weekday", "hour_of_day",
                            "scheduled_hours", "category_encoded"])
    return df


FEATURE_COLS = [
    "weekday",
    "hour_of_day",
    "category_encoded",
    "scheduled_hours",
    "prior_breaks_today",
    "rolling_avg",
]
TARGET_COL = "duration_minutes"

MIN_SAMPLES_FOR_RF = 20  # Minimum records before using Random Forest
