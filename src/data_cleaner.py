"""
data_cleaner.py
===============
Performs data quality checks and light cleaning on raw C-MAPSS DataFrames.

What is done
------------
* Checks for missing / NaN values.
* Checks for duplicate rows.
* Checks for infinite values (replaces with NaN then reports).
* Identifies constant sensors (variance ≈ 0).
* Identifies near-constant sensors (very low variance).
* Analyzes sensor noise levels (coefficient of variation).
* Does NOT drop sensors – only documents them; the downstream modules
  decide what to use.

Public API
----------
    clean_dataset(df, subset, split)  ->  (clean_df, report_dict)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any

from src.config import (
    COLUMN_NAMES,
    CONSTANT_VARIANCE_THRESHOLD,
    NEAR_CONSTANT_VARIANCE_THRESHOLD,
    DATA_CLEANED_DIR,
    ENGINE_ID_COL,
    CYCLE_COL,
    SENSOR_COLS,
    SETTING_COLS,
)


def clean_dataset(
    df: pd.DataFrame,
    subset: str,
    split: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Run all data quality checks and save a cleaned copy.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame from data_loader.load_dataset().
    subset : str
        Dataset identifier, e.g. 'FD001'.
    split : str
        'train' or 'test'.

    Returns
    -------
    clean_df : pd.DataFrame
        Same data after cleaning steps (dtypes fixed, inf→NaN handled).
    report : dict
        Structured quality report for this dataset split.
    """
    report: dict[str, Any] = {
        "subset": subset,
        "split": split,
        "original_shape": df.shape,
    }

    df = df.copy()

    # ------------------------------------------------------------------
    # 1. Infinite values  →  replace with NaN and report
    # ------------------------------------------------------------------
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    inf_mask     = np.isinf(df[numeric_cols])
    inf_count    = int(inf_mask.sum().sum())
    if inf_count > 0:
        df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
    report["infinite_values_found"] = inf_count

    # ------------------------------------------------------------------
    # 2. Missing values
    # ------------------------------------------------------------------
    missing_per_col = df.isnull().sum()
    total_missing   = int(missing_per_col.sum())
    report["total_missing_values"]  = total_missing
    report["missing_per_column"]    = missing_per_col[missing_per_col > 0].to_dict()

    # Drop rows that are fully NaN (shouldn't happen with NASA files, safety check).
    rows_before = len(df)
    df.dropna(how="all", inplace=True)
    report["fully_nan_rows_dropped"] = rows_before - len(df)

    # ------------------------------------------------------------------
    # 3. Duplicate rows
    # ------------------------------------------------------------------
    dup_mask  = df.duplicated()
    dup_count = int(dup_mask.sum())
    if dup_count > 0:
        df.drop_duplicates(inplace=True)
    report["duplicate_rows_found_and_removed"] = dup_count

    # ------------------------------------------------------------------
    # 4. Invalid values (negative cycles or engine IDs)
    # ------------------------------------------------------------------
    invalid_cycle  = int((df[CYCLE_COL] <= 0).sum())
    invalid_engine = int((df[ENGINE_ID_COL] <= 0).sum())
    report["invalid_cycle_values"]  = invalid_cycle
    report["invalid_engine_id_values"] = invalid_engine

    # ------------------------------------------------------------------
    # 5. Sensor variance analysis
    # ------------------------------------------------------------------
    sensor_variances = df[SENSOR_COLS].var()

    constant_sensors     = sensor_variances[sensor_variances <= CONSTANT_VARIANCE_THRESHOLD].index.tolist()
    near_constant_sensors = sensor_variances[
        (sensor_variances > CONSTANT_VARIANCE_THRESHOLD) &
        (sensor_variances <= NEAR_CONSTANT_VARIANCE_THRESHOLD)
    ].index.tolist()

    report["constant_sensors"]      = constant_sensors
    report["near_constant_sensors"] = near_constant_sensors
    report["sensor_variances"]      = sensor_variances.to_dict()

    # ------------------------------------------------------------------
    # 6. Noise analysis  (coefficient of variation)
    # ------------------------------------------------------------------
    sensor_means = df[SENSOR_COLS].mean().replace(0, np.nan)
    cv = (df[SENSOR_COLS].std() / sensor_means.abs()).fillna(0)
    report["sensor_coefficient_of_variation"] = cv.to_dict()

    # ------------------------------------------------------------------
    # 7. Final shape
    # ------------------------------------------------------------------
    report["cleaned_shape"] = df.shape

    # ------------------------------------------------------------------
    # 8. Save cleaned CSV
    # ------------------------------------------------------------------
    DATA_CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_CLEANED_DIR / f"cleaned_{split}_{subset}.csv"
    df.to_csv(out_path, index=False)

    print(f"  [cleaner] {subset}/{split}: {report['original_shape']} -> {df.shape} | "
          f"inf={inf_count}, dup={dup_count}, missing={total_missing} | "
          f"const={len(constant_sensors)}, near-const={len(near_constant_sensors)}")

    return df, report
