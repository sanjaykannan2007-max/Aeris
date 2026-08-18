"""
integration_plots.py
====================
Publication-quality integration visualizations for Person 4 (300 DPI).

Visualizations
--------------
1. RUL vs Engine Cycle: Trajectory of predicted RUL vs true RUL with health boundary shading.
2. Anomaly Score vs Engine Cycle: Fleet telemetry anomaly progression alongside RUL.
3. Engine Health Status Distribution: Categorical breakdown of fleet health stages.
4. Maintenance Category Distribution: Counts and percentages of engines in each action category.
5. 2D RUL vs Anomaly Score Risk Quadrants: Scatter plot illustrating the 4-quadrant decision matrix.

All plots saved to `outputs/plots/` at 300 DPI.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server-side rendering
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    OUTPUTS_PLOTS_DIR,
    PLOT_DPI,
    MAX_RUL,
    MAINTENANCE_DECISION_THRESHOLDS,
)


def _apply_plot_style():
    """Apply consistent aesthetics for all integration plots."""
    try:
        plt.style.use("seaborn-v0_8-darkgrid")
    except Exception:
        plt.style.use("default")
        plt.rcParams["axes.grid"] = True
        plt.rcParams["grid.alpha"] = 0.6
        plt.rcParams["grid.linestyle"] = ":"


def plot_integrated_rul_timeline(
    cycle_df: pd.DataFrame,
    subset: str,
    sample_engines: List[int] = [1, 5, 10, 20],
) -> Path:
    """
    Plot Predicted RUL and Anomaly Score over cycles for sample engines.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    available_engines = sorted(cycle_df[ENGINE_ID_COL].unique())
    selected_engines = [e for e in sample_engines if e in available_engines]
    if not selected_engines:
        selected_engines = available_engines[:4]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=PLOT_DPI)
    axes = axes.flatten()

    for idx, eng in enumerate(selected_engines[:4]):
        ax1 = axes[idx]
        ax2 = ax1.twinx()  # Secondary axis for anomaly score

        eng_df = cycle_df[cycle_df[ENGINE_ID_COL] == eng].sort_values(CYCLE_COL)
        cycles = eng_df[CYCLE_COL].values
        rul_preds = eng_df["predicted_RUL"].values
        anom_scores = eng_df["anomaly_score"].values

        # Plot RUL on primary axis
        p1 = ax1.plot(cycles, rul_preds, color="#1f77b4", linewidth=2.2, label="Predicted RUL (cycles)")
        if "true_RUL" in eng_df.columns:
            ax1.plot(cycles, eng_df["true_RUL"].values, "k--", linewidth=1.5, alpha=0.7, label="True RUL")

        # Plot Anomaly Score on secondary axis
        p2 = ax2.plot(cycles, anom_scores, color="#d62728", linewidth=2.0, linestyle="-.", label="Anomaly Score (0–100)")

        # Thresholds
        ax1.axhline(y=20.0, color="#d62728", linestyle=":", alpha=0.6, label="Critical RUL (20 cycles)")
        ax1.axhline(y=45.0, color="#ff7f0e", linestyle=":", alpha=0.6, label="Maintenance RUL (45 cycles)")

        ax1.set_title(f"Engine #{eng} Integrated Lifecycle Trajectory", fontsize=11, fontweight="bold")
        ax1.set_xlabel("Operational Cycle", fontsize=9)
        ax1.set_ylabel("Remaining Useful Life (cycles)", fontsize=9, color="#1f77b4")
        ax2.set_ylabel("Anomaly Score (0–100)", fontsize=9, color="#d62728")
        ax1.set_ylim(0, max(140, float(np.max(rul_preds)) + 10))
        ax2.set_ylim(0, 105)

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8)

    plt.suptitle(
        f"Dual-Signal Lifecycle Monitoring – {subset}\n(Synchronized RUL Degradation & Anomaly Score Escalation)",
        fontsize=13,
        fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    save_path = OUTPUTS_PLOTS_DIR / f"integration_rul_timeline_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved integrated RUL timeline plot -> {save_path.name}")
    return save_path


