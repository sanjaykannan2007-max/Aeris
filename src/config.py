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
MODELS_ANOMALY_DIR  = PROJECT_ROOT / "models" / "anomaly"

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

# ---------------------------------------------------------------------------
# Anomaly Detection Configuration (Person 3)
# ---------------------------------------------------------------------------
ISOLATION_FOREST_PARAMS = {
    "n_estimators": 150,
    "max_samples": "auto",
    "contamination": 0.08,
    "random_state": 42,
    "n_jobs": -1,
}

# Normalized Anomaly Score Categories (0 - 100)
# 0 = Completely Nominal / Healthy, 100 = Severe Anomaly
ANOMALY_STAGES = {
    "NOMINAL": {"min_score": 0.0, "max_score": 45.0, "label": "Normal", "severity": "Nominal", "color": "#2ca02c"},
    "MILD": {"min_score": 45.0, "max_score": 65.0, "label": "Normal", "severity": "Mild Drift", "color": "#ff7f0e"},
    "MODERATE": {"min_score": 65.0, "max_score": 80.0, "label": "Anomalous", "severity": "Moderate Anomaly", "color": "#d62728"},
    "SEVERE": {"min_score": 80.0, "max_score": 100.0, "label": "Anomalous", "severity": "Severe Anomaly", "color": "#7f0000"},
}

ANOMALY_SCORE_THRESHOLD = 60.0  # Above this score -> Classified as Anomaly

# Sensor Z-Score Deviation Categories (|z|)
SENSOR_DEVIATION_LEVELS = {
    "CRITICAL": {"min_z": 3.0, "label": "Critical deviation", "rank": 1},
    "HIGH": {"min_z": 2.0, "label": "High deviation", "rank": 2},
    "MODERATE": {"min_z": 1.0, "label": "Moderate deviation", "rank": 3},
    "LOW": {"min_z": 0.0, "label": "Low deviation", "rank": 4},
}

# ---------------------------------------------------------------------------
# Person 4 – Integration & Maintenance Recommendation Configuration
# ---------------------------------------------------------------------------
# Multi-Factor Health Decision Thresholds (Configurable)
MAINTENANCE_DECISION_THRESHOLDS = {
    "CRITICAL": {
        "max_rul": 20.0,             # RUL < 20 cycles
        "min_anomaly_score": 80.0,   # Anomaly Score >= 80.0
        "label": "CRITICAL",
        "color": "#d62728",          # Red
        "risk_level": "CRITICAL",
        "default_urgency_window": 5, # Must service within 5 cycles
    },
    "MAINTENANCE_REQUIRED": {
        "max_rul": 45.0,             # RUL < 45 cycles
        "min_anomaly_score": 65.0,   # Anomaly Score >= 65.0
        "label": "MAINTENANCE REQUIRED",
        "color": "#ff7f0e",          # Orange
        "risk_level": "HIGH",
        "default_urgency_window": 15, # Service within 15 cycles
    },
    "MONITOR": {
        "max_rul": 75.0,             # RUL < 75 cycles
        "min_anomaly_score": 45.0,   # Anomaly Score >= 45.0
        "label": "MONITOR",
        "color": "#bcbd22",          # Yellow / Olive
        "risk_level": "MEDIUM",
        "default_urgency_window": 30, # Re-inspect in 30 cycles
    },
    "HEALTHY": {
        "min_rul": 75.0,             # RUL >= 75 cycles
        "max_anomaly_score": 45.0,   # Anomaly Score < 45.0
        "label": "HEALTHY",
        "color": "#2ca02c",          # Green
        "risk_level": "LOW",
        "default_urgency_window": None, # Routine line service
    },
}

