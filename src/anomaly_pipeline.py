"""
anomaly_pipeline.py
===================
End-to-end orchestration of Person 3 Anomaly & Fault Detection.

Workflow
--------
1. Load processed telemetry & engineered features (Person 1).
2. Fit AnomalyDetector (Isolation Forest) on healthy baseline envelope.
3. Save trained model to `models/anomaly/`.
4. Score all operational cycles and generate sensor-level z-score explanations.
5. Aggregate engine-level summary for the test fleet.
6. Integrate with Person 2 RUL predictions if available (`predictions_{subset}_*.csv`).
7. Generate and save 5 publication-quality visualizations (300 DPI).
8. Save structured JSON/TXT evaluation reports.

Public API
----------
    run_anomaly_pipeline(subset, contamination, n_estimators) -> dict
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    RUL_COL,
    RUL_CAPPED_COL,
    DATA_FEATURES_DIR,
    DATA_PROCESSED_DIR,
    MODELS_ANOMALY_DIR,
    OUTPUTS_PREDICTIONS_DIR,
    OUTPUTS_PLOTS_DIR,
    OUTPUTS_REPORTS_DIR,
    ISOLATION_FOREST_PARAMS,
    ANOMALY_SCORE_THRESHOLD,
)
from src.anomaly_detector import AnomalyDetector
from src.anomaly_plots import (
    plot_anomaly_score_timeline,
    plot_sensor_anomaly_highlight,
    plot_anomaly_scatter_regimes,
    plot_anomaly_score_distribution,
    plot_top_abnormal_sensors,
)


def load_dataset_splits(subset: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load feature files or processed data files for the given subset.
    """
    feat_train = DATA_FEATURES_DIR / f"features_train_{subset}.csv"
    feat_test  = DATA_FEATURES_DIR / f"features_test_{subset}.csv"

    if feat_train.exists() and feat_test.exists():
        print(f"  [data] Loading feature data for {subset}...")
        train_df = pd.read_csv(feat_train)
        test_df  = pd.read_csv(feat_test)
    else:
        # Fallback to processed files
        proc_train = DATA_PROCESSED_DIR / f"processed_train_{subset}.csv"
        proc_test  = DATA_PROCESSED_DIR / f"processed_test_{subset}.csv"
        if proc_train.exists() and proc_test.exists():
            print(f"  [data] Loading processed data for {subset}...")
            train_df = pd.read_csv(proc_train)
            test_df  = pd.read_csv(proc_test)
        else:
            raise FileNotFoundError(
                f"Data files not found for {subset}. Please run Person 1 pipeline first:\n"
                f"python run_pipeline.py --dataset {subset}"
            )

    return train_df, test_df


def compute_engine_summary(
    scored_test_df: pd.DataFrame,
    test_df: pd.DataFrame,
    subset: str,
) -> pd.DataFrame:
    """
    Aggregate cycle-level anomaly detections into an engine-level fleet summary.
    """
    summary_records = []
    engine_ids = sorted(scored_test_df[ENGINE_ID_COL].unique())

    for eng in engine_ids:
        eng_scores = scored_test_df[scored_test_df[ENGINE_ID_COL] == eng].sort_values(CYCLE_COL)
        total_cycles = len(eng_scores)
        last_cycle = int(eng_scores[CYCLE_COL].iloc[-1])
        
        final_row = eng_scores.iloc[-1]
        final_score = float(final_row["anomaly_score"])
        final_label = str(final_row["anomaly_label"])
        final_sev = str(final_row["anomaly_severity"])

        anom_cycles = (eng_scores["anomaly_label"] == "Anomalous").sum()
        anom_ratio = round(float(anom_cycles / total_cycles * 100), 2) if total_cycles > 0 else 0.0

        anom_indices = eng_scores[eng_scores["anomaly_label"] == "Anomalous"][CYCLE_COL]
        first_anom = int(anom_indices.iloc[0]) if not anom_indices.empty else None

        # Determine most common top abnormal sensors for this engine
        top1_sensors = eng_scores[eng_scores["anomaly_label"] == "Anomalous"]["top_sensor_1"]
        if not top1_sensors.empty:
            top_degraded = top1_sensors.value_counts().head(2).index.tolist()
            top_degraded_str = ", ".join(top_degraded)
        else:
            top_degraded_str = "None (Nominal)"

        summary_records.append({
            ENGINE_ID_COL: eng,
            "last_observed_cycle": last_cycle,
            "final_anomaly_score": final_score,
            "final_anomaly_severity": final_sev,
            "final_anomaly_status": final_label,
            "total_cycles_observed": total_cycles,
            "total_anomalous_cycles": int(anom_cycles),
            "anomaly_cycle_ratio_pct": anom_ratio,
            "first_anomalous_cycle": first_anom if first_anom is not None else -1,
            "top_degraded_sensors": top_degraded_str,
        })

    return pd.DataFrame(summary_records)


