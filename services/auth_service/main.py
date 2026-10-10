"""DataLens Auth & IAM Microservice (Port 8001).

Handles role-based authentication, session token issuance, alias resolution,
and Row-Level Security (RLS) access context verification.
"""
from pathlib import Path
import secrets
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.shared.data_store import load_access_directory
from services.shared.models import AccessContext, LoginRequest, ROLE_ALIASES
from services.shared.security import (
    SESSIONS,
    get_session,
    log_security_event,
    require_access,
    save_session,
)

router = APIRouter(tags=["IAM & Authentication Microservice"])


@router.post("/api/auth/login")
def login(request: LoginRequest):
    directory = load_access_directory()
    raw_id = request.employee_id.strip()
    eid = raw_id.upper()

    if (
        eid.startswith("EMP")
        or eid.startswith("MANAGER")
        or eid in ("CEO", "EMPLOYEE", "ADMIN")
    ):
        log_security_event(
            "AUTH_REJECTED",
            raw_id,
            "Disabled Legacy Role",
            "Unknown",
            "Login rejected: legacy manager/employee ID disabled in favor of role-based credentials.",
            status="REJECTED",
        )
        raise HTTPException(
            status_code=401,
            detail="Login is role-based. Manager and Employee IDs are disabled. Please use 'GDF' for Global Data Foundation or 'HRBP-(LOCATION)' (e.g., HRBP-KOL, HRBP-MUM, HRBP-DEL, HRBP-BLR, HRBP-HYD, HRBP-CHN, HRBP-PUN, HRBP-GUR).",
        )

    canonical_id = ROLE_ALIASES.get(eid, eid)
    found = directory[directory["employee_id"].str.upper() == canonical_id]

    if found.empty:
        log_security_event(
            "AUTH_FAILURE",
            raw_id,
            "Unknown",
            "Unknown",
            "Authentication failed: unrecognized role ID",
            status="FAILED",
        )
        raise HTTPException(
            status_code=401,
            detail="Role ID not recognized. Authorized role IDs: GDF (Global Data Foundation) or HRBP-(LOCATION) (e.g., HRBP-KOL, HRBP-MUM, HRBP-DEL, HRBP-BLR, HRBP-HYD, HRBP-CHN, HRBP-PUN, HRBP-GUR).",
        )

    user = found.iloc[0].to_dict()
    token = secrets.token_urlsafe(32)
    session_record = {
        "employee_id": user["employee_id"],
        "employee_name": user["employee_name"],
        "location": user["location"],
        "role": user["role"],
    }
    save_session(token, session_record)
    log_security_event(
        "AUTH_SUCCESS",
        user["employee_id"],
        user["role"],
        user["location"],
        f"User successfully authenticated via Auth Microservice (Scope: {user['location']})",
    )
    return {"token": token, "user": session_record, "service": "auth-service"}


@router.get("/api/auth/me")
def current_user(access: AccessContext = Depends(require_access)):
    return access.__dict__


@router.get("/api/auth/validate")
def validate_token(x_employee_token: str | None = Header(default=None)):
    record = get_session(x_employee_token)
    if not record:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")
    return {"valid": True, "context": record}


app = FastAPI(
    title="DataLens IAM & Auth Microservice",
    version="4.0.0",
    description="Role-Based Access Control (RBAC), Token Issuance & Session Validation Service",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
@app.get("/api/auth/health")
def health():
    return {
        "service": "auth-service",
        "name": "IAM & Auth Microservice",
        "port": 8001,
        "status": "healthy",
        "active_sessions": len(SESSIONS),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
