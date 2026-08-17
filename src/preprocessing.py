"""
preprocessing.py
================
Normalises features using scikit-learn scalers.

Data-Leakage Prevention
-----------------------
CRITICAL RULE: The scaler is ALWAYS fitted on training data ONLY.
It is then applied (transform only) to test data.
This mirrors real-world deployment: you don't have access to test statistics
when building your model.

Saved scalers can be loaded by team members to inverse-transform predictions.

Public API
----------
    fit_and_save_scaler(train_df, subset, feature_cols, scaler_type)  -> scaler
    apply_scaler(df, scaler, feature_cols)                             -> pd.DataFrame
    save_processed(df, subset, split)
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from src.config import (
    FEATURE_COLS,
    MODELS_SCALERS_DIR,
    DATA_PROCESSED_DIR,
    ENGINE_ID_COL,
    CYCLE_COL,
    SCALER_TYPE,
)


def _build_scaler(scaler_type: str):
    """Instantiate a new scaler from its string name."""
    if scaler_type == "minmax":
        return MinMaxScaler(feature_range=(0, 1))
    elif scaler_type == "standard":
        return StandardScaler()
    else:
        raise ValueError(f"scaler_type must be 'minmax' or 'standard', got '{scaler_type}'")


def fit_and_save_scaler(
    train_df: pd.DataFrame,
    subset: str,
    feature_cols: list[str] | None = None,
    scaler_type: str = SCALER_TYPE,
):
    """
    Fit a scaler on TRAINING data only and save to disk.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training DataFrame (after RUL labelling).
    subset : str
        Dataset identifier (e.g. 'FD001').
    feature_cols : list[str] | None
        Columns to scale. Defaults to FEATURE_COLS (settings + sensors).
    scaler_type : str
        'minmax' or 'standard'.

    Returns
    -------
    Fitted scaler instance.
    """
    if feature_cols is None:
        feature_cols = [c for c in FEATURE_COLS if c in train_df.columns]

    scaler = _build_scaler(scaler_type)
    scaler.fit(train_df[feature_cols])

    MODELS_SCALERS_DIR.mkdir(parents=True, exist_ok=True)
    scaler_path = MODELS_SCALERS_DIR / f"scaler_{subset}.pkl"
    joblib.dump(scaler, scaler_path)

    print(f"  [preproc] Fitted {type(scaler).__name__} on training data -> saved to {scaler_path.name}")
    return scaler


def apply_scaler(
    df: pd.DataFrame,
    scaler,
    feature_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Transform (never fit) a DataFrame using a pre-fitted scaler.

    Parameters
    ----------
    df : pd.DataFrame
    scaler : fitted sklearn scaler
    feature_cols : list[str] | None

    Returns
    -------
    pd.DataFrame with scaled feature columns.
    """
    df = df.copy()
    if feature_cols is None:
        feature_cols = [c for c in FEATURE_COLS if c in df.columns]

    df[feature_cols] = scaler.transform(df[feature_cols])
    return df


def save_processed(df: pd.DataFrame, subset: str, split: str) -> None:
    """
    Save a processed DataFrame to data/processed/.

    Parameters
    ----------
    df : pd.DataFrame
    subset : str
    split : str  ('train' or 'test')
    """
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_DIR / f"processed_{split}_{subset}.csv"
    df.to_csv(out_path, index=False)
    print(f"  [preproc] Saved -> {out_path.name}  ({df.shape[0]:,} rows × {df.shape[1]} cols)")
