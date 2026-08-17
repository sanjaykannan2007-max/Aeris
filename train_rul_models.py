"""
train_rul_models.py
===================
CLI entry point for Person 2: RUL & Engine Health Prediction Training & Evaluation.

Usage
-----
    # Train both Random Forest & XGBoost on FD001
    python train_rul_models.py --dataset FD001 --model both

    # Train XGBoost on all datasets
    python train_rul_models.py --dataset all --model xgboost
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Any, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import seaborn as sns
except ImportError:
    sns = None

# Ensure src/ is importable
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    VALID_SUBSETS,
    MAX_RUL,
    WINDOW_SIZE,
    SCALER_TYPE,
    DATA_FEATURES_DIR,
    MODELS_RUL_DIR,
    OUTPUTS_PREDICTIONS_DIR,
    OUTPUTS_PLOTS_DIR,
    OUTPUTS_REPORTS_DIR,
    ENGINE_ID_COL,
    CYCLE_COL,
    RUL_COL,
    RUL_CAPPED_COL,
    PLOT_DPI,
    HEALTH_STAGES,
)
from src.dataset_pipeline import run_pipeline
from src.rul_predictor import RULPredictor, evaluate_predictions
from src.health_score import add_health_scores_to_dataframe, calculate_health_score, categorize_health_stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NASA C-MAPSS RUL & Engine Health Prediction Training Pipeline (Person 2)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset", "-d",
        type=str,
        default="FD001",
        help="Dataset to process: FD001, FD002, FD003, FD004, or 'all'",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="both",
        choices=["random_forest", "xgboost", "both"],
        help="Model algorithm to train: 'random_forest', 'xgboost', or 'both'",
    )
    parser.add_argument(
        "--max_rul",
        type=int,
        default=MAX_RUL,
        help="RUL cap value for piecewise linear target.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=WINDOW_SIZE,
        help="Rolling window size for feature engineering if pipeline is re-run.",
    )
    return parser.parse_args()


def load_or_generate_features(subset: str, max_rul: int, window_size: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load feature CSVs or trigger Person 1 pipeline if missing."""
    train_feat_path = DATA_FEATURES_DIR / f"features_{subset}_train.csv"
    test_feat_path  = DATA_FEATURES_DIR / f"features_{subset}_test.csv"

    if train_feat_path.exists() and test_feat_path.exists():
        print(f"  [data] Loading existing feature files for {subset}...")
        train_df = pd.read_csv(train_feat_path)
        test_df  = pd.read_csv(test_feat_path)
    else:
        print(f"  [data] Feature files not found. Running Person 1 data pipeline for {subset}...")
        results = run_pipeline(subset, max_rul=max_rul, window_size=window_size)
        train_df = results["train_features"]
        test_df  = results["test_features"]

    return train_df, test_df


def plot_parity(engine_last_df: pd.DataFrame, subset: str, model_type: str, metrics: dict):
    """Generate Parity Plot (True RUL vs Predicted RUL)."""
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=PLOT_DPI)

    true_rul = engine_last_df["true_RUL"]
    pred_rul = engine_last_df["predicted_RUL"]

    ax.scatter(true_rul, pred_rul, alpha=0.7, color="#2b5c8f", edgecolors="k", linewidth=0.5, label="Test Engines")
    
    max_val = max(true_rul.max(), pred_rul.max()) + 10
    ax.plot([0, max_val], [0, max_val], "r--", linewidth=2, label="Ideal 1:1 Line")

    ax.set_title(f"RUL Prediction Parity Plot – {subset} ({model_type.upper()})\nMAE={metrics['MAE']}, RMSE={metrics['RMSE']}, NASA Score={metrics['NASA_Score']}", fontsize=12, fontweight="bold")
    ax.set_xlabel("True RUL (cycles)", fontsize=10)
    ax.set_ylabel("Predicted RUL (cycles)", fontsize=10)
    ax.set_xlim(0, max_val)
    ax.set_ylim(0, max_val)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"rul_parity_{subset}_{model_type}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved parity plot -> {save_path.name}")


