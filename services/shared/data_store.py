"""Shared data loader, Row-Level Security (RLS), and Column-Level Security (CLS) engine."""
from pathlib import Path
import shutil
import pandas as pd
from fastapi import HTTPException

from .models import (
    AccessContext,
    CORE_COLUMNS,
    ERROR_TYPE_NAMES,
    FILTER_COLUMNS,
    FilterParams,
    GLOBAL_ROLES,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"


def load_employee_data() -> pd.DataFrame:
    excel_path = DATA_DIR / "employee_data.xlsx"
    try:
        return pd.read_excel(excel_path, sheet_name="Source data")
    except PermissionError:
        temp_path = DATA_DIR / "_cached_employee_data.xlsx"
        shutil.copy2(excel_path, temp_path)
        return pd.read_excel(temp_path, sheet_name="Source data")


def load_access_directory() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "access_directory.csv", dtype=str).fillna("")


df = load_employee_data()
directory_df = load_access_directory()


def has_global_access(access: AccessContext) -> bool:
    r = access.role.lower().strip()
    eid = getattr(access, "employee_id", "").lower().strip()
    return (
        r in GLOBAL_ROLES
        or eid in GLOBAL_ROLES
        or access.location.lower().strip() == "all locations"
    )


def has_hrbp_access(access: AccessContext) -> bool:
    r = access.role.lower().strip()
    return any(k in r for k in ["hrbp", "p&o"])


def can_view_compensation(access: AccessContext) -> bool:
    return has_global_access(access) or has_hrbp_access(access)


def is_manager(access: AccessContext) -> bool:
    return has_global_access(access)


def secured_data(
    filters: FilterParams,
    access: AccessContext,
    audit_logger=None,
) -> pd.DataFrame:
    global_access = has_global_access(access)
    if (
        not global_access
        and filters.location
        and filters.location.lower() != access.location.lower()
    ):
        if audit_logger:
            audit_logger(
                "CROSS_LOCATION_BLOCKED",
                access.employee_id,
                access.role,
                access.location,
                f"Blocked unauthorized attempt to query {filters.location}. Scope locked to {access.location}.",
                status="BLOCKED",
            )
        raise HTTPException(
            status_code=403,
            detail=f"You are not authorized to view {filters.location}. Your access is limited by RLS to {access.location}.",
        )
    data = (
        df.copy()
        if global_access
        else df[
            df["LOCATION_DESCRIPTION"].astype(str).str.lower()
            == access.location.lower()
        ].copy()
    )
    if global_access and filters.location and filters.location.lower() != "all":
        data = data[
            data["LOCATION_DESCRIPTION"].astype(str).str.lower()
            == filters.location.lower()
        ]
    for key, value in filters.model_dump().items():
        if not value or key == "location" or value.lower() == "all":
            continue
        data = data[
            data[FILTER_COLUMNS[key]].astype(str).str.lower() == value.lower()
        ]
    return data


def top_values(data: pd.DataFrame, column: str, label: str) -> list[dict]:
    result = (
        data[column]
        .fillna("Not specified")
        .astype(str)
        .value_counts()
        .reset_index()
    )
    result.columns = [label, "employees"]
    return result.to_dict(orient="records")


def numeric_series(data: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(data[column], errors="coerce").dropna()


def compute_quality_report(data: pd.DataFrame) -> dict:
    missing_by_column = {
        c: int(data[c].isna().sum()) for c in CORE_COLUMNS if c in data
    }
    missing_required = (
        int(data[CORE_COLUMNS].isna().any(axis=1).sum())
        if not data.empty
        else 0
    )
    duplicate_rows = int(data.duplicated().sum())
    errors = (
        data["DATA_QUALITY_ERROR_TYPE"]
        .fillna("No Error")
        .astype(str)
        .str.strip()
    )
    source_errors = data[~errors.str.lower().isin(["", "no error", "none", "nan"])]
    observed = source_errors["DATA_QUALITY_ERROR_TYPE"].value_counts().to_dict()
    error_type_counts = [
        {"error_type": name, "count": int(observed.get(name, 0))}
        for name in ERROR_TYPE_NAMES
    ]
    for name, count in observed.items():
        if str(name) not in ERROR_TYPE_NAMES:
            error_type_counts.append({"error_type": str(name), "count": int(count)})
    issues = [
        {
            "type": "Source data quality error",
            "asset": "Source data",
            "description": str(name),
            "records": int(count),
        }
        for name, count in observed.items()
    ]
    if missing_required:
        issues.append(
            {
                "type": "Missing required fields",
                "asset": "Source data",
                "description": "One or more core workforce fields are blank",
                "records": missing_required,
            }
        )
    if duplicate_rows:
        issues.append(
            {
                "type": "Duplicate rows",
                "asset": "Source data",
                "description": "Exact duplicate records detected",
                "records": duplicate_rows,
            }
        )
    total = len(source_errors) + missing_required + duplicate_rows
    return {
        "status": "Passed" if total == 0 else "Attention needed",
        "records_checked": int(len(data)),
        "columns_checked": int(data.shape[1]),
        "source_errors": int(len(source_errors)),
        "missing_required": missing_required,
        "duplicate_rows": duplicate_rows,
        "total_issues": int(total),
        "missing_by_column": missing_by_column,
        "issues": issues,
        "error_type_counts": error_type_counts,
    }

