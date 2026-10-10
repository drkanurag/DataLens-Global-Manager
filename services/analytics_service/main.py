"""DataLens Workforce Analytics & Executive Intelligence Microservice (Port 8002).

Handles workforce KPIs, geographic/department/job-family distributions,
monthly trajectories, employee explorer records, and executive summaries.
"""
from pathlib import Path
import sys
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.shared.data_store import (
    can_view_compensation,
    df,
    has_global_access,
    numeric_series,
    secured_data,
    top_values,
)
from services.shared.models import AccessContext, FILTER_COLUMNS, FilterParams
from services.shared.security import log_security_event, require_access

router = APIRouter(tags=["Workforce Analytics Microservice"])


@router.get("/api/filters")
def get_filters(access: AccessContext = Depends(require_access)):
    data = secured_data(FilterParams(), access, log_security_event)
    options = {
        k: sorted(data[c].dropna().astype(str).unique().tolist())
        for k, c in FILTER_COLUMNS.items()
    }
    options["location"] = (
        sorted(df["LOCATION_DESCRIPTION"].dropna().astype(str).unique().tolist())
        if has_global_access(access)
        else [access.location]
    )
    return options


@router.get("/api/analytics/summary")
def summary(
    filters: FilterParams = Depends(),
    access: AccessContext = Depends(require_access),
):
    data = secured_data(filters, access, log_security_event)
    salary = numeric_series(data, "ANNUAL_SALARY_EC")
    avg_salary = (
        float(salary.mean())
        if (can_view_compensation(access) and not salary.empty)
        else None
    )
    return {
        "total_employees": len(data),
        "locations": int(data["LOCATION_DESCRIPTION"].nunique()),
        "departments": int(data["DEPARTMENT_EC"].nunique()),
        "job_families": int(data["JOB_FAMILY"].nunique()),
        "employee_groups": int(data["EMPLOYEE_GROUP_EC"].nunique()),
        "months": int(data["Month Name"].nunique()),
        "average_salary": avg_salary,
    }


@router.get("/api/analytics/by-location")
def by_location(
    filters: FilterParams = Depends(),
    access: AccessContext = Depends(require_access),
):
    return top_values(
        secured_data(filters, access, log_security_event),
        "LOCATION_DESCRIPTION",
        "location",
    )


@router.get("/api/analytics/by-department")
def by_department(
    filters: FilterParams = Depends(),
    access: AccessContext = Depends(require_access),
):
    return top_values(
        secured_data(filters, access, log_security_event),
        "DEPARTMENT_EC",
        "department",
    )


@router.get("/api/analytics/by-job-family")
def by_job_family(
    filters: FilterParams = Depends(),
    access: AccessContext = Depends(require_access),
):
    return top_values(
        secured_data(filters, access, log_security_event),
        "JOB_FAMILY",
        "job_family",
    )


@router.get("/api/analytics/monthly")
def monthly(
    filters: FilterParams = Depends(),
    access: AccessContext = Depends(require_access),
):
    filters.month = None
    data = secured_data(filters, access, log_security_event)
    order = {
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8,
        "September": 9,
        "October": 10,
        "November": 11,
        "December": 12,
    }
    counts = (
        data["Month Name"]
        .fillna("Not specified")
        .astype(str)
        .value_counts()
        .reset_index()
    )
    counts.columns = ["month", "employees"]
    counts["_order"] = counts.month.map(order).fillna(99)
    return (
        counts.sort_values(["_order", "month"])
        .drop(columns=["_order"])
        .to_dict(orient="records")
    )