def plot_sample_timelines(test_df: pd.DataFrame, predictor: RULPredictor, subset: str, model_type: str, sample_engines: list[int] = [1, 5, 10, 20]):
    """Plot Ground Truth RUL vs Predicted RUL over cycles for sample engines."""
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    available_engines = sorted(test_df[ENGINE_ID_COL].unique())
    selected_engines = [e for e in sample_engines if e in available_engines]
    
    if not selected_engines:
        selected_engines = available_engines[:4]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=PLOT_DPI)
    axes = axes.flatten()

    for idx, eng in enumerate(selected_engines[:4]):
        ax = axes[idx]
        eng_df = test_df[test_df[ENGINE_ID_COL] == eng].sort_values(CYCLE_COL)
        
        preds = predictor.predict(eng_df)
        cycles = eng_df[CYCLE_COL].values
        true_rul = eng_df[RUL_CAPPED_COL].values if RUL_CAPPED_COL in eng_df.columns else eng_df[RUL_COL].values

        ax.plot(cycles, true_rul, "k--", label="True RUL", linewidth=2)
        ax.plot(cycles, preds, "#d95f02", label=f"Predicted ({model_type.upper()})", linewidth=2)

        ax.set_title(f"Engine #{eng} Degradation Trajectory", fontsize=11, fontweight="bold")
        ax.set_xlabel("Operational Cycle", fontsize=9)
        ax.set_ylabel("RUL (cycles)", fontsize=9)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper right")

    plt.suptitle(f"Sample Engine RUL Predictions – {subset} ({model_type.upper()})", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    save_path = OUTPUTS_PLOTS_DIR / f"rul_timeline_{subset}_{model_type}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved timeline plot -> {save_path.name}")


def plot_feature_importances(df_imp: pd.DataFrame, subset: str, model_type: str, top_n: int = 15):
    """Plot top N feature importances."""
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    if df_imp.empty:
        return

    top_df = df_imp.head(top_n).sort_values("importance", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=PLOT_DPI)
    ax.barh(top_df["feature"], top_df["importance"], color="#7570b3")
    ax.set_title(f"Top {top_n} Feature Importances – {subset} ({model_type.upper()})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Importance Score", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6, axis="x")

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"feature_importance_{subset}_{model_type}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved feature importance plot -> {save_path.name}")


def plot_health_distribution(engine_last_df: pd.DataFrame, subset: str, model_type: str):
    """Plot distribution of engine health stages."""
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=PLOT_DPI)

    status_counts = engine_last_df["health_status"].value_counts()
    categories = [HEALTH_STAGES[k]["label"] for k in HEALTH_STAGES]
    counts = [status_counts.get(cat, 0) for cat in categories]
    colors = [HEALTH_STAGES[k]["color"] for k in HEALTH_STAGES]

    bars = ax.bar(categories, counts, color=colors, edgecolor="black", alpha=0.8)
    
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.annotate(f"{height}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  
                        textcoords="offset points",
                        ha="center", va="bottom", fontweight="bold")

    ax.set_title(f"Engine Fleet Health Status Distribution – {subset} ({model_type.upper()})\nTotal Test Engines = {len(engine_last_df)}", fontsize=12, fontweight="bold")
    ax.set_ylabel("Number of Engines", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"health_distribution_{subset}_{model_type}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved health distribution plot -> {save_path.name}")


