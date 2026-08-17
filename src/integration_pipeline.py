"""
integration_pipeline.py
=======================
Unified Integration & Maintenance Recommendation Pipeline (Person 4).

Workflow
--------
1. Load test features (Person 1).
2. Load trained RUL predictor (Person 2) & compute cycle-level RUL predictions.
3. Load trained Anomaly detector (Person 3) & compute cycle-level anomaly scores and sensor attributions.
4. Merge RUL + Anomaly signals on (engine_id, cycle) into a unified dataset.
5. Apply Multi-Factor Health Assessment (HEALTHY, MONITOR, MAINTENANCE REQUIRED, CRITICAL).
6. Generate explainable `decision_reason` and actionable `maintenance_recommendation`.
7. Export cycle-level combined telemetry to `outputs/predictions/cycle_integrated_health_{subset}.csv`.
8. Export engine-level fleet advisory to `outputs/predictions/fleet_maintenance_advisory_{subset}.csv` and `.json`.
9. Generate 5 publication-quality visualizations at 300 DPI in `outputs/plots/`.
10. Generate structured JSON & TXT reports in `outputs/reports/`.

Public API
----------
    run_integration_pipeline(subset, rul_model_type) -> dict
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    RUL_COL,
    RUL_CAPPED_COL,
    DATA_FEATURES_DIR,
    DATA_PROCESSED_DIR,
    MODELS_RUL_DIR,
    MODELS_ANOMALY_DIR,
    OUTPUTS_PREDICTIONS_DIR,
    OUTPUTS_PLOTS_DIR,
    OUTPUTS_REPORTS_DIR,
    MAX_RUL,
    MAINTENANCE_DECISION_THRESHOLDS,
    DISCLAIMER_TEXT,
)
from src.rul_predictor import RULPredictor
from src.anomaly_detector import AnomalyDetector
from src.health_score import calculate_health_score
from src.health_assessment import assess_dataframe
from src.maintenance_recommendation import add_maintenance_recommendations_to_dataframe
from src.integration_plots import (
    plot_integrated_rul_timeline,
    plot_health_status_distribution,
    plot_maintenance_category_breakdown,
    plot_rul_vs_anomaly_risk_quadrant,
)


def load_test_features_and_models(
    subset: str,
    rul_model_type: str = "random_forest",
) -> Tuple[pd.DataFrame, RULPredictor, AnomalyDetector]:
    """
    Load test telemetry features and serialized Person 2 & Person 3 models.
    """
    # 1. Load test features
    feat_path = DATA_FEATURES_DIR / f"features_test_{subset}.csv"
    if not feat_path.exists():
        feat_path = DATA_PROCESSED_DIR / f"processed_test_{subset}.csv"
        if not feat_path.exists():
            raise FileNotFoundError(f"Test feature data not found for {subset}.")

    print(f"  [data] Loading test telemetry features from {feat_path.name}...")
    test_df = pd.read_csv(feat_path)

    # 2. Load RUL Predictor (Person 2) - Try requested model, fall back if missing/unpickle error
    rul_predictor = None
    candidate_types = [rul_model_type, "random_forest", "xgboost"]
    # De-duplicate while preserving order
    seen = set()
    candidate_types = [x for x in candidate_types if not (x in seen or seen.add(x))]

    for m_type in candidate_types:
        rul_model_path = MODELS_RUL_DIR / f"model_{subset}_{m_type}.joblib"
        if rul_model_path.exists():
            try:
                rul_predictor = RULPredictor.load(rul_model_path)
                print(f"  [model] Loaded Person 2 RUL model from {rul_model_path.name} ({m_type})")
                break
            except Exception as e:
                print(f"  [model] Notice: Could not load {rul_model_path.name} ({e}). Trying fallback...")

    if rul_predictor is None:
        raise FileNotFoundError(f"No usable RUL model found for {subset} in {MODELS_RUL_DIR}")

    # 3. Load Anomaly Detector (Person 3)
    anomaly_model_path = MODELS_ANOMALY_DIR / f"isolation_forest_{subset}.joblib"
    if not anomaly_model_path.exists():
        raise FileNotFoundError(f"No Anomaly model found for {subset} in {MODELS_ANOMALY_DIR}")

    print(f"  [model] Loading Person 3 Anomaly model from {anomaly_model_path.name}...")
    anomaly_detector = AnomalyDetector.load(anomaly_model_path)

    return test_df, rul_predictor, anomaly_detector


def build_cycle_level_integration(
    test_df: pd.DataFrame,
    rul_predictor: RULPredictor,
    anomaly_detector: AnomalyDetector,
    subset: str,
) -> pd.DataFrame:
    """
    Perform synchronized cycle-by-cycle prediction, anomaly scoring, and health assessment.
    """
    print(f"  [integration] Running cycle-level RUL predictions and anomaly explanations...")
    
    # 1. RUL Predictions
    rul_preds = rul_predictor.predict(test_df)
    rul_health_scores = calculate_health_score(rul_preds, baseline_max_rul=MAX_RUL)

    # 2. Anomaly Scoring and Sensor Explanations
    anomaly_df = anomaly_detector.score_and_explain(test_df, top_n=3)

    # 3. Combine into unified DataFrame
    combined_df = pd.DataFrame()
    combined_df[ENGINE_ID_COL] = test_df[ENGINE_ID_COL].values
    combined_df[CYCLE_COL] = test_df[CYCLE_COL].values

    if RUL_COL in test_df.columns:
        combined_df["true_RUL"] = test_df[RUL_COL].values
    elif RUL_CAPPED_COL in test_df.columns:
        combined_df["true_RUL"] = test_df[RUL_CAPPED_COL].values

    combined_df["predicted_RUL"] = np.round(rul_preds, 2)
    combined_df["rul_health_score"] = np.round(rul_health_scores, 2)

    # Attach anomaly columns
    combined_df["anomaly_raw_score"] = anomaly_df["anomaly_raw_score"].values
    combined_df["anomaly_score"] = anomaly_df["anomaly_score"].values
    combined_df["anomaly_label"] = anomaly_df["anomaly_label"].values
    combined_df["anomaly_severity"] = anomaly_df["anomaly_severity"].values
    combined_df["top_abnormal_sensors"] = anomaly_df["top_abnormal_sensors"].values
    combined_df["max_sensor_deviation"] = anomaly_df["max_sensor_deviation"].values

    for rank in [1, 2, 3]:
        for col_suffix in ["", "_zscore", "_severity", "_contribution"]:
            cname = f"top_sensor_{rank}{col_suffix}"
            if cname in anomaly_df.columns:
                combined_df[cname] = anomaly_df[cname].values

    # 4. Multi-Factor Health Assessment & Explainability
    combined_df = assess_dataframe(
        combined_df,
        rul_col="predicted_RUL",
        anomaly_score_col="anomaly_score",
        anomaly_status_col="anomaly_label",
        top_sensors_col="top_abnormal_sensors",
    )

    # 5. Actionable Maintenance Recommendations
    combined_df = add_maintenance_recommendations_to_dataframe(
        combined_df,
        health_status_col="engine_health_status",
        top_sensors_col="top_abnormal_sensors",
        rul_col="predicted_RUL",
    )

    return combined_df


def build_fleet_level_summary(
    cycle_integrated_df: pd.DataFrame,
    subset: str,
) -> pd.DataFrame:
    """
    Extract latest observed cycle per engine and build authoritative fleet advisory.
    """
    print(f"  [integration] Generating fleet-level maintenance advisory summary...")
    
    # Identify last observed cycle for each engine
    last_idx = cycle_integrated_df.groupby(ENGINE_ID_COL)[CYCLE_COL].idxmax()
    fleet_df = cycle_integrated_df.loc[last_idx].sort_values(ENGINE_ID_COL).reset_index(drop=True)

    # Rename cycle column for clarity
    fleet_df = fleet_df.rename(columns={
        CYCLE_COL: "latest_observed_cycle",
        "anomaly_score": "latest_anomaly_score",
        "anomaly_label": "latest_anomaly_status",
        "anomaly_severity": "latest_anomaly_severity",
    })

    # Add error metric if ground truth RUL is present
    if "true_RUL" in fleet_df.columns:
        fleet_df["absolute_error"] = np.round(np.abs(fleet_df["predicted_RUL"] - fleet_df["true_RUL"]), 2)

    # Rearrange columns into UI-ready order
    key_cols = [
        ENGINE_ID_COL,
        "latest_observed_cycle",
        "predicted_RUL",
    ]
    if "true_RUL" in fleet_df.columns:
        key_cols.extend(["true_RUL", "absolute_error"])

    key_cols.extend([
        "rul_health_score",
        "latest_anomaly_score",
        "latest_anomaly_status",
        "latest_anomaly_severity",
        "top_abnormal_sensors",
        "engine_health_status",
        "composite_health_score",
        "risk_level",
        "maintenance_recommendation",
        "decision_reason",
        "targeted_action_items",
        "impacted_components",
        "urgency_window_cycles",
    ])

    fleet_summary = fleet_df[key_cols].copy()
    fleet_summary["disclaimer"] = DISCLAIMER_TEXT

    return fleet_summary


def save_integration_outputs(
    cycle_integrated_df: pd.DataFrame,
    fleet_summary_df: pd.DataFrame,
    subset: str,
) -> Dict[str, Path]:
    """
    Export cycle and fleet datasets in CSV and JSON formats.
    """
    OUTPUTS_PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

    cycle_csv_path = OUTPUTS_PREDICTIONS_DIR / f"cycle_integrated_health_{subset}.csv"
    fleet_csv_path = OUTPUTS_PREDICTIONS_DIR / f"fleet_maintenance_advisory_{subset}.csv"
    fleet_json_path = OUTPUTS_PREDICTIONS_DIR / f"fleet_maintenance_advisory_{subset}.json"

    cycle_integrated_df.to_csv(cycle_csv_path, index=False)
    fleet_summary_df.to_csv(fleet_csv_path, index=False)

    fleet_records = fleet_summary_df.to_dict(orient="records")
    with open(fleet_json_path, "w") as f:
        json.dump(fleet_records, f, indent=2)

    print(f"  [export] Saved cycle-level integrated telemetry -> {cycle_csv_path.name}")
    print(f"  [export] Saved fleet maintenance advisory (CSV & JSON) -> {fleet_csv_path.name}")

    return {
        "cycle_csv": cycle_csv_path,
        "fleet_csv": fleet_csv_path,
        "fleet_json": fleet_json_path,
    }


def generate_executive_fleet_report(
    subset: str,
    fleet_summary_df: pd.DataFrame,
    cycle_df: pd.DataFrame,
    elapsed_time: float,
) -> Dict[str, Any]:
    """
    Generate fleet executive health summary report in JSON and TXT formats.
    """
    OUTPUTS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    total_engines = len(fleet_summary_df)
    total_cycles = len(cycle_df)

    status_counts = fleet_summary_df["engine_health_status"].value_counts().to_dict()
    risk_counts = fleet_summary_df["risk_level"].value_counts().to_dict()

    critical_count = int(status_counts.get("CRITICAL", 0))
    maint_count = int(status_counts.get("MAINTENANCE REQUIRED", 0))
    monitor_count = int(status_counts.get("MONITOR", 0))
    healthy_count = int(status_counts.get("HEALTHY", 0))

    critical_engines = fleet_summary_df[fleet_summary_df["engine_health_status"] == "CRITICAL"][ENGINE_ID_COL].tolist()
    maint_engines = fleet_summary_df[fleet_summary_df["engine_health_status"] == "MAINTENANCE REQUIRED"][ENGINE_ID_COL].tolist()

    report_data = {
        "dataset": subset,
        "total_fleet_engines": total_engines,
        "total_operational_cycles_evaluated": total_cycles,
        "health_distribution": {
            "HEALTHY": {"count": healthy_count, "pct": round(healthy_count / total_engines * 100, 1)},
            "MONITOR": {"count": monitor_count, "pct": round(monitor_count / total_engines * 100, 1)},
            "MAINTENANCE_REQUIRED": {"count": maint_count, "pct": round(maint_count / total_engines * 100, 1)},
            "CRITICAL": {"count": critical_count, "pct": round(critical_count / total_engines * 100, 1)},
        },
        "risk_breakdown": {k: int(v) for k, v in risk_counts.items()},
        "critical_engines": critical_engines,
        "maintenance_required_engines": maint_engines,
        "mean_predicted_rul_fleet": round(float(fleet_summary_df["predicted_RUL"].mean()), 2),
        "mean_anomaly_score_fleet": round(float(fleet_summary_df["latest_anomaly_score"].mean()), 2),
        "mean_composite_health_index": round(float(fleet_summary_df["composite_health_score"].mean()), 2),
        "execution_time_seconds": round(elapsed_time, 2),
        "disclaimer": DISCLAIMER_TEXT,
    }

    # Save JSON report
    json_path = OUTPUTS_REPORTS_DIR / f"fleet_health_report_{subset}.json"
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)

    # Save TXT report
    txt_path = OUTPUTS_REPORTS_DIR / f"fleet_health_report_{subset}.txt"
    lines = [
        "=" * 65,
        f"  FLEET HEALTH ASSESSMENT & MAINTENANCE ADVISORY – {subset}",
        "=" * 65,
        "",
        f"Dataset:                       {subset}",
        f"Total Engines Evaluated:       {total_engines}",
        f"Total Cycles Analyzed:         {total_cycles:,}",
        f"Mean Fleet Predicted RUL:      {report_data['mean_predicted_rul_fleet']} cycles",
        f"Mean Fleet Anomaly Score:      {report_data['mean_anomaly_score_fleet']} / 100",
        f"Mean Composite Health Score:   {report_data['mean_composite_health_index']}%",
        "",
        "--- Fleet Health Distribution ---",
        f"  HEALTHY (Green)              : {healthy_count:>4} engines ({healthy_count/total_engines*100:>5.1f}%)",
        f"  MONITOR (Yellow)             : {monitor_count:>4} engines ({monitor_count/total_engines*100:>5.1f}%)",
        f"  MAINTENANCE REQUIRED (Orange): {maint_count:>4} engines ({maint_count/total_engines*100:>5.1f}%)",
        f"  CRITICAL (Red)               : {critical_count:>4} engines ({critical_count/total_engines*100:>5.1f}%)",
        "",
        "--- Priority Engine Grounding & Inspection List ---",
        f"  CRITICAL Engines             : {critical_engines if critical_engines else 'None'}",
        f"  MAINTENANCE REQUIRED Engines : {maint_engines[:15] if maint_engines else 'None'}" + ("..." if len(maint_engines) > 15 else ""),
        "",
        "--- Prototype Advisory Notice ---",
        DISCLAIMER_TEXT,
        "",
        "=" * 65,
    ]

    with open(txt_path, "w") as f:
        f.write("\n".join(lines))

    print(f"  [report] Saved fleet health report -> {json_path.name} + {txt_path.name}")
    return report_data


def run_integration_pipeline(
    subset: str,
    rul_model_type: str = "xgboost",
) -> Dict[str, Any]:
    """
    Execute full Person 4 Integration & Maintenance Advisory Pipeline.
    """
    t0 = time.time()
    print(f"\n{'='*65}")
    print(f"  PERSON 4 INTEGRATION PIPELINE START: {subset}")
    print(f"{'='*65}")

    # 1. Load Data & Models
    test_df, rul_predictor, anomaly_detector = load_test_features_and_models(subset, rul_model_type)

    # 2. Cycle-Level Combined Evaluation
    cycle_integrated_df = build_cycle_level_integration(test_df, rul_predictor, anomaly_detector, subset)

    # 3. Fleet-Level Latest Status Summary
    fleet_summary_df = build_fleet_level_summary(cycle_integrated_df, subset)

    # 4. Save Outputs
    save_integration_outputs(cycle_integrated_df, fleet_summary_df, subset)

    # 5. Generate Visualizations (300 DPI)
    print(f"  [visuals] Generating integration & maintenance plots...")
    plot_integrated_rul_timeline(cycle_integrated_df, subset)
    plot_health_status_distribution(fleet_summary_df, subset)
    plot_maintenance_category_breakdown(fleet_summary_df, subset)
    plot_rul_vs_anomaly_risk_quadrant(fleet_summary_df, subset)

    # 6. Executive Report
    elapsed = time.time() - t0
    report = generate_executive_fleet_report(subset, fleet_summary_df, cycle_integrated_df, elapsed)

    hd = report["health_distribution"]
    print(f"\n--- Fleet Health Summary: {subset} ---")
    print(f"  HEALTHY              : {hd['HEALTHY']['count']} ({hd['HEALTHY']['pct']}%)")
    print(f"  MONITOR              : {hd['MONITOR']['count']} ({hd['MONITOR']['pct']}%)")
    print(f"  MAINTENANCE REQUIRED : {hd['MAINTENANCE_REQUIRED']['count']} ({hd['MAINTENANCE_REQUIRED']['pct']}%)")
    print(f"  CRITICAL             : {hd['CRITICAL']['count']} ({hd['CRITICAL']['pct']}%)")
    print(f"{'='*65}\n")

    return {
        "subset": subset,
        "report": report,
        "cycle_integrated_df": cycle_integrated_df,
        "fleet_summary_df": fleet_summary_df,
    }
