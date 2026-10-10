"""Shared Pydantic schemas, dataclasses, and constants across all DataLens microservices."""
from dataclasses import dataclass
from pydantic import BaseModel

FILTER_COLUMNS = {
    "evp": "EVP",
    "evp1": "SVP",
    "evp2": "CVP",
    "hrbp": "VP",
    "legal_entity": "COMPANY_CODE",
    "location": "LOCATION_DESCRIPTION",
    "employee_group": "EMPLOYEE_GROUP_EC",
    "job_family": "JOB_FAMILY",
    "department": "DEPARTMENT_EC",
    "month": "Month Name",
}

CORE_COLUMNS = [
    "Month Name",
    "EMPLOYEE_NO",
    "LOCATION_DESCRIPTION",
    "DEPARTMENT_EC",
    "JOB_FAMILY",
    "HEADCOUNT",
]

GLOBAL_ROLES = {
    "global data foundation",
    "data foundation",
    "gdf",
    "gdf001",
}

HRBP_ROLES = {
    "hrbp",
    "p&o",
    "hrbp / p&o partner",
    "hrbp - p&o partner",
    "hrbp-mom",
    "hrbp-mom or p&o",
    "hrbp-mom or p&o – kolkata",
    "hrbp-mom or p&o - kolkata",
    "hrbp - mom or p&o - kolkata",
    "hrbp - kolkata",
    "hrbp - mumbai",
    "hrbp - new delhi",
    "hrbp - delhi",
    "hrbp - bengaluru",
    "hrbp - hyderabad",
    "hrbp - chennai",
    "hrbp - pune",
    "hrbp - gurugram",
}

ROLE_ALIASES = {
    "GDF": "GDF001",
    "GLOBAL DATA FOUNDATION": "GDF001",
    "DATA FOUNDATION": "GDF001",
    "HRBP_KOL": "HRBP-KOL",
    "HRBP-KOLKATA": "HRBP-KOL",
    "HRBP_MUM": "HRBP-MUM",
    "HRBP-MUMBAI": "HRBP-MUM",
    "HRBP_DEL": "HRBP-DEL",
    "HRBP-DELHI": "HRBP-DEL",
    "HRBP-NEW-DELHI": "HRBP-DEL",
    "HRBP_BLR": "HRBP-BLR",
    "HRBP-BANGALORE": "HRBP-BLR",
    "HRBP-BENGALURU": "HRBP-BLR",
    "HRBP_HYD": "HRBP-HYD",
    "HRBP-HYDERABAD": "HRBP-HYD",
    "HRBP_CHN": "HRBP-CHN",
    "HRBP-CHENNAI": "HRBP-CHN",
    "HRBP_PUN": "HRBP-PUN",
    "HRBP-PUNE": "HRBP-PUN",
    "HRBP_GUR": "HRBP-GUR",
    "HRBP-GURUGRAM": "HRBP-GUR",
    "HRBP-GURGAON": "HRBP-GUR",
}

ERROR_TYPE_NAMES = [
    "Salary not matching with SAP",
    "Cost centre mismatch with company code",
    "High range penetration percentage",
    "Department Code is not matching EC vs SAP",
    "Incorrect Business Email",
    "Manager is not matching EC vs SAP",
    "Company Code is not matching EC vs SAP",
]

CITY_ALIASES = {
    "new delhi": ["new delhi", "delhi", "ncr", "dilli"],
    "mumbai": ["mumbai", "bombay", "mum"],
    "bengaluru": ["bengaluru", "bangalore", "blr"],
    "kolkata": ["kolkata", "calcutta", "ccu"],
    "chennai": ["chennai", "madras", "maa"],
    "hyderabad": ["hyderabad", "hyd"],
    "pune": ["pune", "poona", "pnq"],
    "gurugram": ["gurugram", "gurgaon", "ggn"],
}

