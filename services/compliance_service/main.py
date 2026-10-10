"""DataLens GDPR, Regulatory Privacy & Security Compliance Microservice (Port 8005).

Manages the immutable rotating security audit log, GDPR (EU 2016/679) compliance
controls, 72-hour breach protocol metadata, stakeholder entitlement matrix, and
CSV/SAR export audit tracking.
"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.shared.models import AccessContext, AuditEventPayload
from services.shared.security import (
    get_audit_logs,
    log_security_event,
    require_access,
)

router = APIRouter(tags=["GDPR & Compliance Microservice"])


@router.get("/api/compliance/audit-log")
def get_compliance_audit_log(access: AccessContext = Depends(require_access)):
    logs = get_audit_logs()
    return {"logs": list(reversed(logs[-50:])), "total_events": len(logs)}


@router.post("/api/compliance/audit-log")
def record_audit_event(payload: AuditEventPayload):
    entry = log_security_event(
        payload.event_type,
        payload.user_id,
        payload.role,
        payload.location,
        payload.details,
        status=payload.status,
    )
    return {"status": "recorded", "event": entry}


@router.get("/api/compliance/gdpr-status")
def get_gdpr_status(access: AccessContext = Depends(require_access)):
    return {
        "status": "Compliant",
        "standards": [
            "GDPR (EU 2016/679)",
            "ISO/IEC 27001",
            "SOC 2 Type II",
            "DPDP Act 2023",
        ],
        "principles": [
            {
                "article": "Article 5(1)(c)",
                "name": "Data Minimisation",
                "status": "Enforced",
                "detail": "Server-side Column-Level Security (CLS) strips compensation numbers for unprivileged roles.",
            },
            {
                "article": "Article 5(1)(f)",
                "name": "Integrity & Confidentiality",
                "status": "Enforced",
                "detail": "Tokenized session management, TLS in-transit encryption, and strict Row-Level Security (RLS).",
            },
            {
                "article": "Article 15",
                "name": "Right of Access (SAR)",
                "status": "Active",
                "detail": "Self-service data view and automated audit ticket generation for personal data requests.",
            },
            {
                "article": "Article 25",
                "name": "Data Protection by Design",
                "status": "Enforced",
                "detail": "Default deny access architecture with location-bound tenant isolation.",
            },
            {
                "article": "Article 32",
                "name": "Security of Processing",
                "status": "Enforced",
                "detail": "Granular RBAC with distinct clearance for Global DF&A, Global Data Foundation, HRBP/P&O, and Employees.",
            },
            {
                "article": "Articles 33 & 34",
                "name": "Breach Notification (72h)",
                "status": "Operational",
                "detail": "Automated anomaly detection, incident response runbook, and 72-hour supervisory authority notification workflow.",
            },
        ],
        "breach_protocol": {
            "sla_hours": 72,
            "dpo_contact": "dpo-privacy@company.com",
            "escalation_steps": [
                "1. Immediate RLS Quarantine & Token Invalidation",
                "2. Forensic Impact Assessment & Record Identification",
                "3. Data Protection Authority (DPA) Notification within 72 Hours",
                "4. Affected Subject Disclosure & Remediation Logging",
            ],
        },
    }


@router.get("/api/compliance/stakeholders")
def get_stakeholders(access: AccessContext = Depends(require_access)):
    matrix = [
        {
            "stakeholder": "Global Data Foundation",
            "role": "Enterprise Master Data Governance",
            "scope": "All Locations (Global)",
            "clearance": "Enterprise Master Data & Governance Clearance",
            "salary_access": "Full Enterprise Visibility",
            "executive_report": "Authorized (Company-Wide)",
            "gdpr_purpose": "Data Quality Auditing, Architecture & Compliance Governance",
        },
        {
            "stakeholder": "HRBP / P&O Partners",
            "role": "People & Organization Location Lead",
            "scope": "Respective Location (Mumbai, Kolkata, Bengaluru, etc.)",
            "clearance": "Location Scope Clearance (Strict RLS Enforced)",
            "salary_access": "Location-Level HR Clearance",
            "executive_report": "Location Briefings Only",
            "gdpr_purpose": "Site Workforce Management & Operations",
        },
        {
            "stakeholder": "HRBP-MOM or P&O – Kolkata",
            "role": "Manufacturing Operations P&O Lead",
            "scope": "Kolkata Location Only",
            "clearance": "Operations Site Management Clearance",
            "salary_access": "Kolkata Operations Clearance",
            "executive_report": "Kolkata Site Briefings Only",
            "gdpr_purpose": "Plant Workforce & Operations Governance",
        },
    ]
    return {"stakeholders": matrix, "matrix": matrix}


@router.post("/api/compliance/log-export")
def log_export_event(
    payload: dict, access: AccessContext = Depends(require_access)
):
    count = payload.get("record_count", 0)
    log_security_event(
        "DATA_EXPORT_AUDIT",
        access.employee_id,
        access.role,
        access.location,
        f"Exported {count} records to CSV under GDPR Article 15 compliance tracking.",
        status="AUDITED",
    )
    return {"status": "recorded"}


app = FastAPI(
    title="DataLens GDPR & Compliance Microservice",
    version="4.0.0",
    description="GDPR Article 5/15/25/32/33 Governance, Audit Trail & Stakeholder Entitlement Service",
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
@app.get("/api/compliance/health")
def health():
    return {
        "service": "compliance-service",
        "name": "GDPR & Compliance Microservice",
        "port": 8005,
        "status": "healthy",
        "audit_events": len(get_audit_logs()),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)

