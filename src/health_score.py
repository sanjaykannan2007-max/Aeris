"""
health_score.py
================
Engine Health Score Calculation & Health Stage Categorisation.

Health Score Definition
------------------------
Computes a normalized engine health score (0% to 100%) based on predicted
Remaining Useful Life (RUL) relative to the baseline maximum RUL (e.g. 125 cycles).

Health Stage Categorisation
---------------------------
- HEALTHY              : Health Score >= 75%
- MONITOR              : 45% <= Health Score < 75%
- MAINTENANCE REQUIRED : 20% <= Health Score < 45%
- CRITICAL             : Health Score < 20%

Public API
----------
    calculate_health_score(predicted_rul, baseline_max_rul, mode) -> float / np.ndarray
    categorize_health_stage(health_score)                         -> str / list[str]
    add_health_scores_to_dataframe(df, rul_col, baseline_max_rul) -> pd.DataFrame
"""

from __future__ import annotations

from typing import Union
import numpy as np
import pandas as pd

from src.config import MAX_RUL, HEALTH_STAGES


def calculate_health_score(
    predicted_rul: Union[float, np.ndarray, pd.Series],
    baseline_max_rul: float = MAX_RUL,
    mode: str = "piecewise_linear",
) -> Union[float, np.ndarray]:
    """
    Calculate normalized engine health score (0.0 to 100.0).

    Parameters
    ----------
    predicted_rul : float, np.ndarray, or pd.Series
        Predicted Remaining Useful Life in cycles.
    baseline_max_rul : float
        Reference maximum expected RUL (default: 125).
    mode : str
        'piecewise_linear' or 'exponential'.

    Returns
    -------
    float or np.ndarray
        Health score ranging from 0.0 to 100.0.
    """
    rul_arr = np.asarray(predicted_rul, dtype=float)
    
    if mode == "piecewise_linear":
        scores = (rul_arr / baseline_max_rul) * 100.0
    elif mode == "exponential":
        # Exponential curve dropping rapidly below 30 cycles
        tau = baseline_max_rul / 2.0
        scores = 100.0 * (1.0 - np.exp(-rul_arr / tau)) / (1.0 - np.exp(-baseline_max_rul / tau))
    else:
        raise ValueError(f"Unknown health score mode: '{mode}'. Choose 'piecewise_linear' or 'exponential'.")

    scores = np.clip(scores, 0.0, 100.0)

    if np.isscalar(predicted_rul):
        return float(scores.item())
    return scores


def categorize_health_stage(
    health_score: Union[float, np.ndarray, pd.Series]
) -> Union[str, list[str]]:
    """
    Categorize a health score (0-100) into health status categories.

    Categories:
    - 'HEALTHY'
    - 'MONITOR'
    - 'MAINTENANCE REQUIRED'
    - 'CRITICAL'

    Parameters
    ----------
    health_score : float, np.ndarray, or pd.Series
        Engine health score between 0 and 100.

    Returns
    -------
    str or list[str]
        Category string or list of category strings.
    """
    def _stage_single(score: float) -> str:
        if score >= HEALTH_STAGES["HEALTHY"]["min_score"]:
            return HEALTH_STAGES["HEALTHY"]["label"]
        elif score >= HEALTH_STAGES["MONITOR"]["min_score"]:
            return HEALTH_STAGES["MONITOR"]["label"]
        elif score >= HEALTH_STAGES["MAINTENANCE_REQUIRED"]["min_score"]:
            return HEALTH_STAGES["MAINTENANCE_REQUIRED"]["label"]
        else:
            return HEALTH_STAGES["CRITICAL"]["label"]

    if np.isscalar(health_score):
        return _stage_single(float(health_score))
    
    scores = np.asarray(health_score, dtype=float)
    return [_stage_single(s) for s in scores]


def add_health_scores_to_dataframe(
    df: pd.DataFrame,
    rul_col: str = "predicted_RUL",
    baseline_max_rul: float = MAX_RUL,
) -> pd.DataFrame:
    """
    Append 'health_score' and 'health_status' columns to a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing predicted RUL column.
    rul_col : str
        Column name holding the RUL predictions.
    baseline_max_rul : float
        Baseline RUL cap for percentage calculation.

    Returns
    -------
    pd.DataFrame
        DataFrame with appended 'health_score' and 'health_status' columns.
    """
    df = df.copy()
    if rul_col not in df.columns:
        raise KeyError(f"Column '{rul_col}' not found in DataFrame.")

    scores = calculate_health_score(df[rul_col].values, baseline_max_rul=baseline_max_rul)
    df["health_score"] = np.round(scores, 2)
    df["health_status"] = categorize_health_stage(scores)

    return df