def integrate_with_person2(
    engine_summary_df: pd.DataFrame,
    subset: str,
) -> Optional[pd.DataFrame]:
    """
    Merge Person 3 Anomaly detections with Person 2 RUL predictions.
    """
    # Check for XGBoost or Random Forest predictions
    pred_xgb_path = OUTPUTS_PREDICTIONS_DIR / f"predictions_{subset}_xgboost.csv"
    pred_rf_path  = OUTPUTS_PREDICTIONS_DIR / f"predictions_{subset}_random_forest.csv"

    pred_path = pred_xgb_path if pred_xgb_path.exists() else (pred_rf_path if pred_rf_path.exists() else None)
    if pred_path is None:
        print(f"  [integration] Person 2 predictions not found for {subset}. Skipping RUL merge.")
        return None

    print(f"  [integration] Merging with Person 2 RUL predictions from {pred_path.name}...")
    rul_df = pd.read_csv(pred_path)

    # Merge on engine_id
    merged_df = pd.merge(
        rul_df,
        engine_summary_df[[
            ENGINE_ID_COL,
            "final_anomaly_score",
            "final_anomaly_severity",
            "final_anomaly_status",
            "anomaly_cycle_ratio_pct",
            "top_degraded_sensors",
        ]],
        on=ENGINE_ID_COL,
        how="left",
    )

    # Generate composite maintenance recommendation
    recommendations = []
    for _, row in merged_df.iterrows():
        rul = float(row.get("predicted_RUL", 100))
        anom_score = float(row.get("final_anomaly_score", 0))

        if rul <= 25 or anom_score >= 80:
            rec = "CRITICAL: Immediate Maintenance & Grounding Required"
        elif rul <= 50 or anom_score >= 65:
            rec = "URGENT: Schedule Inspection & Maintenance"
        elif rul <= 80 or anom_score >= 45:
            rec = "MONITOR: Heightened Telemetry & Vibration Monitoring"
        else:
            rec = "OPERATIONAL: Normal Operating Parameters"
        recommendations.append(rec)

    merged_df["recommended_action"] = recommendations

    # Save integrated health assessment
    integrated_csv = OUTPUTS_PREDICTIONS_DIR / f"integrated_engine_health_{subset}.csv"
    merged_df.to_csv(integrated_csv, index=False)
    print(f"  [integration] Saved integrated engine health -> {integrated_csv.name}")

    return merged_df


