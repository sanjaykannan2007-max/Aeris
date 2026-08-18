"""
fleet_risk.py
=============
Portfolio-level fleet risk aggregation using Monte Carlo simulation.

Simulates fleet health trajectories forward over calendar horizons (3, 7, 14, 30, 60 days)
incorporating correlated fleet shocks and shop capacity limits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, List

from src.config import SENSOR_SUBSYSTEM
from src.uncertainty import ConformalRUL

CORRELATION = 0.25  # Fleet-wide common shock factor


def _subsystem_of(fault_text: str) -> str:
    """Map primary fault mode string to subsystem."""
    for tag, subsystem in SENSOR_SUBSYSTEM.items():
        if tag.lower() in str(fault_text).lower():
            return subsystem
    return "Compressor"


def simulate_fleet(
    fleet_records: List[Dict[str, Any]],
    conformal: ConformalRUL | None = None,
    horizons: Tuple[int, ...] = (3, 7, 14, 30, 60),
    cycles_per_day: float = 2.0,
    n_sims: int = 4000,
    seed: int = 42,
    shop_capacity: int = 6,
) -> Dict[str, Any]:
    """
    Simulate the fleet forward across specified calendar day horizons.
    """
    if conformal is None:
        conformal = ConformalRUL()

    n_engines = len(fleet_records)
    if n_engines == 0:
        return {"engines": 0, "simulations": n_sims, "horizons": []}

    rng = np.random.default_rng(seed)
    preds = np.array([r.get("predicted_RUL", 100.0) for r in fleet_records], dtype=float)

    # Draw conformal samples per engine across simulations
    samples = np.empty((n_engines, n_sims))
    for i, p in enumerate(preds):
        samples[i] = conformal.sample(p, n_sims, rng)

    # Apply correlated fleet shock
    common = rng.normal(0, 1, size=n_sims)
    spread = samples.std(axis=1, keepdims=True)
    samples = samples + CORRELATION * spread * common[None, :]
    samples = np.clip(samples, 0, None)

    subsystems = [_subsystem_of(r.get("primary_fault", "")) for r in fleet_records]

    horizon_results = []
    for days in horizons:
        limit_cycles = days * cycles_per_day
        failed_mask = samples <= limit_cycles    # shape: (n_engines, n_sims)
        per_sim_failures = failed_mask.sum(axis=0)  # shape: (n_sims,)

        exp_failures = failed_mask.mean(axis=1)    # per engine

        # Risk concentration by subsystem
        by_subsystem: Dict[str, float] = {}
        for sub, e_fail in zip(subsystems, exp_failures):
            by_subsystem[sub] = by_subsystem.get(sub, 0.0) + float(e_fail)

        tot_sub = sum(by_subsystem.values()) or 1.0
        concentration = sorted(
            [
                {
                    "subsystem": s,
                    "expected_events": round(v, 2),
                    "share_pct": round((v / tot_sub) * 100.0, 1),
                }
                for s, v in by_subsystem.items() if v > 0.005
            ],
            key=lambda x: -x["expected_events"],
        )

        # Top contributing risk engines
        top_contributors = sorted(
            [
                {
                    "engine_id": r.get("engine_id", 0),
                    "engine_id_code": r.get("engine_id_code", f"AE-{r.get('engine_id', 0):04d}-L"),
                    "health_status": r.get("engine_health_status", "HEALTHY"),
                    "predicted_RUL": float(r.get("predicted_RUL", 100)),
                    "failure_probability": round(float(p_fail), 3),
                    "subsystem": sub,
                }
                for r, p_fail, sub in zip(fleet_records, exp_failures, subsystems)
                if p_fail > 0.01
            ],
            key=lambda x: -x["failure_probability"],
        )[:12]

        # Exceedance curve (probability of >= k failures)
        max_k = int(max(10, np.percentile(per_sim_failures, 99) + 2))
        exceedance = [
            {
                "at_least": k,
                "probability_pct": round(float(np.mean(per_sim_failures >= k)) * 100.0, 1),
            }
            for k in range(1, max_k + 1)
        ]

        over_cap = per_sim_failures > shop_capacity
        shortfall = np.maximum(per_sim_failures - shop_capacity, 0)

        horizon_results.append({
            "horizon_days": days,
            "horizon_cycles": int(round(limit_cycles)),
            "probability_any_grounding_pct": round(float(np.mean(per_sim_failures >= 1)) * 100.0, 1),
            "probability_two_or_more_pct": round(float(np.mean(per_sim_failures >= 2)) * 100.0, 1),
            "expected_groundings": round(float(per_sim_failures.mean()), 2),
            "p50_groundings": int(np.percentile(per_sim_failures, 50)),
            "p90_groundings": int(np.percentile(per_sim_failures, 90)),
            "worst_case_p99": int(np.percentile(per_sim_failures, 99)),
            "shop_capacity": shop_capacity,
            "probability_over_capacity_pct": round(float(np.mean(over_cap)) * 100.0, 1),
            "expected_capacity_shortfall": round(float(shortfall.mean()), 2),
            "exceedance": exceedance,
            "concentration": concentration,
            "top_contributors": top_contributors,
        })

    return {
        "engines": n_engines,
        "simulations": n_sims,
        "cycles_per_day": cycles_per_day,
        "correlation_factor": CORRELATION,
        "shop_capacity": shop_capacity,
        "horizons": horizon_results,
    }
