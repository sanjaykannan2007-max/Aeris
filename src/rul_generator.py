"""
rul_generator.py
================
Calculates Remaining Useful Life (RUL) labels for training and test data.

RUL Definition
--------------
For training data:
    RUL(engine e, cycle t) = max_cycle(e) - t

This is the "true" piece-wise RUL based on the run-to-failure data.

Optional capping (piece-wise linear RUL):
    RUL_capped = min(RUL, MAX_RUL)

For test data:
    The raw RUL file contains the true RUL at the LAST observed cycle.
    We extend this backwards per cycle:
        RUL at cycle t_last - k  =  true_RUL + k

Public API
----------
    add_rul_to_train(df, max_rul)          -> pd.DataFrame
    add_rul_to_test(df, rul_values, max_rul) -> pd.DataFrame
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    MAX_RUL,
    RUL_COL,
    RUL_CAPPED_COL,
)


def add_rul_to_train(
    df: pd.DataFrame,
    max_rul: int = MAX_RUL,
) -> pd.DataFrame:
    """
    Append RUL and RUL_capped columns to the training DataFrame.

    The RUL is computed purely from training data for each engine independently.
    No information from test data is used here (data-leakage prevention).

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned training DataFrame with engine_id and cycle columns.
    max_rul : int
        Cap value. Set to None or 0 to disable capping.

    Returns
    -------
    pd.DataFrame
        Original DataFrame with two new columns appended:
        - 'RUL'        : raw, uncapped remaining useful life
        - 'RUL_capped' : capped at max_rul (piece-wise linear)
    """
    df = df.copy()

    # Max cycle per engine = last observed cycle = failure cycle in training set.
    max_cycles = (
        df.groupby(ENGINE_ID_COL)[CYCLE_COL]
        .max()
        .rename("max_cycle")
    )

    df = df.merge(max_cycles, on=ENGINE_ID_COL, how="left")
    df[RUL_COL] = df["max_cycle"] - df[CYCLE_COL]
    df.drop(columns=["max_cycle"], inplace=True)

    # Capped RUL (piece-wise linear)
    if max_rul and max_rul > 0:
        df[RUL_CAPPED_COL] = df[RUL_COL].clip(upper=max_rul)
    else:
        df[RUL_CAPPED_COL] = df[RUL_COL]

    # Validation
    assert (df[RUL_COL] >= 0).all(), "Negative RUL found in training data!"
    assert (df[RUL_CAPPED_COL] >= 0).all(), "Negative capped RUL found in training data!"

    print(f"  [rul] Train RUL stats: min={df[RUL_COL].min()}, "
          f"max={df[RUL_COL].max()}, mean={df[RUL_COL].mean():.1f} | "
          f"capped_max={df[RUL_CAPPED_COL].max()}")

    return df


def add_rul_to_test(
    df: pd.DataFrame,
    rul_values: np.ndarray,
    max_rul: int = MAX_RUL,
) -> pd.DataFrame:
    """
    Append RUL and RUL_capped columns to the test DataFrame.

    The RUL ground-truth file provides one value per test engine:
    the true RUL AT THE LAST OBSERVED CYCLE.
    We reconstruct the full per-cycle RUL by back-filling from the last cycle.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned test DataFrame with engine_id and cycle columns.
    rul_values : np.ndarray
        Array of shape (n_test_engines,) from load_rul_file().
        rul_values[i] is the true RUL of the (i+1)-th test engine at its
        last observed cycle.
    max_rul : int
        Cap value for RUL_capped column.

    Returns
    -------
    pd.DataFrame
        Test DataFrame with RUL and RUL_capped columns.
    """
    df = df.copy()

    engine_ids = sorted(df[ENGINE_ID_COL].unique())

    if len(engine_ids) != len(rul_values):
        raise ValueError(
            f"Number of test engines ({len(engine_ids)}) does not match "
            f"number of RUL values ({len(rul_values)})."
        )

    # Map engine_id → true RUL at last cycle
    engine_rul_at_last = dict(zip(engine_ids, rul_values))

    # For each engine, last_cycle is the max cycle in test data.
    # RUL at cycle t = true_RUL_at_last + (last_cycle - t)
    max_cycles = df.groupby(ENGINE_ID_COL)[CYCLE_COL].max().to_dict()

    def compute_rul_row(row):
        eng     = row[ENGINE_ID_COL]
        cycle   = row[CYCLE_COL]
        last_c  = max_cycles[eng]
        true_rul_at_last = engine_rul_at_last[eng]
        return true_rul_at_last + (last_c - cycle)

    df[RUL_COL] = df.apply(compute_rul_row, axis=1).astype(int)

    if max_rul and max_rul > 0:
        df[RUL_CAPPED_COL] = df[RUL_COL].clip(upper=max_rul)
    else:
        df[RUL_CAPPED_COL] = df[RUL_COL]

    assert (df[RUL_COL] >= 0).all(), "Negative RUL found in test data!"

    print(f"  [rul] Test  RUL stats: min={df[RUL_COL].min()}, "
          f"max={df[RUL_COL].max()}, mean={df[RUL_COL].mean():.1f} | "
          f"capped_max={df[RUL_CAPPED_COL].max()}")

    return df