@router.get("/api/analytics/employees")
def employees(
    filters: FilterParams = Depends(),
    access: AccessContext = Depends(require_access),
):
    data = secured_data(filters, access, log_security_event).copy()
    wanted = [
        "EMPLOYEE_NO",
        "LOCATION_DESCRIPTION",
        "DEPARTMENT_EC",
        "JOB_FAMILY",
        "EMPLOYEE_GROUP_EC",
        "EVP",
        "ANNUAL_SALARY_EC",
        "DATA_QUALITY_ERROR_TYPE",
        "Month Name",
    ]
    data = data[[c for c in wanted if c in data]].rename(
        columns={
            "EMPLOYEE_NO": "employee_no",
            "LOCATION_DESCRIPTION": "location",
            "DEPARTMENT_EC": "department",
            "JOB_FAMILY": "job_family",
            "EMPLOYEE_GROUP_EC": "employee_group",
            "EVP": "evp",
            "ANNUAL_SALARY_EC": "annual_salary",
            "DATA_QUALITY_ERROR_TYPE": "error_type",
            "Month Name": "month",
        }
    )
    data["annual_salary"] = (
        pd.to_numeric(data.get("annual_salary"), errors="coerce")
        if "annual_salary" in data
        else None
    )
    if not can_view_compensation(access):
        own_id = str(access.employee_id).strip().upper()
        data["annual_salary"] = data.apply(
            lambda r: r["annual_salary"]
            if str(r.get("employee_no", "")).strip().upper() == own_id
            else None,
            axis=1,
        )
    data["error_type"] = (
        data.get("error_type", pd.Series(index=data.index, dtype=str))
        .fillna("No Error")
        .astype(str)
    )
    return {"records": data.fillna("").to_dict(orient="records"), "total": int(len(data))}