def _get_stage_color(stage_name: str) -> str:
    key = stage_name.replace(" ", "_").upper()
    if key in MAINTENANCE_DECISION_THRESHOLDS:
        return MAINTENANCE_DECISION_THRESHOLDS[key]["color"]
    return "#1f77b4"


def plot_health_status_distribution(
    fleet_summary_df: pd.DataFrame,
    subset: str,
) -> Path:
    """
    Plot fleet-wide distribution across the 4 Health Stages (HEALTHY, MONITOR, MAINTENANCE REQUIRED, CRITICAL).
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    status_counts = fleet_summary_df["engine_health_status"].value_counts()
    stages = ["HEALTHY", "MONITOR", "MAINTENANCE REQUIRED", "CRITICAL"]
    counts = [status_counts.get(st, 0) for st in stages]
    colors = [_get_stage_color(st) for st in stages]

    total = len(fleet_summary_df)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=PLOT_DPI)
    bars = ax.bar(stages, counts, color=colors, edgecolor="black", alpha=0.85, width=0.55)

    for bar, cnt in zip(bars, counts):
        if cnt > 0:
            pct = (cnt / total) * 100.0
            ax.annotate(
                f"{cnt} ({pct:.1f}%)",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=10,
            )

    ax.set_title(
        f"Fleet Health Status Distribution – {subset}\nTotal Fleet Engines = {total}",
        fontsize=12,
        fontweight="bold",
    )
    ax.set_ylabel("Number of Engines", fontsize=10)
    ax.set_ylim(0, max(counts) * 1.18 + 2)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"integration_health_distribution_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved health distribution plot -> {save_path.name}")
    return save_path


def plot_maintenance_category_breakdown(
    fleet_summary_df: pd.DataFrame,
    subset: str,
) -> Path:
    """
    Horizontal breakdown of actionable maintenance recommendations across the fleet.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    rec_counts = fleet_summary_df["engine_health_status"].value_counts()
    
    categories = [
        ("HEALTHY", "Normal Flight Operations"),
        ("MONITOR", "Heightened Telemetry Monitoring"),
        ("MAINTENANCE REQUIRED", "Priority Borescope / Overhaul"),
        ("CRITICAL", "Immediate Grounding & Teardown"),
    ]

    labels = [f"{cat}\n({desc})" for cat, desc in categories]
    counts = [rec_counts.get(cat, 0) for cat, _ in categories]
    colors = [_get_stage_color(cat) for cat, _ in categories]

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=PLOT_DPI)
    bars = ax.barh(labels, counts, color=colors, edgecolor="black", alpha=0.85, height=0.55)

    for bar, cnt in zip(bars, counts):
        if cnt > 0:
            width = bar.get_width()
            pct = (cnt / len(fleet_summary_df)) * 100.0
            ax.annotate(
                f" {cnt} engines ({pct:.1f}%)",
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(4, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontweight="bold",
                fontsize=9,
            )

    ax.set_title(
        f"Fleet Maintenance Decision Breakdown – {subset}\nActionable Operational Directives",
        fontsize=12,
        fontweight="bold",
    )
    ax.set_xlabel("Number of Fleet Engines", fontsize=10)
    ax.set_xlim(0, max(counts) * 1.25 + 5)
    ax.grid(True, linestyle=":", alpha=0.6, axis="x")

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"integration_maintenance_matrix_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved maintenance matrix plot -> {save_path.name}")
    return save_path


