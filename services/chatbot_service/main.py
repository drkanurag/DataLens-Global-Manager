"""DataLens Scoped AI Conversational Assistant Microservice (Port 8004).

Handles natural language workforce queries, RLS cross-location query blocking,
CLS compensation confidentiality, employee profile lookups, and SOP remediation guidance.
"""
from pathlib import Path
import re
import sys
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.shared.data_store import (
    can_view_compensation,
    compute_quality_report,
    df,
    has_global_access,
    secured_data,
)
from services.shared.models import (
    AccessContext,
    CITY_ALIASES,
    ChatRequest,
    FAQ_KNOWLEDGE_BASE,
    FilterParams,
)
from services.shared.security import log_security_event, require_access

router = APIRouter(tags=["Scoped AI Chatbot Microservice"])


def detect_unauthorized_location(
    question: str, user_location: str
) -> tuple[bool, str | None]:
    q = " " + question.lower().replace("?", " ") + " "
    user_loc = user_location.strip().lower()
    generic = [
        "other city",
        "another city",
        "other cities",
        "all locations",
        "all cities",
        "nationwide",
        "across all locations",
        "company-wide",
        "entire company",
        "across the company",
    ]
    if any(g in q for g in generic):
        return True, "other corporate locations"
    for canonical, aliases in CITY_ALIASES.items():
        if canonical == user_loc:
            continue
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", q):
                return True, canonical.title()
    return False, None