@router.get("/api/analytics/executive-summary")
def executive_summary(access: AccessContext = Depends(require_access)):
    if not has_global_access(access):
        raise HTTPException(
            status_code=403,
            detail="Executive Summary is strictly restricted to Global Data Foundation clearance.",
        )

    total_headcount = len(df)
    order = {
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8,
        "September": 9,
        "October": 10,
        "November": 11,
        "December": 12,
    }
    monthly_counts = df["Month Name"].value_counts().reset_index()
    monthly_counts.columns = ["month", "headcount"]
    monthly_counts["_order"] = monthly_counts["month"].map(order).fillna(99)
    monthly_trajectory = (
        monthly_counts.sort_values("_order")
        .drop(columns=["_order"])
        .to_dict(orient="records")
    )

    loc_counts = df["LOCATION_DESCRIPTION"].value_counts().reset_index()
    loc_counts.columns = ["location", "headcount"]
    loc_counts["percentage"] = (loc_counts["headcount"] / total_headcount * 100).round(1)

    dept_counts = df["DEPARTMENT_EC"].value_counts().reset_index()
    dept_counts.columns = ["department", "headcount"]
    dept_counts["percentage"] = (
        dept_counts["headcount"] / total_headcount * 100
    ).round(1)

    emp_type = df["EMPLOYEE_GROUP_EC"].value_counts().reset_index()
    emp_type.columns = ["group", "headcount"]
    emp_type["percentage"] = (emp_type["headcount"] / total_headcount * 100).round(1)

    sup_counts = df["SUPERVISOR_EC"].dropna().value_counts()
    unique_supervisors = int(df["SUPERVISOR_EC"].nunique())
    avg_span = float(sup_counts.mean()) if not sup_counts.empty else 0.0
    span_tiers = [
        {
            "tier": "1 Direct Report",
            "count": int((sup_counts == 1).sum()),
            "percentage": round(
                int((sup_counts == 1).sum()) / max(unique_supervisors, 1) * 100, 1
            ),
        },
        {
            "tier": "2-3 Direct Reports",
            "count": int(((sup_counts >= 2) & (sup_counts <= 3)).sum()),
            "percentage": round(
                int(((sup_counts >= 2) & (sup_counts <= 3)).sum())
                / max(unique_supervisors, 1)
                * 100,
                1,
            ),
        },
        {
            "tier": "4+ Direct Reports",
            "count": int((sup_counts >= 4).sum()),
            "percentage": round(
                int((sup_counts >= 4).sum()) / max(unique_supervisors, 1) * 100, 1
            ),
        },
    ]

    has_error = (
        ~df["DATA_QUALITY_ERROR_TYPE"]
        .fillna("No Error")
        .astype(str)
        .str.lower()
        .isin(["", "no error", "nan", "none"])
    )
    df_err = df.copy()
    df_err["has_error"] = has_error

    loc_group = df_err.groupby("LOCATION_DESCRIPTION").agg(
        total=("EMPLOYEE_NO", "count"), errors=("has_error", "sum")
    )
    loc_group["quality_score"] = (
        (loc_group["total"] - loc_group["errors"]) / loc_group["total"] * 100
    ).round(1)
    loc_group["error_rate"] = (loc_group["errors"] / loc_group["total"] * 100).round(1)
    loc_alerts = (
        loc_group[loc_group["quality_score"] < 50.0]
        .reset_index()
        .to_dict(orient="records")
    )

    dept_group = df_err.groupby("DEPARTMENT_EC").agg(
        total=("EMPLOYEE_NO", "count"), errors=("has_error", "sum")
    )
    dept_group["quality_score"] = (
        (dept_group["total"] - dept_group["errors"]) / dept_group["total"] * 100
    ).round(1)
    dept_group["error_rate"] = (
        dept_group["errors"] / dept_group["total"] * 100
    ).round(1)
    dept_alerts = (
        dept_group[dept_group["quality_score"] < 50.0]
        .reset_index()
        .to_dict(orient="records")
    )

    compliance_risks = [
        {
            "flag": "Salary Mismatch vs SAP Payroll",
            "severity": "Critical",
            "count": int(
                (df["DATA_QUALITY_ERROR_TYPE"] == "Salary not matching with SAP").sum()
            ),
            "description": "Discrepancy between Employee Central compensation and SAP Payroll system records.",
        },
        {
            "flag": "Cost Centre Misalignment",
            "severity": "High",
            "count": int(
                (
                    df["DATA_QUALITY_ERROR_TYPE"]
                    == "Cost centre mismatch with company code"
                ).sum()
            ),
            "description": "Allocated cost center does not correspond to legal company entity structure.",
        },
        {
            "flag": "Compa-Ratio Ceiling Exceeded",
            "severity": "High",
            "count": int(
                (
                    df["DATA_QUALITY_ERROR_TYPE"]
                    == "High range penetration percentage"
                ).sum()
            ),
            "description": "Compensation range penetration exceeds 120% pay grade band ceiling.",
        },
        {
            "flag": "Department Code Mismatch",
            "severity": "Medium",
            "count": int(
                (
                    df["DATA_QUALITY_ERROR_TYPE"]
                    == "Department Code is not matching EC vs SAP"
                ).sum()
            ),
            "description": "Department code discrepancy between EC master record and SAP organizational structure.",
        },
        {
            "flag": "Missing or Invalid Corporate Email",
            "severity": "High",
            "count": int(
                (df["DATA_QUALITY_ERROR_TYPE"] == "Incorrect Business Email").sum()
            ),
            "description": "Missing corporate email address or invalid domain syntax inhibiting IAM governance.",
        },
        {
            "flag": "Supervisor Hierarchy Mismatch",
            "severity": "Medium",
            "count": int(
                (
                    df["DATA_QUALITY_ERROR_TYPE"]
                    == "Manager is not matching EC vs SAP"
                ).sum()
            ),
            "description": "Reporting line hierarchy does not match SAP supervisor structures.",
        },
        {
            "flag": "Company Code Discrepancy",
            "severity": "Medium",
            "count": int(
                (
                    df["DATA_QUALITY_ERROR_TYPE"]
                    == "Company Code is not matching EC vs SAP"
                ).sum()
            ),
            "description": "Legal entity company code mismatch between EC and SAP.",
        },
    ]

    return {
        "total_headcount": total_headcount,
        "monthly_trajectory": monthly_trajectory,
        "location_distribution": loc_counts.sort_values(
            "headcount", ascending=False
        ).to_dict(orient="records"),
        "department_distribution": dept_counts.sort_values(
            "headcount", ascending=False
        ).to_dict(orient="records"),
        "employment_type_distribution": emp_type.to_dict(orient="records"),
        "span_of_control": {
            "unique_supervisors": unique_supervisors,
            "total_workforce": total_headcount,
            "average_span": round(avg_span, 2),
            "ratio": f"1 : {avg_span:.1f}",
            "distribution": span_tiers,
        },
        "alerts_exceptions": {
            "location_alerts": loc_alerts,
            "department_alerts": dept_alerts,
            "compliance_risks": compliance_risks,
            "total_compliance_issues": sum(r["count"] for r in compliance_risks),
            "overall_quality_score": round(
                ((total_headcount - has_error.sum()) / total_headcount) * 100, 1
            ),
        },
    }


app = FastAPI(
    title="DataLens Workforce Analytics Microservice",
    version="4.0.0",
    description="Row-Level Secured Workforce KPIs, Trends, Distributions & Executive Briefings",
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
@app.get("/api/analytics/health")
def health():
    return {
        "service": "analytics-service",
        "name": "Workforce Analytics Microservice",
        "port": 8002,
        "status": "healthy",
        "records_loaded": len(df),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