def plot_rul_vs_anomaly_risk_quadrant(
    fleet_summary_df: pd.DataFrame,
    subset: str,
) -> Path:
    """
    2D Risk Quadrant Scatter Plot (Predicted RUL vs Anomaly Score).
    Illustrates why combining RUL prediction with Anomaly Detection is essential.
    """
    _apply_plot_style()
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    ruls = fleet_summary_df["predicted_RUL"].values
    anoms = fleet_summary_df["latest_anomaly_score"].values
    statuses = fleet_summary_df["engine_health_status"].values

    fig, ax = plt.subplots(figsize=(10, 7.5), dpi=PLOT_DPI)

    # Shaded Decision Quadrants
    # 1. Healthy (Bottom-Right: High RUL, Low Anomaly)
    ax.fill_between([75, 140], 0, 45, color="#2ca02c", alpha=0.10, label="Nominal Zone (Healthy)")
    # 2. Early Drift / Monitor (Bottom-Left / Mid: Mod RUL, Mild Anomaly)
    ax.fill_between([45, 75], 0, 65, color="#bcbd22", alpha=0.10, label="Monitoring Zone")
    # 3. Maintenance Required (Low RUL or High Anomaly)
    ax.fill_between([20, 45], 0, 80, color="#ff7f0e", alpha=0.10, label="Maintenance Required Zone")
    # 4. Critical Zone (Left & Top: Low RUL or Severe Anomaly)
    ax.fill_between([0, 20], 0, 100, color="#d62728", alpha=0.12, label="Critical / Grounding Zone")
    ax.fill_between([20, 140], 80, 100, color="#d62728", alpha=0.12)

    # Threshold divider lines
    ax.axvline(x=20.0, color="#d62728", linestyle="--", linewidth=1.2, alpha=0.7)
    ax.axvline(x=45.0, color="#ff7f0e", linestyle="--", linewidth=1.2, alpha=0.7)
    ax.axvline(x=75.0, color="#2ca02c", linestyle="--", linewidth=1.2, alpha=0.7)

    ax.axhline(y=45.0, color="#2ca02c", linestyle="--", linewidth=1.2, alpha=0.7)
    ax.axhline(y=65.0, color="#ff7f0e", linestyle="--", linewidth=1.2, alpha=0.7)
    ax.axhline(y=80.0, color="#d62728", linestyle="--", linewidth=1.2, alpha=0.7)

    # Scatter points for each health stage
    stage_markers = {
        "HEALTHY": {"color": "#2ca02c", "marker": "o", "label": "Engine: HEALTHY"},
        "MONITOR": {"color": "#bcbd22", "marker": "s", "label": "Engine: MONITOR"},
        "MAINTENANCE REQUIRED": {"color": "#ff7f0e", "marker": "D", "label": "Engine: MAINTENANCE REQUIRED"},
        "CRITICAL": {"color": "#d62728", "marker": "^", "label": "Engine: CRITICAL"},
    }

    for st, mdict in stage_markers.items():
        mask = statuses == st
        if mask.any():
            ax.scatter(
                ruls[mask],
                anoms[mask],
                color=mdict["color"],
                marker=mdict["marker"],
                s=55,
                alpha=0.90,
                edgecolors="black",
                linewidth=0.6,
                label=mdict["label"],
                zorder=5,
            )

    ax.set_title(
        f"2D Engine Health Risk Quadrant – {subset}\n(Predicted RUL vs Calibrated Anomaly Score)",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel("Predicted Remaining Useful Life (cycles) [Person 2]", fontsize=10, fontweight="bold")
    ax.set_ylabel("Calibrated Anomaly Score (0 = Nominal, 100 = Critical) [Person 3]", fontsize=10, fontweight="bold")
    ax.set_xlim(0, max(135, float(np.max(ruls)) + 5))
    ax.set_ylim(0, 100)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.95)

    plt.tight_layout()
    save_path = OUTPUTS_PLOTS_DIR / f"integration_rul_vs_anomaly_{subset}.png"
    plt.savefig(save_path)
    plt.close(fig)
    print(f"  [plot] Saved RUL vs Anomaly Risk Quadrant plot -> {save_path.name}")
    return save_path
