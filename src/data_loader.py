"""
data_loader.py
==============
Loads raw NASA C-MAPSS files into pandas DataFrames.

Public API
----------
    load_dataset(subset, split="train")  -> pd.DataFrame
    load_rul_file(subset)                -> np.ndarray
    load_processed_data(subset, split)   -> pd.DataFrame  [convenience – for team members]
    load_features(subset, split)         -> pd.DataFrame  [convenience – for team members]
    load_scaler(subset)                  -> fitted sklearn scaler
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from src.config import (
    COLUMN_NAMES,
    DATA_RAW_DIR,
    DATA_PROCESSED_DIR,
    DATA_FEATURES_DIR,
    MODELS_SCALERS_DIR,
    VALID_SUBSETS,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_subset(subset: str) -> str:
    subset = subset.upper()
    if subset not in VALID_SUBSETS:
        raise ValueError(f"subset must be one of {VALID_SUBSETS}, got '{subset}'")
    return subset


def _validate_split(split: str) -> str:
    split = split.lower()
    if split not in ("train", "test"):
        raise ValueError(f"split must be 'train' or 'test', got '{split}'")
    return split


# ---------------------------------------------------------------------------
# Raw loaders
# ---------------------------------------------------------------------------

def load_dataset(subset: str, split: str = "train") -> pd.DataFrame:
    """
    Load a raw C-MAPSS text file into a clean DataFrame.

    Parameters
    ----------
    subset : str
        One of 'FD001', 'FD002', 'FD003', 'FD004'.
    split : str
        'train' or 'test'.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: engine_id, cycle, setting_1..3, sensor_1..21.
    """
    subset = _validate_subset(subset)
    split  = _validate_split(split)

    filename = f"{split}_{subset}.txt"
    filepath = DATA_RAW_DIR / filename

    if not filepath.exists():
        raise FileNotFoundError(
            f"Raw data file not found: {filepath}\n"
            f"Make sure you placed the C-MAPSS files in: {DATA_RAW_DIR}"
        )

    # NASA files are space-separated; trailing spaces create empty columns.
    df = pd.read_csv(
        filepath,
        sep=r"\s+",
        header=None,
        engine="python",
    )

    # Drop any completely-empty trailing columns introduced by trailing spaces.
    df.dropna(axis=1, how="all", inplace=True)

    # Assign column names.
    if df.shape[1] != len(COLUMN_NAMES):
        raise ValueError(
            f"Expected {len(COLUMN_NAMES)} columns, found {df.shape[1]} in {filename}. "
            "Check the raw file format."
        )
    df.columns = COLUMN_NAMES

    # Ensure integer types for ID columns.
    df["engine_id"] = df["engine_id"].astype(int)
    df["cycle"]     = df["cycle"].astype(int)

    print(f"  [loader] Loaded {split}_{subset}: {df.shape[0]:,} rows × {df.shape[1]} cols "
          f"| {df['engine_id'].nunique()} engines")
    return df


def load_rul_file(subset: str) -> np.ndarray:
    """
    Load the ground-truth RUL vector for a C-MAPSS test subset.

    Parameters
    ----------
    subset : str
        One of 'FD001', 'FD002', 'FD003', 'FD004'.

    Returns
    -------
    np.ndarray, shape (n_engines,)
        True RUL value at the last observed cycle of each test engine.
    """
    subset = _validate_subset(subset)
    filepath = DATA_RAW_DIR / f"RUL_{subset}.txt"

    if not filepath.exists():
        raise FileNotFoundError(f"RUL file not found: {filepath}")

    rul_values = pd.read_csv(filepath, header=None, sep=r"\s+", engine="python")
    rul_values = rul_values.dropna(axis=1, how="all")
    arr = rul_values.iloc[:, 0].values.astype(int)
    print(f"  [loader] Loaded RUL_{subset}: {len(arr)} test-engine true RUL values")
    return arr


# ---------------------------------------------------------------------------
# Convenience loaders for team members
# ---------------------------------------------------------------------------

def load_processed_data(subset: str, split: str = "train") -> pd.DataFrame:
    """
    Load normalised, RUL-labelled processed data.
    Use this for RUL prediction (Person 2).

    Parameters
    ----------
    subset : str
        One of 'FD001', 'FD002', 'FD003', 'FD004'.
    split : str
        'train' or 'test'.

    Returns
    -------
    pd.DataFrame
    """
    subset = _validate_subset(subset)
    split  = _validate_split(split)
    path   = DATA_PROCESSED_DIR / f"processed_{split}_{subset}.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Processed file not found: {path}\n"
            "Run the pipeline first: python run_pipeline.py --dataset all"
        )
    df = pd.read_csv(path)
    print(f"  [loader] Loaded processed {split}_{subset}: {df.shape}")
    return df


def load_features(subset: str, split: str = "train") -> pd.DataFrame:
    """
    Load feature-engineered data (rolling stats, lag features, etc.).
    Use this for LSTM / GRU models (Person 2) or anomaly detection (Person 3).

    Parameters
    ----------
    subset : str
    split : str

    Returns
    -------
    pd.DataFrame
    """
    subset = _validate_subset(subset)
    split  = _validate_split(split)
    path   = DATA_FEATURES_DIR / f"features_{split}_{subset}.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Features file not found: {path}\n"
            "Run the pipeline first: python run_pipeline.py --dataset all"
        )
    df = pd.read_csv(path)
    print(f"  [loader] Loaded features {split}_{subset}: {df.shape}")
    return df


def load_scaler(subset: str):
    """
    Load the fitted scikit-learn scaler for a given subset.
    CRITICAL: This scaler was fitted ONLY on training data.

    Parameters
    ----------
    subset : str

    Returns
    -------
    Fitted sklearn scaler (MinMaxScaler or StandardScaler).
    """
    subset = _validate_subset(subset)
    path   = MODELS_SCALERS_DIR / f"scaler_{subset}.pkl"

    if not path.exists():
        raise FileNotFoundError(
            f"Scaler not found: {path}\n"
            "Run the pipeline first: python run_pipeline.py --dataset all"
        )
    scaler = joblib.load(path)
    print(f"  [loader] Loaded scaler_{subset} ({type(scaler).__name__})")
    return scaler
