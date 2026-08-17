"""
maintenance_recommendation.py
=============================
Actionable Maintenance Decision & Targeted Turbofan Component Advisory (Person 4).

Features
--------
1. Component-Level Root-Cause Targeting: Maps C-MAPSS sensor deviations to physical
   turbofan components (HPC, HPT, LPT, Fan, Combustor, Cooling ducts).
2. Actionable Engineering Recommendations: Generates specific maintenance tasks
   (borescope inspections, vibration spectra, thermal surveys, depot overhaul).
3. Urgency Window Estimation: Computes actionable operating cycle limits before mandatory grounding.
4. Non-Certified Decision Support Disclaimer: Clearly states prototype boundaries.

Public API
----------
    identify_target_components(top_abnormal_sensors) -> dict
    generate_maintenance_recommendation(health_status, top_abnormal_sensors, predicted_rul) -> dict
    add_maintenance_recommendations_to_dataframe(df) -> pd.DataFrame
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set
import numpy as np
import pandas as pd

from src.config import (
    SENSOR_COMPONENT_MAPPINGS,
    MAINTENANCE_DECISION_THRESHOLDS,
    DISCLAIMER_TEXT,
)


def identify_target_components(top_abnormal_sensors: Optional[str]) -> Dict[str, Any]:
    """
    Map sensor names mentioned in abnormal sensor string to physical turbofan components.

    Parameters
    ----------
    top_abnormal_sensors : str, optional
        String containing sensor names (e.g. 'sensor_11 (+3.42σ, High) | sensor_4 (+2.85σ)').

    Returns
    -------
    dict
        {
            'components': list of str (e.g. ['High-Pressure Turbine (HPT)']),
            'systems': list of str (e.g. ['Turbine Gas Path']),
            'sensor_details': list of dict,
        }
    """
    if not top_abnormal_sensors or "nominal" in str(top_abnormal_sensors).lower() or "none" in str(top_abnormal_sensors).lower():
        return {
            "components": ["All Subsystems Nominal"],
            "systems": ["Nominal"],
            "sensor_details": [],
        }

    # Extract all sensor_X tokens
    found_sensors = re.findall(r"sensor_\d+", str(top_abnormal_sensors))
    if not found_sensors:
        return {
            "components": ["General Telemetry"],
            "systems": ["General Engine Health"],
            "sensor_details": [],
        }

    components: List[str] = []
    systems: List[str] = []
    sensor_details: List[Dict[str, str]] = []

    for s in found_sensors:
        if s in SENSOR_COMPONENT_MAPPINGS:
            info = SENSOR_COMPONENT_MAPPINGS[s]
            if info["component"] not in components:
                components.append(info["component"])
            if info["system"] not in systems:
                systems.append(info["system"])
            sensor_details.append({
                "sensor_id": s,
                "sensor_name": info["name"],
                "component": info["component"],
                "system": info["system"],
            })

    return {
        "components": components if components else ["General Subsystems"],
        "systems": systems if systems else ["Core Gas Path"],
        "sensor_details": sensor_details,
    }


def generate_targeted_action_items(
    health_status: str,
    components: List[str],
    systems: List[str],
) -> str:
    """
    Synthesize physical engineering inspection tasks based on implicated components.
    """
    if health_status == "HEALTHY":
        return "Perform standard pre-flight walkaround and routine flight data recorder (FDR) telemetry logging."

    actions = []

    # Check for specific turbofan sections
    all_targets = " ".join(components + systems).lower()

    if "high-pressure compressor" in all_targets or "compression" in all_targets or "hpc" in all_targets:
        actions.append("Perform borescope inspection on HPC stages 5-9 for blade tip erosion, fouling, and clearance loss.")

    if "high-pressure turbine" in all_targets or "hpt" in all_targets or "cooling" in all_targets:
        actions.append("Conduct optical borescope inspection of HPT 1st-stage nozzle guide vanes and blade thermal barrier coating (TBC).")

    if "low-pressure turbine" in all_targets or "lpt" in all_targets:
        actions.append("Inspect LPT rotor stages and exhaust gas temperature (EGT/T48) thermocouple harnesses.")

    if "fan" in all_targets or "air intake" in all_targets:
        actions.append("Inspect titanium fan blade leading edges for foreign object damage (FOD) and perform shaft balance check.")

    if "combustor" in all_targets or "combustion" in all_targets or "fuel" in all_targets:
        actions.append("Inspect fuel flow metering valve, burner nozzles, and combustor liner for hot streaks.")

    if "bleed" in all_targets or "thermal" in all_targets:
        actions.append("Check high-pressure bleed air valve operation and pre-cooler ducting for seal leakage.")

    if not actions:
        actions.append("Execute general propulsion system diagnostic routine and check sensor calibration logs.")

    if health_status == "CRITICAL":
        actions.insert(0, "IMMEDIATE GROUNDING: Remove engine from wing / transfer to overhaul test cell.")

    return " | ".join(actions)


def generate_maintenance_recommendation(
    health_status: str,
    top_abnormal_sensors: Optional[str] = None,
    predicted_rul: float = 100.0,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate comprehensive maintenance recommendation and engineering tasks.

    Parameters
    ----------
    health_status : str
        'HEALTHY', 'MONITOR', 'MAINTENANCE REQUIRED', or 'CRITICAL'.
    top_abnormal_sensors : str, optional
        String of abnormal sensors driving the state.
    predicted_rul : float
        Predicted Remaining Useful Life in cycles.
    thresholds : dict, optional
        Custom thresholds.

    Returns
    -------
    dict
        {
            'primary_recommendation': str,
            'targeted_action_items': str,
            'impacted_components': str,
            'urgency_window_cycles': int or None,
            'disclaimer': str,
        }
    """
    t = thresholds or MAINTENANCE_DECISION_THRESHOLDS
    target_info = identify_target_components(top_abnormal_sensors)
    components = target_info["components"]
    systems = target_info["systems"]

    actions_str = generate_targeted_action_items(health_status, components, systems)
    components_str = ", ".join(components)

    rul = float(predicted_rul)

    # Urgency Window (Remaining cycles safe before mandatory grounding)
    if health_status == "CRITICAL":
        primary = "CRITICAL: Immediate Engine Grounding & Depot-Level Overhaul Required"
        urgency = 0  # 0 cycles (immediate)
    elif health_status == "MAINTENANCE REQUIRED":
        primary = "MAINTENANCE REQUIRED: Schedule Priority Borescope & Component Inspection"
        urgency = max(1, min(int(t["MAINTENANCE_REQUIRED"]["default_urgency_window"]), int(rul - 5) if rul > 5 else 1))
    elif health_status == "MONITOR":
        primary = "MONITOR: Approved for Service with Heightened Telemetry & Vibration Sampling"
        urgency = max(5, min(int(t["MONITOR"]["default_urgency_window"]), int(rul - 15) if rul > 15 else 5))
    else:  # HEALTHY
        primary = "HEALTHY: Continue Normal Flight Operations & Scheduled Line Service"
        urgency = None

    return {
        "primary_recommendation": primary,
        "targeted_action_items": actions_str,
        "impacted_components": components_str,
        "urgency_window_cycles": urgency,
        "disclaimer": DISCLAIMER_TEXT,
    }


