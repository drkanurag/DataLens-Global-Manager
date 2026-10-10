"""DataLens Data Quality & SAP Master-Data Reconciliation Microservice (Port 8003).

Handles automated SAP vs Employee Central (EC) master-data reconciliation checks,
missing field diagnostics, duplicate detection, and SOP rules metadata.
"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.shared.data_store import compute_quality_report, secured_data
from services.shared.models import AccessContext, ERROR_TYPE_NAMES, FilterParams
from services.shared.security import log_security_event, require_access

router = APIRouter(tags=["Data Quality & SAP Audit Microservice"])


@router.get("/api/analytics/data-quality")
def data_quality(
    filters: FilterParams = Depends(),
    access: AccessContext = Depends(require_access),
):
    data = secured_data(filters, access, log_security_event)
    return compute_quality_report(data)


@router.get("/api/data-quality/rules")
def data_quality_rules(access: AccessContext = Depends(require_access)):
    return {
        "service": "data-quality-service",
        "rules_count": len(ERROR_TYPE_NAMES),
        "configured_error_types": ERROR_TYPE_NAMES,
    }


app = FastAPI(
    title="DataLens Data Quality & SAP Audit Microservice",
    version="4.0.0",
    description="Automated SAP vs EC Master-Data Reconciliation & Anomaly Detection Service",
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
@app.get("/api/data-quality/health")
def health():
    return {
        "service": "data-quality-service",
        "name": "Data Quality & SAP Audit Microservice",
        "port": 8003,
        "status": "healthy",
        "rules_configured": len(ERROR_TYPE_NAMES),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
