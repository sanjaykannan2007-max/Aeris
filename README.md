# PS-S02 – Aircraft Engine Health Monitoring: Data Engineering Module

> **Person 1 – Data Engineering** | NASA C-MAPSS Dataset (FD001–FD004)

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
from src.data_loader import load_features, load_scaler

# Feature-engineered data with rolling stats
train_feat = load_features("FD001", split="train")
test_feat  = load_features("FD001", split="test")

# For unsupervised anomaly detection, use sensor columns (already normalised)
sensor_cols = [c for c in train_feat.columns if c.startswith("sensor_")]
X = train_feat[sensor_cols]
```

### Direct CSV Loading (no Python package needed)

```python
import pandas as pd

train_df = pd.read_csv("data/processed/processed_train_FD001.csv")
test_df  = pd.read_csv("data/processed/processed_test_FD001.csv")
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
