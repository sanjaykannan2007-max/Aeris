"""
anomaly_plots.py
================
Publication-quality visualization generation for Anomaly & Fault Detection (Person 3).

Visualizations
--------------
1. Anomaly Score Timeline: Trajectory of anomaly score across cycles for sample engines.
2. Sensor Telemetry with Anomaly Highlighting: Multi-sensor curves with shaded anomaly zones.
3. 2D Operational Regime Scatter: Normal vs Anomalous states in sensor space / PCA.
4. Anomaly Score Distribution: Fleet-wide distribution with severity threshold markers.
5. Top Abnormal Sensors Ranking: Bar chart ranking sensor contribution frequencies.

All plots are saved to `outputs/plots/` at 300 DPI.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless/multi-threaded execution
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    OUTPUTS_PLOTS_DIR,
    PLOT_DPI,
    ANOMALY_SCORE_THRESHOLD,
    ANOMALY_STAGES,
)


def _apply_plot_style():
    """Apply consistent aesthetics for all anomaly plots."""
    try:
        plt.style.use("seaborn-v0_8-darkgrid")
    except Exception:
        plt.style.use("default")
        plt.rcParams["axes.grid"] = True
        plt.rcParams["grid.alpha"] = 0.6
        plt.rcParams["grid.linestyle"] = ":"


def plot_anomaly_score_timeline(
    scored_df: pd.DataFrame,
    subset: str,
    sample_engines: List[int] = [1, 5, 10, 20],
) -> Path:
    """
    Generate 2x2 grid of Anomaly Score (0-100) vs Engine Cycle for sample engines.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    available_engines = sorted(scored_df[ENGINE_ID_COL].unique())
    selected_engines = [e for e in sample_engines if e in available_engines]
    if not selected_engines:
        selected_engines = available_engines[:4]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=PLOT_DPI)
    axes = axes.flatten()

    for idx, eng in enumerate(selected_engines[:4]):
        ax = axes[idx]
        eng_df = scored_df[scored_df[ENGINE_ID_COL] == eng].sort_values(CYCLE_COL)

        cycles = eng_df[CYCLE_COL].values
        scores = eng_df["anomaly_score"].values
        labels = eng_df["anomaly_label"].values

        # Plot base line
        ax.plot(cycles, scores, color="#2b5c8f", linewidth=2.2, label="Anomaly Score (0–100)")
        
        # Highlight anomalous points
        anom_mask = labels == "Anomalous"
        if anom_mask.any():
            ax.scatter(
                cycles[anom_mask],
                scores[anom_mask],
                color="#d62728",
                s=35,
                zorder=5,
                label="Anomalous Cycle",
                edgecolors="black",
                linewidth=0.5,
            )

        # Threshold and stages
        ax.axhline(
            y=ANOMALY_SCORE_THRESHOLD,
            color="#d62728",
            linestyle="--",
            linewidth=1.5,
            label=f"Anomaly Threshold ({ANOMALY_SCORE_THRESHOLD:.0f})",
        )
        ax.axhspan(0, 45, color="#2ca02c", alpha=0.08, label="Nominal Zone" if idx == 0 else "")
        ax.axhspan(45, 65, color="#ff7f0e", alpha=0.08, label="Drift / Monitor" if idx == 0 else "")
        ax.axhspan(65, 100, color="#d62728", alpha=0.08, label="Critical Anomaly" if idx == 0 else "")

        ax.set_title(f"Engine #{eng} Anomaly Score Trajectory", fontsize=11, fontweight="bold")
        ax.set_xlabel("Operational Cycle", fontsize=10)
        ax.set_ylabel("Anomaly Score (0–100)", fontsize=10)
        ax.set_ylim(0, 105)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper left", fontsize=8)

    plt.suptitle(
        f"Isolation Forest Anomaly Progression – {subset}\n(Tracking Degradation from Healthy Baseline to Anomaly Onset)",
        fontsize=13,
        fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    save_path = OUTPUTS_PLOTS_DIR / f"anomaly_score_timeline_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved anomaly timeline plot -> {save_path.name}")
    return save_path


