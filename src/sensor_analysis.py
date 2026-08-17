"""
sensor_analysis.py
==================
Computes per-sensor statistics and categorises sensors across subsets.

Output
------
    outputs/statistics/sensor_statistics.csv   (all sensors, all subsets)

Public API
----------
    analyze_sensors(df, subset, split)  -> pd.DataFrame  (per-sensor stats)
    save_sensor_statistics(records)     -> None
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any

from src.config import (
    CYCLE_COL,
    SENSOR_COLS,
    SETTING_COLS,
    OUTPUTS_STATISTICS_DIR,
    CONSTANT_VARIANCE_THRESHOLD,
    NEAR_CONSTANT_VARIANCE_THRESHOLD,
    CYCLE_CORR_THRESHOLD,
)


def analyze_sensors(
    df: pd.DataFrame,
    subset: str,
    split: str,
) -> pd.DataFrame:
    """
    Compute descriptive statistics for all sensor columns.

    For each sensor the function calculates:
    - mean, std, min, max, variance
    - number of unique values
    - absolute Pearson correlation with cycle (degradation proxy)
    - missing value percentage
    - category: 'constant', 'near_constant', or 'variable'

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned DataFrame (any split).
    subset : str
    split : str

    Returns
    -------
    pd.DataFrame with one row per sensor.
    """
    records = []
    for col in SENSOR_COLS:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        var = float(s.var())
        mean_val = float(s.mean())

        # Correlation with cycle (degradation signal)
        try:
            corr_with_cycle = float(df[[col, CYCLE_COL]].dropna().corr().loc[col, CYCLE_COL])
        except Exception:
            corr_with_cycle = np.nan

        # Category
        if var <= CONSTANT_VARIANCE_THRESHOLD:
            category = "constant"
        elif var <= NEAR_CONSTANT_VARIANCE_THRESHOLD:
            category = "near_constant"
        else:
            category = "variable"

        is_useful = (
            category == "variable"
            and not np.isnan(corr_with_cycle)
            and abs(corr_with_cycle) >= CYCLE_CORR_THRESHOLD
        )

        records.append({
            "subset": subset,
            "split": split,
            "sensor": col,
            "mean": mean_val,
            "std": float(s.std()),
            "min": float(s.min()),
            "max": float(s.max()),
            "variance": var,
            "unique_values": int(s.nunique()),
            "corr_with_cycle": corr_with_cycle,
            "missing_pct": float(df[col].isnull().mean() * 100),
            "category": category,
            "is_potentially_useful": is_useful,
        })

    stats_df = pd.DataFrame(records)
    return stats_df


def save_sensor_statistics(all_stats: list[pd.DataFrame]) -> None:
    """
    Concatenate per-subset sensor statistics and save to CSV.

    Parameters
    ----------
    all_stats : list of DataFrames returned by analyze_sensors()
    """
    OUTPUTS_STATISTICS_DIR.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(all_stats, ignore_index=True)
    out_path = OUTPUTS_STATISTICS_DIR / "sensor_statistics.csv"
    combined.to_csv(out_path, index=False)
    print(f"  [sensor] Sensor statistics saved → {out_path}")
    return combined
