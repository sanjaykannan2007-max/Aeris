# PS-S02 – Aircraft Engine Health Monitoring & Predictive Maintenance

> **Person 1 – Data Engineering** & **Person 2 – RUL & Engine Health Prediction** | NASA C-MAPSS Dataset (FD001–FD004)

---

## Table of Contents

1. [What is C-MAPSS?](#what-is-c-mapss)
2. [Dataset Variants (FD001–FD004)](#dataset-variants)
3. [Dataset Structure & Columns](#dataset-structure)
4. [Project Structure](#project-structure)
5. [Installation](#installation)
6. [How to Run the Pipeline](#how-to-run-the-pipeline)
7. [Data Cleaning Process](#data-cleaning-process)
8. [RUL Calculation](#rul-calculation)
9. [Feature Engineering](#feature-engineering)
10. [Normalisation](#normalisation)
11. [Data Leakage Prevention](#data-leakage-prevention)
12. [Generated Files](#generated-files)
13. [How Team Members Import the Data](#how-team-members-import-the-data)
14. [Configuration Reference](#configuration-reference)
15. [Assumptions Made](#assumptions-made)

---

## What is C-MAPSS?

**C-MAPSS** (Commercial Modular Aero-Propulsion System Simulation) is a NASA simulation tool used to model turbofan engine degradation. The dataset published alongside the paper:

> A. Saxena, K. Goebel, D. Simon, and N. Eklund, *"Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation"*, PHM08, Denver CO, 2008.

provides run-to-failure time series for four different operating scenarios. Each engine starts healthy and degrades until failure. The task is to predict **Remaining Useful Life (RUL)** — how many cycles are left before failure.

---

## Dataset Variants

| Dataset | Conditions | Fault Modes | Train Engines | Test Engines |
|---------|-----------|-------------|---------------|--------------|
| **FD001** | 1 (Sea Level) | HPC Degradation | 100 | 100 |
| **FD002** | 6 | HPC Degradation | 260 | 259 |
| **FD003** | 1 (Sea Level) | HPC + Fan Degradation | 100 | 100 |
| **FD004** | 6 | HPC + Fan Degradation | 248 | 249 |

- **Single condition** (FD001, FD003): engines always operate at sea level — easier to model.
- **Six conditions** (FD002, FD004): engines switch between operating regimes — requires handling multi-modal data (clustering by operating condition is often useful).
- **Single fault** (FD001, FD002): only High Pressure Compressor (HPC) degradation.
- **Dual fault** (FD003, FD004): both HPC and Fan degradation — harder prediction task.

---

## Dataset Structure

Each raw text file has **26 space-separated columns** (no header):

| Column Index | Column Name | Description |
|---|---|---|
| 1 | `engine_id` | Engine unit number |
| 2 | `cycle` | Operating cycle (time step) |
| 3 | `setting_1` | Operational setting 1 |
| 4 | `setting_2` | Operational setting 2 |
| 5 | `setting_3` | Operational setting 3 |
| 6–26 | `sensor_1` … `sensor_21` | Sensor measurements |

**Training files**: Engine runs until failure. The last cycle = failure cycle.  
**Test files**: Engine run ends **before** failure. True RUL at last cycle is in `RUL_FDxxx.txt`.  
**RUL files**: One integer per line = true RUL of that test engine at its last observed cycle.

### Known Sensor Characteristics

Some sensors are constant or near-constant across all datasets (sensor_1, sensor_5, sensor_6, sensor_10, sensor_16, sensor_18, sensor_19 are commonly constant in FD001). These are documented per-dataset in `outputs/statistics/sensor_statistics.csv` — they are **not dropped** from files but are flagged for downstream team members.

---

## Project Structure

```
Parallax/
│
├── data/
│   ├── raw/             ← Original C-MAPSS .txt files (copied here)
│   ├── cleaned/         ← After quality checks (NaN, dup, inf detection)
│   ├── processed/       ← Normalised + RUL-labelled data  ← TEAM USE THIS
│   └── features/        ← Rolling stats, lag features      ← TEAM USE THIS
│
├── notebooks/
│   └── eda.ipynb        ← Interactive EDA notebook
│
├── src/
│   ├── __init__.py
│   ├── config.py           ← All global settings
│   ├── data_loader.py      ← Raw & processed file loaders
│   ├── data_cleaner.py     ← Quality checks & cleaning
│   ├── rul_generator.py    ← RUL labelling (train + test)
│   ├── preprocessing.py    ← Scaling (fit train, apply both)
│   ├── sensor_analysis.py  ← Per-sensor statistics
│   ├── eda_plots.py        ← All EDA visualisations
│   ├── feature_engineering.py ← Rolling features, lag, pct_change
│   └── dataset_pipeline.py    ← Full pipeline for one subset
│
├── models/
│   └── scalers/
│       ├── scaler_FD001.pkl
│       ├── scaler_FD002.pkl
│       ├── scaler_FD003.pkl
│       └── scaler_FD004.pkl
│
├── outputs/
│   ├── plots/           ← 40+ PNG plots at 300 dpi
│   ├── statistics/
│   │   └── sensor_statistics.csv
│   └── reports/
│       ├── report_FD001.txt / .json
│       ├── report_FD002.txt / .json
│       ├── report_FD003.txt / .json
│       └── report_FD004.txt / .json
│
├── run_pipeline.py      ← CLI entry point
├── requirements.txt
└── README.md
```

---

## Installation

```bash
# 1. Clone / navigate to project directory
cd path/to/Parallax

# 2. (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

# 3. Install dependencies
pip install -r requirements.txt
```

> **Python version**: 3.8 or higher recommended.

---

## How to Run the Pipeline

### Run all four datasets (recommended)

```bash
python run_pipeline.py --dataset all
```

### Run a single dataset

```bash
python run_pipeline.py --dataset FD001
python run_pipeline.py --dataset FD002
python run_pipeline.py --dataset FD003
python run_pipeline.py --dataset FD004
```

### Override defaults

```bash
# Custom RUL cap, window size, and scaler
python run_pipeline.py --dataset all --max_rul 130 --window 7 --scaler standard
```

| Argument | Default | Description |
|---|---|---|
| `--dataset` | (required) | `FD001`–`FD004` or `all` |
| `--max_rul` | `125` | RUL cap value |
| `--window` | `5` | Rolling window size in cycles |
| `--scaler` | `minmax` | `minmax` or `standard` |

---

## Person 2 – RUL & Engine Health Prediction Pipeline

Run model training, evaluation, health score computation, and prediction exports:

```bash
# Train both Random Forest & XGBoost models on all datasets
python train_rul_models.py --dataset all --model both

# Train XGBoost on a single dataset
python train_rul_models.py --dataset FD001 --model xgboost
```

### Benchmark Model Evaluation Metrics (Test Engines at Last Observed Cycle)

| Dataset | Model | Final MAE | Final RMSE | Final $R^2$ | NASA Score |
|---|---|---|---|---|---|
| **FD001** | **XGBoost** | **12.12** | **17.37** | **0.812** | **933.3** |
| **FD001** | Random Forest | 12.64 | 18.03 | 0.797 | 1103.5 |
| **FD002** | **Random Forest** | **13.16** | **17.11** | **0.841** | **2058.9** |
| **FD002** | XGBoost | 13.22 | 17.24 | 0.839 | 2190.7 |
| **FD003** | **Random Forest** | **13.27** | **19.25** | **0.758** | **1688.0** |
| **FD003** | XGBoost | 13.95 | 19.56 | 0.750 | 1644.1 |
| **FD004** | **XGBoost** | **14.08** | **19.01** | **0.804** | **2879.4** |
| **FD004** | Random Forest | 14.51 | 19.59 | 0.792 | 3365.6 |


---

## Person 3 – Anomaly & Fault Detection Pipeline

Run Isolation Forest training, 0–100 anomaly scoring, sensor-level z-score deviation ranking, visualizations, and Person 2 integration:

```bash
# Run anomaly detection on all datasets
python run_anomaly_detection.py --dataset all

# Run anomaly detection on a single dataset
python run_anomaly_detection.py --dataset FD001

# Custom hyperparameters
python run_anomaly_detection.py --dataset all --contamination 0.08 --n_estimators 150
```

### Anomaly Detection & Sensor Abnormality Summary

| Dataset | Engines | Test Cycles | Anomalous Cycles (%) | Mean Fleet Score (0-100) | Mean Last-Cycle Score | Leading Abnormal Sensor |
|---|---|---|---|---|---|---|
| **FD001** | 100 | 13,096 | 573 (4.4%) | 26.4 | 30.5 | `sensor_17` (10.7% of anomalies) |
| **FD002** | 259 | 33,991 | 4,492 (13.2%) | 34.8 | 36.1 | `sensor_12` (22.7% of anomalies) |
| **FD003** | 100 | 16,596 | 932 (5.6%) | 20.6 | 23.2 | `sensor_13` (29.8% of anomalies) |
| **FD004** | 248 | 41,214 | 5,594 (13.6%) | 34.8 | 34.7 | `sensor_12` (16.3% of anomalies) |

### Key Anomaly Detection Outputs

1. **Cycle-Level Predictions** (`outputs/predictions/anomaly_predictions_FDxxx.csv`):
   - `anomaly_score`: Calibrated 0–100 normalized score (0 = Nominal, 100 = Critical Anomaly).
   - `anomaly_label`: "Normal" vs "Anomalous".
   - `anomaly_severity`: "Nominal", "Mild Drift", "Moderate Anomaly", "Severe Anomaly".
   - `top_sensor_1..3`, `top_sensor_1..3_zscore`, `top_sensor_1..3_severity`: Ranked sensor deviation degrees.
   - `top_abnormal_sensors`: Human-readable explanation string (e.g. `sensor_11 (+3.42σ, High deviation) | sensor_4 (+2.81σ, High deviation)`).

2. **Engine Fleet Summary** (`outputs/predictions/anomaly_summary_FDxxx.csv`):
   - `last_observed_cycle`, `final_anomaly_score`, `final_anomaly_status`, `total_anomalous_cycles`, `anomaly_cycle_ratio_pct`, `first_anomalous_cycle`, `top_degraded_sensors`.

3. **Integrated Health & Maintenance Assessment** (`outputs/predictions/integrated_engine_health_FDxxx.csv`):
   - Combines Person 2 Predicted RUL + Person 3 Anomaly Score to yield composite actionable recommendations:
     - `CRITICAL: Immediate Maintenance & Grounding Required`
     - `URGENT: Schedule Inspection & Maintenance`
     - `MONITOR: Heightened Telemetry & Vibration Monitoring`
     - `OPERATIONAL: Normal Operating Parameters`

4. **Visualizations** (`outputs/plots/`):
   - `anomaly_score_timeline_FDxxx.png`: Anomaly progression over cycles for sample engines.
   - `anomaly_sensor_highlight_FDxxx.png`: Multi-sensor telemetry with detected anomaly bands shaded in red.
   - `anomaly_scatter_regimes_FDxxx.png`: 2D PCA operational envelope & anomaly boundary.
   - `anomaly_score_distribution_FDxxx.png`: Fleet-wide score histogram with threshold cutoffs.
   - `anomaly_top_sensors_FDxxx.png`: Bar chart ranking leading abnormal sensors.


---

## Person 4 – Integration & Maintenance Recommendation Pipeline

Person 4 unifies Person 2's Predicted RUL with Person 3's Anomaly Scores and abnormal sensor attributions into an authoritative **Fleet Health Assessment & Maintenance Decision Advisory**:

```bash
# Run integration and generate fleet advisory for all datasets
python run_maintenance_advisor.py --dataset all

# Run on a single dataset
python run_maintenance_advisor.py --dataset FD001

# Launch REST API server for UI integration
python run_maintenance_advisor.py --dataset all --serve --port 8000
```

### Fleet Health Assessment & Maintenance Decision Summary (FD001–FD004)

| Dataset | Fleet Engines | HEALTHY (%) | MONITOR (%) | MAINTENANCE REQUIRED (%) | CRITICAL (%) | Mean RUL (cycles) | Mean Anomaly Score |
|---|---|---|---|---|---|---|---|
| **FD001** | 100 | 58 (58.0%) | 16 (16.0%) | 12 (12.0%) | 14 (14.0%) | 78.6 | 30.5 |
| **FD002** | 259 | 105 (40.5%) | 67 (25.9%) | 38 (14.7%) | 49 (18.9%) | 75.3 | 36.1 |
| **FD003** | 100 | 55 (55.0%) | 21 (21.0%) | 15 (15.0%) | 9 (9.0%) | 79.8 | 23.2 |
| **FD004** | 248 | 109 (44.0%) | 61 (24.6%) | 45 (18.1%) | 33 (13.3%) | 80.5 | 34.7 |

### Multi-Factor Decision Framework & Explainability

```
                       ┌───────────────────────────────┐
                       │  Predicted RUL (Person 2)     │
                       │  Anomaly Score (Person 3)     │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       Multi-Factor Health Decision Engine        │
             └────────────────────────┬─────────────────────────┘
                                      │
       ┌──────────────────┬───────────┴───────────┬──────────────────┐
       ▼                  ▼                       ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌───────────────────────┐ ┌──────────────┐
│   HEALTHY    │   │   MONITOR    │   │ MAINTENANCE REQUIRED  │ │   CRITICAL   │
│ RUL ≥ 75     │   │ 45 ≤ RUL < 75│   │ 20 ≤ RUL < 45         │ │ RUL < 20     │
│ Anom < 45    │   │ 45 ≤ Anom <65│   │ 65 ≤ Anom < 80        │ │ Anom ≥ 80    │
└──────┬───────┘   └──────┬───────┘   └───────────┬───────────┘ └──────┬───────┘
       │                  │                       │                    │
       ▼                  ▼                       ▼                    ▼
Normal Flight      Heightened Telemetry   Priority Borescope    Immediate Engine
Operations         & Vibration Sampling   & Overhaul Inspection Grounding & Teardown
```

### Generated Files & Artifacts (Person 4)

1. **Cycle-Level Integrated Telemetry** (`outputs/predictions/cycle_integrated_health_FDxxx.csv`):
   - Full cycle-by-cycle dataset containing `engine_id`, `cycle`, `predicted_RUL`, `true_RUL`, `rul_health_score`, `anomaly_score`, `anomaly_label`, `anomaly_severity`, `top_abnormal_sensors`, `engine_health_status`, `composite_health_score`, `risk_level`, `maintenance_recommendation`, `decision_reason`, `targeted_action_items`, `impacted_components`, `urgency_window_cycles`.

2. **Fleet Maintenance Advisory** (`outputs/predictions/fleet_maintenance_advisory_FDxxx.csv` & `.json`):
   - Engine-level latest observed operational state and direct UI dashboard payload.

3. **Executive Health Reports** (`outputs/reports/fleet_health_report_FDxxx.json` & `.txt`):
   - Fleet-wide status distributions, grounding lists, and executive statistics.

4. **Integration Visualizations (300 DPI)** (`outputs/plots/`):
   - `integration_rul_timeline_FDxxx.png`: Synchronized RUL degradation vs Anomaly score timeline.
   - `integration_health_distribution_FDxxx.png`: Fleet health stage distribution.
   - `integration_maintenance_matrix_FDxxx.png`: Actionable maintenance directives breakdown.
   - `integration_rul_vs_anomaly_FDxxx.png`: 2D Engine Health Risk Quadrant scatter plot.

### REST API Endpoints for UI Dashboard

Launch the REST server via `python run_maintenance_advisor.py --serve --port 8000`:

| Endpoint | Method | Description | Example Query |
|---|---|---|---|
| `/health` | `GET` | Service status check | `curl http://localhost:8000/health` |
| `/api/fleet/summary` | `GET` | Fleet health KPIs and engine list | `curl http://localhost:8000/api/fleet/summary?dataset=FD001` |
| `/api/engine/{id}` | `GET` | Engine latest diagnostic & recommendation | `curl http://localhost:8000/api/engine/20?dataset=FD001` |
| `/api/engine/{id}/history` | `GET` | Full historical cycle trajectory | `curl http://localhost:8000/api/engine/20/history?dataset=FD001` |
| `/api/predict` | `POST` | Live telemetry real-time inference | `curl -X POST http://localhost:8000/api/predict -d '{"engine_id":12,"cycle":180,"predicted_rul":35,"anomaly_score":82}'` |




---

## Data Cleaning Process

The cleaning step (`src/data_cleaner.py`) performs the following checks **without blindly deleting columns**:

| Check | Action |
|---|---|
| Missing / NaN values | Count and report; rows fully NaN are dropped |
| Infinite values | Replaced with NaN, then counted and reported |
| Duplicate rows | Detected and removed |
| Invalid cycle / engine ID | Negative or zero values are flagged in the report |
| Constant sensors | Variance ≤ 1e-10 → flagged as "constant" |
| Near-constant sensors | Variance ≤ 1e-3 → flagged as "near_constant" |
| Noisy sensors | Coefficient of Variation (σ/μ) computed and reported |

All findings are saved to:
- `outputs/reports/report_FDxxx.txt` (human readable)
- `outputs/reports/report_FDxxx.json` (machine readable)
- `outputs/statistics/sensor_statistics.csv` (per-sensor table)

---

## RUL Calculation

### Training data

```
RUL(engine e, cycle t) = max_cycle(e) - t
```

This is calculated per engine independently using only training data.

### Capped RUL (Piece-Wise Linear)

```
RUL_capped = min(RUL, MAX_RUL)    # default MAX_RUL = 125
```

Capping prevents the model from trying to learn differences between "200 cycles remaining" and "300 cycles remaining" — both are "healthy engine, not close to failure". This is standard practice in C-MAPSS literature.

> **Both `RUL` and `RUL_capped` are preserved in processed files.** Use `RUL_capped` for model training (recommended), `RUL` for analysis.

### Test data

The `RUL_FDxxx.txt` file provides the **true RUL at the last observed cycle** for each test engine.

For the full time series:
```
RUL at cycle t = true_RUL_at_last_cycle + (last_cycle - t)
```

---

## Feature Engineering

All features are calculated **per engine** to prevent leakage between engines:

| Feature | Formula |
|---|---|
| `sensor_N_rolling_mean` | Mean over last `WINDOW_SIZE` cycles |
| `sensor_N_rolling_std` | Std over last `WINDOW_SIZE` cycles |
| `sensor_N_diff` | `sensor[t] - sensor[t-1]` |
| `sensor_N_pct_change` | `(sensor[t] - sensor[t-1]) / |sensor[t-1]| × 100` |
| `setting_N_rolling_mean` | Mean over last `WINDOW_SIZE` cycles |

Window size is configurable via `--window` (default: 5).

**Anti-leakage**: Rolling windows use `min_periods=1` and only look backward. No future cycles are referenced.

---

## Normalisation

| Step | Details |
|---|---|
| Scaler fitted on | **Training data only** |
| Applied to | Both training and test data |
| Scaler type | `MinMaxScaler` (default) or `StandardScaler` |
| Columns scaled | All 3 operational settings + all 21 sensors |
| Saved as | `models/scalers/scaler_FDxxx.pkl` |

```python
# Example: load and use the scaler
from src.data_loader import load_scaler
scaler = load_scaler("FD001")
scaler.inverse_transform(predictions)  # de-normalise model output
```

---

## Data Leakage Prevention

All decisions are documented here:

| Rule | Implementation |
|---|---|
| Scaler fitted on training only | `fit_and_save_scaler()` is called with `train_df` only; `apply_scaler()` is used for test data |
| RUL computed from training data only | `add_rul_to_train()` uses `max_cycle` per engine from training set |
| Rolling features computed per engine | `groupby(engine_id)` before rolling — cycle 1 of engine 2 never sees engine 1's data |
| Test RUL from ground-truth file | Ground-truth RUL values are used, not derived from test statistics |
| No train/test mixing | Data is kept in separate DataFrames throughout the pipeline |

---

## Generated Files

After running `python run_pipeline.py --dataset all`, the following files are created:

### Processed data (normalised + RUL-labelled)
```
data/processed/
├── processed_train_FD001.csv
├── processed_test_FD001.csv
├── processed_train_FD002.csv
├── processed_test_FD002.csv
├── processed_train_FD003.csv
├── processed_test_FD003.csv
├── processed_train_FD004.csv
└── processed_test_FD004.csv
```

### Feature-engineered data
```
data/features/
├── features_train_FD001.csv
├── features_test_FD001.csv
├── features_train_FD002.csv
├── features_test_FD002.csv
├── features_train_FD003.csv
├── features_test_FD003.csv
├── features_train_FD004.csv
└── features_test_FD004.csv
```

### Scalers
```
models/scalers/
├── scaler_FD001.pkl
├── scaler_FD002.pkl
├── scaler_FD003.pkl
└── scaler_FD004.pkl
```

### Plots (40+ images)
```
outputs/plots/
├── FD001_sensor_distributions.png
├── FD001_sensor_violin.png
├── FD001_correlation_matrix.png
├── FD001_sensor_variance.png
├── FD001_sensor_trends.png
├── FD001_degradation_curves.png
├── FD001_rul_distribution.png
├── FD001_operating_conditions.png
├── FD001_engine_lifetime.png
├── FD001_sensor_statistics_heatmap.png
├── FD002_*.png  (same 10 plots)
├── FD003_*.png  (same 10 plots)
├── FD004_*.png  (same 10 plots)
├── cross_dataset_comparison.png
└── cross_dataset_sensor_correlation.png
```

---

## How Team Members Import the Data

### Person 2 – RUL Prediction

```python
import sys
sys.path.insert(0, "path/to/Parallax")  # or add to PYTHONPATH

from src.data_loader import load_processed_data, load_scaler

# Load training data with RUL labels
train_df = load_processed_data("FD001", split="train")
test_df  = load_processed_data("FD001", split="test")

# Columns available: engine_id, cycle, setting_1..3, sensor_1..21, RUL, RUL_capped
# Use RUL_capped for training your model (recommended)
X_train = train_df.drop(columns=["engine_id", "cycle", "RUL", "RUL_capped"])
y_train = train_df["RUL_capped"]

# Load scaler to inverse-transform predictions
scaler = load_scaler("FD001")
```

### Person 3 – Anomaly / Fault Detection

```python
from src.anomaly_detector import AnomalyDetector
from src.data_loader import load_features

# 1. Load telemetry features
test_feat = load_features("FD001", split="test")

# 2. Load trained Isolation Forest
detector = AnomalyDetector.load("models/anomaly/isolation_forest_FD001.joblib")

# 3. Generate 0-100 anomaly scores and sensor deviations
scored_df = detector.score_and_explain(test_feat, top_n=3)
```

### Person 4 – Health Assessment, Maintenance Decision System & UI

```python
import pandas as pd

# Load the combined health & anomaly dataset
integrated_df = pd.read_csv("outputs/predictions/integrated_engine_health_FD001.csv")

# Available columns for Fleet Dashboard / Maintenance Advisory:
# - engine_id
# - last_observed_cycle
# - predicted_RUL          (Person 2: Remaining Useful Life)
# - health_score           (Person 2: 0-100% health score)
# - health_status          (Person 2: HEALTHY / MONITOR / MAINTENANCE REQUIRED / CRITICAL)
# - final_anomaly_score    (Person 3: 0-100 calibrated anomaly score)
# - final_anomaly_status   (Person 3: Normal / Anomalous)
# - final_anomaly_severity (Person 3: Nominal / Mild Drift / Moderate Anomaly / Severe Anomaly)
# - top_degraded_sensors   (Person 3: e.g. "sensor_11, sensor_4")
# - recommended_action     (Integrated Maintenance Recommendation)

for _, row in integrated_df.head(5).iterrows():
    print(f"Engine #{int(row['engine_id'])} | RUL: {row['predicted_RUL']:.1f} cycles | "
          f"Anomaly: {row['final_anomaly_score']:.1f} ({row['final_anomaly_status']}) | "
          f"Top Degraded: {row['top_degraded_sensors']} -> {row['recommended_action']}")
```

### Direct CSV Loading (no Python package needed)

```python
import pandas as pd

# Anomaly cycle predictions
anom_df = pd.read_csv("outputs/predictions/anomaly_predictions_FD001.csv")

# Fleet health overview
fleet_df = pd.read_csv("outputs/predictions/integrated_engine_health_FD001.csv")
```


---

## Configuration Reference

Edit `src/config.py` to change pipeline-wide settings:

| Setting | Default | Description |
|---|---|---|
| `MAX_RUL` | `125` | RUL cap in cycles |
| `WINDOW_SIZE` | `5` | Rolling window size |
| `SCALER_TYPE` | `"minmax"` | Normalisation method |
| `CONSTANT_VARIANCE_THRESHOLD` | `1e-10` | Below this → constant sensor |
| `NEAR_CONSTANT_VARIANCE_THRESHOLD` | `1e-3` | Below this → near-constant sensor |
| `CYCLE_CORR_THRESHOLD` | `0.10` | Min \|corr with cycle\| for "useful" sensor |
| `PLOT_DPI` | `300` | Plot resolution |

---

## Assumptions Made

1. **RUL cap = 125**: This is the most commonly used value in C-MAPSS literature. It forces the model to treat all early-life cycles equivalently. This is configurable via `--max_rul`.

2. **Sensors are NOT dropped**: Constant/near-constant sensors are flagged but kept in all output files. Downstream team members can filter using `sensor_statistics.csv`.

3. **Rolling features start from cycle 1**: `min_periods=1` is used, meaning the first cycle has a rolling mean equal to its own value. This avoids NaN in features.

4. **All 21 sensors are scaled**: Even constant sensors are passed through the scaler. They will simply have the same value after scaling and can be ignored by the model.

5. **Operating conditions are NOT cluster-labelled**: For FD002/FD004 (6 conditions), operating condition clustering is documented in the EDA plots but is left to the modelling team to implement if needed.

6. **Test RUL back-propagation**: We assume the test RUL file gives the true RUL at the LAST cycle of each test engine. This is the standard interpretation of the NASA dataset.

---

*Generated by the Data Engineering Pipeline for PS-S02 Hackathon Project.*