def generate_anomaly_report(
    subset: str,
    detector: AnomalyDetector,
    scored_test_df: pd.DataFrame,
    engine_summary_df: pd.DataFrame,
    sensor_ranking_df: pd.DataFrame,
    elapsed_time: float,
) -> Dict[str, Any]:
    """
    Generate comprehensive evaluation report for Anomaly Detection.
    """
    OUTPUTS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    total_engines = int(len(engine_summary_df))
    total_cycles = int(len(scored_test_df))
    anom_cycles = int((scored_test_df["anomaly_label"] == "Anomalous").sum())
    anom_pct = round(float(anom_cycles / total_cycles * 100), 2) if total_cycles > 0 else 0.0

    engines_with_anomalies = int((engine_summary_df["total_anomalous_cycles"] > 0).sum())
    engines_with_anomalies_pct = round(float(engines_with_anomalies / total_engines * 100), 2) if total_engines > 0 else 0.0

    sev_counts = scored_test_df["anomaly_severity"].value_counts().to_dict()

    top_sensors_list = (
        sensor_ranking_df.head(5)[["sensor", "top_1_frequency_pct", "top_1_abnormal_count"]].to_dict(orient="records")
        if not sensor_ranking_df.empty else []
    )

    report_data = {
        "dataset": subset,
        "model": "Isolation Forest",
        "contamination": detector.contamination,
        "n_estimators": detector.n_estimators,
        "anomaly_score_threshold": detector.score_threshold,
        "total_test_engines": total_engines,
        "total_test_cycles": total_cycles,
        "anomalous_cycles_count": anom_cycles,
        "anomalous_cycles_pct": anom_pct,
        "engines_exhibiting_anomalies_count": engines_with_anomalies,
        "engines_exhibiting_anomalies_pct": engines_with_anomalies_pct,
        "mean_anomaly_score_fleet": round(float(scored_test_df["anomaly_score"].mean()), 2),
        "mean_anomaly_score_last_cycle": round(float(engine_summary_df["final_anomaly_score"].mean()), 2),
        "severity_distribution": {k: int(v) for k, v in sev_counts.items()},
        "top_contributing_sensors": top_sensors_list,
        "execution_time_seconds": round(elapsed_time, 2),
        "notes": (
            "C-MAPSS is a run-to-failure simulation dataset without explicit binary ground-truth anomaly tags. "
            "Anomaly detection is evaluated via baseline deviation, progressive degradation tracking, and "
            "correlation with physical degradation markers."
        ),
    }

    # Save JSON report
    json_path = OUTPUTS_REPORTS_DIR / f"anomaly_report_{subset}.json"
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)

    # Save Human-readable TXT report
    txt_path = OUTPUTS_REPORTS_DIR / f"anomaly_report_{subset}.txt"
    lines = [
        "=" * 60,
        f"  ANOMALY & FAULT DETECTION REPORT – {subset}",
        "=" * 60,
        "",
        f"Dataset:                  {subset}",
        f"Algorithm:                Isolation Forest (Unsupervised)",
        f"Contamination Rate:       {detector.contamination}",
        f"Number of Estimators:     {detector.n_estimators}",
        f"Anomaly Score Threshold:  {detector.score_threshold} (0-100 Scale)",
        "",
        "--- Fleet-Level Anomaly Statistics ---",
        f"Total Test Engines:       {total_engines}",
        f"Total Operational Cycles: {total_cycles:,}",
        f"Anomalous Cycles Flagged: {anom_cycles:,} ({anom_pct}%)",
        f"Engines with Anomalies:   {engines_with_anomalies} / {total_engines} ({engines_with_anomalies_pct}%)",
        f"Mean Fleet Anomaly Score: {report_data['mean_anomaly_score_fleet']}",
        f"Mean Final-Cycle Score:   {report_data['mean_anomaly_score_last_cycle']}",
        "",
        "--- Severity Breakdown (All Cycles) ---",
    ]
    for sev, cnt in sev_counts.items():
        lines.append(f"  {sev:<20s}: {cnt:>6,} cycles ({cnt/total_cycles*100:.1f}%)")

    lines.extend([
        "",
        "--- Top Contributing Abnormal Sensors ---",
    ])
    for item in top_sensors_list:
        lines.append(f"  {item['sensor']:<12s}: Leading contributor in {item['top_1_frequency_pct']:.1f}% of anomalous cycles ({item['top_1_abnormal_count']} cycles)")

    lines.extend([
        "",
        "--- Evaluation & Ground Truth Note ---",
        report_data["notes"],
        "",
        "=" * 60,
    ])

    with open(txt_path, "w") as f:
        f.write("\n".join(lines))

    print(f"  [report] Saved anomaly report -> {json_path.name} + {txt_path.name}")
    return report_data


