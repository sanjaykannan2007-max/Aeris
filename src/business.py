"""
business.py
===========
Maintenance Economics, 5x5 Aviation Safety Risk Assessment, and Cost Optimization.

Calculates planned intervention costs versus unscheduled AOG downtime risks,
determines cost-optimal replacement thresholds, and structures SMS risk ratings.
"""

from __future__ import annotations

from typing import Dict, Any, List
from src.config import COST_MODEL as C, MAINTENANCE_PROTOCOLS, SENSOR_SUBSYSTEM

SEVERITY_ORDER = ["Negligible", "Minor", "Major", "Hazardous", "Catastrophic"]
LIKELIHOOD_ORDER = ["Improbable", "Remote", "Occasional", "Probable", "Frequent"]


def subsystem_of(fault_text: str) -> str:
    """Map fault description to primary physical subsystem."""
    for tag, subsystem in SENSOR_SUBSYSTEM.items():
        if tag.lower() in str(fault_text).lower():
            return subsystem
    return "Compressor"


def protocol_for(subsystem: str) -> Dict[str, Any]:
    return MAINTENANCE_PROTOCOLS.get(subsystem, MAINTENANCE_PROTOCOLS["Unclassified"])


def severity_of(subsystem: str, status: str) -> str:
    """Assess SMS severity level (1-5)."""
    aog_risk = protocol_for(subsystem)["aog_risk"]
    base = {"high": 3, "medium": 2, "low": 1}.get(aog_risk, 2)
    if status == "CRITICAL":
        base += 1
    elif status == "HEALTHY":
        base -= 1
    idx = max(0, min(len(SEVERITY_ORDER) - 1, base))
    return SEVERITY_ORDER[idx]


def likelihood_of(failure_probability: float) -> str:
    for threshold, label in ((0.60, "Frequent"), (0.30, "Probable"), (0.10, "Occasional"), (0.02, "Remote")):
        if failure_probability >= threshold:
            return label
    return "Improbable"


def risk_rating(severity: str, likelihood: str) -> Dict[str, Any]:
    """5x5 SMS Safety Matrix calculation."""
    s = SEVERITY_ORDER.index(severity) + 1
    l = LIKELIHOOD_ORDER.index(likelihood) + 1
    score = s * l
    if score >= 15:
        band, action = "CRITICAL", "Unacceptable — ground until rectified"
    elif score >= 9:
        band, action = "HIGH", "Rectify before next departure"
    elif score >= 5:
        band, action = "MEDIUM", "Schedule within current maintenance window"
    else:
        band, action = "LOW", "Routine surveillance under maintenance program"
    return {"severity": severity, "likelihood": likelihood, "score": score, "band": band, "action": action}


def cost_analysis(rul_predicted: float, failure_probability: float, subsystem: str) -> Dict[str, Any]:
    """Calculate financial tradeoffs: Planned Intervention vs Unscheduled Grounding."""
    proto = protocol_for(subsystem)
    labour_cost = proto["labour_hours"] * C["labour_rate_per_hour"]
    planned_cost = C["planned_shop_visit"] + labour_cost

    unplanned_event_cost = (
        C["unplanned_removal"]
        + (C["aog_per_day"] * C["mean_aog_days_unplanned"])
        + (C["secondary_damage_probability"] * C["secondary_damage_cost"])
        + C["cancellation_cost"]
    )

    expected_unplanned = (failure_probability * unplanned_event_cost) + ((1.0 - failure_probability) * C["planned_shop_visit"])
    expected_savings = expected_unplanned - planned_cost

    return {
        "subsystem": subsystem,
        "protocol_code": proto["code"],
        "labour_hours": proto["labour_hours"],
        "labour_cost": round(labour_cost),
        "planned_intervention_cost": round(planned_cost),
        "unplanned_event_cost": round(unplanned_event_cost),
        "failure_probability": round(failure_probability, 3),
        "expected_cost_if_deferred": round(expected_unplanned),
        "expected_saving": round(expected_savings),
        "days_of_cover": round(rul_predicted / C["cycles_per_day"], 1),
    }


def fleet_cost_summary(engine_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll per-engine economic analysis up to fleet-wide totals."""
    if not engine_records:
        return {"total_engines": 0, "total_expected_savings": 0}

    total_planned = 0
    total_deferred = 0
    savings_list = []
    risk_bands: Dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for eng in engine_records:
        rul = float(eng.get("predicted_RUL", 100))
        anom = float(eng.get("latest_anomaly_score", 0))
        status = str(eng.get("engine_health_status", "HEALTHY"))
        sub = subsystem_of(eng.get("primary_fault", ""))
        
        # Estimate failure probability in next 30 days (60 cycles)
        fail_prob = float(np.clip((60.0 - rul) / 60.0, 0.0, 1.0)) if rul < 60 else 0.02
        if anom > 70:
            fail_prob = max(fail_prob, 0.65)

        c_info = cost_analysis(rul, fail_prob, sub)
        sev = severity_of(sub, status)
        like = likelihood_of(fail_prob)
        r_info = risk_rating(sev, like)

        risk_bands[r_info["band"]] = risk_bands.get(r_info["band"], 0) + 1
        sav = c_info["expected_saving"]
        if sav > 0:
            savings_list.append(sav)

        total_planned += c_info["planned_intervention_cost"]
        total_deferred += c_info["expected_cost_if_deferred"]

    total_sav = sum(savings_list)
    n_worth = len(savings_list)

    return {
        "total_engines": len(engine_records),
        "total_expected_savings": round(total_sav),
        "engines_worth_intervening": n_worth,
        "mean_saving_per_intervention": round(total_sav / max(n_worth, 1)),
        "total_deferred_exposure": round(total_deferred),
        "risk_bands": risk_bands,
        "cost_assumptions": C,
    }
