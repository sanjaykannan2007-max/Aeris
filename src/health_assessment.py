"""
health_assessment.py
====================
Multi-Factor Engine Health Assessment & Explainable Decision Logic (Person 4).

Features
--------
1. Dual-Signal Health Assessment: Combines Predicted Remaining Useful Life (Person 2)
   and Isolation Forest Anomaly Scores (Person 3) into an authoritative health stage.
2. 4-Stage Health Classification:
   - HEALTHY (Nominal operations, high RUL, low anomaly)
   - MONITOR (Mild degradation or telemetry drift)
   - MAINTENANCE REQUIRED (Low RUL or significant abnormal behaviour)
   - CRITICAL (Imminent failure RUL or severe anomaly)
3. Transparent Explainability: Generates human-readable `decision_reason` detailing
   the exact quantitative factors that triggered the classification.
4. Composite Health Index (0-100%): Weighted fusion of RUL capacity and anomaly nominality.

Public API
----------
    assess_engine_health(predicted_rul, anomaly_score, anomaly_status) -> dict
    generate_decision_reason(predicted_rul, anomaly_score, anomaly_status, top_sensors, health_status) -> str
    assess_dataframe(df, rul_col, anomaly_score_col, anomaly_status_col, top_sensors_col) -> pd.DataFrame
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.config import (
    MAX_RUL,
    MAINTENANCE_DECISION_THRESHOLDS,
    SENSOR_COMPONENT_MAPPINGS,
)


def assess_engine_health(
    predicted_rul: float,
    anomaly_score: float,
    anomaly_status: str = "Normal",
    max_sensor_dev: Optional[float] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate multi-factor health stage and risk level for a single engine/cycle.

    Parameters
    ----------
    predicted_rul : float
        Predicted Remaining Useful Life in cycles (Person 2).
    anomaly_score : float
        Calibrated anomaly score from 0 to 100 (Person 3).
    anomaly_status : str
        'Normal' or 'Anomalous' (Person 3).
    max_sensor_dev : float, optional
        Maximum standardized sensor z-score deviation observed.
    thresholds : dict, optional
        Custom decision thresholds (defaults to MAINTENANCE_DECISION_THRESHOLDS).

    Returns
    -------
    dict
        {
            'health_status': 'HEALTHY' | 'MONITOR' | 'MAINTENANCE REQUIRED' | 'CRITICAL',
            'risk_level': 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL',
            'composite_health_score': float (0.0 to 100.0),
            'rul_component_score': float,
            'anomaly_component_score': float,
        }
    """
    t = thresholds or MAINTENANCE_DECISION_THRESHOLDS

    rul = float(predicted_rul)
    anom = float(anomaly_score)
    is_anom_label = str(anomaly_status).strip().lower() in ("anomalous", "anomaly", "1", "true")

    # 1. Evaluate Decision Hierarchy
    # Rule 1: CRITICAL (Imminent RUL breach OR Severe Anomaly)
    if rul < t["CRITICAL"]["max_rul"] or anom >= t["CRITICAL"]["min_anomaly_score"]:
        health_status = t["CRITICAL"]["label"]
        risk_level = t["CRITICAL"]["risk_level"]

    # Rule 2: MAINTENANCE REQUIRED (Low RUL OR Moderate Anomaly)
    elif rul < t["MAINTENANCE_REQUIRED"]["max_rul"] or anom >= t["MAINTENANCE_REQUIRED"]["min_anomaly_score"]:
        health_status = t["MAINTENANCE_REQUIRED"]["label"]
        risk_level = t["MAINTENANCE_REQUIRED"]["risk_level"]

    # Rule 3: MONITOR (Moderate RUL OR Mild Drift OR Flagged Anomaly)
    elif rul < t["MONITOR"]["max_rul"] or anom >= t["MONITOR"]["min_anomaly_score"] or is_anom_label:
        health_status = t["MONITOR"]["label"]
        risk_level = t["MONITOR"]["risk_level"]

    # Rule 4: HEALTHY (High RUL AND Nominal Telemetry)
    else:
        health_status = t["HEALTHY"]["label"]
        risk_level = t["HEALTHY"]["risk_level"]

    # 2. Composite Health Index (0 to 100%)
    # RUL Capacity: normalized against MAX_RUL (125 cycles)
    rul_pct = np.clip((rul / MAX_RUL) * 100.0, 0.0, 100.0)
    # Anomaly Nominality: 100 minus anomaly score
    anom_nominality = np.clip(100.0 - anom, 0.0, 100.0)

    # Weighted fusion: 60% RUL capacity + 40% Telemetry Nominality
    composite = 0.60 * rul_pct + 0.40 * anom_nominality
    composite = round(float(np.clip(composite, 0.0, 100.0)), 2)

    return {
        "health_status": health_status,
        "risk_level": risk_level,
        "composite_health_score": composite,
        "rul_component_score": round(float(rul_pct), 2),
        "anomaly_component_score": round(float(anom_nominality), 2),
    }


