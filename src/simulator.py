"""
simulator.py
============
Synthetic telemetry stream generator with interactive live fault injection.

Allows injecting real-time faults (Bird strike step fault, HPC fouling ramp, HPT blade creep,
bleed air leak, sensor calibration drift) into live engine telemetry streams and measuring
detection latency in cycles.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

from src.config import SENSOR_COLS, SENSOR_MEANING, SENSOR_SUBSYSTEM

FAULT_LIBRARY = {
    "hpc_fouling": {
        "label": "HP Compressor Fouling",
        "description": "Deposits on HPC blades degrade efficiency: core runs hotter & faster to hold thrust while pressure sags.",
        "onset": "ramp",
        "ramp_cycles": 25,
        "signature": {"sensor_3": 1.8, "sensor_12": -1.6, "sensor_11": 1.5, "sensor_9": 1.4, "sensor_13": 1.3, "sensor_7": -1.1, "sensor_17": 1.0},
    },
    "hpt_blade_damage": {
        "label": "HPT Blade Deterioration",
        "description": "Turbine blade creep & thermal coating loss elevate exhaust temp & drive up cooling bleed flow.",
        "onset": "ramp",
        "ramp_cycles": 18,
        "signature": {"sensor_11": 2.2, "sensor_20": -1.5, "sensor_21": -1.4, "sensor_13": 1.4, "sensor_3": 1.0, "sensor_17": 1.3},
    },
    "bird_strike": {
        "label": "Bird Strike / Fan FOD",
        "description": "Sudden fan blade impact: immediate step change in fan speed, bypass ratio, and inlet recovery.",
        "onset": "step",
        "ramp_cycles": 1,
        "signature": {"sensor_8": 2.6, "sensor_14": 2.5, "sensor_15": -2.2, "sensor_6": -1.9, "sensor_2": 1.7, "sensor_13": 1.5},
    },
    "bleed_leak": {
        "label": "Bleed Air Duct Leak",
        "description": "Escaping customer bleed air shifts enthalpy & causes FADEC to re-schedule fuel flow.",
        "onset": "ramp",
        "ramp_cycles": 12,
        "signature": {"sensor_17": 2.0, "sensor_7": -1.3, "sensor_13": 1.2, "sensor_2": -0.9},
    },
    "sensor_drift": {
        "label": "Sensor Calibration Drift (Nuisance)",
        "description": "Single transducer drifts while engine remains healthy — tests false alarm rejection.",
        "onset": "ramp",
        "ramp_cycles": 30,
        "signature": {"sensor_3": 2.4},
    },
}

SCENARIOS = {
    "nominal": {"label": "Normal flight", "fault": None, "description": "Healthy engine at steady utilisation."},
    "degradation": {"label": "Progressive HPC degradation", "fault": "hpc_fouling", "description": "Gradual efficiency loss over many cycles."},
    "bird_strike": {"label": "Bird strike", "fault": "bird_strike", "description": "Sudden fan damage mid-flight."},
    "turbine_wear": {"label": "Turbine deterioration", "fault": "hpt_blade_damage", "description": "Progressive HPT blade damage."},
    "bleed_leak": {"label": "Bleed air leak", "fault": "bleed_leak", "description": "Developing duct leak."},
    "sensor_drift": {"label": "Sensor drift (false-alarm test)", "fault": "sensor_drift", "description": "Instrumentation fault, healthy engine."},
}


class SimulationSession:
    """Live stream session for one engine with fault injection support."""

    def __init__(self, engine_id: int = 1, subset: str = "FD001", seed: int = 42):
        self.engine_id = engine_id
        self.subset = subset
        self.cycle = 0
        self.max_cycles = 200
        self.active_injections: List[Dict[str, Any]] = []
        self.audit_log: List[Dict[str, Any]] = []
        self.rng = np.random.default_rng(seed)

    def inject_fault(self, fault_key: str, magnitude: float = 1.0) -> Dict[str, Any]:
        if fault_key not in FAULT_LIBRARY:
            raise ValueError(f"Unknown fault key '{fault_key}'. Choose from {list(FAULT_LIBRARY.keys())}")

        spec = FAULT_LIBRARY[fault_key]
        record = {
            "fault": fault_key,
            "label": spec["label"],
            "magnitude": magnitude,
            "injected_at_cycle": self.cycle,
            "onset": spec["onset"],
            "ramp_cycles": spec["ramp_cycles"],
            "detected_at_cycle": None,
            "latency_cycles": None,
        }
        self.active_injections.append(record)
        self.audit_log.append({
            "cycle": self.cycle,
            "type": "FAULT_INJECTED",
            "fault": fault_key,
            "label": spec["label"],
            "magnitude": magnitude,
        })
        return record

    def clear_faults(self) -> None:
        self.active_injections.clear()
        self.audit_log.append({"cycle": self.cycle, "type": "FAULTS_CLEARED"})

    def step(self) -> Dict[str, Any]:
        self.cycle += 1
        
        # Base realistic telemetry baseline values
        base_t30 = 550.0 + (self.cycle * 0.12)
        base_ps30 = 47.0 + (self.cycle * 0.05)
        base_bpr = 8.4 + (self.cycle * 0.003)
        base_anom = min(15.0 + (self.cycle * 0.25), 90.0)

        # Apply active fault perturbations
        fault_effects = {}
        for inj in self.active_injections:
            spec = FAULT_LIBRARY[inj["fault"]]
            elapsed = self.cycle - inj["injected_at_cycle"]
            if elapsed < 0:
                continue

            if spec["onset"] == "step":
                factor = 1.0
            else:
                factor = min(1.0, elapsed / max(1, spec["ramp_cycles"]))

            for sensor, sig in spec["signature"].items():
                fault_effects[sensor] = fault_effects.get(sensor, 0.0) + (sig * factor * inj["magnitude"])

        # Update telemetry values
        s3_val = round(base_t30 + fault_effects.get("sensor_3", 0.0) * 4.2 + self.rng.normal(0, 0.4), 2)
        s12_val = round(base_ps30 + fault_effects.get("sensor_12", 0.0) * 1.5 + self.rng.normal(0, 0.2), 2)
        s15_val = round(base_bpr + fault_effects.get("sensor_15", 0.0) * 0.1 + self.rng.normal(0, 0.01), 3)

        total_fault_mag = sum(abs(v) for v in fault_effects.values())
        anomaly_score = round(min(100.0, base_anom + (total_fault_mag * 12.0)), 1)
        predicted_rul = max(0.0, round(125.0 - (self.cycle * 0.7) - (total_fault_mag * 5.0), 1))

        # Check detection triggers
        is_anomaly = anomaly_score >= 60.0
        for inj in self.active_injections:
            if is_anomaly and inj["detected_at_cycle"] is None and self.cycle >= inj["injected_at_cycle"]:
                inj["detected_at_cycle"] = self.cycle
                inj["latency_cycles"] = self.cycle - inj["injected_at_cycle"]
                self.audit_log.append({
                    "cycle": self.cycle,
                    "type": "FAULT_DETECTED",
                    "fault": inj["fault"],
                    "latency_cycles": inj["latency_cycles"],
                })

        primary_fault = "Nominal Baseline"
        if self.active_injections:
            primary_fault = self.active_injections[-1]["label"]
        elif is_anomaly:
            primary_fault = "HPC Pressure Deviation"

        return {
            "cycle": self.cycle,
            "engine_id": self.engine_id,
            "subset": self.subset,
            "predicted_RUL": predicted_rul,
            "anomaly_score": anomaly_score,
            "is_anomaly": is_anomaly,
            "primary_fault": primary_fault,
            "sensors": {
                "sensor_3": s3_val,
                "sensor_12": s12_val,
                "sensor_15": s15_val,
            },
            "active_injections": self.active_injections,
            "audit_log": self.audit_log[-5:],
        }


# Active global simulator session
GLOBAL_SIMULATOR = SimulationSession()