def add_maintenance_recommendations_to_dataframe(
    df: pd.DataFrame,
    health_status_col: str = "engine_health_status",
    top_sensors_col: str = "top_abnormal_sensors",
    rul_col: str = "predicted_RUL",
) -> pd.DataFrame:
    """
    Add maintenance recommendations and targeted actions to a DataFrame.
    """
    out_df = df.copy()

    if health_status_col not in out_df.columns:
        if "health_status" in out_df.columns:
            health_status_col = "health_status"
        else:
            raise KeyError(f"Health status column '{health_status_col}' not found.")

    if rul_col not in out_df.columns:
        if "predicted_rul" in out_df.columns:
            rul_col = "predicted_rul"
        elif "RUL" in out_df.columns:
            rul_col = "RUL"

    primaries = []
    actions = []
    components_list = []
    urgencies = []

    for _, row in out_df.iterrows():
        h_stat = str(row.get(health_status_col, "HEALTHY"))
        top_sens = str(row.get(top_sensors_col, "")) if top_sensors_col in row else ""
        rul_val = float(row.get(rul_col, 100.0)) if rul_col in row else 100.0

        rec = generate_maintenance_recommendation(h_stat, top_sens, rul_val)
        primaries.append(rec["primary_recommendation"])
        actions.append(rec["targeted_action_items"])
        components_list.append(rec["impacted_components"])
        urgencies.append(rec["urgency_window_cycles"] if rec["urgency_window_cycles"] is not None else -1)

    out_df["maintenance_recommendation"] = primaries
    out_df["targeted_action_items"] = actions
    out_df["impacted_components"] = components_list
    out_df["urgency_window_cycles"] = urgencies

    return out_df
