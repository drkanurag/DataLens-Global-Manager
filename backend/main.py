"""DataLens Enterprise Backend Entrypoint.

Delegates to the DataLens Microservices API Gateway (`services.api_gateway.main:app`)
while preserving full backward compatibility for `uvicorn main:app --reload` inside `backend/`.
"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.api_gateway.main import app
from services.shared.data_store import (
    can_view_compensation,
    compute_quality_report as quality_report,
    df,
    directory_df as directory,
    has_global_access,
    has_hrbp_access,
    is_manager,
    load_employee_data,
    numeric_series,
    secured_data,
    top_values,
)
from services.shared.models import (
    AccessContext,
    CITY_ALIASES,
    CORE_COLUMNS,
    ChatRequest,
    ERROR_TYPE_NAMES,
    FAQ_KNOWLEDGE_BASE,
    FILTER_COLUMNS,
    FilterParams,
    GLOBAL_ROLES,
    HRBP_ROLES,
    LoginRequest,
    ROLE_ALIASES,
)
from services.shared.security import (
    SECURITY_AUDIT_LOG,
    SESSIONS,
    log_security_event,
    require_access,
)

__all__ = [
    "app",
    "df",
    "directory",
    "SESSIONS",
    "SECURITY_AUDIT_LOG",
    "AccessContext",
    "LoginRequest",
    "ChatRequest",
    "FilterParams",
    "require_access",
    "secured_data",
    "quality_report",
    "log_security_event",
    "has_global_access",
    "has_hrbp_access",
    "can_view_compensation",
    "is_manager",
    "load_employee_data",
    "top_values",
    "numeric_series",
    "FILTER_COLUMNS",
    "CORE_COLUMNS",
    "GLOBAL_ROLES",
    "HRBP_ROLES",
    "ROLE_ALIASES",
    "ERROR_TYPE_NAMES",
    "CITY_ALIASES",
    "FAQ_KNOWLEDGE_BASE",
]