FAQ_KNOWLEDGE_BASE = {
    "how do i correct the cost centre for my employee": "Submit a master-data correction request to HR or Finance. Include the employee ID, the correct cost centre, effective date, and manager approval. After the source is corrected, refresh the dashboard data.",
    "how do i correct the cost center for my employee": "Submit a master-data correction request to HR or Finance. Include the employee ID, the correct cost centre, effective date, and manager approval. After the source is corrected, refresh the dashboard data.",
    "how do i get access to my organization reports": "Request access through your reporting owner or IT service desk. Provide your business justification and manager approval. Access should be assigned through the organisation's role and location entitlement process.",
    "how do i get access to my organisation reports": "Request access through your reporting owner or IT service desk. Provide your business justification and manager approval. Access should be assigned through the organisation's role and location entitlement process.",
    "how do i report a salary mismatch": "Raise a payroll or HR data-quality ticket with the employee ID, expected salary, source-system reference, and supporting evidence. Do not share sensitive salary details in the chatbot.",
    "how are data quality errors calculated": "The dashboard counts non-'No Error' values in DATA_QUALITY_ERROR_TYPE inside the user's authorised scope.",
    "how often is the dashboard data refreshed": "This prototype reads the workbook when the FastAPI server starts. Replace or update the source workbook and restart the server to refresh the dashboard.",
    "why can i not view another location": "Location access is enforced by your employee ID on the server. The dashboard and chatbot only return records for your authorised location.",
    "what is gdpr and how does datalens comply": "DataLens complies with GDPR (General Data Protection Regulation EU 2016/679) through: (1) Article 5 Data Minimisation via column-level salary masking; (2) Article 15 Right of Access via self-service employee records; (3) Article 25 Privacy by Design with server-side Row-Level Security (RLS); (4) Article 32 Security of Processing through granular RBAC; and (5) Articles 33/34 Breach Notification protocol ensuring 72-hour incident escalation.",
    "how are data breaches handled": "Data breaches are handled under a formal 4-stage Incident Response Protocol: (1) Immediate RLS quarantine and session invalidation; (2) Forensic assessment of affected records; (3) Mandatory Data Protection Authority (DPA) notification within 72 hours per GDPR Article 33; and (4) Communication to affected data subjects with corrective remediation.",
    "what are the stakeholder access roles": "DataLens access is provisioned for: (1) Global DF&A (enterprise-wide financial and workforce analytics); (2) Global Data Foundation (enterprise-wide master data and data quality governance); (3) HRBP / P&O Partners (location-scoped management clearance for Mumbai, Delhi, Bengaluru, etc.); (4) HRBP-MOM or P&O – Kolkata (Kolkata plant operations workforce clearance); (5) Corporate Leadership / CEO; and (6) Standard Employees (location-bound with confidential salary masking).",
    "what is global dfa": "Global DF&A (Data, Finance & Analytics) has enterprise-wide governance clearance across all corporate locations to conduct workforce financial modeling, span-of-control benchmarking, and executive strategic briefings.",
    "what is global data foundation": "Global Data Foundation has full enterprise data access across all locations to perform master data architecture validation, SAP-to-EC synchronization diagnostics, and automated quality remediation.",
    "what is hrbp kolkata": "HRBP-MOM or P&O – Kolkata holds People & Organization governance clearance specifically for the Kolkata manufacturing and operations workforce, with location-bound RLS and quality remediation authority.",
}

MICROSERVICE_REGISTRY = {
    "api_gateway": {"name": "API Gateway Service", "port": 8000, "prefix": "/api"},
    "auth_service": {"name": "IAM & Auth Microservice", "port": 8001, "prefix": "/api/auth"},
    "analytics_service": {"name": "Workforce Analytics Microservice", "port": 8002, "prefix": "/api/analytics"},
    "data_quality_service": {"name": "Data Quality & SAP Audit Microservice", "port": 8003, "prefix": "/api/analytics/data-quality"},
    "chatbot_service": {"name": "Scoped AI Chatbot Microservice", "port": 8004, "prefix": "/api/chat"},
    "compliance_service": {"name": "GDPR & Compliance Microservice", "port": 8005, "prefix": "/api/compliance"},
}


class LoginRequest(BaseModel):
    employee_id: str


class ChatRequest(BaseModel):
    question: str
    filters: dict[str, str | None] = {}
    history: list[dict[str, str]] = []


class FilterParams(BaseModel):
    evp: str | None = None
    evp1: str | None = None
    evp2: str | None = None
    hrbp: str | None = None
    legal_entity: str | None = None
    location: str | None = None
    employee_group: str | None = None
    job_family: str | None = None
    department: str | None = None
    month: str | None = None


class AuditEventPayload(BaseModel):
    event_type: str
    user_id: str
    role: str
    location: str
    details: str
    status: str = "SUCCESS"


@dataclass
class AccessContext:
    employee_id: str
    employee_name: str
    location: str
    role: str
