"""
EBT System — ML Training
Trains and evaluates baseline + Random Forest models on break history.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

from app.ml.preprocessing import (
    build_feature_dataframe, FEATURE_COLS, TARGET_COL, MIN_SAMPLES_FOR_RF
)


def train_and_evaluate(breaks_with_attendance):
    """
    Returns a dict with:
      - model: trained RandomForestRegressor or None
      - baseline_mae, baseline_rmse
      - rf_mae, rf_rmse (if RF trained)
      - model_used: "Random Forest" or "Historical Average Baseline"
      - status: human-readable message
      - category_averages: dict {category: avg_duration}
      - n_samples: int
    """
    df = build_feature_dataframe(breaks_with_attendance)
    result = {
        "model": None,
        "baseline_mae": None,
        "baseline_rmse": None,
        "rf_mae": None,
        "rf_rmse": None,
        "model_used": "Historical Average Baseline",
        "status": "",
        "category_averages": {},
        "n_samples": 0,
        "df": None,
    }

    if df.empty:
        result["status"] = "No usable historical break records found. Predictions will use defaults."
        return result

    n = len(df)
    result["n_samples"] = n
    result["df"] = df

    # Category averages for baseline
    cat_avg = df.groupby("category")[TARGET_COL].mean().to_dict()
    result["category_averages"] = cat_avg
    overall_avg = df[TARGET_COL].mean()

    if n < 5:
        result["status"] = (
            f"Only {n} records available. Minimum 5 needed for baseline evaluation. "
            "Using global average as baseline."
        )
        return result

    # Baseline evaluation (hold out last 20% chronologically)
    split_idx = max(1, int(n * 0.8))
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    if len(test_df) == 0:
        result["status"] = "Insufficient data for a held-out test set."
        return result

    # Baseline: predict category average from training set
    train_cat_avg = train_df.groupby("category")[TARGET_COL].mean().to_dict()
    baseline_preds = test_df["category"].map(train_cat_avg).fillna(train_df[TARGET_COL].mean())
    y_test = test_df[TARGET_COL]
    result["baseline_mae"] = round(float(mean_absolute_error(y_test, baseline_preds)), 2)
    result["baseline_rmse"] = round(float(np.sqrt(mean_squared_error(y_test, baseline_preds))), 2)

    if n >= MIN_SAMPLES_FOR_RF:
        X_train = train_df[FEATURE_COLS]
        y_train = train_df[TARGET_COL]
        X_test = test_df[FEATURE_COLS]

        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X_train, y_train)
        rf_preds = rf.predict(X_test)
        result["rf_mae"] = round(float(mean_absolute_error(y_test, rf_preds)), 2)
        result["rf_rmse"] = round(float(np.sqrt(mean_squared_error(y_test, rf_preds))), 2)
        result["model"] = rf
        result["model_used"] = "Random Forest"
        result["status"] = (
            f"Random Forest trained on {split_idx} samples, evaluated on {len(test_df)} held-out samples."
        )
    else:
        result["status"] = (
            f"Only {n} samples available ({MIN_SAMPLES_FOR_RF} needed for Random Forest). "
            f"Using Historical Average Baseline evaluated on {len(test_df)} held-out samples."
        )

    return result
