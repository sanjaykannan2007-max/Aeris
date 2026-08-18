"""
index.py
========
Vercel Serverless Function entrypoint for AERIS Python backend API.
"""

import json
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api import AerisAPIService, get_db_connection

service = AerisAPIService()

def handler(request, response=None):
    """
    Vercel Serverless Function HTTP handler interface.
    Handles WSGI / Vercel request object.
    """
    path = getattr(request, 'path', '/')
    method = getattr(request, 'method', 'GET').upper()
    parsed = urlparse(path)
    params = parse_qs(parsed.query)

    # Route GET requests
    if method == "GET":
        if parsed.path == "/health":
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "ONLINE", "system": "AERIS Operational Platform"})
            }

        elif parsed.path == "/api/fleet/summary":
            subset = params.get("dataset", ["FD001"])[0]
            data = service.get_fleet_summary(subset)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(data)
            }

        elif parsed.path.startswith("/api/engine/") and "/history" in parsed.path:
            eng_id = int(parsed.path.strip("/").split("/")[2])
            subset = params.get("dataset", ["FD001"])[0]
            data = service.get_engine_history(eng_id, subset)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(data)
            }

        elif parsed.path.startswith("/api/engine/"):
            eng_id = int(parsed.path.strip("/").split("/")[2])
            subset = params.get("dataset", ["FD001"])[0]
            data = service.get_engine_details(eng_id, subset)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(data)
            }

    # Default fallback / WSGI Handler bridge
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": "AERIS Serverless Endpoint Active", "path": path})
    }

# Standard WSGI app entrypoint for Vercel Python runtime
app = handler
