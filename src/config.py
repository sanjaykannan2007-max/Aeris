"""
config.py
=========
Central configuration for the C-MAPSS Data Engineering Pipeline.
Edit values here to change behaviour across the whole pipeline.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_RAW_DIR        = PROJECT_ROOT / "data" / "raw"
DATA_CLEANED_DIR    = PROJECT_ROOT / "data" / "cleaned"
DATA_PROCESSED_DIR  = PROJECT_ROOT / "data" / "processed"
DATA_FEATURES_DIR   = PROJECT_ROOT / "data" / "features"

MODELS_SCALERS_DIR  = PROJECT_ROOT / "models" / "scalers"
MODELS_RUL_DIR      = PROJECT_ROOT / "models" / "rul"

OUTPUTS_PLOTS_DIR       = PROJECT_ROOT / "outputs" / "plots"
OUTPUTS_STATISTICS_DIR  = PROJECT_ROOT / "outputs" / "statistics"
OUTPUTS_REPORTS_DIR     = PROJECT_ROOT / "outputs" / "reports"
OUTPUTS_PREDICTIONS_DIR = PROJECT_ROOT / "outputs" / "predictions"

NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

# ---------------------------------------------------------------------------
# Column Names  (NASA C-MAPSS: 26 space-separated columns)
# ---------------------------------------------------------------------------
COLUMN_NAMES = (
    ["engine_id", "cycle"]
    + [f"setting_{i}" for i in range(1, 4)]      # 3 operational settings
    + [f"sensor_{i}" for i in range(1, 22)]      # 21 sensor measurements
)

ENGINE_ID_COL   = "engine_id"
CYCLE_COL       = "cycle"
SETTING_COLS    = [f"setting_{i}" for i in range(1, 4)]
SENSOR_COLS     = [f"sensor_{i}" for i in range(1, 22)]
FEATURE_COLS    = SETTING_COLS + SENSOR_COLS     # columns to be normalised

# ---------------------------------------------------------------------------
# Valid Dataset Identifiers
# ---------------------------------------------------------------------------
VALID_SUBSETS = ["FD001", "FD002", "FD003", "FD004"]

# ---------------------------------------------------------------------------
# RUL Configuration
# ---------------------------------------------------------------------------
MAX_RUL = 125           # Piece-wise linear cap (widely used in literature)
RUL_COL         = "RUL"
RUL_CAPPED_COL  = "RUL_capped"

# ---------------------------------------------------------------------------
# Feature Engineering
# ---------------------------------------------------------------------------
WINDOW_SIZE = 5         # Rolling window (cycles); applies per engine

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
# Choose "minmax" or "standard"
SCALER_TYPE = "minmax"

# ---------------------------------------------------------------------------
# Sensor Analysis Thresholds
# ---------------------------------------------------------------------------
CONSTANT_VARIANCE_THRESHOLD      = 1e-10   # sensor is constant
NEAR_CONSTANT_VARIANCE_THRESHOLD = 1e-3    # sensor is near-constant / barely useful
CYCLE_CORR_THRESHOLD             = 0.10    # |corr with cycle| above this → potentially useful

# ---------------------------------------------------------------------------
# Plot Settings
# ---------------------------------------------------------------------------
PLOT_DPI      = 300
PLOT_FIGSIZE  = (14, 8)
PLOT_STYLE    = "seaborn-v0_8-darkgrid"

# ---------------------------------------------------------------------------
# Dataset-Specific Metadata (for documentation / reports)
# ---------------------------------------------------------------------------
DATASET_META = {
    "FD001": {
        "conditions": 1,
        "fault_modes": 1,
        "description": "Single condition (Sea Level), HPC Degradation",
        "train_engines": 100,
        "test_engines": 100,
    },
    "FD002": {
        "conditions": 6,
        "fault_modes": 1,
        "description": "Six conditions, HPC Degradation",
        "train_engines": 260,
        "test_engines": 259,
    },
    "FD003": {
        "conditions": 1,
        "fault_modes": 2,
        "description": "Single condition (Sea Level), HPC + Fan Degradation",
        "train_engines": 100,
        "test_engines": 100,
    },
    "FD004": {
        "conditions": 6,
        "fault_modes": 2,
        "description": "Six conditions, HPC + Fan Degradation",
        "train_engines": 248,
        "test_engines": 249,
    },
}

# ---------------------------------------------------------------------------
# RUL Model Hyperparameters
# ---------------------------------------------------------------------------
RF_PARAMS = {
    "n_estimators": 100,
    "max_depth": 15,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "random_state": 42,
    "n_jobs": -1,
}

XGB_PARAMS = {
    "n_estimators": 100,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
}

# ---------------------------------------------------------------------------
# Engine Health Score Thresholds (%)
# ---------------------------------------------------------------------------
HEALTH_STAGES = {
    "HEALTHY": {"min_score": 75.0, "label": "HEALTHY", "color": "green"},
    "MONITOR": {"min_score": 45.0, "label": "MONITOR", "color": "yellow"},
    "MAINTENANCE_REQUIRED": {"min_score": 20.0, "label": "MAINTENANCE REQUIRED", "color": "orange"},
    "CRITICAL": {"min_score": 0.0, "label": "CRITICAL", "color": "red"},
}