def generate_decision_reason(
    predicted_rul: float,
    anomaly_score: float,
    anomaly_status: str,
    top_abnormal_sensors: Optional[str] = None,
    health_status: Optional[str] = None,
) -> str:
    """
    Generate explainable, human-readable natural language reason for the decision.

    Parameters
    ----------
    predicted_rul : float
        Predicted RUL in cycles.
    anomaly_score : float
        Anomaly score (0-100).
    anomaly_status : str
        'Normal' or 'Anomalous'.
    top_abnormal_sensors : str, optional
        Summary string of top contributing sensors.
    health_status : str, optional
        Assigned health status.

    Returns
    -------
    str
        Concise, professional natural language rationale.
    """
    rul = float(predicted_rul)
    anom = float(anomaly_score)

    if health_status is None:
        assessment = assess_engine_health(rul, anom, anomaly_status)
        health_status = assessment["health_status"]

    sensors_clause = ""
    if top_abnormal_sensors and "nominal" not in top_abnormal_sensors.lower() and "none" not in top_abnormal_sensors.lower():
        sensors_clause = f" | Sensor deviations: {top_abnormal_sensors}"

    if health_status == "CRITICAL":
        if rul < 20.0 and anom >= 80.0:
            return f"CRITICAL: Imminent end-of-life (RUL: {rul:.1f} cycles) combined with severe multi-sensor anomaly (Score: {anom:.1f}/100){sensors_clause}."
        elif rul < 20.0:
            return f"CRITICAL: Exhausted remaining operational life (RUL: {rul:.1f} cycles < 20 cycle threshold){sensors_clause}."
        else:
            return f"CRITICAL: Severe telemetry anomaly detected (Score: {anom:.1f}/100 >= 80) indicating acute sub-system fault{sensors_clause}."

    elif health_status == "MAINTENANCE REQUIRED":
        if rul < 45.0 and anom >= 65.0:
            return f"MAINTENANCE REQUIRED: Low remaining life (RUL: {rul:.1f} cycles) with significant sensor abnormality (Score: {anom:.1f}/100){sensors_clause}."
        elif rul < 45.0:
            return f"MAINTENANCE REQUIRED: Approaching maintenance threshold (RUL: {rul:.1f} cycles < 45 cycle limit){sensors_clause}."
        else:
            return f"MAINTENANCE REQUIRED: Elevated anomaly score ({anom:.1f}/100 >= 65) indicating active degradation{sensors_clause}."

    elif health_status == "MONITOR":
        if anom >= 45.0:
            return f"MONITOR: Mild telemetry drift detected (Score: {anom:.1f}/100) with RUL at {rul:.1f} cycles{sensors_clause}."
        else:
            return f"MONITOR: Mid-life operational regime (RUL: {rul:.1f} cycles < 75 cycles); telemetry currently nominal."

    else:  # HEALTHY
        return f"HEALTHY: High remaining useful life (RUL: {rul:.1f} cycles >= 75) with nominal baseline telemetry (Score: {anom:.1f}/100)."


def assess_dataframe(
    df: pd.DataFrame,
    rul_col: str = "predicted_RUL",
    anomaly_score_col: str = "anomaly_score",
    anomaly_status_col: str = "anomaly_status",
    top_sensors_col: str = "top_abnormal_sensors",
) -> pd.DataFrame:
    """
    Vectorized / row-wise evaluation of health assessment across a pandas DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing RUL and anomaly columns.
    rul_col : str
        Column name for predicted RUL.
    anomaly_score_col : str
        Column name for anomaly score.
    anomaly_status_col : str
        Column name for anomaly status/label.
    top_sensors_col : str
        Column name for abnormal sensors description.

    Returns
    -------
    pd.DataFrame
        DataFrame with appended health assessment and explainability columns.
    """
    out_df = df.copy()

    # Resolve column names if variations exist
    if rul_col not in out_df.columns:
        if "RUL" in out_df.columns:
            rul_col = "RUL"
        elif "predicted_rul" in out_df.columns:
            rul_col = "predicted_rul"
        else:
            raise KeyError(f"Predicted RUL column '{rul_col}' not found in DataFrame.")

    if anomaly_score_col not in out_df.columns:
        if "final_anomaly_score" in out_df.columns:
            anomaly_score_col = "final_anomaly_score"
        elif "score" in out_df.columns:
            anomaly_score_col = "score"

    if anomaly_status_col not in out_df.columns:
        if "anomaly_label" in out_df.columns:
            anomaly_status_col = "anomaly_label"
        elif "final_anomaly_status" in out_df.columns:
            anomaly_status_col = "final_anomaly_status"

    health_statuses = []
    risk_levels = []
    composite_scores = []
    reasons = []

    for _, row in out_df.iterrows():
        rul = float(row.get(rul_col, 100.0))
        anom = float(row.get(anomaly_score_col, 0.0)) if anomaly_score_col in row else 0.0
        status_lbl = str(row.get(anomaly_status_col, "Normal"))
        top_sensors = str(row.get(top_sensors_col, "")) if top_sensors_col in row else ""

        eval_res = assess_engine_health(rul, anom, status_lbl)
        h_stat = eval_res["health_status"]
        r_lvl = eval_res["risk_level"]
        comp = eval_res["composite_health_score"]
        reason = generate_decision_reason(rul, anom, status_lbl, top_sensors, h_stat)

        health_statuses.append(h_stat)
        risk_levels.append(r_lvl)
        composite_scores.append(comp)
        reasons.append(reason)

    out_df["engine_health_status"] = health_statuses
    out_df["composite_health_score"] = composite_scores
    out_df["risk_level"] = risk_levels
    out_df["decision_reason"] = reasons

    return out_df
