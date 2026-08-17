"""
anomaly_detector.py
===================
Isolation Forest-based Anomaly and Fault Detection for NASA C-MAPSS Engines.

Key Features
------------
1. Baseline Healthy Envelope: Learns normal sensor behavior from healthy baseline cycles.
2. Isolation Forest: Unsupervised anomaly detection on multidimensional telemetry.
3. Calibrated 0-100 Anomaly Score: 0 = Nominal/Healthy, 100 = Severe Anomaly.
4. Sensor-Level Abnormality & Contribution: Standardized z-score deviation ranking
   identifying which sensors deviate most from nominal operating conditions.
5. Model Persistence: Serialization and deserialization via joblib.

Public API
----------
    AnomalyDetector(n_estimators, contamination, random_state)
    categorize_deviation(z_score) -> (str, str)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    RUL_COL,
    RUL_CAPPED_COL,
    SENSOR_COLS,
    SETTING_COLS,
    ISOLATION_FOREST_PARAMS,
    ANOMALY_STAGES,
    ANOMALY_SCORE_THRESHOLD,
    SENSOR_DEVIATION_LEVELS,
    CONSTANT_VARIANCE_THRESHOLD,
    NEAR_CONSTANT_VARIANCE_THRESHOLD,
    MAX_RUL,
)


def categorize_deviation(z_score: float) -> Tuple[str, str]:
    """
    Categorize a standardized z-score deviation into severity and contribution.

    Parameters
    ----------
    z_score : float
        Standardized deviation score.

    Returns
    -------
    Tuple[str, str]
        (severity_label, contribution_level)
    """
    abs_z = abs(z_score)
    if abs_z >= SENSOR_DEVIATION_LEVELS["CRITICAL"]["min_z"]:
        return "Critical deviation", "High contribution"
    elif abs_z >= SENSOR_DEVIATION_LEVELS["HIGH"]["min_z"]:
        return "High deviation", "High contribution"
    elif abs_z >= SENSOR_DEVIATION_LEVELS["MODERATE"]["min_z"]:
        return "Moderate deviation", "Medium contribution"
    else:
        return "Low deviation", "Low contribution"


class AnomalyDetector:
    """
    Isolation Forest anomaly detector with calibrated 0-100 scoring
    and sensor-level contribution explanations.
    """

    def __init__(
        self,
        n_estimators: int = ISOLATION_FOREST_PARAMS["n_estimators"],
        contamination: float = ISOLATION_FOREST_PARAMS["contamination"],
        max_samples: Union[str, int, float] = ISOLATION_FOREST_PARAMS["max_samples"],
        random_state: int = ISOLATION_FOREST_PARAMS["random_state"],
        score_threshold: float = ANOMALY_SCORE_THRESHOLD,
    ):
        """
        Initialize AnomalyDetector.

        Parameters
        ----------
        n_estimators : int
            Number of trees in Isolation Forest.
        contamination : float
            Expected proportion of anomalous samples.
        max_samples : Union[str, int, float]
            Number of samples to draw from X to train each tree.
        random_state : int
            Random seed for reproducibility.
        score_threshold : float
            Threshold (0-100) above which a sample is flagged as 'Anomalous'.
        """
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.max_samples = max_samples
        self.random_state = random_state
        self.score_threshold = score_threshold

        self.model: Optional[IsolationForest] = None
        self.feature_names: List[str] = []
        self.sensor_cols_used: List[str] = []
        self.baseline_stats: Dict[str, Dict[str, float]] = {}
        
        # Decision score calibration bounds
        self.score_min_raw: float = -0.5
        self.score_max_raw: float = 0.5
        self.is_fitted: bool = False

    def _get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Extract valid feature columns, excluding identifiers, targets, and constant columns."""
        ignore_cols = {ENGINE_ID_COL, CYCLE_COL, RUL_COL, RUL_CAPPED_COL, "anomaly_score", "anomaly_label"}
        candidate_cols = [c for c in df.columns if c not in ignore_cols and pd.api.types.is_numeric_dtype(df[c])]

        # Filter out zero/constant variance columns
        valid_cols = []
        for col in candidate_cols:
            var = float(df[col].var()) if len(df) > 1 else 1.0
            if var > CONSTANT_VARIANCE_THRESHOLD:
                valid_cols.append(col)

        return valid_cols

    def fit(
        self,
        train_df: pd.DataFrame,
        subset: Optional[str] = None,
        healthy_baseline_only: bool = True,
        healthy_min_rul: float = 100.0,
    ) -> AnomalyDetector:
        """
        Fit Isolation Forest and compute baseline nominal distribution.

        Parameters
        ----------
        train_df : pd.DataFrame
            Engine training features DataFrame.
        subset : Optional[str]
            Dataset identifier (e.g. 'FD001') to load pre-calculated sensor classifications.
        healthy_baseline_only : bool
            If True, calculates baseline sensor statistics from healthy initial cycles.
        healthy_min_rul : float
            Threshold for identifying healthy cycles (if RUL / RUL_capped is present).

        Returns
        -------
        AnomalyDetector
            Fitted instance.
        """
        self.feature_names = self._get_feature_columns(train_df)
        if not self.feature_names:
            raise ValueError("No valid numeric feature columns found in training data.")

        # Check for constant / near-constant sensors from Person 1 report if available
        excluded_sensors = set()
        if subset:
            report_path = Path("outputs/reports") / f"report_{subset}.json"
            if report_path.exists():
                try:
                    with open(report_path) as f:
                        rdata = json.load(f)
                        excluded_sensors.update(rdata.get("constant_sensors", []))
                        excluded_sensors.update(rdata.get("near_constant_sensors", []))
                except Exception:
                    pass

        self.sensor_cols_used = [
            c for c in SENSOR_COLS
            if c in train_df.columns and c not in excluded_sensors
        ]
        if not self.sensor_cols_used:
            self.sensor_cols_used = [
                c for c in SENSOR_COLS if c in train_df.columns and float(train_df[c].var()) > CONSTANT_VARIANCE_THRESHOLD
            ]

        # 1. Compute baseline nominal statistics from healthy cycles
        if healthy_baseline_only and (RUL_CAPPED_COL in train_df.columns or RUL_COL in train_df.columns):
            rul_col = RUL_CAPPED_COL if RUL_CAPPED_COL in train_df.columns else RUL_COL
            healthy_df = train_df[train_df[rul_col] >= healthy_min_rul]
            if len(healthy_df) < 50:
                healthy_df = train_df.groupby(ENGINE_ID_COL).head(30)
        else:
            # First 30 cycles of each engine represent early healthy operation
            healthy_df = train_df.groupby(ENGINE_ID_COL).head(30) if ENGINE_ID_COL in train_df.columns else train_df

        self.baseline_stats = {}
        for col in self.sensor_cols_used:
            s = healthy_df[col].dropna()
            mean_val = float(s.mean())
            std_val = float(s.std()) if float(s.std()) > 1e-6 else 1e-6
            self.baseline_stats[col] = {
                "mean": mean_val,
                "std": std_val,
                "min": float(s.min()),
                "max": float(s.max()),
                "p25": float(s.quantile(0.25)),
                "p75": float(s.quantile(0.75)),
            }

        # 2. Fit Isolation Forest on telemetry features
        X_train = train_df[self.feature_names].fillna(0)
        print(f"  [anomaly] Training Isolation Forest on {len(X_train):,} rows with {len(self.feature_names)} features...")
        
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.model.fit(X_train)

        # 3. Calibrate decision score boundaries for 0-100 scaling
        raw_scores = self.model.decision_function(X_train)
        # 1st percentile and 99th percentile for robust normalization
        self.score_min_raw = float(np.percentile(raw_scores, 0.5))
        self.score_max_raw = float(np.percentile(raw_scores, 99.5))
        if self.score_max_raw <= self.score_min_raw:
            self.score_max_raw = self.score_min_raw + 1.0

        self.is_fitted = True
        print(f"  [anomaly] Model fitted successfully. Score range: [{self.score_min_raw:.4f}, {self.score_max_raw:.4f}]")
        return self

    def _compute_normalized_score(self, raw_decision: np.ndarray) -> np.ndarray:
        """
        Transform raw Isolation Forest decision score into normalized 0-100 Anomaly Score.
        Invert so lower decision function (outlier) -> higher anomaly score (0-100).
        """
        # Linear min-max scaling with inversion
        norm = (self.score_max_raw - raw_decision) / (self.score_max_raw - self.score_min_raw)
        scaled_score = np.clip(norm * 100.0, 0.0, 100.0)
        return np.round(scaled_score, 2)

    def predict(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate anomaly predictions, normalized anomaly scores (0-100), and raw scores.

        Parameters
        ----------
        df : pd.DataFrame
            Telemetry/feature DataFrame.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray, np.ndarray]
            - anomaly_labels: np.ndarray with strings ('Normal' or 'Anomalous')
            - anomaly_scores: np.ndarray with floats in [0.0, 100.0]
            - raw_scores: np.ndarray with raw decision function values
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("AnomalyDetector must be fitted before calling predict().")

        # Ensure all required features are present
        missing = set(self.feature_names) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required feature columns: {missing}")

        X = df[self.feature_names].fillna(0)
        raw_scores = self.model.decision_function(X)
        anomaly_scores = self._compute_normalized_score(raw_scores)

        # Binary classification based on threshold or model decision
        raw_preds = self.model.predict(X)  # -1 = anomaly, +1 = normal
        
        # Label is 'Anomalous' if score exceeds threshold OR raw_preds is -1
        is_anom = (anomaly_scores >= self.score_threshold) | (raw_preds == -1)
        anomaly_labels = np.where(is_anom, "Anomalous", "Normal")

        return anomaly_labels, anomaly_scores, raw_scores

    def get_severity(self, anomaly_score: float) -> str:
        """Categorize an anomaly score into severity stages."""
        if anomaly_score >= ANOMALY_STAGES["SEVERE"]["min_score"]:
            return ANOMALY_STAGES["SEVERE"]["severity"]
        elif anomaly_score >= ANOMALY_STAGES["MODERATE"]["min_score"]:
            return ANOMALY_STAGES["MODERATE"]["severity"]
        elif anomaly_score >= ANOMALY_STAGES["MILD"]["min_score"]:
            return ANOMALY_STAGES["MILD"]["severity"]
        else:
            return ANOMALY_STAGES["NOMINAL"]["severity"]

    def explain_anomalies(
        self,
        df: pd.DataFrame,
        top_n: int = 3,
    ) -> pd.DataFrame:
        """
        Compute sensor-level deviations and rank contributing abnormal sensors.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with sensor columns.
        top_n : int
            Number of top abnormal sensors to detail.

        Returns
        -------
        pd.DataFrame
            DataFrame containing structured explanation columns.
        """
        if not self.baseline_stats:
            raise RuntimeError("Baseline statistics not computed. Fit model first.")

        available_sensors = [s for s in self.sensor_cols_used if s in df.columns]
        if not available_sensors:
            raise ValueError("No matching sensor columns found for explanation.")

        # Compute z-scores for all sensors simultaneously
        z_matrix = np.zeros((len(df), len(available_sensors)), dtype=float)
        for idx, s in enumerate(available_sensors):
            mu = self.baseline_stats[s]["mean"]
            std = self.baseline_stats[s]["std"]
            values = df[s].values
            z_matrix[:, idx] = (values - mu) / std

        abs_z_matrix = np.abs(z_matrix)

        # Prepare explanation records
        explanations: List[Dict[str, Any]] = []
        n_sensors = len(available_sensors)

        for row_idx in range(len(df)):
            row_abs_z = abs_z_matrix[row_idx]
            row_z = z_matrix[row_idx]

            # Sort sensor indices by absolute deviation descending
            sorted_indices = np.argsort(-row_abs_z)

            row_expl: Dict[str, Any] = {}
            summary_parts: List[str] = []

            for rank in range(min(top_n, n_sensors)):
                s_idx = sorted_indices[rank]
                s_name = available_sensors[s_idx]
                z_val = round(float(row_z[s_idx]), 2)
                abs_z = round(float(row_abs_z[s_idx]), 2)
                
                sev, contrib = categorize_deviation(z_val)
                sign_str = f"+{z_val:.2f}σ" if z_val >= 0 else f"{z_val:.2f}σ"

                rank_num = rank + 1
                row_expl[f"top_sensor_{rank_num}"] = s_name
                row_expl[f"top_sensor_{rank_num}_zscore"] = z_val
                row_expl[f"top_sensor_{rank_num}_abs_dev"] = abs_z
                row_expl[f"top_sensor_{rank_num}_severity"] = sev
                row_expl[f"top_sensor_{rank_num}_contribution"] = contrib

                if abs_z >= 1.0:
                    summary_parts.append(f"{s_name} ({sign_str}, {sev})")

            row_expl["top_abnormal_sensors"] = " | ".join(summary_parts) if summary_parts else "All sensors within nominal range"
            row_expl["max_sensor_deviation"] = round(float(row_abs_z[sorted_indices[0]]), 2)
            
            explanations.append(row_expl)

        return pd.DataFrame(explanations)

    def score_and_explain(
        self,
        df: pd.DataFrame,
        top_n: int = 3,
    ) -> pd.DataFrame:
        """
        Run full anomaly scoring, classification, and sensor-level explanation.

        Parameters
        ----------
        df : pd.DataFrame
            Input telemetry / feature DataFrame.
        top_n : int
            Number of top sensors to record.

        Returns
        -------
        pd.DataFrame
            Merged DataFrame with identification columns, anomaly scores,
            anomaly labels, severity, and sensor-level contributions.
        """
        labels, scores, raw_scores = self.predict(df)
        expl_df = self.explain_anomalies(df, top_n=top_n)

        out_df = pd.DataFrame()
        if ENGINE_ID_COL in df.columns:
            out_df[ENGINE_ID_COL] = df[ENGINE_ID_COL].values
        if CYCLE_COL in df.columns:
            out_df[CYCLE_COL] = df[CYCLE_COL].values

        out_df["anomaly_raw_score"] = np.round(raw_scores, 4)
        out_df["anomaly_score"] = scores
        out_df["anomaly_label"] = labels
        out_df["anomaly_severity"] = [self.get_severity(s) for s in scores]

        # Combine with explanation columns
        for c in expl_df.columns:
            out_df[c] = expl_df[c].values

        return out_df

    def get_fleet_sensor_abnormality_summary(self, df_with_scores: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate fleet-wide ranking of sensors contributing to anomalies.

        Parameters
        ----------
        df_with_scores : pd.DataFrame
            DataFrame produced by score_and_explain.

        Returns
        -------
        pd.DataFrame
            Summary table ranking sensors by frequency of being top abnormal.
        """
        anom_rows = df_with_scores[df_with_scores["anomaly_label"] == "Anomalous"]
        if anom_rows.empty:
            anom_rows = df_with_scores

        records = []
        for s in self.sensor_cols_used:
            is_top1 = (anom_rows["top_sensor_1"] == s).sum()
            is_top3 = (
                (anom_rows["top_sensor_1"] == s) |
                (anom_rows.get("top_sensor_2", pd.Series()) == s) |
                (anom_rows.get("top_sensor_3", pd.Series()) == s)
            ).sum()
            
            records.append({
                "sensor": s,
                "top_1_abnormal_count": int(is_top1),
                "top_3_abnormal_count": int(is_top3),
                "top_1_frequency_pct": round(float(is_top1 / len(anom_rows) * 100), 2) if len(anom_rows) > 0 else 0.0,
            })

        summary_df = pd.DataFrame(records).sort_values("top_1_abnormal_count", ascending=False).reset_index(drop=True)
        return summary_df

    def save(self, filepath: Union[str, Path]) -> Path:
        """Save fitted AnomalyDetector instance to disk."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        save_dict = {
            "n_estimators": self.n_estimators,
            "contamination": self.contamination,
            "max_samples": self.max_samples,
            "random_state": self.random_state,
            "score_threshold": self.score_threshold,
            "score_min_raw": self.score_min_raw,
            "score_max_raw": self.score_max_raw,
            "feature_names": self.feature_names,
            "sensor_cols_used": self.sensor_cols_used,
            "baseline_stats": self.baseline_stats,
            "model": self.model,
            "is_fitted": self.is_fitted,
        }
        joblib.dump(save_dict, filepath)
        print(f"  [anomaly] Model successfully saved to -> {filepath}")
        return filepath

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> AnomalyDetector:
        """Load fitted AnomalyDetector from disk."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Anomaly model file not found: {filepath}")

        saved_dict = joblib.load(filepath)
        instance = cls(
            n_estimators=saved_dict["n_estimators"],
            contamination=saved_dict["contamination"],
            max_samples=saved_dict["max_samples"],
            random_state=saved_dict["random_state"],
            score_threshold=saved_dict["score_threshold"],
        )
        instance.score_min_raw = saved_dict["score_min_raw"]
        instance.score_max_raw = saved_dict["score_max_raw"]
        instance.feature_names = saved_dict["feature_names"]
        instance.sensor_cols_used = saved_dict["sensor_cols_used"]
        instance.baseline_stats = saved_dict["baseline_stats"]
        instance.model = saved_dict["model"]
        instance.is_fitted = saved_dict["is_fitted"]

        print(f"  [anomaly] Loaded AnomalyDetector model from -> {filepath}")
        return instance
