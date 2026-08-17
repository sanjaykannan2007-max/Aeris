"""
feature_engineering.py
=======================
Creates time-series features from sensor readings.

All rolling calculations are performed WITHIN each engine's time series.
This guarantees:
  - No data leakage between engines.
  - No future information is used (rolling window is backward-looking only).

Features Created (per sensor)
-----------------------------
  <sensor>              : current raw value
  <sensor>_rolling_mean : rolling mean over last WINDOW_SIZE cycles
  <sensor>_rolling_std  : rolling std  over last WINDOW_SIZE cycles
  <sensor>_diff         : difference from previous cycle (lag-1)
  <sensor>_pct_change   : percentage change from previous cycle

For operational settings, only rolling_mean is added (they are discrete).

Public API
----------
    engineer_features(df, window, sensor_cols)  -> pd.DataFrame
    save_features(df, subset, split)            -> None
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    SENSOR_COLS,
    SETTING_COLS,
    WINDOW_SIZE,
    DATA_FEATURES_DIR,
)


def engineer_features(
    df: pd.DataFrame,
    window: int = WINDOW_SIZE,
    sensor_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Add rolling statistics, lag-1 differences, and percentage changes
    for every sensor column.

    All features are calculated per-engine to prevent leakage between engines.
    """
    if sensor_cols is None:
        sensor_cols = [c for c in SENSOR_COLS if c in df.columns]

    df = df.copy()
    df.sort_values([ENGINE_ID_COL, CYCLE_COL], inplace=True)
    df.reset_index(drop=True, inplace=True)

    n_orig_cols = len(df.columns)
    
    grp = df.groupby(ENGINE_ID_COL, sort=False)
    diff_df = grp[sensor_cols].diff().fillna(0)
    shift_df = grp[sensor_cols].shift(1)

    roll = grp[sensor_cols].rolling(window=window, min_periods=1)
    roll_mean = roll.mean().reset_index(level=0, drop=True)
    roll_std  = roll.std().fillna(0).reset_index(level=0, drop=True)

    for col in sensor_cols:
        df[f"{col}_rolling_mean"] = roll_mean[col]
        df[f"{col}_rolling_std"]  = roll_std[col]
        df[f"{col}_diff"]         = diff_df[col]

        prev = shift_df[col]
        diff = diff_df[col]
        df[f"{col}_pct_change"]   = np.where(prev.abs() > 1e-9, (diff / prev.abs()) * 100.0, 0.0)

    setting_cols_present = [c for c in SETTING_COLS if c in df.columns]
    if setting_cols_present:
        roll_settings = grp[setting_cols_present].rolling(window=window, min_periods=1).mean().reset_index(level=0, drop=True)
        for col in setting_cols_present:
            df[f"{col}_rolling_mean"] = roll_settings[col]

    new_feats = len(df.columns) - n_orig_cols
    print(f"  [features] Engineered {new_feats} new features | shape: {df.shape}")

    return df


def save_features(df: pd.DataFrame, subset: str, split: str) -> None:
    """
    Save feature-engineered DataFrame to data/features/.

    Parameters
    ----------
    df : pd.DataFrame
    subset : str
    split : str
    """
    DATA_FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_FEATURES_DIR / f"features_{split}_{subset}.csv"
    df.to_csv(out_path, index=False)
    print(f"  [features] Saved -> {out_path.name}  ({df.shape[0]:,} rows × {df.shape[1]} cols)")
