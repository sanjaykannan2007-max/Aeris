"""
auth.py
=======
Authentication, Password Hashing, Session Management & RBAC Security Layer for AERIS.

Roles:
- ADMIN
- MAINTENANCE_MANAGER
- ENGINEER
- ANALYST
- VIEWER
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Any, Dict, Optional

# Active user sessions store (token -> session dict)
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash password securely using SHA-256 with a salt."""
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}${hashed}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt$hash string."""
    try:
        salt, expected_hash = stored_hash.split('$')
        computed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return secrets.compare_digest(computed, expected_hash)
    except Exception:
        return False

def create_session(email: str, role: str, full_name: str) -> str:
    """Generate session token for authenticated user."""
    token = secrets.token_hex(24)
    ACTIVE_SESSIONS[token] = {
        "email": email,
        "role": role,
        "full_name": full_name,
        "created_at": time.time(),
        "expires_at": time.time() + 86400  # 24 hours
    }
    return token

def get_session(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve session if valid and not expired."""
    session = ACTIVE_SESSIONS.get(token)
    if not session:
        return None
    if time.time() > session["expires_at"]:
        del ACTIVE_SESSIONS[token]
        return None
    return session

def destroy_session(token: str):
    """Invalidate session token."""
    ACTIVE_SESSIONS.pop(token, None)

# Role Access Matrix
ROLE_PERMISSIONS = {
    "ADMIN": ["all"],
    "MAINTENANCE_MANAGER": ["fleet", "aircraft", "engines", "maintenance", "workorders", "alerts", "reports"],
    "ENGINEER": ["fleet", "aircraft", "engines", "telemetry", "diagnostics", "simulator", "alerts"],
    "ANALYST": ["fleet", "engines", "analytics", "models", "reports"],
    "VIEWER": ["fleet", "aircraft", "engines", "read_only"],
}

def has_permission(role: str, resource: str) -> bool:
    """Check if role has access to specific resource."""
    allowed = ROLE_PERMISSIONS.get(role, [])
    return "all" in allowed or resource in allowed
