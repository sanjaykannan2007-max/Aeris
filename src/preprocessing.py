"""
preprocessing.py
================
Regime-aware z-score normalisation for C-MAPSS telemetry.

Groups flight conditions into K operating regimes (using KMeans on settings 1..3)
and normalises sensor channels within each regime to account for multi-modal operation.
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.cluster import KMeans

from src.config import (
    SETTING_COLS,
    SENSOR_COLS,
    MODELS_SCALERS_DIR,
)

class RegimeNormalizer:
    """Regime-aware normalizer: clusters operational settings and z-scores sensors per regime."""

    def __init__(self, n_regimes: int = 1, variance_threshold: float = 1e-5):
        self.n_regimes = n_regimes
        self.variance_threshold = variance_threshold
        self.kmeans = None
        self.stats = {}            # regime_id -> {col: (mean, std)}
        self.active_sensors = []

    def fit(self, df: pd.DataFrame) -> RegimeNormalizer:
        df = df.copy()
        setting_cols = [c for c in SETTING_COLS if c in df.columns]
        sensor_cols = [c for c in SENSOR_COLS if c in df.columns]

        # Determine active sensors (non-constant overall)
        self.active_sensors = [c for c in sensor_cols if df[c].var() > self.variance_threshold]

        if self.n_regimes > 1 and setting_cols:
            self.kmeans = KMeans(n_clusters=self.n_regimes, random_state=42, n_init=10)
            regimes = self.kmeans.fit_predict(df[setting_cols])
        else:
            self.kmeans = None
            regimes = np.zeros(len(df), dtype=int)

        df["_regime"] = regimes

        for r in range(self.n_regimes):
            sub = df[df["_regime"] == r]
            if len(sub) == 0:
                continue
            self.stats[r] = {}
            for col in self.active_sensors:
                mean = float(sub[col].mean())
                std = float(sub[col].std())
                if std < 1e-6:
                    std = 1.0
                self.stats[r][col] = (mean, std)

        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        setting_cols = [c for c in SETTING_COLS if c in out.columns]

        if self.kmeans is not None and setting_cols:
            regimes = self.kmeans.predict(out[setting_cols])
        else:
            regimes = np.zeros(len(out), dtype=int)

        out["_regime"] = regimes

        for col in self.active_sensors:
            vals = out[col].to_numpy(dtype=float)
            norm_vals = np.zeros_like(vals)
            for r in range(self.n_regimes):
                mask = (regimes == r)
                if not np.any(mask):
                    continue
                mean, std = self.stats.get(r, {}).get(col, (0.0, 1.0))
                norm_vals[mask] = (vals[mask] - mean) / std
            out[col] = norm_vals

        return out

    def save(self, filepath: str | Path) -> None:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath: str | Path) -> RegimeNormalizer:
        return joblib.load(filepath)


def fit_and_save_scaler(
    df: pd.DataFrame,
    subset: str,
    feature_cols: list[str] | None = None,
    scaler_type: str = "minmax",
) -> RegimeNormalizer:
    """
    Fits RegimeNormalizer on training dataframe and saves it to models/scalers/.
    n_regimes is set to 6 for multi-regime subsets (FD002, FD004) and 1 for single-regime (FD001, FD003).
    """
    n_regimes = 6 if subset in ["FD002", "FD004"] else 1
    scaler = RegimeNormalizer(n_regimes=n_regimes)
    scaler.fit(df)

    out_path = MODELS_SCALERS_DIR / f"scaler_{subset}.joblib"
    scaler.save(out_path)
    return scaler


def apply_scaler(df: pd.DataFrame, scaler: RegimeNormalizer, feature_cols: list[str] | None = None) -> pd.DataFrame:
    """Transforms dataframe using fitted RegimeNormalizer."""
    return scaler.transform(df)


def save_processed(df: pd.DataFrame, subset: str, split: str = "train") -> None:
    """Saves processed dataframe to data/processed directory."""
    from src.config import DATA_PROCESSED_DIR
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_PROCESSED_DIR / f"{subset}_{split}_processed.csv"
    df.to_csv(out_file, index=False)