def run_anomaly_pipeline(
    subset: str,
    contamination: float = ISOLATION_FOREST_PARAMS["contamination"],
    n_estimators: int = ISOLATION_FOREST_PARAMS["n_estimators"],
) -> Dict[str, Any]:
    """
    Execute full anomaly detection pipeline for a given C-MAPSS subset.
    """
    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"  ANOMALY DETECTION PIPELINE START: {subset}")
    print(f"{'='*60}")

    # 1. Load Data
    train_df, test_df = load_dataset_splits(subset)

    # 2. Fit Anomaly Detector
    detector = AnomalyDetector(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=42,
    )
    detector.fit(train_df, subset=subset, healthy_baseline_only=True)

    # 3. Save Model
    MODELS_ANOMALY_DIR.mkdir(parents=True, exist_ok=True)
    model_save_path = MODELS_ANOMALY_DIR / f"isolation_forest_{subset}.joblib"
    detector.save(model_save_path)

    # 4. Score and Explain Test Set
    print(f"  [anomaly] Scoring test telemetry and computing sensor deviations...")
    scored_test_df = detector.score_and_explain(test_df, top_n=3)

    OUTPUTS_PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    anom_pred_csv = OUTPUTS_PREDICTIONS_DIR / f"anomaly_predictions_{subset}.csv"
    scored_test_df.to_csv(anom_pred_csv, index=False)
    print(f"  [export] Saved cycle-level anomaly predictions -> {anom_pred_csv.name}")

    # 5. Compute Engine Fleet Summary
    engine_summary_df = compute_engine_summary(scored_test_df, test_df, subset)
    anom_summary_csv = OUTPUTS_PREDICTIONS_DIR / f"anomaly_summary_{subset}.csv"
    engine_summary_df.to_csv(anom_summary_csv, index=False)
    print(f"  [export] Saved engine-level anomaly summary -> {anom_summary_csv.name}")

    # 6. Sensor Abnormality Ranking
    sensor_ranking_df = detector.get_fleet_sensor_abnormality_summary(scored_test_df)

    # 7. Integrate with Person 2 RUL Predictions
    integrated_df = integrate_with_person2(engine_summary_df, subset)

    # 8. Generate Visualizations
    print(f"  [visuals] Generating anomaly detection plots...")
    plot_anomaly_score_timeline(scored_test_df, subset)
    plot_sensor_anomaly_highlight(test_df, scored_test_df, subset)
    plot_anomaly_scatter_regimes(test_df, scored_test_df, subset)
    plot_anomaly_score_distribution(scored_test_df, subset)
    plot_top_abnormal_sensors(sensor_ranking_df, subset)

    # 9. Generate Report
    elapsed = time.time() - t0
    report = generate_anomaly_report(
        subset=subset,
        detector=detector,
        scored_test_df=scored_test_df,
        engine_summary_df=engine_summary_df,
        sensor_ranking_df=sensor_ranking_df,
        elapsed_time=elapsed,
    )

    print(f"\n--- Anomaly Performance Summary: {subset} ---")
    print(f"  Anomalous Cycles   : {report['anomalous_cycles_count']:,} / {report['total_test_cycles']:,} ({report['anomalous_cycles_pct']}%)")
    print(f"  Engines with Anom  : {report['engines_exhibiting_anomalies_count']} / {report['total_test_engines']} ({report['engines_exhibiting_anomalies_pct']}%)")
    print(f"  Mean Fleet Score   : {report['mean_anomaly_score_fleet']}")
    print(f"  Mean Final Score   : {report['mean_anomaly_score_last_cycle']}")
    if not sensor_ranking_df.empty:
        top1 = sensor_ranking_df.iloc[0]
        print(f"  Leading Sensor     : {top1['sensor']} ({top1['top_1_frequency_pct']}% of anomalies)")
    print(f"{'='*60}\n")

    return {
        "subset": subset,
        "report": report,
        "detector": detector,
        "scored_test_df": scored_test_df,
        "engine_summary_df": engine_summary_df,
        "integrated_df": integrated_df,
    }
