"""
run_pipeline.py
===============
CLI entry point for the C-MAPSS Data Engineering Pipeline.

Usage
-----
    # Process a single dataset
    python run_pipeline.py --dataset FD001

    # Process all four datasets
    python run_pipeline.py --dataset all

    # Override defaults
    python run_pipeline.py --dataset all --max_rul 130 --window 7 --scaler standard
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

# Make sure src/ is importable when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import VALID_SUBSETS, MAX_RUL, WINDOW_SIZE, SCALER_TYPE
from src.dataset_pipeline import run_pipeline
from src.sensor_analysis  import save_sensor_statistics
from src.eda_plots        import run_cross_dataset_eda


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NASA C-MAPSS Data Engineering Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset", "-d",
        type=str,
        required=True,
        help="Dataset to process: FD001, FD002, FD003, FD004, or 'all'",
    )
    parser.add_argument(
        "--max_rul",
        type=int,
        default=MAX_RUL,
        help="RUL cap (piece-wise linear). Set to 0 to disable capping.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=WINDOW_SIZE,
        help="Rolling window size for feature engineering (cycles).",
    )
    parser.add_argument(
        "--scaler",
        type=str,
        default=SCALER_TYPE,
        choices=["minmax", "standard"],
        help="Scaler type: 'minmax' (MinMaxScaler) or 'standard' (StandardScaler).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Determine which subsets to process
    if args.dataset.lower() == "all":
        subsets = VALID_SUBSETS
    else:
        subset = args.dataset.upper()
        if subset not in VALID_SUBSETS:
            print(f"ERROR: Unknown dataset '{args.dataset}'. Choose from {VALID_SUBSETS} or 'all'.")
            sys.exit(1)
        subsets = [subset]

    print("\n" + "=" * 65)
    print("  NASA C-MAPSS DATA ENGINEERING PIPELINE")
    print(f"  Datasets : {subsets}")
    print(f"  MAX_RUL  : {args.max_rul}")
    print(f"  Window   : {args.window}")
    print(f"  Scaler   : {args.scaler}")
    print("=" * 65 + "\n")

    t_total   = time.time()
    all_results   = {}
    all_sensor_stats = []
    all_train_dfs = {}
    failed        = []

    for subset in subsets:
        try:
            result = run_pipeline(
                subset,
                max_rul     = args.max_rul,
                window_size = args.window,
                scaler_type = args.scaler,
            )
            all_results[subset]   = result
            all_sensor_stats.append(result["sensor_stats"])
            all_train_dfs[subset] = result["train_df"]
        except Exception:
            failed.append(subset)
            print(f"\n[ERROR] Pipeline failed for {subset}:")
            traceback.print_exc()

    # ------------------------------------------------------------------ #
    # Cross-dataset EDA (only if more than one succeeded)
    # ------------------------------------------------------------------ #
    if len(all_train_dfs) > 1:
        print("\nGenerating cross-dataset comparison plots...")
        try:
            run_cross_dataset_eda(all_train_dfs)
        except Exception:
            print("[WARNING] Cross-dataset EDA failed:")
            traceback.print_exc()

    # ------------------------------------------------------------------ #
    # Combined sensor statistics
    # ------------------------------------------------------------------ #
    if all_sensor_stats:
        print("\nSaving combined sensor statistics...")
        try:
            save_sensor_statistics(all_sensor_stats)
        except Exception:
            print("[WARNING] Could not save sensor statistics:")
            traceback.print_exc()

    # ------------------------------------------------------------------ #
    # Summary table
    # ------------------------------------------------------------------ #
    elapsed = time.time() - t_total
    print("\n" + "=" * 65)
    print("  PIPELINE SUMMARY")
    print("=" * 65)
    print(f"  {'Dataset':<10} {'Status':<12} {'Train Rows':>12} {'Test Rows':>12} {'Engines':>10}")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*10}")

    for subset in subsets:
        if subset in failed:
            print(f"  {subset:<10} {'FAILED':<12}")
        else:
            r = all_results[subset]["dataset_report"]
            status = "OK"
            print(
                f"  {subset:<10} {status:<12} "
                f"{r['train_rows']:>12,} {r['test_rows']:>12,} {r['train_engines']:>10}"
            )

    print(f"\n  Total runtime: {elapsed:.1f}s")
    if failed:
        print(f"\n  [WARNING] Failed subsets: {failed}")
    print("=" * 65 + "\n")

    if failed and len(failed) == len(subsets):
        sys.exit(1)


if __name__ == "__main__":
    main()
