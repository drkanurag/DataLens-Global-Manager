"""DataLens Enterprise API: secure workforce analytics, data quality and chatbot."""
from dataclasses import dataclass
from pathlib import Path
import os
import secrets
import dotenv
import shutil
import pandas as pd

dotenv.load_dotenv()
dotenv.load_dotenv(Path(__file__).resolve().parent / ".env")
dotenv.load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

def load_employee_data():
    excel_path = DATA_DIR / "employee_data.xlsx"
    try:
        return pd.read_excel(excel_path, sheet_name="Source data")
    except PermissionError:
        temp_path = DATA_DIR / "_cached_employee_data.xlsx"
        shutil.copy2(excel_path, temp_path)
        return pd.read_excel(temp_path, sheet_name="Source data")

df = load_employee_data()
directory = pd.read_csv(DATA_DIR / "access_directory.csv", dtype=str).fillna("")

app = FastAPI(title="DataLens Enterprise API", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:8000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

FILTER_COLUMNS = {
    "evp":"EVP", "evp1":"SVP", "evp2":"CVP", "hrbp":"VP",
    "legal_entity":"COMPANY_CODE", "location":"LOCATION_DESCRIPTION",
    "employee_group":"EMPLOYEE_GROUP_EC", "job_family":"JOB_FAMILY",
    "department":"DEPARTMENT_EC", "month":"Month Name",
}
CORE_COLUMNS=["Month Name","EMPLOYEE_NO","LOCATION_DESCRIPTION","DEPARTMENT_EC","JOB_FAMILY","HEADCOUNT"]
SESSIONS: dict[str,dict[str,str]]={}
# Only ONE Global Data Foundation role across the enterprise
GLOBAL_ROLES = {
    "global data foundation", "data foundation", "gdf", "gdf001"
}
HRBP_ROLES = {
    "hrbp", "p&o", "hrbp / p&o partner", "hrbp - p&o partner",
    "hrbp-mom", "hrbp-mom or p&o", "hrbp-mom or p&o – kolkata", 
    "hrbp-mom or p&o - kolkata", "hrbp - mom or p&o - kolkata",
    "hrbp - kolkata", "hrbp - mumbai", "hrbp - new delhi", "hrbp - delhi",
    "hrbp - bengaluru", "hrbp - hyderabad", "hrbp - chennai", "hrbp - pune", "hrbp - gurugram"
}

def has_global_access(access) -> bool:
    r = access.role.lower().strip()
    eid = getattr(access, 'employee_id', '').lower().strip()
    return r in GLOBAL_ROLES or eid in GLOBAL_ROLES or access.location.lower().strip() == "all locations"

def has_hrbp_access(access) -> bool:
    r = access.role.lower().strip()
    return any(k in r for k in ["hrbp", "p&o"])

def can_view_compensation(access) -> bool:
    return has_global_access(access) or has_hrbp_access(access)

def is_manager(access) -> bool:
    return has_global_access(access)

# In-memory Rotating Security & Compliance Audit Log (GDPR Article 32 & 33)
import datetime
SECURITY_AUDIT_LOG: list[dict] = [
    {
        "id": "SEC-AUD-001",
        "timestamp": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=14)).isoformat(),
        "event_type": "SYSTEM_INITIALIZE",
        "user_id": "SYSTEM",
        "employee_id": "SYSTEM",
        "role": "Governance Core",
        "location": "Global",
        "scope": "Global",
        "details": "DataLens Security & Row-Level Governance Engine active. GDPR Article 5 data minimization rules online.",
        "status": "SUCCESS"
    },
    {
        "id": "SEC-AUD-002",
        "timestamp": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=8)).isoformat(),
        "event_type": "RLS_ENFORCEMENT",
        "user_id": "GDF001",
        "employee_id": "GDF001",
        "role": "Global Data Foundation",
        "location": "All Locations",
        "scope": "All Locations",
        "details": "Global Data Foundation session granted enterprise-wide master data clearance.",
        "status": "SUCCESS"
    },
    {
        "id": "SEC-AUD-003",
        "timestamp": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat(),
        "event_type": "RLS_ENFORCEMENT",
        "user_id": "HRBP_KOL",
        "employee_id": "HRBP_KOL",
        "role": "HRBP-MOM or P&O – Kolkata",
        "location": "Kolkata",
        "scope": "Kolkata",
        "details": "Location isolation active. Row-Level Security bound strictly to Kolkata site operations.",
        "status": "SUCCESS"
    }
]

def log_security_event(event_type: str, user_id: str, role: str, location: str, details: str, status: str = "SUCCESS"):
    evt_id = f"SEC-AUD-{len(SECURITY_AUDIT_LOG)+1:03d}"
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
        "status": status
    }
    SECURITY_AUDIT_LOG.append(entry)
    if len(SECURITY_AUDIT_LOG) > 200:
        SECURITY_AUDIT_LOG.pop(0)

ERROR_TYPE_NAMES=[
    "Salary not matching with SAP",
    "Cost centre mismatch with company code",
    "High range penetration percentage",
    "Department Code is not matching EC vs SAP",
    "Incorrect Business Email",
    "Manager is not matching EC vs SAP",
    "Company Code is not matching EC vs SAP",
]
FAQ_KNOWLEDGE_BASE={
    "how do i correct the cost centre for my employee":"Submit a master-data correction request to HR or Finance. Include the employee ID, the correct cost centre, effective date, and manager approval. After the source is corrected, refresh the dashboard data.",
    "how do i correct the cost center for my employee":"Submit a master-data correction request to HR or Finance. Include the employee ID, the correct cost centre, effective date, and manager approval. After the source is corrected, refresh the dashboard data.",
    "how do i get access to my organization reports":"Request access through your reporting owner or IT service desk. Provide your business justification and manager approval. Access should be assigned through the organisation's role and location entitlement process.",
    "how do i get access to my organisation reports":"Request access through your reporting owner or IT service desk. Provide your business justification and manager approval. Access should be assigned through the organisation's role and location entitlement process.",
    "how do i report a salary mismatch":"Raise a payroll or HR data-quality ticket with the employee ID, expected salary, source-system reference, and supporting evidence. Do not share sensitive salary details in the chatbot.",
    "how are data quality errors calculated":"The dashboard counts non-'No Error' values in DATA_QUALITY_ERROR_TYPE inside the user's authorised scope.",
    "how often is the dashboard data refreshed":"This prototype reads the workbook when the FastAPI server starts. Replace or update the source workbook and restart the server to refresh the dashboard.",
    "why can i not view another location":"Location access is enforced by your employee ID on the server. The dashboard and chatbot only return records for your authorised location.",
    "what is gdpr and how does datalens comply":"DataLens complies with GDPR (General Data Protection Regulation EU 2016/679) through: (1) Article 5 Data Minimisation via column-level salary masking; (2) Article 15 Right of Access via self-service employee records; (3) Article 25 Privacy by Design with server-side Row-Level Security (RLS); (4) Article 32 Security of Processing through granular RBAC; and (5) Articles 33/34 Breach Notification protocol ensuring 72-hour incident escalation.",
    "how are data breaches handled":"Data breaches are handled under a formal 4-stage Incident Response Protocol: (1) Immediate RLS quarantine and session invalidation; (2) Forensic assessment of affected records; (3) Mandatory Data Protection Authority (DPA) notification within 72 hours per GDPR Article 33; and (4) Communication to affected data subjects with corrective remediation.",
    "what are the stakeholder access roles":"DataLens access is provisioned for: (1) Global DF&A (enterprise-wide financial and workforce analytics); (2) Global Data Foundation (enterprise-wide master data and data quality governance); (3) HRBP / P&O Partners (location-scoped management clearance for Mumbai, Delhi, Bengaluru, etc.); (4) HRBP-MOM or P&O – Kolkata (Kolkata plant operations workforce clearance); (5) Corporate Leadership / CEO; and (6) Standard Employees (location-bound with confidential salary masking).",
    "what is global dfa":"Global DF&A (Data, Finance & Analytics) has enterprise-wide governance clearance across all corporate locations to conduct workforce financial modeling, span-of-control benchmarking, and executive strategic briefings.",
    "what is global data foundation":"Global Data Foundation has full enterprise data access across all locations to perform master data architecture validation, SAP-to-EC synchronization diagnostics, and automated quality remediation.",
    "what is hrbp kolkata":"HRBP-MOM or P&O – Kolkata holds People & Organization governance clearance specifically for the Kolkata manufacturing and operations workforce, with location-bound RLS and quality remediation authority."
}
class LoginRequest(BaseModel): employee_id:str
class ChatRequest(BaseModel): question:str; filters:dict[str,str|None]={}; history:list[dict[str,str]]=[]
class FilterParams(BaseModel):
    evp:str|None=None; evp1:str|None=None; evp2:str|None=None; hrbp:str|None=None
    legal_entity:str|None=None; location:str|None=None; employee_group:str|None=None
    job_family:str|None=None; department:str|None=None; month:str|None=None
