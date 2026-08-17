"""
run_anomaly_detection.py
========================
CLI entry point for Person 3: Anomaly & Fault Detection on NASA C-MAPSS Engines.

Usage
-----
    # Run anomaly detection on a single dataset (e.g. FD001)
    python run_anomaly_detection.py --dataset FD001

    # Run anomaly detection on all four datasets
    python run_anomaly_detection.py --dataset all

    # Custom contamination rate and number of estimators
    python run_anomaly_detection.py --dataset all --contamination 0.08 --n_estimators 150
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

# Ensure project root and src/ are importable
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import VALID_SUBSETS, ISOLATION_FOREST_PARAMS
from src.anomaly_pipeline import run_anomaly_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NASA C-MAPSS Anomaly & Fault Detection Pipeline (Person 3)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset", "-d",
        type=str,
        default="FD001",
        help="Dataset to process: FD001, FD002, FD003, FD004, or 'all'",
    )
    parser.add_argument(
        "--contamination", "-c",
        type=float,
        default=ISOLATION_FOREST_PARAMS["contamination"],
        help="Contamination parameter for Isolation Forest (expected anomaly proportion).",
    )
    parser.add_argument(
        "--n_estimators", "-n",
        type=int,
        default=ISOLATION_FOREST_PARAMS["n_estimators"],
        help="Number of trees in Isolation Forest.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Determine datasets to process
    if args.dataset.lower() == "all":
        subsets = VALID_SUBSETS
    else:
        subset = args.dataset.upper()
        if subset not in VALID_SUBSETS:
            print(f"ERROR: Unknown dataset '{args.dataset}'. Choose from {VALID_SUBSETS} or 'all'.")
            sys.exit(1)
        subsets = [subset]

    print("\n" + "=" * 65)
    print("  PERSON 3 – ANOMALY & FAULT DETECTION PIPELINE")
    print(f"  Datasets      : {subsets}")
    print(f"  Contamination : {args.contamination}")
    print(f"  N Estimators  : {args.n_estimators}")
    print("=" * 65 + "\n")

    t_start = time.time()
    all_reports = []
    failed = []

    for subset in subsets:
        try:
            res = run_anomaly_pipeline(
                subset=subset,
                contamination=args.contamination,
                n_estimators=args.n_estimators,
            )
            all_reports.append(res["report"])
        except Exception:
            failed.append(subset)
            print(f"\n[ERROR] Anomaly detection failed for {subset}:")
            traceback.print_exc()

    elapsed = time.time() - t_start

    # Summary Table
    print("\n" + "=" * 80)
    print("  SUMMARY OF ALL ANOMALY DETECTION RUNS")
    print("=" * 80)
    print(
        f"  {'Dataset':<10} {'Engines':>8} {'Cycles':>10} {'Anomalous':>12} "
        f"{'Anom %':>8} {'Mean Score':>12} {'Leading Sensor':<16}"
    )
    print(f"  {'-'*10} {'-'*8} {'-'*10} {'-'*12} {'-'*8} {'-'*12} {'-'*16}")

    for r in all_reports:
        top_s = r["top_contributing_sensors"][0]["sensor"] if r["top_contributing_sensors"] else "N/A"
        print(
            f"  {r['dataset']:<10} {r['total_test_engines']:>8} {r['total_test_cycles']:>10,} "
            f"{r['anomalous_cycles_count']:>12,} {r['anomalous_cycles_pct']:>7.1f}% "
            f"{r['mean_anomaly_score_fleet']:>12.1f} {top_s:<16}"
        )

    print(f"\n  Total time elapsed: {elapsed:.1f}s")
    if failed:
        print(f"  [WARNING] Failed datasets: {failed}")
    print("=" * 80 + "\n")

    if failed and len(failed) == len(subsets):
        sys.exit(1)


if __name__ == "__main__":
    main()
