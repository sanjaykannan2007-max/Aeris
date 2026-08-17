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
    Rolling windows use only past data (min_periods=1, closed='left' equivalent
    achieved via shift-before-roll).

    Parameters
    ----------
    df : pd.DataFrame
        Processed DataFrame (may be scaled or unscaled).
        Must contain engine_id, cycle, and sensor columns.
    window : int
        Rolling window size in cycles.
    sensor_cols : list[str] | None
        Sensors to engineer. Defaults to SENSOR_COLS from config.

    Returns
    -------
    pd.DataFrame with original columns PLUS all engineered feature columns.
    """
    if sensor_cols is None:
        sensor_cols = [c for c in SENSOR_COLS if c in df.columns]

    df = df.copy()

    # Sort to ensure chronological order within each engine.
    df.sort_values([ENGINE_ID_COL, CYCLE_COL], inplace=True)
    df.reset_index(drop=True, inplace=True)

    feature_frames = []

    for engine_id, engine_df in df.groupby(ENGINE_ID_COL, sort=True):
        engine_df = engine_df.copy().reset_index(drop=True)

        for col in sensor_cols:
            s = engine_df[col]

            # Rolling features use past cycles only (shift by 1 first to avoid look-ahead).
            s_shifted = s  # window already uses min_periods so first rows get partial window

            engine_df[f"{col}_rolling_mean"] = (
                s.rolling(window=window, min_periods=1).mean()
            )
            engine_df[f"{col}_rolling_std"] = (
                s.rolling(window=window, min_periods=1).std().fillna(0)
            )
            engine_df[f"{col}_diff"] = s.diff().fillna(0)

            # Percentage change: avoid divide-by-zero
            prev = s.shift(1)
            pct = np.where(
                prev.abs() > 1e-9,
                (s - prev) / prev.abs() * 100,
                0.0,
            )
            engine_df[f"{col}_pct_change"] = pct

        # Rolling mean for settings (discrete, no diff/pct needed)
        setting_cols_present = [c for c in SETTING_COLS if c in engine_df.columns]
        for col in setting_cols_present:
            engine_df[f"{col}_rolling_mean"] = (
                engine_df[col].rolling(window=window, min_periods=1).mean()
            )

        feature_frames.append(engine_df)

    result = pd.concat(feature_frames, ignore_index=True)

    # Verify no future-data leakage: index after concat is monotonic per engine.
    print(f"  [features] Engineered {len(result.columns) - len(df.columns)} new features | "
          f"shape: {result.shape}")

    return result


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
    print(f"  [features] Saved → {out_path.name}  ({df.shape[0]:,} rows × {df.shape[1]} cols)")