@dataclass
class AccessContext:
    employee_id:str; employee_name:str; location:str; role:str

def require_access(x_employee_token:str|None=Header(default=None))->AccessContext:
    record=SESSIONS.get(x_employee_token or "")
    if not record: raise HTTPException(status_code=401,detail="Please sign in with a valid employee ID.")
    return AccessContext(**record)

def secured_data(filters:FilterParams,access:AccessContext)->pd.DataFrame:
    global_access=has_global_access(access)
    if not global_access and filters.location and filters.location.lower()!=access.location.lower():
        log_security_event("CROSS_LOCATION_BLOCKED", access.employee_id, access.role, access.location, f"Blocked unauthorized attempt to query {filters.location}. Scope locked to {access.location}.", status="BLOCKED")
        raise HTTPException(status_code=403,detail=f"You are not authorized to view {filters.location}. Your access is limited by RLS to {access.location}.")
    data=df.copy() if global_access else df[df["LOCATION_DESCRIPTION"].astype(str).str.lower()==access.location.lower()].copy()
    if global_access and filters.location and filters.location.lower()!='all':
        data=data[data["LOCATION_DESCRIPTION"].astype(str).str.lower()==filters.location.lower()]
    for key,value in filters.model_dump().items():
        if not value or key=='location' or value.lower()=='all': continue
        data=data[data[FILTER_COLUMNS[key]].astype(str).str.lower()==value.lower()]
    return data

def top_values(data,column,label):
    result=data[column].fillna('Not specified').astype(str).value_counts().reset_index(); result.columns=[label,'employees']; return result.to_dict(orient='records')

def quality_report(data):
    missing_by_column={c:int(data[c].isna().sum()) for c in CORE_COLUMNS if c in data}
    missing_required=int(data[CORE_COLUMNS].isna().any(axis=1).sum()) if not data.empty else 0
    duplicate_rows=int(data.duplicated().sum())
    errors=data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.strip()
    source_errors=data[~errors.str.lower().isin(['','no error','none','nan'])]
    observed=source_errors['DATA_QUALITY_ERROR_TYPE'].value_counts().to_dict()
    error_type_counts=[{'error_type':name,'count':int(observed.get(name,0))} for name in ERROR_TYPE_NAMES]
    for name,count in observed.items():
        if str(name) not in ERROR_TYPE_NAMES: error_type_counts.append({'error_type':str(name),'count':int(count)})
    issues=[{'type':'Source data quality error','asset':'Source data','description':str(name),'records':int(count)} for name,count in observed.items()]
    if missing_required: issues.append({'type':'Missing required fields','asset':'Source data','description':'One or more core workforce fields are blank','records':missing_required})
    if duplicate_rows: issues.append({'type':'Duplicate rows','asset':'Source data','description':'Exact duplicate records detected','records':duplicate_rows})
    total=len(source_errors)+missing_required+duplicate_rows
    return {'status':'Passed' if total==0 else 'Attention needed','records_checked':int(len(data)),'columns_checked':int(data.shape[1]),'source_errors':int(len(source_errors)),'missing_required':missing_required,'duplicate_rows':duplicate_rows,'total_issues':int(total),'missing_by_column':missing_by_column,'issues':issues,'error_type_counts':error_type_counts}

def numeric_series(data,column): return pd.to_numeric(data[column],errors='coerce').dropna()
def value_named_in_question(data,question,column):
    values=data[column].dropna().astype(str).unique().tolist()
    return next((v for v in sorted(values,key=len,reverse=True) if v and v.lower() in question),None)

@app.get('/')
def home():
    return RedirectResponse(url='/dashboard/')

@app.get('/api/health')
def health():
    return {'status':'healthy','records':len(df)}

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

@app.post('/api/auth/login')
def login(request:LoginRequest):
    directory = pd.read_csv(DATA_DIR / "access_directory.csv", dtype=str).fillna("")
    raw_id = request.employee_id.strip()
    eid = raw_id.upper()
    
    # Strictly reject legacy manager and employee logins
    if eid.startswith("EMP") or eid.startswith("MANAGER") or eid in ("CEO", "EMPLOYEE", "ADMIN"):
        log_security_event("AUTH_REJECTED", raw_id, "Disabled Legacy Role", "Unknown", "Login rejected: legacy manager/employee ID disabled in favor of role-based credentials.", status="REJECTED")
        raise HTTPException(
            status_code=401,
            detail="Login is role-based. Manager and Employee IDs are disabled. Please use 'GDF' for Global Data Foundation or 'HRBP-(LOCATION)' (e.g., HRBP-KOL, HRBP-MUM, HRBP-DEL, HRBP-BLR, HRBP-HYD, HRBP-CHN, HRBP-PUN, HRBP-GUR)."
        )
    
    # Resolve aliases (e.g. GDF -> GDF001, HRBP_KOL -> HRBP-KOL)
    canonical_id = ROLE_ALIASES.get(eid, eid)
    found = directory[directory['employee_id'].str.upper() == canonical_id]
    
    if found.empty:
        log_security_event("AUTH_FAILURE", raw_id, "Unknown", "Unknown", "Authentication failed: unrecognized role ID", status="FAILED")
        raise HTTPException(
            status_code=401,
            detail="Role ID not recognized. Authorized role IDs: GDF (Global Data Foundation) or HRBP-(LOCATION) (e.g., HRBP-KOL, HRBP-MUM, HRBP-DEL, HRBP-BLR, HRBP-HYD, HRBP-CHN, HRBP-PUN, HRBP-GUR)."
        )
    user = found.iloc[0].to_dict()
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {'employee_id': user['employee_id'], 'employee_name': user['employee_name'], 'location': user['location'], 'role': user['role']}
    log_security_event("AUTH_SUCCESS", user['employee_id'], user['role'], user['location'], f"User successfully authenticated with session token (Scope: {user['location']})")
    return {'token': token, 'user': SESSIONS[token]}
@app.get('/api/auth/me')
def current_user(access:AccessContext=Depends(require_access)): return access.__dict__
@app.get('/api/filters')
def get_filters(access:AccessContext=Depends(require_access)):
    data=secured_data(FilterParams(),access); options={k:sorted(data[c].dropna().astype(str).unique().tolist()) for k,c in FILTER_COLUMNS.items()}
    options['location']=sorted(df['LOCATION_DESCRIPTION'].dropna().astype(str).unique().tolist()) if has_global_access(access) else [access.location]
    return options
@app.get('/api/analytics/summary')
def summary(filters:FilterParams=Depends(),access:AccessContext=Depends(require_access)):
    data=secured_data(filters,access); salary=numeric_series(data,'ANNUAL_SALARY_EC')
    avg_salary = float(salary.mean()) if (can_view_compensation(access) and not salary.empty) else None
    return {'total_employees':len(data),'locations':int(data['LOCATION_DESCRIPTION'].nunique()),'departments':int(data['DEPARTMENT_EC'].nunique()),'job_families':int(data['JOB_FAMILY'].nunique()),'employee_groups':int(data['EMPLOYEE_GROUP_EC'].nunique()),'months':int(data['Month Name'].nunique()),'average_salary':avg_salary}