def run_person2_pipeline(subset: str, model_type: str, max_rul: int, window_size: int) -> dict:
    """Run Person 2 training, evaluation, and export pipeline for one subset & model."""
    print(f"\n{'='*60}")
    print(f"  PERSON 2 PIPELINE START: {subset} | Model: {model_type.upper()}")
    print(f"{'='*60}")

    # 1. Load feature data
    train_df, test_df = load_or_generate_features(subset, max_rul, window_size)

    # 2. Train model
    predictor = RULPredictor(model_type=model_type)
    predictor.fit(train_df)

    # 3. Save model
    model_filename = f"model_{subset}_{model_type}.joblib"
    model_path = MODELS_RUL_DIR / model_filename
    predictor.save(model_path)

    # 4. Evaluate predictions
    cycle_metrics, last_cycle_metrics, engine_last_df = predictor.evaluate(test_df)

    # 5. Add Health Score and Health Stage
    engine_last_df = add_health_scores_to_dataframe(
        engine_last_df,
        rul_col="predicted_RUL",
        baseline_max_rul=max_rul,
    )
    engine_last_df["absolute_error"] = np.round(np.abs(engine_last_df["predicted_RUL"] - engine_last_df["true_RUL"]), 2)

    # Rearrange columns for clarity
    cols = [ENGINE_ID_COL, CYCLE_COL, "true_RUL", "predicted_RUL", "absolute_error", "health_score", "health_status"]
    engine_last_df = engine_last_df[cols].rename(columns={CYCLE_COL: "last_observed_cycle"})

    # 6. Save Predictions (CSV & JSON)
    OUTPUTS_PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    csv_pred_path  = OUTPUTS_PREDICTIONS_DIR / f"predictions_{subset}_{model_type}.csv"
    json_pred_path = OUTPUTS_PREDICTIONS_DIR / f"predictions_{subset}_{model_type}.json"

    engine_last_df.to_csv(csv_pred_path, index=False)
    
    pred_summary = {
        "subset": subset,
        "model_type": model_type,
        "evaluation_last_cycle": last_cycle_metrics,
        "evaluation_all_cycles": cycle_metrics,
        "predictions": engine_last_df.to_dict(orient="records"),
    }
    with open(json_pred_path, "w") as f:
        json.dump(pred_summary, f, indent=2)

    print(f"  [export] Saved engine predictions -> {csv_pred_path.name} & {json_pred_path.name}")

    # 7. Feature Importances
    df_imp = predictor.get_feature_importances()

    # 8. Generate Visualizations
    plot_parity(engine_last_df, subset, model_type, last_cycle_metrics)
    plot_sample_timelines(test_df, predictor, subset, model_type)
    plot_feature_importances(df_imp, subset, model_type)
    plot_health_distribution(engine_last_df, subset, model_type)

    # Summary Output
    print(f"\n--- Performance Summary: {subset} ({model_type.upper()}) ---")
    print(f"  Final-Cycle MAE       : {last_cycle_metrics['MAE']}")
    print(f"  Final-Cycle RMSE      : {last_cycle_metrics['RMSE']}")
    print(f"  Final-Cycle R²        : {last_cycle_metrics['R2']}")
    print(f"  NASA Asymmetric Score : {last_cycle_metrics['NASA_Score']}")

    return {
        "subset": subset,
        "model_type": model_type,
        "last_cycle_metrics": last_cycle_metrics,
        "cycle_metrics": cycle_metrics,
        "model_path": str(model_path),
        "predictions_path": str(csv_pred_path),
        "top_features": df_imp.head(10).to_dict(orient="records") if not df_imp.empty else [],
    }


def main():
    args = parse_args()

    if args.dataset.lower() == "all":
        subsets = VALID_SUBSETS
    else:
        subset = args.dataset.upper()
        if subset not in VALID_SUBSETS:
            print(f"ERROR: Unknown dataset '{args.dataset}'. Choose from {VALID_SUBSETS} or 'all'.")
            sys.exit(1)
        subsets = [subset]

    models_to_train = ["random_forest", "xgboost"] if args.model == "both" else [args.model]

    print("\n" + "=" * 65)
    print("  PERSON 2 – RUL & ENGINE HEALTH PREDICTION PIPELINE")
    print(f"  Datasets : {subsets}")
    print(f"  Models   : {models_to_train}")
    print(f"  MAX_RUL  : {args.max_rul}")
    print("=" * 65 + "\n")

    t_start = time.time()
    all_summary_results = []

    for subset in subsets:
        for model_type in models_to_train:
            try:
                res = run_person2_pipeline(subset, model_type, args.max_rul, args.window)
                all_summary_results.append(res)
            except Exception:
                print(f"\n[ERROR] Training failed for {subset} ({model_type}):")
                traceback.print_exc()

    # Save summary report
    OUTPUTS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_json_path = OUTPUTS_REPORTS_DIR / "rul_model_evaluation.json"
    with open(report_json_path, "w") as f:
        json.dump(all_summary_results, f, indent=2)

    elapsed = time.time() - t_start
    print("\n" + "=" * 65)
    print("  SUMMARY OF ALL TRAINED MODELS")
    print("=" * 65)
    print(f"  {'Dataset':<10} {'Model':<16} {'MAE':>8} {'RMSE':>8} {'R²':>8} {'NASA Score':>12}")
    print(f"  {'-'*10} {'-'*16} {'-'*8} {'-'*8} {'-'*8} {'-'*12}")

    for res in all_summary_results:
        m = res["last_cycle_metrics"]
        print(f"  {res['subset']:<10} {res['model_type']:<16} {m['MAE']:>8.2f} {m['RMSE']:>8.2f} {m['R2']:>8.3f} {m['NASA_Score']:>12.1f}")

    print(f"\n  Total time elapsed: {elapsed:.1f}s")
    print(f"  Evaluation summary saved -> {report_json_path.name}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