# Mapping of C-MAPSS Sensor IDs to Physical Turbofan Components
SENSOR_COMPONENT_MAPPINGS = {
    "sensor_1": {"name": "T2 (Total Fan Inlet Temp)", "component": "Fan & Inlet Cowl", "system": "Air Intake"},
    "sensor_2": {"name": "T24 (LPC Outlet Temp)", "component": "Low-Pressure Compressor (LPC)", "system": "Compression"},
    "sensor_3": {"name": "T30 (HPC Outlet Temp)", "component": "High-Pressure Compressor (HPC)", "system": "Compression"},
    "sensor_4": {"name": "T48 (LPT Outlet Temp)", "component": "Low-Pressure Turbine (LPT)", "system": "Turbine Gas Path"},
    "sensor_5": {"name": "P2 (Fan Inlet Pressure)", "component": "Fan & Inlet Cowl", "system": "Air Intake"},
    "sensor_6": {"name": "P15 (Bypass Duct Pressure)", "component": "Bypass Duct & Fan Exit", "system": "Secondary Flow"},
    "sensor_7": {"name": "P30 (HPC Outlet Total Pressure)", "component": "High-Pressure Compressor (HPC)", "system": "Compression"},
    "sensor_8": {"name": "Nf (Physical Fan Speed)", "component": "Fan Rotor & Low-Pressure Shaft", "system": "Rotary Mechanics"},
    "sensor_9": {"name": "Nc (Physical Core Speed)", "component": "High-Pressure Core Spool", "system": "Rotary Mechanics"},
    "sensor_10": {"name": "epr (Engine Pressure Ratio)", "component": "Turbine Expansion & Exhaust Nozzle", "system": "Gas Expansion"},
    "sensor_11": {"name": "T50 (HPT Outlet Temp)", "component": "High-Pressure Turbine (HPT)", "system": "Turbine Gas Path"},
    "sensor_12": {"name": "Ps30 (HPC Static Pressure)", "component": "Diffuser & Combustor Inlet", "system": "Combustion"},
    "sensor_13": {"name": "Phi (Corrected Fan Speed)", "component": "Fan Governor & FADEC", "system": "Control & Speed"},
    "sensor_14": {"name": "NRc (Corrected Core Speed)", "component": "Core High-Pressure Governor", "system": "Control & Speed"},
    "sensor_15": {"name": "BPR (Bypass Ratio)", "component": "Bypass Splitter & Fan Aero", "system": "Aerodynamics"},
    "sensor_16": {"name": "farB (Burner Fuel-Air Ratio)", "component": "Fuel Nozzles & Combustor Liner", "system": "Fuel / Combustion"},
    "sensor_17": {"name": "htBleed (Bleed Enthalpy)", "component": "Customer Bleed & Anti-Ice System", "system": "Thermal & Bleed"},
    "sensor_18": {"name": "Nf_dmd (Demanded Fan Speed)", "component": "FADEC Thrust Command", "system": "Avionics / FADEC"},
    "sensor_19": {"name": "PCNfR_dmd (Demanded Corr. Fan Speed)", "component": "FADEC Control Unit", "system": "Avionics / FADEC"},
    "sensor_20": {"name": "W31 (HPT Coolant Bleed Flow)", "component": "HPT Vane Cooling Gas Path", "system": "Cooling"},
    "sensor_21": {"name": "W32 (LPT Coolant Bleed Flow)", "component": "LPT Blade Cooling Bleed", "system": "Cooling"},
}

DISCLAIMER_TEXT = (
    "NOTICE: This predictive health assessment and maintenance recommendation system is a research "
    "decision-support prototype developed for C-MAPSS turbofan data. It does not replace or supersede "
    "certified FAA/EASA airworthiness directives, engine shop manuals (ESM), or approved airline standard operating procedures."
)

# ---------------------------------------------------------------------------
# Regime & Multi-Condition Normalization Configuration
# ---------------------------------------------------------------------------
N_REGIMES = {
    "FD001": 1,
    "FD002": 6,
    "FD003": 1,
    "FD004": 6,
}

# ---------------------------------------------------------------------------
# Subsystem & Protocol Mapping
# ---------------------------------------------------------------------------
SENSOR_SUBSYSTEM = {
    "sensor_1": "Air Intake", "sensor_2": "Compressor", "sensor_3": "Compressor",
    "sensor_4": "Turbine", "sensor_5": "Air Intake", "sensor_6": "Secondary Flow",
    "sensor_7": "Compressor", "sensor_8": "Mechanical", "sensor_9": "Mechanical",
    "sensor_10": "Turbine", "sensor_11": "Turbine", "sensor_12": "Combustion",
    "sensor_13": "Control & Speed", "sensor_14": "Control & Speed", "sensor_15": "Aerodynamics",
    "sensor_16": "Combustion", "sensor_17": "Thermal", "sensor_18": "Control & Speed",
    "sensor_19": "Control & Speed", "sensor_20": "Cooling", "sensor_21": "Cooling",
    "T2": "Air Intake", "T24": "Compressor", "T30": "Compressor", "T48": "Turbine",
    "P2": "Air Intake", "P15": "Secondary Flow", "P30": "Compressor", "Nf": "Mechanical",
    "Nc": "Mechanical", "epr": "Turbine", "T50": "Turbine", "Ps30": "Combustion",
    "Phi": "Control & Speed", "NRc": "Control & Speed", "BPR": "Aerodynamics",
    "farB": "Combustion", "htBleed": "Thermal", "Nf_dmd": "Control & Speed",
    "PCNfR_dmd": "Control & Speed", "W31": "Cooling", "W32": "Cooling",
}

