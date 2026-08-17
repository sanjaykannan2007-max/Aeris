"""
dataset_pipeline.py
===================
Orchestrates the complete data-engineering pipeline for a single C-MAPSS subset.

Pipeline Steps
--------------
1. Load raw training and test data
2. Clean data (quality checks, report)
3. Add RUL labels to training data
4. Add RUL labels to test data (using ground-truth RUL file)
5. Sensor analysis (statistics, categorisation)
6. EDA plots
7. Fit scaler on training data; transform both splits
8. Save processed CSVs
9. Feature engineering (rolling stats, lag features)
10. Save feature CSVs
11. Generate per-dataset report
12. Final validation checks

Public API
----------
    run_pipeline(subset, max_rul, window_size, scaler_type)  -> dict
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    SENSOR_COLS,
    SETTING_COLS,
    FEATURE_COLS,
    MAX_RUL,
    WINDOW_SIZE,
    SCALER_TYPE,
    OUTPUTS_REPORTS_DIR,
    RUL_COL,
    RUL_CAPPED_COL,
)
from src.data_loader      import load_dataset, load_rul_file
from src.data_cleaner     import clean_dataset
from src.rul_generator    import add_rul_to_train, add_rul_to_test
from src.preprocessing    import fit_and_save_scaler, apply_scaler, save_processed
from src.sensor_analysis  import analyze_sensors
from src.feature_engineering import engineer_features, save_features
from src.eda_plots        import run_eda


def run_pipeline(
    subset: str,
    max_rul: int   = MAX_RUL,
    window_size: int = WINDOW_SIZE,
    scaler_type: str = SCALER_TYPE,
) -> dict[str, Any]:
    """
    Execute the full data-engineering pipeline for one C-MAPSS subset.

    Parameters
    ----------
    subset : str
        One of 'FD001', 'FD002', 'FD003', 'FD004'.
    max_rul : int
        RUL cap value.
    window_size : int
        Rolling window size for feature engineering.
    scaler_type : str
        'minmax' or 'standard'.

    Returns
    -------
    dict with keys:
        'subset', 'train_df', 'test_df', 'train_features', 'test_features',
        'train_report', 'test_report', 'sensor_stats', 'scaler', 'dataset_report'
    """
    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"  PIPELINE START: {subset}")
    print(f"{'='*60}")

    results: dict[str, Any] = {"subset": subset}

    # ------------------------------------------------------------------ #
    # STEP 1 – Load raw data
    # ------------------------------------------------------------------ #
    print(f"\n[1/10] Loading raw data...")
    train_raw = load_dataset(subset, "train")
    test_raw  = load_dataset(subset, "test")
    rul_values = load_rul_file(subset)

    # ------------------------------------------------------------------ #
    # STEP 2 – Clean data
    # ------------------------------------------------------------------ #
    print(f"\n[2/10] Cleaning data...")
    train_clean, train_clean_report = clean_dataset(train_raw, subset, "train")
    test_clean,  test_clean_report  = clean_dataset(test_raw,  subset, "test")
    results["train_report"] = train_clean_report
    results["test_report"]  = test_clean_report

    # ------------------------------------------------------------------ #
    # STEP 3 – Add RUL to training data
    # ------------------------------------------------------------------ #
    print(f"\n[3/10] Generating RUL labels for training data...")
    train_rul = add_rul_to_train(train_clean, max_rul=max_rul)

    # ------------------------------------------------------------------ #
    # STEP 4 – Add RUL to test data
    # ------------------------------------------------------------------ #
    print(f"\n[4/10] Generating RUL labels for test data...")
    test_rul = add_rul_to_test(test_clean, rul_values, max_rul=max_rul)

    # ------------------------------------------------------------------ #
    # STEP 5 – Sensor analysis (on training data)
    # ------------------------------------------------------------------ #
    print(f"\n[5/10] Analysing sensors...")
    sensor_stats = analyze_sensors(train_clean, subset, "train")
    results["sensor_stats"] = sensor_stats

    # ------------------------------------------------------------------ #
    # STEP 6 – EDA plots
    # ------------------------------------------------------------------ #
    print(f"\n[6/10] Generating EDA plots...")
    try:
        run_eda(train_rul, subset)
    except Exception as e:
        print(f"  [WARNING] EDA failed for {subset}: {e}")
        traceback.print_exc()

    # ------------------------------------------------------------------ #
    # STEP 7 – Fit scaler on training data; apply to both splits
    # ------------------------------------------------------------------ #
    print(f"\n[7/10] Normalising features...")
    feature_cols = [c for c in FEATURE_COLS if c in train_rul.columns]

    # CRITICAL: fit ONLY on training data
    scaler = fit_and_save_scaler(train_rul, subset,
                                 feature_cols=feature_cols,
                                 scaler_type=scaler_type)
    results["scaler"] = scaler

    train_scaled = apply_scaler(train_rul,  scaler, feature_cols)
    test_scaled  = apply_scaler(test_rul,   scaler, feature_cols)

    # ------------------------------------------------------------------ #
    # STEP 8 – Save processed CSVs
    # ------------------------------------------------------------------ #
    print(f"\n[8/10] Saving processed data...")
    save_processed(train_scaled, subset, "train")
    save_processed(test_scaled,  subset, "test")
    results["train_df"] = train_scaled
    results["test_df"]  = test_scaled

    # ------------------------------------------------------------------ #
    # STEP 9 – Feature engineering
    # ------------------------------------------------------------------ #
    print(f"\n[9/10] Engineering features...")
    train_feat = engineer_features(train_scaled, window=window_size)
    test_feat  = engineer_features(test_scaled,  window=window_size)
    save_features(train_feat, subset, "train")
    save_features(test_feat,  subset, "test")
    results["train_features"] = train_feat
    results["test_features"]  = test_feat

    # ------------------------------------------------------------------ #
    # STEP 10 – Generate dataset report
    # ------------------------------------------------------------------ #
    print(f"\n[10/10] Generating report...")
    dataset_report = _build_report(
        subset, train_rul, test_rul, train_clean_report, test_clean_report, sensor_stats
    )
    results["dataset_report"] = dataset_report
    _save_report(dataset_report, subset)

    # ------------------------------------------------------------------ #
    # VALIDATION
    # ------------------------------------------------------------------ #
    print(f"\n--- Validation: {subset} ---")
    _validate(train_scaled, test_scaled, train_feat, test_feat, subset)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  PIPELINE DONE: {subset}  [{elapsed:.1f}s]")
    print(f"{'='*60}\n")

    return results


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _build_report(
    subset: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    train_report: dict,
    test_report: dict,
    sensor_stats: pd.DataFrame,
) -> dict[str, Any]:
    """Build the human-readable dataset summary report."""
    lifetimes = train_df.groupby(ENGINE_ID_COL)[CYCLE_COL].max()

    constant_sensors = sensor_stats[sensor_stats["category"] == "constant"]["sensor"].tolist()
    near_const_sensors = sensor_stats[sensor_stats["category"] == "near_constant"]["sensor"].tolist()
    useful_sensors = sensor_stats[sensor_stats["is_potentially_useful"] == True]["sensor"].tolist()

    rul_stats = {}
    if RUL_COL in train_df.columns:
        rul_stats = {
            "mean_RUL":   round(float(train_df[RUL_COL].mean()), 2),
            "std_RUL":    round(float(train_df[RUL_COL].std()),  2),
            "min_RUL":    int(train_df[RUL_COL].min()),
            "max_RUL":    int(train_df[RUL_COL].max()),
            "mean_RUL_capped": round(float(train_df[RUL_CAPPED_COL].mean()), 2) if RUL_CAPPED_COL in train_df.columns else None,
        }

    return {
        "subset":           subset,
        "train_engines":    int(train_df[ENGINE_ID_COL].nunique()),
        "test_engines":     int(test_df[ENGINE_ID_COL].nunique()),
        "train_rows":       int(len(train_df)),
        "test_rows":        int(len(test_df)),
        "total_cycles":     int(train_df[CYCLE_COL].max()),
        "n_sensors":        len(SENSOR_COLS),
        "n_settings":       len(SETTING_COLS),
        "train_missing":    train_report.get("total_missing_values", 0),
        "test_missing":     test_report.get("total_missing_values", 0),
        "train_duplicates": train_report.get("duplicate_rows_found_and_removed", 0),
        "constant_sensors": constant_sensors,
        "near_constant_sensors": near_const_sensors,
        "useful_sensors":   useful_sensors,
        "engine_lifetime_avg_cycles": round(float(lifetimes.mean()), 1),
        "engine_lifetime_min_cycles": int(lifetimes.min()),
        "engine_lifetime_max_cycles": int(lifetimes.max()),
        "rul_statistics":   rul_stats,
    }


def _save_report(report: dict, subset: str) -> None:
    OUTPUTS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = OUTPUTS_REPORTS_DIR / f"report_{subset}.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)

    # Human-readable text
    txt_path = OUTPUTS_REPORTS_DIR / f"report_{subset}.txt"
    lines = [
        f"=" * 55,
        f"  DATA ENGINEERING REPORT – {subset}",
        f"=" * 55,
        f"",
        f"Dataset:             {report['subset']}",
        f"Training Engines:    {report['train_engines']}",
        f"Test Engines:        {report['test_engines']}",
        f"Training Rows:       {report['train_rows']:,}",
        f"Test Rows:           {report['test_rows']:,}",
        f"Sensors:             {report['n_sensors']}",
        f"Operational Settings:{report['n_settings']}",
        f"",
        f"--- Data Quality ---",
        f"Training Missing:    {report['train_missing']}",
        f"Test Missing:        {report['test_missing']}",
        f"Training Duplicates: {report['train_duplicates']}",
        f"",
        f"--- Sensor Analysis ---",
        f"Constant Sensors:    {', '.join(report['constant_sensors']) or 'None'}",
        f"Near-Constant:       {', '.join(report['near_constant_sensors']) or 'None'}",
        f"Useful Sensors:      {', '.join(report['useful_sensors']) or 'None'}",
        f"",
        f"--- Engine Lifetime ---",
        f"Average:             {report['engine_lifetime_avg_cycles']} cycles",
        f"Minimum:             {report['engine_lifetime_min_cycles']} cycles",
        f"Maximum:             {report['engine_lifetime_max_cycles']} cycles",
        f"",
        f"--- RUL Statistics (Training) ---",
    ]
    for k, v in report.get("rul_statistics", {}).items():
        lines.append(f"  {k:25s}: {v}")
    lines.append("")

    with open(txt_path, "w") as f:
        f.write("\n".join(lines))

    print(f"  [report] Saved → {json_path.name} + {txt_path.name}")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    train_feat: pd.DataFrame,
    test_feat: pd.DataFrame,
    subset: str,
) -> None:
    errors = []

    # 1. No NaN in processed data
    train_nan = train_df.isnull().sum().sum()
    test_nan  = test_df.isnull().sum().sum()
    if train_nan > 0:
        errors.append(f"NaN in processed train: {train_nan}")
    if test_nan > 0:
        errors.append(f"NaN in processed test:  {test_nan}")

    # 2. No infinite values
    num_cols = train_df.select_dtypes(include=[np.number]).columns
    if np.isinf(train_df[num_cols].values).any():
        errors.append("Infinite values in processed train data")
    if np.isinf(test_df[test_df.select_dtypes(include=[np.number]).columns].values).any():
        errors.append("Infinite values in processed test data")

    # 3. RUL ≥ 0
    if RUL_COL in train_df.columns:
        if (train_df[RUL_COL] < 0).any():
            errors.append("Negative RUL values in training data")
    if RUL_COL in test_df.columns:
        if (test_df[RUL_COL] < 0).any():
            errors.append("Negative RUL values in test data")

    # 4. engine_id and cycle preserved
    for col in [ENGINE_ID_COL, CYCLE_COL]:
        if col not in train_df.columns:
            errors.append(f"'{col}' missing from processed train")
        if col not in test_df.columns:
            errors.append(f"'{col}' missing from processed test")

    # 5. Feature columns match between train and test
    train_feat_cols = set(train_feat.columns)
    test_feat_cols  = set(test_feat.columns)
    diff = train_feat_cols.symmetric_difference(test_feat_cols)
    if diff:
        errors.append(f"Feature column mismatch between train/test: {diff}")

    # 6. Feature data has no NaN (rolling creates some at start; fill was applied)
    feat_nan_train = train_feat.isnull().sum().sum()
    if feat_nan_train > 0:
        errors.append(f"NaN in train features: {feat_nan_train}")

    if errors:
        print(f"  [VALIDATION] FAIL {subset} - {len(errors)} issue(s):")
        for e in errors:
            print(f"    * {e}")
    else:
        print(f"  [VALIDATION] PASS {subset} - All checks passed!")