def plot_sensor_anomaly_highlight(
    features_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    subset: str,
    engine_id: int = 1,
    key_sensors: Optional[List[str]] = None,
) -> Path:
    """
    Plot multi-sensor telemetry for a specific engine with shaded anomalous regions.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    available_engines = sorted(features_df[ENGINE_ID_COL].unique())
    if engine_id not in available_engines:
        engine_id = available_engines[0]

    eng_feat = features_df[features_df[ENGINE_ID_COL] == engine_id].sort_values(CYCLE_COL)
    eng_score = scored_df[scored_df[ENGINE_ID_COL] == engine_id].sort_values(CYCLE_COL)

    # Select representative sensors
    if key_sensors is None:
        candidate_sensors = ["sensor_4", "sensor_11", "sensor_8", "sensor_9", "sensor_2", "sensor_15"]
        key_sensors = [s for s in candidate_sensors if s in eng_feat.columns][:4]

    fig, axes = plt.subplots(len(key_sensors), 1, figsize=(13, 3 * len(key_sensors)), dpi=PLOT_DPI, sharex=True)
    if len(key_sensors) == 1:
        axes = [axes]

    cycles = eng_feat[CYCLE_COL].values
    anom_labels = eng_score["anomaly_label"].values

    # Identify continuous anomalous cycle intervals for shaded spans
    anom_indices = np.where(anom_labels == "Anomalous")[0]

    sensor_descriptions = {
        "sensor_2": "LPC Outlet Temp (T24)",
        "sensor_3": "HPC Outlet Temp (T30)",
        "sensor_4": "LPT Outlet Temp (T48)",
        "sensor_7": "HPC Outlet Pressure (P30)",
        "sensor_8": "Physical Fan Speed (Nf)",
        "sensor_9": "Physical Core Speed (Nc)",
        "sensor_11": "HPT Outlet Temp (T50)",
        "sensor_12": "Fan Inlet Static Pressure (Ps30)",
        "sensor_15": "Bypass Ratio",
    }

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"]

    for idx, s in enumerate(key_sensors):
        ax = axes[idx]
        values = eng_feat[s].values
        desc = sensor_descriptions.get(s, s)

        ax.plot(cycles, values, color=colors[idx % len(colors)], linewidth=2.0, label=f"{s} ({desc})")

        # Shade anomalous cycles
        for anom_idx in anom_indices:
            c = cycles[anom_idx]
            ax.axvspan(c - 0.5, c + 0.5, color="#d62728", alpha=0.25, lw=0)

        # Dummy span for legend
        ax.axvspan(np.nan, np.nan, color="#d62728", alpha=0.25, label="Detected Anomaly Region")

        ax.set_ylabel(f"{s}\n(Normalised)", fontsize=9, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper left", fontsize=9)

    axes[-1].set_xlabel("Operational Cycle", fontsize=10, fontweight="bold")
    plt.suptitle(
        f"Engine #{engine_id} Sensor Telemetry & Anomaly Regions – {subset}\n(Red bands indicate cycles flagged as abnormal by Isolation Forest)",
        fontsize=12,
        fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    save_path = OUTPUTS_PLOTS_DIR / f"anomaly_sensor_highlight_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved sensor anomaly highlight plot -> {save_path.name}")
    return save_path


def plot_anomaly_scatter_regimes(
    features_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    subset: str,
) -> Path:
    """
    Plot 2D Scatter of engine operational space (PCA components) showing Normal vs Anomalous points.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    ignore_cols = {ENGINE_ID_COL, CYCLE_COL, "RUL", "RUL_capped"}
    feat_cols = [c for c in features_df.columns if c not in ignore_cols and pd.api.types.is_numeric_dtype(features_df[c])]

    X = features_df[feat_cols].fillna(0)
    
    # Use PCA to project multi-sensor space into 2 principal dimensions
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X)
    var_exp = pca.explained_variance_ratio_ * 100.0

    labels = scored_df["anomaly_label"].values
    normal_mask = labels == "Normal"
    anom_mask = labels == "Anomalous"

    fig, ax = plt.subplots(figsize=(9, 7), dpi=PLOT_DPI)

    # Plot normal points
    ax.scatter(
        X_pca[normal_mask, 0],
        X_pca[normal_mask, 1],
        color="#2b5c8f",
        alpha=0.45,
        s=20,
        label="Nominal Operations (Inliers)",
        edgecolors="none",
    )

    # Plot anomalous points
    ax.scatter(
        X_pca[anom_mask, 0],
        X_pca[anom_mask, 1],
        color="#d62728",
        alpha=0.85,
        s=35,
        marker="^",
        label="Detected Anomalies (Outliers)",
        edgecolors="black",
        linewidth=0.5,
    )

    ax.set_title(
        f"Operational Envelope & Anomaly Boundaries – {subset} (PCA Projection)\nNormal vs Abnormal State Separation",
        fontsize=12,
        fontweight="bold",
    )
    ax.set_xlabel(f"Principal Component 1 ({var_exp[0]:.1f}% Variance)", fontsize=10)
    ax.set_ylabel(f"Principal Component 2 ({var_exp[1]:.1f}% Variance)", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=10)

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"anomaly_scatter_regimes_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved anomaly scatter regime plot -> {save_path.name}")
    return save_path


