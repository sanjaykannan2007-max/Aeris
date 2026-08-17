"""
api.py
======
REST API Backend Service for UI Dashboard & Fleet Health Monitoring (Person 4).

Endpoints
---------
- GET  /health                                : Service health check
- GET  /api/fleet/summary?dataset=FD001       : Fleet health stage counts and KPIs
- GET  /api/engine/{id}?dataset=FD001         : Engine-level maintenance decision and diagnostics
- GET  /api/engine/{id}/history?dataset=FD001 : Full cycle-by-cycle telemetry and health trajectory
- POST /api/predict                           : Live telemetry inference (RUL + Anomaly + Maintenance)

Can be launched via:
    python run_maintenance_advisor.py --serve --port 8000
    or python src/api.py --port 8000
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import OUTPUTS_PREDICTIONS_DIR, VALID_SUBSETS, MODELS_RUL_DIR, MODELS_ANOMALY_DIR
from src.health_assessment import assess_engine_health, generate_decision_reason
from src.maintenance_recommendation import generate_maintenance_recommendation


class EngineHealthAPIService:
    """In-memory cache and service layer for UI API queries."""

    def __init__(self):
        self.fleet_data_cache: Dict[str, pd.DataFrame] = {}
        self.cycle_data_cache: Dict[str, pd.DataFrame] = {}

    def get_fleet_summary(self, subset: str = "FD001") -> Dict[str, Any]:
        """Fetch fleet summary for dataset."""
        subset = subset.upper()
        if subset not in self.fleet_data_cache:
            p = OUTPUTS_PREDICTIONS_DIR / f"fleet_maintenance_advisory_{subset}.csv"
            if not p.exists():
                return {"error": f"Advisory data not generated for {subset}. Run pipeline first."}
            self.fleet_data_cache[subset] = pd.read_csv(p)

        df = self.fleet_data_cache[subset]
        total = len(df)
        counts = df["engine_health_status"].value_counts().to_dict()

        return {
            "dataset": subset,
            "total_engines": total,
            "health_distribution": {
                "HEALTHY": int(counts.get("HEALTHY", 0)),
                "MONITOR": int(counts.get("MONITOR", 0)),
                "MAINTENANCE_REQUIRED": int(counts.get("MAINTENANCE REQUIRED", 0)),
                "CRITICAL": int(counts.get("CRITICAL", 0)),
            },
            "mean_predicted_rul": round(float(df["predicted_RUL"].mean()), 2),
            "mean_anomaly_score": round(float(df["latest_anomaly_score"].mean()), 2),
            "mean_composite_health": round(float(df["composite_health_score"].mean()), 2),
            "engines": df[["engine_id", "latest_observed_cycle", "predicted_RUL", "latest_anomaly_score", "engine_health_status", "risk_level"]].to_dict(orient="records"),
        }

    def get_engine_detail(self, engine_id: int, subset: str = "FD001") -> Dict[str, Any]:
        """Fetch latest advisory diagnostics for a specific engine."""
        subset = subset.upper()
        if subset not in self.fleet_data_cache:
            p = OUTPUTS_PREDICTIONS_DIR / f"fleet_maintenance_advisory_{subset}.csv"
            if not p.exists():
                return {"error": f"Advisory data not found for {subset}."}
            self.fleet_data_cache[subset] = pd.read_csv(p)

        df = self.fleet_data_cache[subset]
        row = df[df["engine_id"] == engine_id]
        if row.empty:
            return {"error": f"Engine #{engine_id} not found in {subset} fleet."}

        record = row.iloc[0].to_dict()
        # Clean numpy types for JSON serialization
        clean_record = {}
        for k, v in record.items():
            if isinstance(v, (np.integer, int)):
                clean_record[k] = int(v)
            elif isinstance(v, (np.floating, float)):
                clean_record[k] = round(float(v), 2)
            else:
                clean_record[k] = str(v)

        return clean_record

    def get_engine_history(self, engine_id: int, subset: str = "FD001") -> Dict[str, Any]:
        """Fetch cycle-by-cycle trajectory for interactive charts."""
        subset = subset.upper()
        if subset not in self.cycle_data_cache:
            p = OUTPUTS_PREDICTIONS_DIR / f"cycle_integrated_health_{subset}.csv"
            if not p.exists():
                return {"error": f"Cycle data not found for {subset}."}
            self.cycle_data_cache[subset] = pd.read_csv(p)

        df = self.cycle_data_cache[subset]
        eng_df = df[df["engine_id"] == engine_id].sort_values("cycle")
        if eng_df.empty:
            return {"error": f"No cycle history for Engine #{engine_id} in {subset}."}

        history = eng_df[[
            "cycle",
            "predicted_RUL",
            "anomaly_score",
            "anomaly_label",
            "engine_health_status",
            "composite_health_score",
        ]].to_dict(orient="records")

        return {
            "dataset": subset,
            "engine_id": int(engine_id),
            "total_cycles": len(history),
            "trajectory": history,
        }


SERVICE = EngineHealthAPIService()


UI_DIR = PROJECT_ROOT / "ui"

class RequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler implementing REST endpoints and UI static file serving."""

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        dataset = query.get("dataset", ["FD001"])[0]

        # 1. Static UI Web Assets
        if path in ("/", "/index.html", "/dashboard"):
            index_file = UI_DIR / "index.html"
            if index_file.exists():
                self._set_headers(200, content_type="text/html; charset=utf-8")
                with open(index_file, "rb") as f:
                    self.wfile.write(f.read())
                return
        elif path == "/styles.css":
            css_file = UI_DIR / "styles.css"
            if css_file.exists():
                self._set_headers(200, content_type="text/css; charset=utf-8")
                with open(css_file, "rb") as f:
                    self.wfile.write(f.read())
                return
        elif path == "/app.js":
            js_file = UI_DIR / "app.js"
            if js_file.exists():
                self._set_headers(200, content_type="application/javascript; charset=utf-8")
                with open(js_file, "rb") as f:
                    self.wfile.write(f.read())
                return

        # 2. REST API Endpoints
        if path == "/health":
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "online",
                "service": "NASA C-MAPSS Engine Health & Maintenance API",
                "version": "1.0.0",
                "supported_datasets": VALID_SUBSETS,
            }).encode("utf-8"))

        elif path == "/api/fleet/summary":
            res = SERVICE.get_fleet_summary(dataset)
            status_code = 400 if "error" in res else 200
            self._set_headers(status_code)
            self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

        elif path.startswith("/api/engine/") and path.endswith("/history"):
            parts = path.strip("/").split("/")
            try:
                eng_id = int(parts[2])
                res = SERVICE.get_engine_history(eng_id, dataset)
                status_code = 400 if "error" in res else 200
            except Exception as e:
                res = {"error": f"Invalid engine ID: {e}"}
                status_code = 400
            self._set_headers(status_code)
            self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

        elif path.startswith("/api/engine/"):
            parts = path.strip("/").split("/")
            try:
                eng_id = int(parts[2])
                res = SERVICE.get_engine_detail(eng_id, dataset)
                status_code = 400 if "error" in res else 200
            except Exception as e:
                res = {"error": f"Invalid engine ID: {e}"}
                status_code = 400
            self._set_headers(status_code)
            self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({
                "error": f"Endpoint not found: {path}",
                "available_endpoints": [
                    "GET / (Web UI Dashboard)",
                    "GET /health",
                    "GET /api/fleet/summary?dataset=FD001",
                    "GET /api/engine/{engine_id}?dataset=FD001",
                    "GET /api/engine/{engine_id}/history?dataset=FD001",
                    "POST /api/predict",
                ],
            }).encode("utf-8"))

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/predict":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
                rul = float(data.get("predicted_rul", data.get("predicted_RUL", 100.0)))
                anom = float(data.get("anomaly_score", 0.0))
                anom_stat = str(data.get("anomaly_status", data.get("anomaly_label", "Normal")))
                top_sens = str(data.get("top_abnormal_sensors", ""))

                eval_res = assess_engine_health(rul, anom, anom_stat)
                h_stat = eval_res["health_status"]
                reason = generate_decision_reason(rul, anom, anom_stat, top_sens, h_stat)
                rec = generate_maintenance_recommendation(h_stat, top_sens, rul)

                response = {
                    "engine_id": int(data.get("engine_id", 1)),
                    "cycle": int(data.get("cycle", 1)),
                    "predicted_rul": rul,
                    "anomaly_score": anom,
                    "anomaly_status": anom_stat,
                    "engine_health_status": h_stat,
                    "composite_health_score": eval_res["composite_health_score"],
                    "risk_level": eval_res["risk_level"],
                    "decision_reason": reason,
                    "maintenance_recommendation": rec["primary_recommendation"],
                    "targeted_action_items": rec["targeted_action_items"],
                    "impacted_components": rec["impacted_components"],
                    "urgency_window_cycles": rec["urgency_window_cycles"],
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": f"Inference failed: {e}"}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found."}).encode("utf-8"))


def run_server(port: int = 8000, host: str = "0.0.0.0"):
    """Run REST API Server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"\n{'='*65}")
    print(f"  NASA C-MAPSS ENGINE HEALTH REST API RUNNING")
    print(f"  Host : http://localhost:{port}")
    print(f"  Docs :")
    print(f"    - GET  http://localhost:{port}/health")
    print(f"    - GET  http://localhost:{port}/api/fleet/summary?dataset=FD001")
    print(f"    - GET  http://localhost:{port}/api/engine/1?dataset=FD001")
    print(f"    - GET  http://localhost:{port}/api/engine/1/history?dataset=FD001")
    print(f"    - POST http://localhost:{port}/api/predict")
    print(f"{'='*65}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping server...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NASA C-MAPSS REST API Service")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to listen on.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address.")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)