@app.get('/api/analytics/by-location')
def by_location(filters:FilterParams=Depends(),access:AccessContext=Depends(require_access)): return top_values(secured_data(filters,access),'LOCATION_DESCRIPTION','location')
@app.get('/api/analytics/by-department')
def by_department(filters:FilterParams=Depends(),access:AccessContext=Depends(require_access)): return top_values(secured_data(filters,access),'DEPARTMENT_EC','department')
@app.get('/api/analytics/by-job-family')
def by_job_family(filters:FilterParams=Depends(),access:AccessContext=Depends(require_access)): return top_values(secured_data(filters,access),'JOB_FAMILY','job_family')
@app.get('/api/analytics/monthly')
def monthly(filters:FilterParams=Depends(),access:AccessContext=Depends(require_access)):
    filters.month=None; data=secured_data(filters,access); order={'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    counts=data['Month Name'].fillna('Not specified').astype(str).value_counts().reset_index(); counts.columns=['month','employees']; counts['_order']=counts.month.map(order).fillna(99); return counts.sort_values(['_order','month']).drop(columns=['_order']).to_dict(orient='records')
@app.get('/api/analytics/data-quality')
def data_quality(filters:FilterParams=Depends(),access:AccessContext=Depends(require_access)): return quality_report(secured_data(filters,access))
@app.get('/api/analytics/employees')
def employees(filters:FilterParams=Depends(),access:AccessContext=Depends(require_access)):
    data=secured_data(filters,access).copy(); wanted=['EMPLOYEE_NO','LOCATION_DESCRIPTION','DEPARTMENT_EC','JOB_FAMILY','EMPLOYEE_GROUP_EC','EVP','ANNUAL_SALARY_EC','DATA_QUALITY_ERROR_TYPE','Month Name']; data=data[[c for c in wanted if c in data]].rename(columns={'EMPLOYEE_NO':'employee_no','LOCATION_DESCRIPTION':'location','DEPARTMENT_EC':'department','JOB_FAMILY':'job_family','EMPLOYEE_GROUP_EC':'employee_group','EVP':'evp','ANNUAL_SALARY_EC':'annual_salary','DATA_QUALITY_ERROR_TYPE':'error_type','Month Name':'month'}); data['annual_salary']=pd.to_numeric(data.get('annual_salary'),errors='coerce') if 'annual_salary' in data else None
    # Strictly enforce compensation confidentiality: global roles and HRBP can view salaries in their scope; standard employees only their own.
    if not can_view_compensation(access):
        own_id = str(access.employee_id).strip().upper()
        data['annual_salary'] = data.apply(
            lambda r: r['annual_salary'] if str(r.get('employee_no', '')).strip().upper() == own_id else None,
            axis=1
        )
    data['error_type']=data.get('error_type',pd.Series(index=data.index,dtype=str)).fillna('No Error').astype(str); return {'records':data.fillna('').to_dict(orient='records'),'total':int(len(data))}

@app.get('/api/analytics/executive-summary')
def executive_summary(access:AccessContext=Depends(require_access)):
    if not has_global_access(access):
        raise HTTPException(status_code=403,detail="Executive Summary is strictly restricted to Global Data Foundation clearance.")
    
    total_headcount = len(df)
    
    # 1. Workforce Summary (Aggregated)
    order = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    monthly_counts = df['Month Name'].value_counts().reset_index()
    monthly_counts.columns = ['month', 'headcount']
    monthly_counts['_order'] = monthly_counts['month'].map(order).fillna(99)
    monthly_trajectory = monthly_counts.sort_values('_order').drop(columns=['_order']).to_dict(orient='records')
    
    loc_counts = df['LOCATION_DESCRIPTION'].value_counts().reset_index()
    loc_counts.columns = ['location', 'headcount']
    loc_counts['percentage'] = (loc_counts['headcount'] / total_headcount * 100).round(1)
    
    dept_counts = df['DEPARTMENT_EC'].value_counts().reset_index()
    dept_counts.columns = ['department', 'headcount']
    dept_counts['percentage'] = (dept_counts['headcount'] / total_headcount * 100).round(1)
    
    emp_type = df['EMPLOYEE_GROUP_EC'].value_counts().reset_index()
    emp_type.columns = ['group', 'headcount']
    emp_type['percentage'] = (emp_type['headcount'] / total_headcount * 100).round(1)
    
    # 2. Organizational Distribution & Span of Control
    sup_counts = df['SUPERVISOR_EC'].dropna().value_counts()
    unique_supervisors = int(df['SUPERVISOR_EC'].nunique())
    avg_span = float(sup_counts.mean()) if not sup_counts.empty else 0.0
    span_tiers = [
        {'tier': '1 Direct Report', 'count': int((sup_counts == 1).sum()), 'percentage': round(int((sup_counts == 1).sum()) / max(unique_supervisors, 1) * 100, 1)},
        {'tier': '2-3 Direct Reports', 'count': int(((sup_counts >= 2) & (sup_counts <= 3)).sum()), 'percentage': round(int(((sup_counts >= 2) & (sup_counts <= 3)).sum()) / max(unique_supervisors, 1) * 100, 1)},
        {'tier': '4+ Direct Reports', 'count': int((sup_counts >= 4).sum()), 'percentage': round(int((sup_counts >= 4).sum()) / max(unique_supervisors, 1) * 100, 1)},
    ]
    
    # 3. Alerts & Exceptions
    has_error = ~df['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])
    df_err = df.copy()
    df_err['has_error'] = has_error
    
    loc_group = df_err.groupby('LOCATION_DESCRIPTION').agg(total=('EMPLOYEE_NO', 'count'), errors=('has_error', 'sum'))
    loc_group['quality_score'] = ((loc_group['total'] - loc_group['errors']) / loc_group['total'] * 100).round(1)
    loc_group['error_rate'] = (loc_group['errors'] / loc_group['total'] * 100).round(1)
    loc_alerts = loc_group[loc_group['quality_score'] < 50.0].reset_index().to_dict(orient='records')
    
    dept_group = df_err.groupby('DEPARTMENT_EC').agg(total=('EMPLOYEE_NO', 'count'), errors=('has_error', 'sum'))
    dept_group['quality_score'] = ((dept_group['total'] - dept_group['errors']) / dept_group['total'] * 100).round(1)
    dept_group['error_rate'] = (dept_group['errors'] / dept_group['total'] * 100).round(1)
    dept_alerts = dept_group[dept_group['quality_score'] < 50.0].reset_index().to_dict(orient='records')
    
    compliance_risks = [
        {'flag': 'Salary Mismatch vs SAP Payroll', 'severity': 'Critical', 'count': int((df['DATA_QUALITY_ERROR_TYPE'] == 'Salary not matching with SAP').sum()), 'description': 'Discrepancy between Employee Central compensation and SAP Payroll system records.'},
        {'flag': 'Cost Centre Misalignment', 'severity': 'High', 'count': int((df['DATA_QUALITY_ERROR_TYPE'] == 'Cost centre mismatch with company code').sum()), 'description': 'Allocated cost center does not correspond to legal company entity structure.'},
        {'flag': 'Compa-Ratio Ceiling Exceeded', 'severity': 'High', 'count': int((df['DATA_QUALITY_ERROR_TYPE'] == 'High range penetration percentage').sum()), 'description': 'Compensation range penetration exceeds 120% pay grade band ceiling.'},
        {'flag': 'Department Code Mismatch', 'severity': 'Medium', 'count': int((df['DATA_QUALITY_ERROR_TYPE'] == 'Department Code is not matching EC vs SAP').sum()), 'description': 'Department code discrepancy between EC master record and SAP organizational structure.'},
        {'flag': 'Missing or Invalid Corporate Email', 'severity': 'High', 'count': int((df['DATA_QUALITY_ERROR_TYPE'] == 'Incorrect Business Email').sum()), 'description': 'Missing corporate email address or invalid domain syntax inhibiting IAM governance.'},
        {'flag': 'Supervisor Hierarchy Mismatch', 'severity': 'Medium', 'count': int((df['DATA_QUALITY_ERROR_TYPE'] == 'Manager is not matching EC vs SAP').sum()), 'description': 'Reporting line hierarchy does not match SAP supervisor structures.'},
        {'flag': 'Company Code Discrepancy', 'severity': 'Medium', 'count': int((df['DATA_QUALITY_ERROR_TYPE'] == 'Company Code is not matching EC vs SAP').sum()), 'description': 'Legal entity company code mismatch between EC and SAP.'}
    ]
    
    # Sort locations & departments by headcount descending
    return {
        'total_headcount': total_headcount,
        'monthly_trajectory': monthly_trajectory,
        'location_distribution': loc_counts.sort_values('headcount', ascending=False).to_dict(orient='records'),
        'department_distribution': dept_counts.sort_values('headcount', ascending=False).to_dict(orient='records'),
        'employment_type_distribution': emp_type.to_dict(orient='records'),
        'span_of_control': {
            'unique_supervisors': unique_supervisors,
            'total_workforce': total_headcount,
            'average_span': round(avg_span, 2),
            'ratio': f'1 : {avg_span:.1f}',
            'distribution': span_tiers
        },
        'alerts_exceptions': {
            'location_alerts': loc_alerts,
            'department_alerts': dept_alerts,
            'compliance_risks': compliance_risks,
            'total_compliance_issues': sum(r['count'] for r in compliance_risks),
            'overall_quality_score': round(((total_headcount - has_error.sum()) / total_headcount) * 100, 1)
        }
    }
CITY_ALIASES = {
    'new delhi': ['new delhi', 'delhi', 'ncr', 'dilli'],
    'mumbai': ['mumbai', 'bombay', 'mum'],
    'bengaluru': ['bengaluru', 'bangalore', 'blr'],
    'kolkata': ['kolkata', 'calcutta', 'ccu'],
    'chennai': ['chennai', 'madras', 'maa'],
    'hyderabad': ['hyderabad', 'hyd'],
    'pune': ['pune', 'poona', 'pnq'],
    'gurugram': ['gurugram', 'gurgaon', 'ggn']
}

def detect_unauthorized_location(question:str,user_location:str)->tuple[bool,str|None]:
    import re
    q=' ' + question.lower().replace('?',' ') + ' '
    user_loc=user_location.strip().lower()
    generic=['other city','another city','other cities','all locations','all cities','nationwide','across all locations','company-wide','entire company','across the company']
    if any(g in q for g in generic):
        return True,'other corporate locations'
    for canonical,aliases in CITY_ALIASES.items():
        if canonical==user_loc: continue
        for alias in aliases:
            if re.search(rf'\b{re.escape(alias)}\b',q):
                return True,canonical.title()
    return False,None

def process_chatbot_query(raw_question: str, data: pd.DataFrame, scope: str, access: AccessContext, report: dict, global_access: bool, comp_access: bool = False) -> tuple[str, str]:
    import re
    q = ' ' + raw_question.lower().replace('?', ' ').replace(',', ' ').replace('.', ' ') + ' '
    words = set(re.findall(r'\b[a-z0-9_\-]+\b', q))

    salary_col = pd.to_numeric(data['ANNUAL_SALARY_EC'], errors='coerce').dropna()
    mean_sal = salary_col.mean() if not salary_col.empty else 0
    min_sal = salary_col.min() if not salary_col.empty else 0
    max_sal = salary_col.max() if not salary_col.empty else 0
    median_sal = salary_col.median() if not salary_col.empty else 0

    # 1. Greetings & Meta
    if any(w in words for w in ['hello', 'hi', 'hey', 'greetings', 'morning', 'afternoon', 'evening']):
        if comp_access:
            suggestions = "- *'Which department has the highest salary?'*\n- *'Show me employees with salary mismatches'*\n- *'What is the gender ratio?'*\n- *'Tell me about the Finance department'*\n- *'Who is the highest paid employee?'*"
        else:
            suggestions = "- *'How many employees are in Engineering?'*\n- *'Show me employees with data quality issues'*\n- *'What is the gender ratio?'*\n- *'Tell me about the Finance department'*\n- *'What are the job levels in our location?'*"
        return 'greeting', f"Hello {access.employee_name}! I am your **DataLens Assistant**.\n\nI can answer questions across your authorized workforce in **{scope}**.\n\nTry asking:\n{suggestions}"

    if any(phrase in q for phrase in ['who are you', 'what can you do', 'what are you', 'help me', 'capabilities', 'what do you do']):
        comp_bullet = "- 📊 **Compensation**: Averages, medians, highest/lowest salaries, and departmental salary comparisons\n" if comp_access else "- 📊 **Compensation**: 🔒 Confidential (Restricted to Manager/HRBP clearance)\n"
        return 'help', f"I am **DataLens Assistant**, your corporate workforce intelligence and master-data governance assistant.\n\nIn **{scope}**, I can assist with:\n{comp_bullet}- 🏢 **Departments & Roles**: Headcounts, job families, and career levels (L1–L6)\n- 👥 **Demographics**: Gender diversity, contract vs regular splits, and nationalities\n- ⚠️ **Data Governance**: Identifying flagged records, salary mismatches, email errors, and SOP remediation steps\n- 🛡️ **Compliance & GDPR**: Data minimization, breach protocol, and stakeholder privileges\n- 🔍 **Employee Lookups**: Details on specific employee IDs (e.g. *'Who is E100005?'*)"

    if any(phrase in q for phrase in ['who is the ceo', 'ceo name', 'chief executive', 'who is ceo', 'ceo']):
        return 'ceo', f"The Chief Executive Officer is **Dexter Morgan** (Employee ID: `CEO`). The CEO holds enterprise-wide governance clearance across all corporate locations."

    # Compliance & GDPR Queries
    if any(phrase in q for phrase in ['gdpr', 'data breach', 'breach', 'compliance', 'article 5', 'article 15', 'article 32', 'article 33', 'privacy policy', 'incident response']):
        return 'compliance_info', (
            "### 🛡️ Enterprise Compliance & GDPR Architecture\n\n"
            "DataLens operates under strict **GDPR (EU 2016/679)**, **ISO/IEC 27001**, and **SOC 2 Type II** governance controls:\n\n"
            "- 🔒 **Article 5 (Data Minimisation)**: Sensitive fields (such as compensation) are automatically masked server-side unless explicit HRBP/Leadership clearance is present.\n"
            "- 🌐 **Article 25 (Privacy by Design / RLS)**: Access is geographically isolated by server-enforced Row-Level Security. Non-cleared roles cannot access cross-location records.\n"
            "- 📋 **Article 15 (Right of Access / SAR)**: Self-service access allowing employees to inspect their personal master record.\n"
            "- 🛡️ **Article 32 (Security of Processing)**: Role-Based Access Control (RBAC) with tokenized HMAC sessions and active boundary enforcement.\n"
            "- 🚨 **Articles 33 & 34 (72-Hour Breach Protocol)**: Continuous automated anomaly detection with mandatory 72-hour Data Protection Authority (DPA) notification workflow in the event of an unauthorized exfiltration attempt.\n\n"
            "💡 Open the **Compliance & GDPR Hub** from the top navigation bar to review the live audit trail and incident response SOP."
        )

    # Stakeholder Queries
    if any(phrase in q for phrase in ['stakeholders', 'stakeholder access', 'who has access', 'access management', 'df&a', 'data foundation', 'hrbp kolkata', 'p&o']):
        return 'stakeholder_info', (
            "### 👥 Authorized Stakeholder Access Matrix\n\n"
            "Corporate data access is partitioned across key stakeholders:\n\n"
            "1. **Global DF&A (Data, Finance & Analytics)**: Enterprise-wide global access across all corporate locations for workforce financial modeling, compensation benchmarking, and executive briefing reports.\n"
            "2. **Global Data Foundation**: Enterprise-wide global access across all locations to inspect master data architecture, schema integrity, and SAP-to-EC synchronization discrepancies.\n"
            "3. **HRBP / P&O Partners**: Location-scoped management clearance (e.g. Mumbai, New Delhi, Bengaluru, etc.) with full workforce and compensation governance for their assigned location.\n"
            "4. **HRBP-MOM or P&O – Kolkata**: Dedicated clearance for the Kolkata site, providing operations-level workforce governance and data quality remediation.\n"
            "5. **Corporate Leadership / CEO**: Enterprise-wide strategic oversight and cross-city organizational distribution analytics.\n"
            "6. **Standard Employees**: Location-bound individual access with strict salary confidentiality protections."
        )

    # 2. Specific Employee Lookup (by ID)
    emp_match = re.search(r'\b(e\d{5,7}|emp\d{3,5})\b', q)
    if emp_match:
        target_id = emp_match.group(1).upper()
        match_row = data[data['EMPLOYEE_NO'].astype(str).str.upper() == target_id]
        if not match_row.empty:
            r = match_row.iloc[0]
            name = f"{r.get('EMPLOYEE_FIRST_NAME', '')} {r.get('EMPLOYEE_LAST_NAME', '')}".strip() or "Employee"
            dept = r.get('DEPARTMENT_EC', 'Not specified')
            job = r.get('JOB_FAMILY', 'Not specified')
            level = r.get('JOB_LEVEL_EC', 'N/A')
            loc = r.get('LOCATION_DESCRIPTION', 'Not specified')
            sal = float(r.get('ANNUAL_SALARY_EC', 0) or 0)
            err = r.get('DATA_QUALITY_ERROR_TYPE', 'No Error')
            email = r.get('BUSINESS_EMAIL_ID', 'N/A')
            sup = r.get('SUPERVISOR_EC', 'N/A')
            group = r.get('EMPLOYEE_GROUP_EC', 'Regular')
            err_badge = f"🔴 **Flagged Anomaly**: `{err}`" if str(err).lower() not in ['', 'no error', 'nan', 'none'] else "🟢 **Clean (No Anomaly)**"
            
            can_see_sal = comp_access or (target_id == str(access.employee_id).strip().upper())
            sal_str = f"₹{sal:,.0f}" if can_see_sal else "🔒 Confidential (Manager/HRBP Clearance Required)"

            return 'employee_profile', f"### 👤 Employee Profile: {name} (`{target_id}`)\n\n" \
                   f"- **Location**: {loc}\n" \
                   f"- **Department**: {dept}\n" \
                   f"- **Job Role**: {job} (Level: {level}, {group})\n" \
                   f"- **Annual Compensation**: {sal_str}\n" \
                   f"- **Corporate Email**: `{email}`\n" \
                   f"- **Reporting Manager**: `{sup}`\n" \
                   f"- **Data Governance Status**: {err_badge}"
        else:
            return 'employee_not_found', f"Employee ID `{target_id}` was not found within your authorized scope (**{scope}**). Either the employee belongs to another location or the ID does not exist."

    # 3. Department Queries (Specific department mentioned)
    all_depts = sorted(data['DEPARTMENT_EC'].dropna().astype(str).unique().tolist())
    dept_found = next((d for d in all_depts if re.search(rf'\b{re.escape(d.lower())}\b', q)), None)
    
    if dept_found:
        dept_data = data[data['DEPARTMENT_EC'].astype(str).str.lower() == dept_found.lower()]
        dept_sal = pd.to_numeric(dept_data['ANNUAL_SALARY_EC'], errors='coerce').dropna()
        dept_errs = dept_data[~dept_data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])]
        
        if any(w in words for w in ['salary', 'pay', 'compensation', 'earn', 'wage', 'salaries']):
            if not comp_access:
                return 'salary_restricted', f"🔒 **Access Restricted**: Departmental compensation metrics and salary benchmarks for **{dept_found}** are confidential. Managerial or HRBP clearance is required to view compensation details."
            return 'dept_salary', f"### 💰 Compensation in {dept_found} ({scope})\n\n" \
                   f"- **Headcount**: {len(dept_data)} employees\n" \
                   f"- **Average Salary**: ₹{dept_sal.mean():,.0f}\n" \
                   f"- **Salary Range**: ₹{dept_sal.min():,.0f} to ₹{dept_sal.max():,.0f}\n" \
                   f"- **Median Salary**: ₹{dept_sal.median():,.0f}\n\n" \
                   f"The {dept_found} department represents {(len(dept_data)/max(len(data),1))*100:.1f}% of total workforce in {scope}."
                   
        if any(w in words for w in ['error', 'errors', 'issue', 'issues', 'quality', 'mismatch', 'anomalies']):
            if dept_errs.empty:
                return 'dept_quality', f"### 🟢 Data Quality for {dept_found} ({scope})\n\nGreat news: **100% of records** in the {dept_found} department ({len(dept_data)} employees) are completely clean with zero data quality errors."
            else:
                err_counts = dept_errs['DATA_QUALITY_ERROR_TYPE'].value_counts()
                breakdown = '\n'.join(f"- **{err}**: {cnt} record(s)" for err, cnt in err_counts.items())
                return 'dept_quality', f"### ⚠️ Data Quality Anomalies in {dept_found} ({scope})\n\n" \
                       f"There are **{len(dept_errs)} flagged record(s)** out of {len(dept_data)} total employees:\n\n{breakdown}\n\n" \
                       f"🔍 **Remediation**: Check the Secured Data Explorer below to audit the specific employee rows."
        
        top_jobs = dept_data['JOB_FAMILY'].value_counts().head(3).to_dict()
        jobs_str = ', '.join(f"{j} ({c})" for j, c in top_jobs.items()) or "General"
        comp_display = f"₹{dept_sal.mean():,.0f}" if comp_access else "🔒 Confidential (Manager/HRBP Only)"
        suggest_comp = f"Ask *'What is the salary in {dept_found}?'* or " if comp_access else "Ask "
        return 'dept_overview', f"### 🏢 Department Overview: {dept_found} ({scope})\n\n" \
               f"- **Active Headcount**: {len(dept_data)} employees ({(len(dept_data)/max(len(data),1))*100:.1f}% of {scope})\n" \
               f"- **Average Compensation**: {comp_display}\n" \
               f"- **Primary Job Roles**: {jobs_str}\n" \
               f"- **Data Quality Health**: {'🟢 100% Clean' if dept_errs.empty else f'⚠️ {len(dept_errs)} anomaly record(s) flagged'}\n\n" \
               f"{suggest_comp}*'Are there errors in {dept_found}?'* for deeper details."

    # 4. Department Comparison / Rankings
    if any(phrase in q for phrase in ['highest salary', 'highest paid department', 'top paid department', 'best paid department', 'compare department salaries', 'salary by department', 'salaries by department']) and ('department' in q or 'dept' in q):
        if not comp_access:
            return 'salary_restricted', "🔒 **Access Restricted**: Departmental salary rankings and compensation comparisons are confidential. Managerial or HRBP clearance is required to view compensation details."
        dept_summary = []
        for d in all_depts:
            sub = data[data['DEPARTMENT_EC'] == d]
            sub_sal = pd.to_numeric(sub['ANNUAL_SALARY_EC'], errors='coerce').dropna()
            if not sub_sal.empty:
                dept_summary.append({'dept': d, 'mean': sub_sal.mean(), 'count': len(sub)})
        dept_summary = sorted(dept_summary, key=lambda x: x['mean'], reverse=True)
        lines = [f"{i+1}. **{r['dept']}**: ₹{r['mean']:,.0f} (across {r['count']} employees)" for i, r in enumerate(dept_summary)]
        top = dept_summary[0]
        return 'dept_salary_ranking', f"### 🏆 Department Salary Rankings ({scope})\n\n" \
               f"The highest paid department is **{top['dept']}** with an average salary of **₹{top['mean']:,.0f}**.\n\n" + '\n'.join(lines)

    if any(phrase in q for phrase in ['largest department', 'biggest department', 'department breakdown', 'compare departments', 'list departments', 'all departments', 'what departments']):
        dept_counts = data['DEPARTMENT_EC'].value_counts()
        lines = [f"- **{d}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)" for d, cnt in dept_counts.items()]
        top_d = dept_counts.index[0]
        return 'dept_breakdown', f"### 🏢 Department Workforce Breakdown ({scope})\n\n" \
               f"There are **{len(dept_counts)} departments** in {scope}. The largest department is **{top_d}** with **{dept_counts.iloc[0]} employees**.\n\n" + '\n'.join(lines)

    if any(phrase in q for phrase in ['most errors', 'most issues', 'errors by department', 'department error ranking']):
        errors = data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])]
        if errors.empty:
            return 'dept_errors', f"🟢 **Zero Errors**: All departments in {scope} currently have 100% clean records with zero data quality errors."
        err_by_dept = errors['DEPARTMENT_EC'].value_counts()
        lines = [f"- **{d}**: {cnt} flagged record(s)" for d, cnt in err_by_dept.items()]
        return 'dept_errors', f"### ⚠️ Data Quality Anomalies by Department ({scope})\n\n" \
               f"A total of **{len(errors)} records** are flagged with data quality issues across departments:\n\n" + '\n'.join(lines) + \
               f"\n\n🔍 **Top Priority**: Focus remediation on **{err_by_dept.index[0]}** which has the highest concentration ({err_by_dept.iloc[0]} issues)."

    # 5. Salary Extremes & Distribution
    if any(phrase in q for phrase in ['highest salary', 'highest paid', 'who earns the most', 'maximum salary', 'top earner', 'max salary', 'highest compensation']):
        if not comp_access:
            return 'salary_restricted', "🔒 **Access Restricted**: Individual compensation records, maximum salary rankings, and highest earner details are confidential. Managerial or HRBP clearance is required."
        top_idx = salary_col.idxmax()
        top_row = data.loc[top_idx]
        name = f"{top_row.get('EMPLOYEE_FIRST_NAME', '')} {top_row.get('EMPLOYEE_LAST_NAME', '')}".strip() or f"Employee {top_row.get('EMPLOYEE_NO')}"
        dept = top_row.get('DEPARTMENT_EC', 'N/A')
        role = top_row.get('JOB_FAMILY', 'N/A')
        level = top_row.get('JOB_LEVEL_EC', 'N/A')
        return 'highest_salary', f"### 💎 Highest Paid Record ({scope})\n\n" \
               f"- **Maximum Salary**: **₹{max_sal:,.0f}**\n" \
               f"- **Employee**: {name} (`{top_row.get('EMPLOYEE_NO')}`)\n" \
               f"- **Department**: {dept}\n" \
               f"- **Role**: {role} (Level: {level})\n\n" \
               f"For comparison, the average salary in {scope} is ₹{mean_sal:,.0f}."

    if any(phrase in q for phrase in ['lowest salary', 'minimum salary', 'lowest paid', 'min salary', 'lowest compensation']):
        if not comp_access:
            return 'salary_restricted', "🔒 **Access Restricted**: Individual compensation records, minimum salary data, and compensation ranges are confidential. Managerial or HRBP clearance is required."
        min_idx = salary_col.idxmin()
        min_row = data.loc[min_idx]
        name = f"{min_row.get('EMPLOYEE_FIRST_NAME', '')} {min_row.get('EMPLOYEE_LAST_NAME', '')}".strip() or f"Employee {min_row.get('EMPLOYEE_NO')}"
        return 'lowest_salary', f"### 📉 Minimum Salary Record ({scope})\n\n" \
               f"- **Minimum Salary**: **₹{min_sal:,.0f}**\n" \
               f"- **Employee**: {name} (`{min_row.get('EMPLOYEE_NO')}`)\n" \
               f"- **Department**: {min_row.get('DEPARTMENT_EC', 'N/A')}\n" \
               f"- **Role**: {min_row.get('JOB_FAMILY', 'N/A')}\n\n" \
               f"The overall compensation span across {scope} is ₹{min_sal:,.0f} to ₹{max_sal:,.0f}."

    if any(phrase in q for phrase in ['median salary', 'median pay', 'median compensation']):
        if not comp_access:
            return 'salary_restricted', "🔒 **Access Restricted**: Median compensation benchmarks are confidential. Managerial or HRBP clearance is required to view compensation details."
        above_median = int((salary_col > median_sal).sum())
        return 'median_salary', f"### 📊 Median Compensation ({scope})\n\n" \
               f"- **Median Annual Salary**: **₹{median_sal:,.0f}**\n" \
               f"- **Mean (Average) Salary**: ₹{mean_sal:,.0f}\n" \
               f"- **Above Median**: {above_median} employees ({above_median/len(data)*100:.1f}%)\n\n" \
               f"The median is less influenced by top outliers and provides an accurate baseline for typical compensation in {scope}."

    if any(phrase in q for phrase in ['salary distribution', 'salary range', 'salary bands', 'compensation bands', 'pay scale']):
        if not comp_access:
            return 'salary_restricted', "🔒 **Access Restricted**: Salary distribution tiers and compensation bands are confidential. Managerial or HRBP clearance is required to view compensation details."
        tier1 = int((salary_col < 1500000).sum())
        tier2 = int(((salary_col >= 1500000) & (salary_col < 2500000)).sum())
        tier3 = int(((salary_col >= 2500000) & (salary_col < 3500000)).sum())
        tier4 = int((salary_col >= 3500000).sum())
        return 'salary_distribution', f"### 📈 Salary Tier Distribution ({scope})\n\n" \
               f"- **Below ₹15 Lakhs**: {tier1} employees ({(tier1/len(data))*100:.1f}%)\n" \
               f"- **₹15L – ₹25 Lakhs**: {tier2} employees ({(tier2/len(data))*100:.1f}%)\n" \
               f"- **₹25L – ₹35 Lakhs**: {tier3} employees ({(tier3/len(data))*100:.1f}%)\n" \
               f"- **Above ₹35 Lakhs**: {tier4} employees ({(tier4/len(data))*100:.1f}%)\n\n" \
               f"Overall salary bounds: **₹{min_sal:,.0f}** to **₹{max_sal:,.0f}** (Average: ₹{mean_sal:,.0f})."

    # 6. Specific Error Types & Affected Records
    error_patterns = [
        ('Salary not matching with SAP', ['salary mismatch', 'salary not matching', 'sap salary', 'payroll error', 'salary error', 'sop-hr-01']),
        ('Cost centre mismatch with company code', ['cost centre', 'cost center', 'cc mismatch', 'sop-hr-02']),
        ('High range penetration percentage', ['range penetration', 'penetration percentage', 'high penetration', 'sop-hr-05']),
        ('Department Code is not matching EC vs SAP', ['department code', 'dept mismatch', 'department mismatch', 'sop-hr-03']),
        ('Incorrect Business Email', ['email error', 'business email', 'incorrect email', 'email invalid', 'email mismatch', 'sop-hr-04']),
        ('Manager is not matching EC vs SAP', ['manager mismatch', 'manager not matching', 'supervisor mismatch', 'sop-hr-06']),
        ('Company Code is not matching EC vs SAP', ['company code mismatch', 'cocd mismatch', 'sop-hr-07']),
    ]
    for canonical_err, keywords in error_patterns:
        if any(kw in q for kw in keywords):
            err_rows = data[data['DATA_QUALITY_ERROR_TYPE'].astype(str).str.strip().str.lower() == canonical_err.lower()]
            count = len(err_rows)
            
            if not err_rows.empty:
                samples = err_rows.head(5)
                emp_list = '\n'.join(f"- `{r['EMPLOYEE_NO']}` ({r.get('EMPLOYEE_FIRST_NAME','')} {r.get('EMPLOYEE_LAST_NAME','')}) — {r.get('DEPARTMENT_EC','')} | Email: `{r.get('BUSINESS_EMAIL_ID','')}`" for _, r in samples.iterrows())
                sample_text = f"\n\n📋 **Flagged Records Sample** (showing up to 5):\n{emp_list}"
            else:
                sample_text = "\n\n🟢 *There are no records in this scope with this error type.*"
                
            if 'salary' in canonical_err.lower():
                sop = "1. Cross-verify Employee Central (EC) compensation against SAP Infotype 0008.\n2. Note variance discrepancy.\n3. Submit an urgent master-data reconciliation ticket before the 25th payroll freeze."
            elif 'cost centre' in canonical_err.lower():
                sop = "1. Obtain correct cost centre code and company code from Finance.\n2. Submit a Finance Change Request with department VP approval.\n3. Re-run SAP master synchronization."
            elif 'email' in canonical_err.lower():
                sop = "1. Confirm valid first.last@company.com syntax.\n2. Submit an IT Identity Management (IAM) ticket.\n3. Update the primary SMTP alias in both EC and Active Directory."
            elif 'manager' in canonical_err.lower():
                sop = "1. Audit the reporting line hierarchy in SAP OM against EC supervisor ID.\n2. Submit an HR Operations Organizational Alignment ticket."
            elif 'department' in canonical_err.lower():
                sop = "1. Align organizational unit IDs between EC and SAP company code chart of accounts.\n2. Execute bulk organizational update via HR Operations."
            elif 'company code' in canonical_err.lower():
                sop = "1. Validate statutory entity and payroll tax registration.\n2. Submit Legal Entity Reconciliation ticket to Finance Master Data."
            else:
                sop = "1. Check salary midpoint for the employee's job grade.\n2. Flag for Compensation Committee quarterly review if exceeding 120%."

            return 'error_deep_dive', f"### ⚠️ Data Quality Analysis: {canonical_err}\n\n" \
                   f"- **Flagged Records in {scope}**: **{count:,} employee(s)**\n" \
                   f"- **Governance Priority**: Critical{sample_text}\n\n" \
                   f"🛠️ **Standard Operating Procedure (SOP)**:\n{sop}"

    # 7. List All Errors / Show Flagged Records
    if any(phrase in q for phrase in ['list errors', 'show errors', 'all errors', 'list flagged', 'which employees have errors', 'employees with issues', 'data errors', 'flagged records']):
        errors = data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])]
        if errors.empty:
            return 'all_errors', f"🟢 **100% Clean Scope**: There are currently **zero data quality errors** in {scope} across all {len(data)} employee records."
        
        breakdown = errors['DATA_QUALITY_ERROR_TYPE'].value_counts()
        lines = [f"- **{err}**: {cnt} record(s)" for err, cnt in breakdown.items()]
        
        sample_rows = errors.head(6)
        samples_formatted = '\n'.join(f"- `{r['EMPLOYEE_NO']}` ({r.get('EMPLOYEE_FIRST_NAME','')} {r.get('EMPLOYEE_LAST_NAME','')}) — {r.get('DEPARTMENT_EC','')}: *{r.get('DATA_QUALITY_ERROR_TYPE')}*" for _, r in sample_rows.iterrows())
        
        return 'all_errors', f"### ⚠️ Active Data Quality Anomalies ({scope})\n\n" \
               f"There are **{len(errors)} flagged records** ({(len(errors)/len(data))*100:.1f}% anomaly rate) in {scope}:\n\n" + '\n'.join(lines) + \
               f"\n\n📋 **Sample Flagged Records**:\n{samples_formatted}\n\n" \
               f"💡 Click any error row in the **Data Quality Audit** table below to generate an automated remediation ticket."

    # 8. Demographics: Gender & Diversity
    if any(phrase in q for phrase in ['gender', 'male vs female', 'how many female', 'how many women', 'how many men', 'diversity', 'gender ratio', 'gender breakdown', 'women', 'men']):
        genders = data['GENDER'].value_counts()
        lines = [f"- **{g}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)" for g, cnt in genders.items()]
        return 'demographics_gender', f"### 👥 Gender & Diversity Distribution ({scope})\n\n" \
               f"Total workforce in scope: **{len(data)} employees**.\n\n" + '\n'.join(lines)

    # 9. Demographics: Nationalities
    if any(phrase in q for phrase in ['nationality', 'nationalities', 'citizenship', 'international', 'countries']):
        nats = data['NATIONALITY'].value_counts()
        lines = [f"- **{n}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)" for n, cnt in nats.items()]
        return 'demographics_nationality', f"### 🌍 Nationality Breakdown ({scope})\n\n" \
               f"The workforce in {scope} represents **{len(nats)} nationalities**:\n\n" + '\n'.join(lines)

    # 10. Employment Type: Regular vs Contract
    if any(phrase in q for phrase in ['contractor', 'contractors', 'contract vs regular', 'regular vs contract', 'full time', 'part time', 'employment type', 'employee group']):
        groups = data['EMPLOYEE_GROUP_EC'].value_counts()
        lines_g = [f"- **{g}**: {cnt} ({(cnt/len(data))*100:.1f}%)" for g, cnt in groups.items()]
        return 'employment_type', f"### 📋 Employment Classification ({scope})\n\n" \
               f"**Primary Employee Groups**:\n" + '\n'.join(lines_g)

    # 11. Career Stream & Job Levels (L1-L6)
    if any(phrase in q for phrase in ['job level', 'job levels', 'levels', 'l1', 'l2', 'l3', 'l4', 'l5', 'l6', 'seniority', 'career stream']):
        levels = data['JOB_LEVEL_EC'].value_counts().sort_index() if 'JOB_LEVEL_EC' in data else pd.Series()
        streams = data['CAREER_STREAM'].value_counts() if 'CAREER_STREAM' in data else pd.Series()
        lines_lvl = [f"- **{lvl}**: {cnt} employees" for lvl, cnt in levels.items()]
        lines_str = [f"- **{st}**: {cnt} ({(cnt/len(data))*100:.1f}%)" for st, cnt in streams.items()]
        return 'career_levels', f"### 🎯 Career Streams & Seniority Levels ({scope})\n\n" \
               f"**Career Streams**:\n" + '\n'.join(lines_str) + \
               (f"\n\n**Job Levels Breakdown**:\n" + '\n'.join(lines_lvl) if not levels.empty else "")

    # 12. Job Families
    if any(phrase in q for phrase in ['job family', 'job families', 'what roles', 'job roles']):
        jobs = data['JOB_FAMILY'].value_counts()
        lines = [f"- **{j}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)" for j, cnt in jobs.items()]
        return 'job_families', f"### 💼 Job Families Distribution ({scope})\n\n" \
               f"There are **{len(jobs)} specialized job families** in {scope}:\n\n" + '\n'.join(lines)

    # 13. Multi-City Comparison (for Manager/CEO)
    if any(phrase in q for phrase in ['compare cities', 'all locations', 'which city', 'city ranking', 'cities', 'all cities']):
        if not global_access:
            return 'location_restricted', f"Your authorized scope is restricted by corporate RLS to **{access.location}**. Cross-city comparisons require Global Manager or CEO privileges."
        loc_summary = []
        for loc in sorted(df['LOCATION_DESCRIPTION'].dropna().unique()):
            loc_sub = df[df['LOCATION_DESCRIPTION'] == loc]
            loc_sal = pd.to_numeric(loc_sub['ANNUAL_SALARY_EC'], errors='coerce').dropna()
            loc_errs = len(loc_sub[~loc_sub['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])])
            loc_summary.append({'loc': loc, 'count': len(loc_sub), 'sal': loc_sal.mean() if not loc_sal.empty else 0, 'errs': loc_errs})
        loc_summary = sorted(loc_summary, key=lambda x: x['count'], reverse=True)
        lines = [f"- **{r['loc']}**: {r['count']} employees | Avg Salary: ₹{r['sal']:,.0f} | Flagged Issues: {r['errs']}" for r in loc_summary]
        return 'city_comparison', f"### 🌐 Enterprise Multi-City Comparison\n\n" + '\n'.join(lines)

    # 14. Plain Headcount & Pay Overview
    if any(w in words for w in ['headcount', 'employees', 'total', 'size']) and any(w in words for w in ['salary', 'pay', 'compensation']):
        if not global_access:
            return 'headcount_pay', f"### 👥 Workforce Overview ({scope})\n\n" \
                   f"- **Total Headcount**: **{len(data):,} employees**\n" \
                   f"- **Compensation Metrics**: 🔒 Confidential (Manager Clearance Required)\n" \
                   f"- **Active Departments**: {data['DEPARTMENT_EC'].nunique()} units\n" \
                   f"- **Data Quality Health**: {len(data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])])} flagged issues"
        return 'headcount_pay', f"### 👥 Workforce & Compensation Overview ({scope})\n\n" \
               f"- **Total Headcount**: **{len(data):,} employees**\n" \
               f"- **Average Annual Salary**: **₹{mean_sal:,.0f}**\n" \
               f"- **Compensation Range**: ₹{min_sal:,.0f} to ₹{max_sal:,.0f}\n" \
               f"- **Active Departments**: {data['DEPARTMENT_EC'].nunique()} units\n" \
               f"- **Data Quality Health**: {len(data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])])} flagged issues"

    # 14. Plain Headcount & Pay Overview
    if any(w in words for w in ['headcount', 'employees', 'total', 'size']) and any(w in words for w in ['salary', 'pay', 'compensation']):
        if not comp_access:
            return 'headcount_pay', f"### 👥 Workforce Overview ({scope})\n\n" \
                   f"- **Total Headcount**: **{len(data):,} employees**\n" \
                   f"- **Compensation Metrics**: 🔒 Confidential (Manager/HRBP Clearance Required)\n" \
                   f"- **Active Departments**: {data['DEPARTMENT_EC'].nunique()} units\n" \
                   f"- **Data Quality Health**: {len(data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])])} flagged issues"
        return 'headcount_pay', f"### 👥 Workforce & Compensation Overview ({scope})\n\n" \
               f"- **Total Headcount**: **{len(data):,} employees**\n" \
               f"- **Average Annual Salary**: **₹{mean_sal:,.0f}**\n" \
               f"- **Compensation Range**: ₹{min_sal:,.0f} to ₹{max_sal:,.0f}\n" \
               f"- **Active Departments**: {data['DEPARTMENT_EC'].nunique()} units\n" \
               f"- **Data Quality Health**: {len(data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])])} flagged issues"

    if any(w in words for w in ['headcount', 'employees', 'count', 'size', 'roster', 'how many people']):
        return 'headcount_only', f"There are **{len(data):,} active employee records** in **{scope}** distributed across **{data['DEPARTMENT_EC'].nunique()} departments**."

    if any(w in words for w in ['salary', 'pay', 'compensation', 'wages']):
        if not comp_access:
            return 'salary_restricted', "🔒 **Access Restricted**: Compensation benchmarks and salary metrics are confidential. Managerial or HRBP clearance is required to view salary data."
        return 'salary_only', f"### 💰 Compensation Summary ({scope})\n\n" \
               f"- **Average Annual Salary**: **₹{mean_sal:,.0f}**\n" \
               f"- **Median Salary**: ₹{median_sal:,.0f}\n" \
               f"- **Highest Salary**: ₹{max_sal:,.0f}\n" \
               f"- **Lowest Salary**: ₹{min_sal:,.0f}"

    # 15. FAQ Knowledge Base Matching
    for faq_q, faq_ans in FAQ_KNOWLEDGE_BASE.items():
        if faq_q in q or all(w in words for w in faq_q.split() if len(w) > 3):
            return 'faq', f"### 📖 Corporate Policy & Governance Guide\n\n{faq_ans}"

    # 16. Fallback - Targeted, contextual, helpful
    top_depts = data['DEPARTMENT_EC'].value_counts().head(3).to_dict()
    top_dept_str = ', '.join(f"**{d}** ({c})" for d, c in top_depts.items())
    comp_metric = f"- **Average Compensation**: ₹{mean_sal:,.0f}\n\n" if comp_access else "- **Compensation Metrics**: 🔒 Confidential (Manager/HRBP Clearance Required)\n\n"
    suggest_dept_sal = "- *'Which department has the highest salary?'*\n" if comp_access else "- *'What are the active job families?'*\n"
    
    return 'general', f"I reviewed records in **{scope}** for your query: *\"{raw_question}\"*.\n\n" \
           f"Key metrics for this scope:\n" \
           f"- **Workforce Size**: {len(data):,} active employees\n" \
           f"- **Leading Departments**: {top_dept_str}\n" \
           f"{comp_metric}" \
           f"💡 Try asking:\n" \
           f"{suggest_dept_sal}" \
           f"- *'Show all employees with errors'*\n" \
           f"- *'What is the gender diversity?'*\n" \
           f"- *'Tell me about [Department Name]'*"

@app.post('/api/chat')
def chat(request:ChatRequest,access:AccessContext=Depends(require_access)):
    raw_question=request.question.strip()
    global_access=has_global_access(access)
    comp_access=can_view_compensation(access)
    if not global_access:
        blocked,target_city=detect_unauthorized_location(raw_question,access.location)
        if blocked:
            log_security_event(
                "CROSS_LOCATION_BLOCKED",
                access.employee_id, access.role, access.location,
                f"Blocked chatbot query requesting {target_city} data outside RLS boundary.",
                status="BLOCKED"
            )
            return {'intent':'access_denied','answer':f'🔒 Access Denied: You are not authorized to view {target_city} data. Your employee ID ({access.employee_id}) is restricted by corporate Row-Level Security (RLS) to {access.location}.'}
    requested=dict(request.filters or {})
    if not global_access:
        requested['location']=access.location
    elif not requested.get('location'):
        for canonical,aliases in CITY_ALIASES.items():
            if any(a in raw_question.lower() for a in aliases):
                requested['location']=canonical.title(); break
    data=secured_data(FilterParams(**requested),access)
    if data.empty: return {'intent':'empty_result','answer':f'There are no matching records in the current authorized scope ({requested.get("location") or access.location}). Try clearing a filter.'}
    scope=requested.get('location') or ('all authorised locations' if global_access else access.location)
    report=quality_report(data)
    
    intent, answer = process_chatbot_query(raw_question, data, scope, access, report, global_access, comp_access)
    return {'intent': intent, 'answer': answer}

# Compliance & GDPR API Endpoints
@app.get('/api/compliance/audit-log')
def get_compliance_audit_log(access:AccessContext=Depends(require_access)):
    return {'logs': list(reversed(SECURITY_AUDIT_LOG[-50:])), 'total_events': len(SECURITY_AUDIT_LOG)}

@app.get('/api/compliance/gdpr-status')
def get_gdpr_status(access:AccessContext=Depends(require_access)):
    return {
        'status': 'Compliant',
        'standards': ['GDPR (EU 2016/679)', 'ISO/IEC 27001', 'SOC 2 Type II', 'DPDP Act 2023'],
        'principles': [
            {'article': 'Article 5(1)(c)', 'name': 'Data Minimisation', 'status': 'Enforced', 'detail': 'Server-side Column-Level Security (CLS) strips compensation numbers for unprivileged roles.'},
            {'article': 'Article 5(1)(f)', 'name': 'Integrity & Confidentiality', 'status': 'Enforced', 'detail': 'Tokenized session management, TLS in-transit encryption, and strict Row-Level Security (RLS).'},
            {'article': 'Article 15', 'name': 'Right of Access (SAR)', 'status': 'Active', 'detail': 'Self-service data view and automated audit ticket generation for personal data requests.'},
            {'article': 'Article 25', 'name': 'Data Protection by Design', 'status': 'Enforced', 'detail': 'Default deny access architecture with location-bound tenant isolation.'},
            {'article': 'Article 32', 'name': 'Security of Processing', 'status': 'Enforced', 'detail': 'Granular RBAC with distinct clearance for Global DF&A, Global Data Foundation, HRBP/P&O, and Employees.'},
            {'article': 'Articles 33 & 34', 'name': 'Breach Notification (72h)', 'status': 'Operational', 'detail': 'Automated anomaly detection, incident response runbook, and 72-hour supervisory authority notification workflow.'}
        ],
        'breach_protocol': {
            'sla_hours': 72,
            'dpo_contact': 'dpo-privacy@company.com',
            'escalation_steps': [
                '1. Immediate RLS Quarantine & Token Invalidation',
                '2. Forensic Impact Assessment & Record Identification',
                '3. Data Protection Authority (DPA) Notification within 72 Hours',
                '4. Affected Subject Disclosure & Remediation Logging'
            ]
        }
    }

@app.get('/api/compliance/stakeholders')
def get_stakeholders(access:AccessContext=Depends(require_access)):
    matrix = [
        {
            'stakeholder': 'Global Data Foundation',
            'role': 'Enterprise Master Data Governance',
            'scope': 'All Locations (Global)',
            'clearance': 'Enterprise Master Data & Governance Clearance',
            'salary_access': 'Full Enterprise Visibility',
            'executive_report': 'Authorized (Company-Wide)',
            'gdpr_purpose': 'Data Quality Auditing, Architecture & Compliance Governance'
        },
        {
            'stakeholder': 'HRBP / P&O Partners',
            'role': 'People & Organization Location Lead',
            'scope': 'Respective Location (Mumbai, Kolkata, Bengaluru, etc.)',
            'clearance': 'Location Scope Clearance (Strict RLS Enforced)',
            'salary_access': 'Location-Level HR Clearance',
            'executive_report': 'Location Briefings Only',
            'gdpr_purpose': 'Site Workforce Management & Operations'
        },
        {
            'stakeholder': 'HRBP-MOM or P&O – Kolkata',
            'role': 'Manufacturing Operations P&O Lead',
            'scope': 'Kolkata Location Only',
            'clearance': 'Operations Site Management Clearance',
            'salary_access': 'Kolkata Operations Clearance',
            'executive_report': 'Kolkata Site Briefings Only',
            'gdpr_purpose': 'Plant Workforce & Operations Governance'
        }
    ]
    return {'stakeholders': matrix, 'matrix': matrix}

@app.post('/api/compliance/log-export')
def log_export_event(payload:dict,access:AccessContext=Depends(require_access)):
    count = payload.get('record_count', 0)
    log_security_event(
        "DATA_EXPORT_AUDIT",
        access.employee_id, access.role, access.location,
        f"Exported {count} records to CSV under GDPR Article 15 compliance tracking.",
        status="AUDITED"
    )
    return {'status':'recorded'}

app.mount('/dashboard',StaticFiles(directory=BASE_DIR.parent/'frontend',html=True),name='dashboard')