def plot_anomaly_score_distribution(
    scored_df: pd.DataFrame,
    subset: str,
) -> Path:
    """
    Plot fleet-wide distribution of normalized anomaly scores with stage cutoffs.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    scores = scored_df["anomaly_score"].values
    anom_pct = float((scored_df["anomaly_label"] == "Anomalous").mean() * 100)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=PLOT_DPI)

    # Histogram
    n, bins, patches = ax.hist(
        scores,
        bins=50,
        density=True,
        color="#2b5c8f",
        alpha=0.65,
        edgecolor="black",
        linewidth=0.5,
    )

    # Color code histogram bars based on anomaly stages
    for bin_left, bin_right, patch in zip(bins[:-1], bins[1:], patches):
        bin_center = (bin_left + bin_right) / 2.0
        if bin_center >= ANOMALY_STAGES["SEVERE"]["min_score"]:
            patch.set_facecolor("#7f0000")
        elif bin_center >= ANOMALY_STAGES["MODERATE"]["min_score"]:
            patch.set_facecolor("#d62728")
        elif bin_center >= ANOMALY_STAGES["MILD"]["min_score"]:
            patch.set_facecolor("#ff7f0e")
        else:
            patch.set_facecolor("#2ca02c")

    # Threshold indicator
    ax.axvline(
        x=ANOMALY_SCORE_THRESHOLD,
        color="black",
        linestyle="--",
        linewidth=2.0,
        label=f"Anomaly Threshold ({ANOMALY_SCORE_THRESHOLD:.0f})",
    )

    ax.set_title(
        f"Fleet Anomaly Score Distribution – {subset}\nTotal Cycles = {len(scored_df):,} | Anomalous Cycles = {anom_pct:.1f}%",
        fontsize=12,
        fontweight="bold",
    )
    ax.set_xlabel("Calibrated Anomaly Score (0 = Nominal, 100 = Critical)", fontsize=10)
    ax.set_ylabel("Probability Density", fontsize=10)
    ax.set_xlim(0, 100)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=10)

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"anomaly_score_distribution_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved anomaly score distribution plot -> {save_path.name}")
    return save_path


def plot_top_abnormal_sensors(
    sensor_summary_df: pd.DataFrame,
    subset: str,
    top_n: int = 10,
) -> Path:
    """
    Horizontal bar chart ranking sensors that most frequently trigger anomalies.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    if sensor_summary_df.empty:
        return OUTPUTS_PLOTS_DIR / f"anomaly_top_sensors_{subset}.png"

    top_df = sensor_summary_df.head(top_n).sort_values("top_1_frequency_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=PLOT_DPI)
    bars = ax.barh(top_df["sensor"], top_df["top_1_frequency_pct"], color="#d95f02", edgecolor="black", alpha=0.85)

    # Annotate bars with exact percentages
    for bar in bars:
        width = bar.get_width()
        ax.annotate(
            f"{width:.1f}%",
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(4, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontweight="bold",
            fontsize=9,
        )

    ax.set_title(
        f"Top Contributing Abnormal Sensors – {subset}\n(Frequency of Being Ranked #1 Leading Deviation During Anomalous Cycles)",
        fontsize=12,
        fontweight="bold",
    )
    ax.set_xlabel("Contribution Frequency as Leading Abnormal Sensor (%)", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6, axis="x")

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"anomaly_top_sensors_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved top abnormal sensors plot -> {save_path.name}")
    return save_path
