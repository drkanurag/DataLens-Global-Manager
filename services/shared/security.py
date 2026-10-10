"""Cross-service session management, token validation, and distributed security audit logging."""
import datetime
import json
from pathlib import Path
from fastapi import Header, HTTPException

from .models import AccessContext
from .data_store import DATA_DIR

SESSIONS_FILE = DATA_DIR / "_sessions_store.json"
AUDIT_LOG_FILE = DATA_DIR / "_security_audit_log.json"

SESSIONS: dict[str, dict[str, str]] = {}

DEFAULT_AUDIT_LOGS: list[dict] = [
    {
        "id": "SEC-AUD-001",
        "timestamp": (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=14)
        ).isoformat(),
        "event_type": "SYSTEM_INITIALIZE",
        "user_id": "SYSTEM",
        "employee_id": "SYSTEM",
        "role": "Governance Core",
        "location": "Global",
        "scope": "Global",
        "details": "DataLens Microservices Mesh & Row-Level Governance Engine active. GDPR Article 5 data minimization rules online.",
        "status": "SUCCESS",
    },
    {
        "id": "SEC-AUD-002",
        "timestamp": (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=8)
        ).isoformat(),
        "event_type": "RLS_ENFORCEMENT",
        "user_id": "GDF001",
        "employee_id": "GDF001",
        "role": "Global Data Foundation",
        "location": "All Locations",
        "scope": "All Locations",
        "details": "Global Data Foundation session granted enterprise-wide master data clearance.",
        "status": "SUCCESS",
    },
    {
        "id": "SEC-AUD-003",
        "timestamp": (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=5)
        ).isoformat(),
        "event_type": "RLS_ENFORCEMENT",
        "user_id": "HRBP_KOL",
        "employee_id": "HRBP_KOL",
        "role": "HRBP-MOM or P&O – Kolkata",
        "location": "Kolkata",
        "scope": "Kolkata",
        "details": "Location isolation active. Row-Level Security bound strictly to Kolkata site operations.",
        "status": "SUCCESS",
    },
]

SECURITY_AUDIT_LOG: list[dict] = list(DEFAULT_AUDIT_LOGS)


def _load_sessions_from_disk() -> dict[str, dict[str, str]]:
    if SESSIONS_FILE.exists():
        try:
            data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                SESSIONS.update(data)
        except Exception:
            pass
    return SESSIONS


def _save_sessions_to_disk() -> None:
    try:
        SESSIONS_FILE.write_text(json.dumps(SESSIONS, indent=2), encoding="utf-8")
    except Exception:
        pass


def save_session(token: str, user_record: dict[str, str]) -> None:
    _load_sessions_from_disk()
    SESSIONS[token] = user_record
    _save_sessions_to_disk()


def get_session(token: str | None) -> dict[str, str] | None:
    if not token:
        return None
    if token in SESSIONS:
        return SESSIONS[token]
    _load_sessions_from_disk()
    return SESSIONS.get(token)


def get_audit_logs() -> list[dict]:
    global SECURITY_AUDIT_LOG
    if AUDIT_LOG_FILE.exists():
        try:
            loaded = json.loads(AUDIT_LOG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, list) and loaded:
                SECURITY_AUDIT_LOG = loaded
        except Exception:
            pass
    return SECURITY_AUDIT_LOG


def log_security_event(
    event_type: str,
    user_id: str,
    role: str,
    location: str,
    details: str,
    status: str = "SUCCESS",
) -> dict:
    logs = get_audit_logs()
    evt_id = f"SEC-AUD-{len(logs) + 1:03d}"
    entry = {
        "id": evt_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "employee_id": user_id,
        "role": role,
        "location": location,
        "scope": location,
        "details": details,
        "status": status,
    }
    logs.append(entry)
    if len(logs) > 200:
        logs.pop(0)
    try:
        AUDIT_LOG_FILE.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    except Exception:
        pass
    return entry


def require_access(
    x_employee_token: str | None = Header(default=None),
) -> AccessContext:
    record = get_session(x_employee_token or "")
    if not record:
        raise HTTPException(
            status_code=401, detail="Please sign in with a valid employee ID."
        )
    return AccessContext(**record)

