"""
run_maintenance_advisor.py
==========================
CLI entry point for Person 4: Integration & Maintenance Recommendation Pipeline.

Usage
-----
    # Run integration on a single dataset
    python run_maintenance_advisor.py --dataset FD001

    # Run integration on all four datasets
    python run_maintenance_advisor.py --dataset all

    # Run integration on all datasets and launch REST API server
    python run_maintenance_advisor.py --dataset all --serve --port 8000
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import VALID_SUBSETS
from src.integration_pipeline import run_integration_pipeline
from src.api import run_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NASA C-MAPSS Integrated Health Assessment & Maintenance Decision Pipeline (Person 4)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset", "-d",
        type=str,
        default="FD001",
        help="Dataset to process: FD001, FD002, FD003, FD004, or 'all'",
    )
    parser.add_argument(
        "--model_type", "-m",
        type=str,
        default="random_forest",
        choices=["random_forest", "xgboost"],
        help="RUL model to integrate with.",
    )
    parser.add_argument(
        "--serve", "-s",
        action="store_true",
        help="Launch the REST API backend server after generating datasets.",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind the REST API server to.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Determine datasets
    if args.dataset.lower() == "all":
        subsets = VALID_SUBSETS
    else:
        subset = args.dataset.upper()
        if subset not in VALID_SUBSETS:
            print(f"ERROR: Unknown dataset '{args.dataset}'. Choose from {VALID_SUBSETS} or 'all'.")
            sys.exit(1)
        subsets = [subset]

    print("\n" + "=" * 65)
    print("  PERSON 4 – INTEGRATION & MAINTENANCE ADVISORY PIPELINE")
    print(f"  Datasets    : {subsets}")
    print(f"  RUL Model   : {args.model_type.upper()}")
    print(f"  Serve API   : {args.serve}")
    print("=" * 65 + "\n")

    t_start = time.time()
    all_reports = []
    failed = []

    for subset in subsets:
        try:
            res = run_integration_pipeline(
                subset=subset,
                rul_model_type=args.model_type,
            )
            all_reports.append(res["report"])
        except Exception:
            failed.append(subset)
            print(f"\n[ERROR] Integration pipeline failed for {subset}:")
            traceback.print_exc()

    elapsed = time.time() - t_start

    # Print Combined Fleet Health Summary Table
    print("\n" + "=" * 80)
    print("  FLEET HEALTH & MAINTENANCE DECISION SUMMARY (ALL DATASETS)")
    print("=" * 80)
    print(
        f"  {'Dataset':<10} {'Engines':>8} {'Healthy':>10} {'Monitor':>10} "
        f"{'Maint Req':>12} {'Critical':>10} {'Mean RUL':>12} {'Mean Anom':>12}"
    )
    print(f"  {'-'*10} {'-'*8} {'-'*10} {'-'*10} {'-'*12} {'-'*10} {'-'*12} {'-'*12}")

    for r in all_reports:
        hd = r["health_distribution"]
        print(
            f"  {r['dataset']:<10} {r['total_fleet_engines']:>8} "
            f"{hd['HEALTHY']['count']:>10} {hd['MONITOR']['count']:>10} "
            f"{hd['MAINTENANCE_REQUIRED']['count']:>12} {hd['CRITICAL']['count']:>10} "
            f"{r['mean_predicted_rul_fleet']:>12.1f} {r['mean_anomaly_score_fleet']:>12.1f}"
        )

    print(f"\n  Total processing time: {elapsed:.1f}s")
    if failed:
        print(f"  [WARNING] Failed datasets: {failed}")
    print("=" * 80 + "\n")

    # If --serve requested, launch the API server
    if args.serve:
        run_server(port=args.port)


if __name__ == "__main__":
    main()
