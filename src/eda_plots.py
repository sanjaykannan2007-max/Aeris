"""
eda_plots.py
============
Generates and saves all Exploratory Data Analysis plots.

All plots are saved to outputs/plots/ at 300 dpi in PNG format.

Public API
----------
    run_eda(train_df, subset, report)      -> None  (generates all per-dataset plots)
    run_cross_dataset_eda(all_dfs)         -> None  (generates comparison plots)
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
from pathlib import Path
from typing import Any

from src.config import (
    SENSOR_COLS,
    SETTING_COLS,
    ENGINE_ID_COL,
    CYCLE_COL,
    RUL_COL,
    OUTPUTS_PLOTS_DIR,
    PLOT_DPI,
    PLOT_FIGSIZE,
    PLOT_STYLE,
    CONSTANT_VARIANCE_THRESHOLD,
)

warnings.filterwarnings("ignore")

for _style in [PLOT_STYLE, "seaborn-v0_8-darkgrid", "seaborn-v0_8-whitegrid", "ggplot"]:
    try:
        plt.style.use(_style)
        break
    except Exception:
        continue

PALETTE = "viridis"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _savefig(fig, name: str, subset: str = "") -> None:
    OUTPUTS_PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"{subset}_" if subset else ""
    path   = OUTPUTS_PLOTS_DIR / f"{prefix}{name}.png"
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)


def _variable_sensors(df: pd.DataFrame) -> list[str]:
    """Return sensor columns that are NOT constant (have variance > threshold)."""
    return [
        c for c in SENSOR_COLS
        if c in df.columns and df[c].var() > CONSTANT_VARIANCE_THRESHOLD
    ]


# ---------------------------------------------------------------------------
# Per-Dataset EDA
# ---------------------------------------------------------------------------

def plot_sensor_distributions(df: pd.DataFrame, subset: str) -> None:
    """Box plots for all variable sensors."""
    vsensors = _variable_sensors(df)
    if not vsensors:
        return

    n = len(vsensors)
    ncols = 4
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 4, nrows * 3.5))
    axes = axes.flatten()

    for i, col in enumerate(vsensors):
        ax = axes[i]
        data = df[col].dropna()
        ax.boxplot(data, patch_artist=True,
                   boxprops=dict(facecolor="#4C72B0", alpha=0.7),
                   medianprops=dict(color="white", linewidth=2))
        ax.set_title(col, fontsize=10, fontweight="bold")
        ax.set_xlabel("")
        ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

    # Hide unused axes
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(f"{subset} – Sensor Distributions (Box Plots)", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    _savefig(fig, "sensor_distributions", subset)
    print(f"  [eda] {subset}: sensor_distributions saved")


def plot_sensor_violin(df: pd.DataFrame, subset: str) -> None:
    """Violin plots for up to 12 variable sensors."""
    vsensors = _variable_sensors(df)[:12]
    if not vsensors:
        return

    # Melt for seaborn
    melted = df[vsensors].melt(var_name="sensor", value_name="value").dropna()

    fig, ax = plt.subplots(figsize=(16, 6))
    sns.violinplot(data=melted, x="sensor", y="value", ax=ax,
                   palette="muted", cut=0, inner="quartile")
    ax.set_title(f"{subset} – Sensor Violin Plots (Top 12 variable sensors)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Sensor", fontsize=11)
    ax.set_ylabel("Value", fontsize=11)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    _savefig(fig, "sensor_violin", subset)
    print(f"  [eda] {subset}: sensor_violin saved")


def plot_correlation_matrix(df: pd.DataFrame, subset: str) -> None:
    """Correlation heatmap of variable sensors + cycle."""
    vsensors = _variable_sensors(df)
    cols     = [CYCLE_COL] + vsensors

    corr = df[cols].corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))

    fig, ax = plt.subplots(figsize=(min(24, len(cols) * 0.9 + 2), min(20, len(cols) * 0.9 + 2)))
    sns.heatmap(
        corr, mask=mask, ax=ax,
        cmap="coolwarm", center=0, vmin=-1, vmax=1,
        annot=len(cols) <= 18, fmt=".2f", annot_kws={"size": 7},
        linewidths=0.3, square=True,
        cbar_kws={"shrink": 0.7},
    )
    ax.set_title(f"{subset} – Sensor Correlation Matrix", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _savefig(fig, "correlation_matrix", subset)
    print(f"  [eda] {subset}: correlation_matrix saved")


def plot_sensor_variance(df: pd.DataFrame, subset: str) -> None:
    """Bar chart of sensor variances (log scale)."""
    variances = df[SENSOR_COLS].var().sort_values(ascending=False)
    variances  = variances[variances > 0]

    fig, ax = plt.subplots(figsize=(14, 5))
    colors = ["#e74c3c" if v <= 1e-3 else "#2ecc71" for v in variances]
    ax.bar(variances.index, variances.values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_yscale("log")
    ax.set_title(f"{subset} – Sensor Variance (log scale) | Red = near-constant",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Sensor", fontsize=11)
    ax.set_ylabel("Variance (log)", fontsize=11)
    plt.xticks(rotation=45, ha="right", fontsize=9)
    plt.tight_layout()
    _savefig(fig, "sensor_variance", subset)
    print(f"  [eda] {subset}: sensor_variance saved")


def plot_sensor_trends(df: pd.DataFrame, subset: str, n_engines: int = 10) -> None:
    """
    Line plots of sensor mean across cycles (averaged over n_engines engines).
    Shows the average degradation trend.
    """
    vsensors = _variable_sensors(df)
    if not vsensors:
        return

    # Use first n_engines for clarity
    engines = sorted(df[ENGINE_ID_COL].unique())[:n_engines]
    subset_df = df[df[ENGINE_ID_COL].isin(engines)]

    # Average across selected engines at each cycle
    trend = subset_df.groupby(CYCLE_COL)[vsensors].mean()

    ncols = 4
    nrows = (len(vsensors) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 5, nrows * 3.5))
    axes = axes.flatten()

    cmap_colors = plt.cm.viridis(np.linspace(0, 1, len(vsensors)))

    for i, col in enumerate(vsensors):
        ax = axes[i]
        ax.plot(trend.index, trend[col], color=cmap_colors[i], linewidth=1.8)
        ax.set_title(col, fontsize=9, fontweight="bold")
        ax.set_xlabel("Cycle", fontsize=8)
        ax.set_ylabel("Mean Value", fontsize=8)
        ax.tick_params(labelsize=7)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(
        f"{subset} – Average Sensor Trends over Cycles (first {n_engines} engines)",
        fontsize=13, fontweight="bold", y=1.01
    )
    plt.tight_layout()
    _savefig(fig, "sensor_trends", subset)
    print(f"  [eda] {subset}: sensor_trends saved")


def plot_degradation_curves(df: pd.DataFrame, subset: str, n_engines: int = 20) -> None:
    """
    Individual engine degradation curves for a subset of engines.
    Shows RUL (if present) or cycle over time per engine.
    """
    vsensors = _variable_sensors(df)
    if not vsensors:
        return

    # Pick sensor most correlated with cycle as degradation proxy
    corrs = df[[CYCLE_COL] + vsensors].corr()[CYCLE_COL].drop(CYCLE_COL).abs()
    best_sensor = corrs.idxmax()

    engines = sorted(df[ENGINE_ID_COL].unique())[:n_engines]
    cmap_colors = plt.cm.plasma(np.linspace(0, 1, len(engines)))

    fig, ax = plt.subplots(figsize=(14, 7))
    for idx, (eng, color) in enumerate(zip(engines, cmap_colors)):
        eng_data = df[df[ENGINE_ID_COL] == eng].sort_values(CYCLE_COL)
        ax.plot(eng_data[CYCLE_COL], eng_data[best_sensor],
                alpha=0.55, linewidth=1.0, color=color)

    ax.set_title(
        f"{subset} – Individual Engine Degradation Curves\n"
        f"Sensor: {best_sensor} (highest |corr| with cycle) — {n_engines} engines",
        fontsize=12, fontweight="bold"
    )
    ax.set_xlabel("Operating Cycle", fontsize=11)
    ax.set_ylabel(best_sensor, fontsize=11)
    sm = plt.cm.ScalarMappable(cmap="plasma", norm=plt.Normalize(vmin=1, vmax=n_engines))
    plt.colorbar(sm, ax=ax, label="Engine index")
    plt.tight_layout()
    _savefig(fig, "degradation_curves", subset)
    print(f"  [eda] {subset}: degradation_curves saved (sensor={best_sensor})")


def plot_rul_distribution(df: pd.DataFrame, subset: str) -> None:
    """Histogram + KDE of RUL (training data)."""
    if RUL_COL not in df.columns:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Uncapped RUL
    ax = axes[0]
    ax.hist(df[RUL_COL], bins=50, color="#3498db", edgecolor="white", linewidth=0.4, alpha=0.85)
    ax.set_title(f"{subset} – RUL Distribution (Uncapped)", fontsize=12, fontweight="bold")
    ax.set_xlabel("RUL (cycles)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.axvline(df[RUL_COL].mean(), color="red", linestyle="--", label=f"Mean={df[RUL_COL].mean():.0f}")
    ax.legend()

    # Capped RUL
    rul_capped_col = "RUL_capped"
    if rul_capped_col in df.columns:
        ax = axes[1]
        ax.hist(df[rul_capped_col], bins=50, color="#e67e22", edgecolor="white", linewidth=0.4, alpha=0.85)
        ax.set_title(f"{subset} – RUL Distribution (Capped)", fontsize=12, fontweight="bold")
        ax.set_xlabel("RUL_capped (cycles)", fontsize=11)
        ax.set_ylabel("Frequency", fontsize=11)
        ax.axvline(df[rul_capped_col].mean(), color="red", linestyle="--",
                   label=f"Mean={df[rul_capped_col].mean():.0f}")
        ax.legend()
    else:
        axes[1].set_visible(False)

    plt.tight_layout()
    _savefig(fig, "rul_distribution", subset)
    print(f"  [eda] {subset}: rul_distribution saved")


def plot_operating_conditions(df: pd.DataFrame, subset: str) -> None:
    """Scatter plots of operational settings to show operating condition clusters."""
    setting_cols_present = [c for c in SETTING_COLS if c in df.columns]
    if len(setting_cols_present) < 2:
        return

    fig, axes = plt.subplots(1, min(3, len(setting_cols_present)), figsize=(16, 5))
    if not hasattr(axes, "__len__"):
        axes = [axes]

    pairs = [
        (setting_cols_present[0], setting_cols_present[1]),
        (setting_cols_present[0], setting_cols_present[2]) if len(setting_cols_present) > 2 else None,
        (setting_cols_present[1], setting_cols_present[2]) if len(setting_cols_present) > 2 else None,
    ]

    for ax, pair in zip(axes, [p for p in pairs if p is not None]):
        sc = ax.scatter(df[pair[0]], df[pair[1]],
                        c=df[ENGINE_ID_COL], cmap="tab20",
                        alpha=0.3, s=5, linewidths=0)
        ax.set_xlabel(pair[0], fontsize=10)
        ax.set_ylabel(pair[1], fontsize=10)
        ax.set_title(f"{pair[0]} vs {pair[1]}", fontsize=10, fontweight="bold")

    fig.suptitle(f"{subset} – Operating Condition Clusters", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _savefig(fig, "operating_conditions", subset)
    print(f"  [eda] {subset}: operating_conditions saved")


def plot_engine_lifetime(df: pd.DataFrame, subset: str) -> None:
    """Histogram of engine lifetimes (max cycle per engine)."""
    lifetimes = df.groupby(ENGINE_ID_COL)[CYCLE_COL].max()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(lifetimes, bins=30, color="#9b59b6", edgecolor="white", linewidth=0.5, alpha=0.85)
    ax.axvline(lifetimes.mean(), color="red",    linestyle="--", label=f"Mean={lifetimes.mean():.0f}")
    ax.axvline(lifetimes.median(), color="orange", linestyle="--", label=f"Median={lifetimes.median():.0f}")
    ax.set_title(f"{subset} – Engine Lifetime Distribution", fontsize=12, fontweight="bold")
    ax.set_xlabel("Lifetime (cycles)", fontsize=11)
    ax.set_ylabel("Number of Engines", fontsize=11)
    ax.legend()
    plt.tight_layout()
    _savefig(fig, "engine_lifetime", subset)
    print(f"  [eda] {subset}: engine_lifetime saved")


def plot_sensor_statistics_heatmap(df: pd.DataFrame, subset: str) -> None:
    """Heatmap of per-sensor statistics (mean, std, min, max) normalised."""
    vsensors = _variable_sensors(df)
    if not vsensors:
        return

    stats = df[vsensors].describe().T[["mean", "std", "min", "max"]]
    # Normalise each metric column independently for visual comparison
    normed = (stats - stats.min()) / (stats.max() - stats.min() + 1e-12)

    fig, ax = plt.subplots(figsize=(8, max(6, len(vsensors) * 0.45)))
    sns.heatmap(normed, ax=ax, cmap="YlOrRd", annot=True, fmt=".2f",
                linewidths=0.3, cbar_kws={"shrink": 0.7}, annot_kws={"size": 8})
    ax.set_title(f"{subset} – Sensor Statistics Heatmap (normalised)", fontsize=12, fontweight="bold")
    plt.tight_layout()
    _savefig(fig, "sensor_statistics_heatmap", subset)
    print(f"  [eda] {subset}: sensor_statistics_heatmap saved")


# ---------------------------------------------------------------------------
# Cross-Dataset Comparison
# ---------------------------------------------------------------------------

def plot_cross_dataset_comparison(all_dfs: dict[str, pd.DataFrame]) -> None:
    """
    Compare average engine lifetimes and sensor variability across FD001–FD004.
    """
    # 1. Engine lifetime comparison
    lifetime_stats = {}
    for subset, df in all_dfs.items():
        lt = df.groupby(ENGINE_ID_COL)[CYCLE_COL].max()
        lifetime_stats[subset] = {"mean": lt.mean(), "std": lt.std(), "min": lt.min(), "max": lt.max()}

    lt_df = pd.DataFrame(lifetime_stats).T

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    subsets = list(lt_df.index)
    means   = lt_df["mean"].values
    stds    = lt_df["std"].values
    colors  = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12"]
    bars    = ax.bar(subsets, means, yerr=stds, color=colors,
                     capsize=8, edgecolor="white", linewidth=0.8, alpha=0.85)
    ax.set_title("Average Engine Lifetime by Dataset", fontsize=12, fontweight="bold")
    ax.set_xlabel("Dataset", fontsize=11)
    ax.set_ylabel("Cycles", fontsize=11)
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                f"{mean:.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # 2. Number of engines comparison
    ax = axes[1]
    n_engines = {s: df[ENGINE_ID_COL].nunique() for s, df in all_dfs.items()}
    ax.bar(list(n_engines.keys()), list(n_engines.values()),
           color=colors, edgecolor="white", linewidth=0.8, alpha=0.85)
    ax.set_title("Number of Training Engines by Dataset", fontsize=12, fontweight="bold")
    ax.set_xlabel("Dataset", fontsize=11)
    ax.set_ylabel("Number of Engines", fontsize=11)

    fig.suptitle("C-MAPSS Cross-Dataset Comparison", fontsize=14, fontweight="bold")
    plt.tight_layout()
    _savefig(fig, "cross_dataset_comparison")
    print("  [eda] cross_dataset_comparison saved")


def plot_cross_dataset_sensor_corr(all_dfs: dict[str, pd.DataFrame]) -> None:
    """
    Compare sensor-cycle correlations across all four datasets as a grouped bar chart.
    Helps identify which sensors are degradation signals in each dataset.
    """
    corr_data = {}
    for subset, df in all_dfs.items():
        vsensors = _variable_sensors(df)
        corr = df[[CYCLE_COL] + vsensors].corr()[CYCLE_COL].drop(CYCLE_COL)
        corr_data[subset] = corr

    corr_df = pd.DataFrame(corr_data).fillna(0)

    fig, ax = plt.subplots(figsize=(18, 6))
    x = np.arange(len(corr_df))
    width = 0.2
    colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12"]

    for i, (subset, color) in enumerate(zip(corr_df.columns, colors)):
        ax.bar(x + i * width, corr_df[subset], width, label=subset,
               color=color, edgecolor="white", linewidth=0.5, alpha=0.85)

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(corr_df.index, rotation=45, ha="right", fontsize=9)
    ax.set_title("Sensor–Cycle Correlation Comparison (FD001–FD004)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Sensor", fontsize=11)
    ax.set_ylabel("Pearson Correlation with Cycle", fontsize=11)
    ax.legend(title="Dataset")
    plt.tight_layout()
    _savefig(fig, "cross_dataset_sensor_correlation")
    print("  [eda] cross_dataset_sensor_correlation saved")


# ---------------------------------------------------------------------------
# Main EDA runner
# ---------------------------------------------------------------------------

def run_eda(train_df: pd.DataFrame, subset: str) -> None:
    """
    Run all per-dataset EDA plots.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training DataFrame (after RUL labelling, before or after scaling).
    subset : str
    """
    print(f"\n  === EDA: {subset} ===")
    plot_sensor_distributions(train_df, subset)
    plot_sensor_violin(train_df, subset)
    plot_correlation_matrix(train_df, subset)
    plot_sensor_variance(train_df, subset)
    plot_sensor_trends(train_df, subset)
    plot_degradation_curves(train_df, subset)
    plot_rul_distribution(train_df, subset)
    plot_operating_conditions(train_df, subset)
    plot_engine_lifetime(train_df, subset)
    plot_sensor_statistics_heatmap(train_df, subset)
    print(f"  === EDA complete: {subset} ===\n")


def run_cross_dataset_eda(all_train_dfs: dict[str, pd.DataFrame]) -> None:
    """
    Run cross-dataset comparison plots.

    Parameters
    ----------
    all_train_dfs : dict mapping subset → training DataFrame
    """
    print("\n  === Cross-Dataset EDA ===")
    plot_cross_dataset_comparison(all_train_dfs)
    plot_cross_dataset_sensor_corr(all_train_dfs)
    print("  === Cross-Dataset EDA complete ===\n")