def process_chatbot_query(
    raw_question: str,
    data: pd.DataFrame,
    scope: str,
    access: AccessContext,
    report: dict,
    global_access: bool,
    comp_access: bool = False,
) -> tuple[str, str]:
    q = (
        " "
        + raw_question.lower()
        .replace("?", " ")
        .replace(",", " ")
        .replace(".", " ")
        + " "
    )
    words = set(re.findall(r"\b[a-z0-9_\-]+\b", q))

    salary_col = pd.to_numeric(data["ANNUAL_SALARY_EC"], errors="coerce").dropna()
    mean_sal = salary_col.mean() if not salary_col.empty else 0
    min_sal = salary_col.min() if not salary_col.empty else 0
    max_sal = salary_col.max() if not salary_col.empty else 0
    median_sal = salary_col.median() if not salary_col.empty else 0

    # 1. Greetings & Meta
    if any(
        w in words
        for w in [
            "hello",
            "hi",
            "hey",
            "greetings",
            "morning",
            "afternoon",
            "evening",
        ]
    ):
        if comp_access:
            suggestions = "- *'Which department has the highest salary?'*\n- *'Show me employees with salary mismatches'*\n- *'What is the gender ratio?'*\n- *'Tell me about the Finance department'*\n- *'Who is the highest paid employee?'*"
        else:
            suggestions = "- *'How many employees are in Engineering?'*\n- *'Show me employees with data quality issues'*\n- *'What is the gender ratio?'*\n- *'Tell me about the Finance department'*\n- *'What are the job levels in our location?'*"
        return (
            "greeting",
            f"Hello {access.employee_name}! I am your **DataLens Assistant**.\n\nI can answer questions across your authorized workforce in **{scope}**.\n\nTry asking:\n{suggestions}",
        )

    if any(
        phrase in q
        for phrase in [
            "who are you",
            "what can you do",
            "what are you",
            "help me",
            "capabilities",
            "what do you do",
        ]
    ):
        comp_bullet = (
            "- 📊 **Compensation**: Averages, medians, highest/lowest salaries, and departmental salary comparisons\n"
            if comp_access
            else "- 📊 **Compensation**: 🔒 Confidential (Restricted to Manager/HRBP clearance)\n"
        )
        return (
            "help",
            f"I am **DataLens Assistant**, your corporate workforce intelligence and master-data governance assistant.\n\nIn **{scope}**, I can assist with:\n{comp_bullet}- 🏢 **Departments & Roles**: Headcounts, job families, and career levels (L1–L6)\n- 👥 **Demographics**: Gender diversity, contract vs regular splits, and nationalities\n- ⚠️ **Data Governance**: Identifying flagged records, salary mismatches, email errors, and SOP remediation steps\n- 🛡️ **Compliance & GDPR**: Data minimization, breach protocol, and stakeholder privileges\n- 🔍 **Employee Lookups**: Details on specific employee IDs (e.g. *'Who is E100005?'*)",
        )

    if any(
        phrase in q
        for phrase in [
            "who is the ceo",
            "ceo name",
            "chief executive",
            "who is ceo",
            "ceo",
        ]
    ):
        return (
            "ceo",
            "The Chief Executive Officer is **Dexter Morgan** (Employee ID: `CEO`). The CEO holds enterprise-wide governance clearance across all corporate locations.",
        )

    # Compliance & GDPR Queries
    if any(
        phrase in q
        for phrase in [
            "gdpr",
            "data breach",
            "breach",
            "compliance",
            "article 5",
            "article 15",
            "article 32",
            "article 33",
            "privacy policy",
            "incident response",
        ]
    ):
        return "compliance_info", (
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
    if any(
        phrase in q
        for phrase in [
            "stakeholders",
            "stakeholder access",
            "who has access",
            "access management",
            "df&a",
            "data foundation",
            "hrbp kolkata",
            "p&o",
        ]
    ):
        return "stakeholder_info", (
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
    emp_match = re.search(r"\b(e\d{5,7}|emp\d{3,5})\b", q)
    if emp_match:
        target_id = emp_match.group(1).upper()
        match_row = data[data["EMPLOYEE_NO"].astype(str).str.upper() == target_id]
        if not match_row.empty:
            r = match_row.iloc[0]
            name = (
                f"{r.get('EMPLOYEE_FIRST_NAME', '')} {r.get('EMPLOYEE_LAST_NAME', '')}".strip()
                or "Employee"
            )
            dept = r.get("DEPARTMENT_EC", "Not specified")
            job = r.get("JOB_FAMILY", "Not specified")
            level = r.get("JOB_LEVEL_EC", "N/A")
            loc = r.get("LOCATION_DESCRIPTION", "Not specified")
            sal = float(r.get("ANNUAL_SALARY_EC", 0) or 0)
            err = r.get("DATA_QUALITY_ERROR_TYPE", "No Error")
            email = r.get("BUSINESS_EMAIL_ID", "N/A")
            sup = r.get("SUPERVISOR_EC", "N/A")
            group = r.get("EMPLOYEE_GROUP_EC", "Regular")
            err_badge = (
                f"🔴 **Flagged Anomaly**: `{err}`"
                if str(err).lower() not in ["", "no error", "nan", "none"]
                else "🟢 **Clean (No Anomaly)**"
            )

            can_see_sal = comp_access or (
                target_id == str(access.employee_id).strip().upper()
            )
            sal_str = (
                f"₹{sal:,.0f}"
                if can_see_sal
                else "🔒 Confidential (Manager/HRBP Clearance Required)"
            )

            return (
                "employee_profile",
                f"### 👤 Employee Profile: {name} (`{target_id}`)\n\n"
                f"- **Location**: {loc}\n"
                f"- **Department**: {dept}\n"
                f"- **Job Role**: {job} (Level: {level}, {group})\n"
                f"- **Annual Compensation**: {sal_str}\n"
                f"- **Corporate Email**: `{email}`\n"
                f"- **Reporting Manager**: `{sup}`\n"
                f"- **Data Governance Status**: {err_badge}",
            )
        else:
            return (
                "employee_not_found",
                f"Employee ID `{target_id}` was not found within your authorized scope (**{scope}**). Either the employee belongs to another location or the ID does not exist.",
            )

    # 3. Department Queries (Specific department mentioned)
    all_depts = sorted(data["DEPARTMENT_EC"].dropna().astype(str).unique().tolist())
    dept_found = next(
        (d for d in all_depts if re.search(rf"\b{re.escape(d.lower())}\b", q)),
        None,
    )

    if dept_found:
        dept_data = data[
            data["DEPARTMENT_EC"].astype(str).str.lower() == dept_found.lower()
        ]
        dept_sal = pd.to_numeric(
            dept_data["ANNUAL_SALARY_EC"], errors="coerce"
        ).dropna()
        dept_errs = dept_data[
            ~dept_data["DATA_QUALITY_ERROR_TYPE"]
            .fillna("No Error")
            .astype(str)
            .str.lower()
            .isin(["", "no error", "nan", "none"])
        ]

        if any(
            w in words
            for w in ["salary", "pay", "compensation", "earn", "wage", "salaries"]
        ):
            if not comp_access:
                return (
                    "salary_restricted",
                    f"🔒 **Access Restricted**: Departmental compensation metrics and salary benchmarks for **{dept_found}** are confidential. Managerial or HRBP clearance is required to view compensation details.",
                )
            return (
                "dept_salary",
                f"### 💰 Compensation in {dept_found} ({scope})\n\n"
                f"- **Headcount**: {len(dept_data)} employees\n"
                f"- **Average Salary**: ₹{dept_sal.mean():,.0f}\n"
                f"- **Salary Range**: ₹{dept_sal.min():,.0f} to ₹{dept_sal.max():,.0f}\n"
                f"- **Median Salary**: ₹{dept_sal.median():,.0f}\n\n"
                f"The {dept_found} department represents {(len(dept_data)/max(len(data),1))*100:.1f}% of total workforce in {scope}.",
            )

        if any(
            w in words
            for w in [
                "error",
                "errors",
                "issue",
                "issues",
                "quality",
                "mismatch",
                "anomalies",
            ]
        ):
            if dept_errs.empty:
                return (
                    "dept_quality",
                    f"### 🟢 Data Quality for {dept_found} ({scope})\n\nGreat news: **100% of records** in the {dept_found} department ({len(dept_data)} employees) are completely clean with zero data quality errors.",
                )
            else:
                err_counts = dept_errs["DATA_QUALITY_ERROR_TYPE"].value_counts()
                breakdown = "\n".join(
                    f"- **{err}**: {cnt} record(s)"
                    for err, cnt in err_counts.items()
                )
                return (
                    "dept_quality",
                    f"### ⚠️ Data Quality Anomalies in {dept_found} ({scope})\n\n"
                    f"There are **{len(dept_errs)} flagged record(s)** out of {len(dept_data)} total employees:\n\n{breakdown}\n\n"
                    f"🔍 **Remediation**: Check the Secured Data Explorer below to audit the specific employee rows.",
                )

        top_jobs = dept_data["JOB_FAMILY"].value_counts().head(3).to_dict()
        jobs_str = (
            ", ".join(f"{j} ({c})" for j, c in top_jobs.items()) or "General"
        )
        comp_display = (
            f"₹{dept_sal.mean():,.0f}"
            if comp_access
            else "🔒 Confidential (Manager/HRBP Only)"
        )
        suggest_comp = (
            f"Ask *'What is the salary in {dept_found}?'* or "
            if comp_access
            else "Ask "
        )
        return (
            "dept_overview",
            f"### 🏢 Department Overview: {dept_found} ({scope})\n\n"
            f"- **Active Headcount**: {len(dept_data)} employees ({(len(dept_data)/max(len(data),1))*100:.1f}% of {scope})\n"
            f"- **Average Compensation**: {comp_display}\n"
            f"- **Primary Job Roles**: {jobs_str}\n"
            f"- **Data Quality Health**: {'🟢 100% Clean' if dept_errs.empty else f'⚠️ {len(dept_errs)} anomaly record(s) flagged'}\n\n"
            f"{suggest_comp}*'Are there errors in {dept_found}?'* for deeper details.",
        )

    # 4. Department Comparison / Rankings
    if any(
        phrase in q
        for phrase in [
            "highest salary",
            "highest paid department",
            "top paid department",
            "best paid department",
            "compare department salaries",
            "salary by department",
            "salaries by department",
        ]
    ) and ("department" in q or "dept" in q):
        if not comp_access:
            return (
                "salary_restricted",
                "🔒 **Access Restricted**: Departmental salary rankings and compensation comparisons are confidential. Managerial or HRBP clearance is required to view compensation details.",
            )
        dept_summary = []
        for d in all_depts:
            sub = data[data["DEPARTMENT_EC"] == d]
            sub_sal = pd.to_numeric(
                sub["ANNUAL_SALARY_EC"], errors="coerce"
            ).dropna()
            if not sub_sal.empty:
                dept_summary.append(
                    {"dept": d, "mean": sub_sal.mean(), "count": len(sub)}
                )
        dept_summary = sorted(dept_summary, key=lambda x: x["mean"], reverse=True)
        lines = [
            f"{i+1}. **{r['dept']}**: ₹{r['mean']:,.0f} (across {r['count']} employees)"
            for i, r in enumerate(dept_summary)
        ]
        top = dept_summary[0]
        return (
            "dept_salary_ranking",
            f"### 🏆 Department Salary Rankings ({scope})\n\n"
            f"The highest paid department is **{top['dept']}** with an average salary of **₹{top['mean']:,.0f}**.\n\n"
            + "\n".join(lines),
        )

    if any(
        phrase in q
        for phrase in [
            "largest department",
            "biggest department",
            "department breakdown",
            "compare departments",
            "list departments",
            "all departments",
            "what departments",
        ]
    ):
        dept_counts = data["DEPARTMENT_EC"].value_counts()
        lines = [
            f"- **{d}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)"
            for d, cnt in dept_counts.items()
        ]
        top_d = dept_counts.index[0]
        return (
            "dept_breakdown",
            f"### 🏢 Department Workforce Breakdown ({scope})\n\n"
            f"There are **{len(dept_counts)} departments** in {scope}. The largest department is **{top_d}** with **{dept_counts.iloc[0]} employees**.\n\n"
            + "\n".join(lines),
        )

    if any(
        phrase in q
        for phrase in [
            "most errors",
            "most issues",
            "errors by department",
            "department error ranking",
        ]
    ):
        errors = data[
            ~data["DATA_QUALITY_ERROR_TYPE"]
            .fillna("No Error")
            .astype(str)
            .str.lower()
            .isin(["", "no error", "nan", "none"])
        ]
        if errors.empty:
            return (
                "dept_errors",
                f"🟢 **Zero Errors**: All departments in {scope} currently have 100% clean records with zero data quality errors.",
            )
        err_by_dept = errors["DEPARTMENT_EC"].value_counts()
        lines = [
            f"- **{d}**: {cnt} flagged record(s)"
            for d, cnt in err_by_dept.items()
        ]
        return (
            "dept_errors",
            f"### ⚠️ Data Quality Anomalies by Department ({scope})\n\n"
            f"A total of **{len(errors)} records** are flagged with data quality issues across departments:\n\n"
            + "\n".join(lines)
            + f"\n\n🔍 **Top Priority**: Focus remediation on **{err_by_dept.index[0]}** which has the highest concentration ({err_by_dept.iloc[0]} issues).",
        )

    # 5. Salary Extremes & Distribution
    if any(
        phrase in q
        for phrase in [
            "highest salary",
            "highest paid",
            "who earns the most",
            "maximum salary",
            "top earner",
            "max salary",
            "highest compensation",
        ]
    ):
        if not comp_access:
            return (
                "salary_restricted",
                "🔒 **Access Restricted**: Individual compensation records, maximum salary rankings, and highest earner details are confidential. Managerial or HRBP clearance is required.",
            )
        top_idx = salary_col.idxmax()
        top_row = data.loc[top_idx]
        name = (
            f"{top_row.get('EMPLOYEE_FIRST_NAME', '')} {top_row.get('EMPLOYEE_LAST_NAME', '')}".strip()
            or f"Employee {top_row.get('EMPLOYEE_NO')}"
        )
        dept = top_row.get("DEPARTMENT_EC", "N/A")
        role = top_row.get("JOB_FAMILY", "N/A")
        level = top_row.get("JOB_LEVEL_EC", "N/A")
        return (
            "highest_salary",
            f"### 💎 Highest Paid Record ({scope})\n\n"
            f"- **Maximum Salary**: **₹{max_sal:,.0f}**\n"
            f"- **Employee**: {name} (`{top_row.get('EMPLOYEE_NO')}`)\n"
            f"- **Department**: {dept}\n"
            f"- **Role**: {role} (Level: {level})\n\n"
            f"For comparison, the average salary in {scope} is ₹{mean_sal:,.0f}.",
        )

    if any(
        phrase in q
        for phrase in [
            "lowest salary",
            "minimum salary",
            "lowest paid",
            "min salary",
            "lowest compensation",
        ]
    ):
        if not comp_access:
            return (
                "salary_restricted",
                "🔒 **Access Restricted**: Individual compensation records, minimum salary data, and compensation ranges are confidential. Managerial or HRBP clearance is required.",
            )
        min_idx = salary_col.idxmin()
        min_row = data.loc[min_idx]
        name = (
            f"{min_row.get('EMPLOYEE_FIRST_NAME', '')} {min_row.get('EMPLOYEE_LAST_NAME', '')}".strip()
            or f"Employee {min_row.get('EMPLOYEE_NO')}"
        )
        return (
            "lowest_salary",
            f"### 📉 Minimum Salary Record ({scope})\n\n"
            f"- **Minimum Salary**: **₹{min_sal:,.0f}**\n"
            f"- **Employee**: {name} (`{min_row.get('EMPLOYEE_NO')}`)\n"
            f"- **Department**: {min_row.get('DEPARTMENT_EC', 'N/A')}\n"
            f"- **Role**: {min_row.get('JOB_FAMILY', 'N/A')}\n\n"
            f"The overall compensation span across {scope} is ₹{min_sal:,.0f} to ₹{max_sal:,.0f}.",
        )

    if any(
        phrase in q
        for phrase in ["median salary", "median pay", "median compensation"]
    ):
        if not comp_access:
            return (
                "salary_restricted",
                "🔒 **Access Restricted**: Median compensation benchmarks are confidential. Managerial or HRBP clearance is required to view compensation details.",
            )
        above_median = int((salary_col > median_sal).sum())
        return (
            "median_salary",
            f"### 📊 Median Compensation ({scope})\n\n"
            f"- **Median Annual Salary**: **₹{median_sal:,.0f}**\n"
            f"- **Mean (Average) Salary**: ₹{mean_sal:,.0f}\n"
            f"- **Above Median**: {above_median} employees ({above_median/len(data)*100:.1f}%)\n\n"
            f"The median is less influenced by top outliers and provides an accurate baseline for typical compensation in {scope}.",
        )

    if any(
        phrase in q
        for phrase in [
            "salary distribution",
            "salary range",
            "salary bands",
            "compensation bands",
            "pay scale",
        ]
    ):
        if not comp_access:
            return (
                "salary_restricted",
                "🔒 **Access Restricted**: Salary distribution tiers and compensation bands are confidential. Managerial or HRBP clearance is required to view compensation details.",
            )
        tier1 = int((salary_col < 1500000).sum())
        tier2 = int(((salary_col >= 1500000) & (salary_col < 2500000)).sum())
        tier3 = int(((salary_col >= 2500000) & (salary_col < 3500000)).sum())
        tier4 = int((salary_col >= 3500000).sum())
        return (
            "salary_distribution",
            f"### 📈 Salary Tier Distribution ({scope})\n\n"
            f"- **Below ₹15 Lakhs**: {tier1} employees ({(tier1/len(data))*100:.1f}%)\n"
            f"- **₹15L – ₹25 Lakhs**: {tier2} employees ({(tier2/len(data))*100:.1f}%)\n"
            f"- **₹25L – ₹35 Lakhs**: {tier3} employees ({(tier3/len(data))*100:.1f}%)\n"
            f"- **Above ₹35 Lakhs**: {tier4} employees ({(tier4/len(data))*100:.1f}%)\n\n"
            f"Overall salary bounds: **₹{min_sal:,.0f}** to **₹{max_sal:,.0f}** (Average: ₹{mean_sal:,.0f}).",
        )

    # 6. Specific Error Types & Affected Records
    error_patterns = [
        (
            "Salary not matching with SAP",
            [
                "salary mismatch",
                "salary not matching",
                "sap salary",
                "payroll error",
                "salary error",
                "sop-hr-01",
            ],
        ),
        (
            "Cost centre mismatch with company code",
            ["cost centre", "cost center", "cc mismatch", "sop-hr-02"],
        ),
        (
            "High range penetration percentage",
            [
                "range penetration",
                "penetration percentage",
                "high penetration",
                "sop-hr-05",
            ],
        ),
        (
            "Department Code is not matching EC vs SAP",
            [
                "department code",
                "dept mismatch",
                "department mismatch",
                "sop-hr-03",
            ],
        ),
        (
            "Incorrect Business Email",
            [
                "email error",
                "business email",
                "incorrect email",
                "email invalid",
                "email mismatch",
                "sop-hr-04",
            ],
        ),
        (
            "Manager is not matching EC vs SAP",
            [
                "manager mismatch",
                "manager not matching",
                "supervisor mismatch",
                "sop-hr-06",
            ],
        ),
        (
            "Company Code is not matching EC vs SAP",
            ["company code mismatch", "cocd mismatch", "sop-hr-07"],
        ),
    ]
    for canonical_err, keywords in error_patterns:
        if any(kw in q for kw in keywords):
            err_rows = data[
                data["DATA_QUALITY_ERROR_TYPE"]
                .astype(str)
                .str.strip()
                .str.lower()
                == canonical_err.lower()
            ]
            count = len(err_rows)

            if not err_rows.empty:
                samples = err_rows.head(5)
                emp_list = "\n".join(
                    f"- `{r['EMPLOYEE_NO']}` ({r.get('EMPLOYEE_FIRST_NAME','')} {r.get('EMPLOYEE_LAST_NAME','')}) — {r.get('DEPARTMENT_EC','')} | Email: `{r.get('BUSINESS_EMAIL_ID','')}`"
                    for _, r in samples.iterrows()
                )
                sample_text = f"\n\n📋 **Flagged Records Sample** (showing up to 5):\n{emp_list}"
            else:
                sample_text = "\n\n🟢 *There are no records in this scope with this error type.*"

            if "salary" in canonical_err.lower():
                sop = "1. Cross-verify Employee Central (EC) compensation against SAP Infotype 0008.\n2. Note variance discrepancy.\n3. Submit an urgent master-data reconciliation ticket before the 25th payroll freeze."
            elif "cost centre" in canonical_err.lower():
                sop = "1. Obtain correct cost centre code and company code from Finance.\n2. Submit a Finance Change Request with department VP approval.\n3. Re-run SAP master synchronization."
            elif "email" in canonical_err.lower():
                sop = "1. Confirm valid first.last@company.com syntax.\n2. Submit an IT Identity Management (IAM) ticket.\n3. Update the primary SMTP alias in both EC and Active Directory."
            elif "manager" in canonical_err.lower():
                sop = "1. Audit the reporting line hierarchy in SAP OM against EC supervisor ID.\n2. Submit an HR Operations Organizational Alignment ticket."
            elif "department" in canonical_err.lower():
                sop = "1. Align organizational unit IDs between EC and SAP company code chart of accounts.\n2. Execute bulk organizational update via HR Operations."
            elif "company code" in canonical_err.lower():
                sop = "1. Validate statutory entity and payroll tax registration.\n2. Submit Legal Entity Reconciliation ticket to Finance Master Data."
            else:
                sop = "1. Check salary midpoint for the employee's job grade.\n2. Flag for Compensation Committee quarterly review if exceeding 120%."

            return (
                "error_deep_dive",
                f"### ⚠️ Data Quality Analysis: {canonical_err}\n\n"
                f"- **Flagged Records in {scope}**: **{count:,} employee(s)**\n"
                f"- **Governance Priority**: Critical{sample_text}\n\n"
                f"🛠️ **Standard Operating Procedure (SOP)**:\n{sop}",
            )

    # 7. List All Errors / Show Flagged Records
    if any(
        phrase in q
        for phrase in [
            "list errors",
            "show errors",
            "all errors",
            "list flagged",
            "which employees have errors",
            "employees with issues",
            "data errors",
            "flagged records",
        ]
    ):
        errors = data[
            ~data["DATA_QUALITY_ERROR_TYPE"]
            .fillna("No Error")
            .astype(str)
            .str.lower()
            .isin(["", "no error", "nan", "none"])
        ]
        if errors.empty:
            return (
                "all_errors",
                f"🟢 **100% Clean Scope**: There are currently **zero data quality errors** in {scope} across all {len(data)} employee records.",
            )

        breakdown = errors["DATA_QUALITY_ERROR_TYPE"].value_counts()
        lines = [f"- **{err}**: {cnt} record(s)" for err, cnt in breakdown.items()]

        sample_rows = errors.head(6)
        samples_formatted = "\n".join(
            f"- `{r['EMPLOYEE_NO']}` ({r.get('EMPLOYEE_FIRST_NAME','')} {r.get('EMPLOYEE_LAST_NAME','')}) — {r.get('DEPARTMENT_EC','')}: *{r.get('DATA_QUALITY_ERROR_TYPE')}*"
            for _, r in sample_rows.iterrows()
        )

        return (
            "all_errors",
            f"### ⚠️ Active Data Quality Anomalies ({scope})\n\n"
            f"There are **{len(errors)} flagged records** ({(len(errors)/len(data))*100:.1f}% anomaly rate) in {scope}:\n\n"
            + "\n".join(lines)
            + f"\n\n📋 **Sample Flagged Records**:\n{samples_formatted}\n\n"
            f"💡 Click any error row in the **Data Quality Audit** table below to generate an automated remediation ticket.",
        )

    # 8. Demographics: Gender & Diversity
    if any(
        phrase in q
        for phrase in [
            "gender",
            "male vs female",
            "how many female",
            "how many women",
            "how many men",
            "diversity",
            "gender ratio",
            "gender breakdown",
            "women",
            "men",
        ]
    ):
        genders = data["GENDER"].value_counts()
        lines = [
            f"- **{g}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)"
            for g, cnt in genders.items()
        ]
        return (
            "demographics_gender",
            f"### 👥 Gender & Diversity Distribution ({scope})\n\n"
            f"Total workforce in scope: **{len(data)} employees**.\n\n"
            + "\n".join(lines),
        )

    # 9. Demographics: Nationalities
    if any(
        phrase in q
        for phrase in [
            "nationality",
            "nationalities",
            "citizenship",
            "international",
            "countries",
        ]
    ):
        nats = data["NATIONALITY"].value_counts()
        lines = [
            f"- **{n}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)"
            for n, cnt in nats.items()
        ]
        return (
            "demographics_nationality",
            f"### 🌍 Nationality Breakdown ({scope})\n\n"
            f"The workforce in {scope} represents **{len(nats)} nationalities**:\n\n"
            + "\n".join(lines),
        )

    # 10. Employment Type: Regular vs Contract
    if any(
        phrase in q
        for phrase in [
            "contractor",
            "contractors",
            "contract vs regular",
            "regular vs contract",
            "full time",
            "part time",
            "employment type",
            "employee group",
        ]
    ):
        groups = data["EMPLOYEE_GROUP_EC"].value_counts()
        lines_g = [
            f"- **{g}**: {cnt} ({(cnt/len(data))*100:.1f}%)"
            for g, cnt in groups.items()
        ]
        return (
            "employment_type",
            f"### 📋 Employment Classification ({scope})\n\n"
            f"**Primary Employee Groups**:\n" + "\n".join(lines_g),
        )

    # 11. Career Stream & Job Levels (L1-L6)
    if any(
        phrase in q
        for phrase in [
            "job level",
            "job levels",
            "levels",
            "l1",
            "l2",
            "l3",
            "l4",
            "l5",
            "l6",
            "seniority",
            "career stream",
        ]
    ):
        levels = (
            data["JOB_LEVEL_EC"].value_counts().sort_index()
            if "JOB_LEVEL_EC" in data
            else pd.Series()
        )
        streams = (
            data["CAREER_STREAM"].value_counts()
            if "CAREER_STREAM" in data
            else pd.Series()
        )
        lines_lvl = [f"- **{lvl}**: {cnt} employees" for lvl, cnt in levels.items()]
        lines_str = [
            f"- **{st}**: {cnt} ({(cnt/len(data))*100:.1f}%)"
            for st, cnt in streams.items()
        ]
        return (
            "career_levels",
            f"### 🎯 Career Streams & Seniority Levels ({scope})\n\n"
            f"**Career Streams**:\n"
            + "\n".join(lines_str)
            + (
                f"\n\n**Job Levels Breakdown**:\n" + "\n".join(lines_lvl)
                if not levels.empty
                else ""
            ),
        )

    # 12. Job Families
    if any(
        phrase in q
        for phrase in ["job family", "job families", "what roles", "job roles"]
    ):
        jobs = data["JOB_FAMILY"].value_counts()
        lines = [
            f"- **{j}**: {cnt} employees ({(cnt/len(data))*100:.1f}%)"
            for j, cnt in jobs.items()
        ]
        return (
            "job_families",
            f"### 💼 Job Families Distribution ({scope})\n\n"
            f"There are **{len(jobs)} specialized job families** in {scope}:\n\n"
            + "\n".join(lines),
        )

    # 13. Multi-City Comparison (for Manager/CEO)
    if any(
        phrase in q
        for phrase in [
            "compare cities",
            "all locations",
            "which city",
            "city ranking",
            "cities",
            "all cities",
        ]
    ):
        if not global_access:
            return (
                "location_restricted",
                f"Your authorized scope is restricted by corporate RLS to **{access.location}**. Cross-city comparisons require Global Manager or CEO privileges.",
            )
        loc_summary = []
        for loc in sorted(df["LOCATION_DESCRIPTION"].dropna().unique()):
            loc_sub = df[df["LOCATION_DESCRIPTION"] == loc]
            loc_sal = pd.to_numeric(
                loc_sub["ANNUAL_SALARY_EC"], errors="coerce"
            ).dropna()
            loc_errs = len(
                loc_sub[
                    ~loc_sub["DATA_QUALITY_ERROR_TYPE"]
                    .fillna("No Error")
                    .astype(str)
                    .str.lower()
                    .isin(["", "no error", "nan", "none"])
                ]
            )
            loc_summary.append(
                {
                    "loc": loc,
                    "count": len(loc_sub),
                    "sal": loc_sal.mean() if not loc_sal.empty else 0,
                    "errs": loc_errs,
                }
            )
        loc_summary = sorted(loc_summary, key=lambda x: x["count"], reverse=True)
        lines = [
            f"- **{r['loc']}**: {r['count']} employees | Avg Salary: ₹{r['sal']:,.0f} | Flagged Issues: {r['errs']}"
            for r in loc_summary
        ]
        return (
            "city_comparison",
            "### 🌐 Enterprise Multi-City Comparison\n\n" + "\n".join(lines),
        )

    # 14. Plain Headcount & Pay Overview
    if any(w in words for w in ["headcount", "employees", "total", "size"]) and any(
        w in words for w in ["salary", "pay", "compensation"]
    ):
        if not comp_access:
            return (
                "headcount_pay",
                f"### 👥 Workforce Overview ({scope})\n\n"
                f"- **Total Headcount**: **{len(data):,} employees**\n"
                f"- **Compensation Metrics**: 🔒 Confidential (Manager/HRBP Clearance Required)\n"
                f"- **Active Departments**: {data['DEPARTMENT_EC'].nunique()} units\n"
                f"- **Data Quality Health**: {len(data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])])} flagged issues",
            )
        return (
            "headcount_pay",
            f"### 👥 Workforce & Compensation Overview ({scope})\n\n"
            f"- **Total Headcount**: **{len(data):,} employees**\n"
            f"- **Average Annual Salary**: **₹{mean_sal:,.0f}**\n"
            f"- **Compensation Range**: ₹{min_sal:,.0f} to ₹{max_sal:,.0f}\n"
            f"- **Active Departments**: {data['DEPARTMENT_EC'].nunique()} units\n"
            f"- **Data Quality Health**: {len(data[~data['DATA_QUALITY_ERROR_TYPE'].fillna('No Error').astype(str).str.lower().isin(['', 'no error', 'nan', 'none'])])} flagged issues",
        )

    if any(
        w in words
        for w in ["headcount", "employees", "count", "size", "roster", "how many people"]
    ):
        return (
            "headcount_only",
            f"There are **{len(data):,} active employee records** in **{scope}** distributed across **{data['DEPARTMENT_EC'].nunique()} departments**.",
        )

    if any(w in words for w in ["salary", "pay", "compensation", "wages"]):
        if not comp_access:
            return (
                "salary_restricted",
                "🔒 **Access Restricted**: Compensation benchmarks and salary metrics are confidential. Managerial or HRBP clearance is required to view salary data.",
            )
        return (
            "salary_only",
            f"### 💰 Compensation Summary ({scope})\n\n"
            f"- **Average Annual Salary**: **₹{mean_sal:,.0f}**\n"
            f"- **Median Salary**: ₹{median_sal:,.0f}\n"
            f"- **Highest Salary**: ₹{max_sal:,.0f}\n"
            f"- **Lowest Salary**: ₹{min_sal:,.0f}",
        )

    # 15. FAQ Knowledge Base Matching
    for faq_q, faq_ans in FAQ_KNOWLEDGE_BASE.items():
        if faq_q in q or all(w in words for w in faq_q.split() if len(w) > 3):
            return "faq", f"### 📖 Corporate Policy & Governance Guide\n\n{faq_ans}"

    # 16. Fallback
    top_depts = data["DEPARTMENT_EC"].value_counts().head(3).to_dict()
    top_dept_str = ", ".join(f"**{d}** ({c})" for d, c in top_depts.items())
    comp_metric = (
        f"- **Average Compensation**: ₹{mean_sal:,.0f}\n\n"
        if comp_access
        else "- **Compensation Metrics**: 🔒 Confidential (Manager/HRBP Clearance Required)\n\n"
    )
    suggest_dept_sal = (
        "- *'Which department has the highest salary?'*\n"
        if comp_access
        else "- *'What are the active job families?'*\n"
    )

    return (
        "general",
        f'I reviewed records in **{scope}** for your query: *"{raw_question}"*.\n\n'
        f"Key metrics for this scope:\n"
        f"- **Workforce Size**: {len(data):,} active employees\n"
        f"- **Leading Departments**: {top_dept_str}\n"
        f"{comp_metric}"
        f"💡 Try asking:\n"
        f"{suggest_dept_sal}"
        f"- *'Show all employees with errors'*\n"
        f"- *'What is the gender diversity?'*\n"
        f"- *'Tell me about [Department Name]'*",
    )


@router.post("/api/chat")
def chat(request: ChatRequest, access: AccessContext = Depends(require_access)):
    raw_question = request.question.strip()
    global_access = has_global_access(access)
    comp_access = can_view_compensation(access)
    if not global_access:
        blocked, target_city = detect_unauthorized_location(
            raw_question, access.location
        )
        if blocked:
            log_security_event(
                "CROSS_LOCATION_BLOCKED",
                access.employee_id,
                access.role,
                access.location,
                f"Blocked chatbot query requesting {target_city} data outside RLS boundary.",
                status="BLOCKED",
            )
            return {
                "intent": "access_denied",
                "answer": f"🔒 Access Denied: You are not authorized to view {target_city} data. Your employee ID ({access.employee_id}) is restricted by corporate Row-Level Security (RLS) to {access.location}.",
            }
    requested = dict(request.filters or {})
    if not global_access:
        requested["location"] = access.location
    elif not requested.get("location"):
        for canonical, aliases in CITY_ALIASES.items():
            if any(a in raw_question.lower() for a in aliases):
                requested["location"] = canonical.title()
                break
    data = secured_data(FilterParams(**requested), access, log_security_event)
    if data.empty:
        return {
            "intent": "empty_result",
            "answer": f'There are no matching records in the current authorized scope ({requested.get("location") or access.location}). Try clearing a filter.',
        }
    scope = requested.get("location") or (
        "all authorised locations" if global_access else access.location
    )
    report = compute_quality_report(data)

    intent, answer = process_chatbot_query(
        raw_question, data, scope, access, report, global_access, comp_access
    )
    return {"intent": intent, "answer": answer, "service": "chatbot-service"}


app = FastAPI(
    title="DataLens Scoped AI Chatbot Microservice",
    version="4.0.0",
    description="Deterministic Workforce Intelligence, SOP Remediation & RLS-Grounded Assistant",
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
@app.get("/api/chat/health")
def health():
    return {
        "service": "chatbot-service",
        "name": "Scoped AI Chatbot Microservice",
        "port": 8004,
        "status": "healthy",
        "faq_topics": len(FAQ_KNOWLEDGE_BASE),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)