MAINTENANCE_PROTOCOLS = {
    "Compressor": {
        "code": "TASK-72-30-01",
        "title": "HPC borescope inspection & stage-1/2 blade wash",
        "labour_hours": 12.0,
        "aog_risk": "high",
        "recommended_window_days": 7,
    },
    "Turbine": {
        "code": "TASK-72-50-04",
        "title": "HPT shroud tile inspection & NGV thermal check",
        "labour_hours": 18.0,
        "aog_risk": "high",
        "recommended_window_days": 5,
    },
    "Thermal": {
        "code": "TASK-75-21-00",
        "title": "Bleed valve actuator test & duct insulation audit",
        "labour_hours": 6.0,
        "aog_risk": "medium",
        "recommended_window_days": 14,
    },
    "Combustion": {
        "code": "TASK-72-40-02",
        "title": "Combustor fuel nozzle flow test & liner inspection",
        "labour_hours": 14.0,
        "aog_risk": "high",
        "recommended_window_days": 7,
    },
    "Mechanical": {
        "code": "TASK-72-00-11",
        "title": "Main bearing oil chip detector & vibration audit",
        "labour_hours": 8.0,
        "aog_risk": "medium",
        "recommended_window_days": 10,
    },
    "Cooling": {
        "code": "TASK-75-30-01",
        "title": "Turbine cooling air circuit flow check & valve overhaul",
        "labour_hours": 10.0,
        "aog_risk": "medium",
        "recommended_window_days": 10,
    },
    "Air Intake": {
        "code": "TASK-71-11-01",
        "title": "Inlet cowl lip anti-ice & fan acoustic panel audit",
        "labour_hours": 4.0,
        "aog_risk": "low",
        "recommended_window_days": 21,
    },
    "Secondary Flow": {
        "code": "TASK-75-10-00",
        "title": "Bypass duct seal inspection & pressure tap calibration",
        "labour_hours": 5.0,
        "aog_risk": "low",
        "recommended_window_days": 21,
    },
    "Control & Speed": {
        "code": "TASK-73-20-00",
        "title": "FADEC sensor harness continuity & speed sensor test",
        "labour_hours": 4.0,
        "aog_risk": "low",
        "recommended_window_days": 21,
    },
    "Aerodynamics": {
        "code": "TASK-72-21-00",
        "title": "Fan blade variable pitch mechanism & acoustic liner check",
        "labour_hours": 8.0,
        "aog_risk": "medium",
        "recommended_window_days": 14,
    },
    "Unclassified": {
        "code": "TASK-70-00-00",
        "title": "General line inspection & telemetry re-calibration",
        "labour_hours": 4.0,
        "aog_risk": "low",
        "recommended_window_days": 14,
    },
}

# ---------------------------------------------------------------------------
# Business & Financial Model Configuration
# ---------------------------------------------------------------------------
COST_MODEL = {
    "planned_shop_visit": 150000.0,       # Base cost of planned overhaul ($)
    "unplanned_removal": 450000.0,         # Emergency removal & teardown ($)
    "aog_per_day": 85000.0,                # Aircraft Grounded loss per day ($)
    "mean_aog_days_unplanned": 2.5,        # Avg days grounded for unplanned event
    "secondary_damage_probability": 0.35,  # Chance of collateral engine damage
    "secondary_damage_cost": 220000.0,     # Cost of secondary damage ($)
    "cancellation_cost": 40000.0,          # Passenger rebooking & logistics ($)
    "labour_rate_per_hour": 185.0,         # Certified technician rate ($/hr)
    "cycles_per_day": 2.0,                 # Avg flight cycles per day
}

SENSOR_MEANING = {
    "sensor_1": "T2 - Fan inlet temp (°R)",
    "sensor_2": "T24 - LPC outlet temp (°R)",
    "sensor_3": "T30 - HPC outlet temp (°R)",
    "sensor_4": "T48 - LPT outlet temp (°R)",
    "sensor_5": "P2 - Fan inlet pressure (psia)",
    "sensor_6": "P15 - Bypass duct pressure (psia)",
    "sensor_7": "P30 - HPC outlet total pressure (psia)",
    "sensor_8": "Nf - Physical fan speed (rpm)",
    "sensor_9": "Nc - Physical core speed (rpm)",
    "sensor_10": "epr - Engine pressure ratio",
    "sensor_11": "T50 - HPT outlet temp (°R)",
    "sensor_12": "Ps30 - HPC static pressure (psia)",
    "sensor_13": "Phi - Corrected fan speed (rpm)",
    "sensor_14": "NRc - Corrected core speed (rpm)",
    "sensor_15": "BPR - Bypass ratio",
    "sensor_16": "farB - Burner fuel-air ratio",
    "sensor_17": "htBleed - Bleed enthalpy",
    "sensor_18": "Nf_dmd - Demanded fan speed (rpm)",
    "sensor_19": "PCNfR_dmd - Demanded corrected fan speed (rpm)",
    "sensor_20": "W31 - HPT coolant bleed flow (lbm/s)",
    "sensor_21": "W32 - LPT coolant bleed flow (lbm/s)",
}




