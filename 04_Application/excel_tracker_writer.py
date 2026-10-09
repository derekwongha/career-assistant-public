"""
Step 5 — Excel Application Tracker Writer Module.

Handles reading, validating, and writing application records into the existing Excel tracker workbook.
Preserves placeholder-row architecture (APP-001..APP-100), formatting, Data Validation, formulas,
and Dashboard sheet formulas.
"""

import os
import shutil
import tempfile

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
import openpyxl

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
# Your own tracker workbook. Override with CAREER_TRACKER_PATH. This path is gitignored.
DEFAULT_EXCEL_PATH = Path(
    os.environ.get(
        "CAREER_TRACKER_PATH",
        str(WORKSPACE_DIR / "data" / "job_application_tracker.xlsx"),
    )
)

ALLOWED_WORK_TYPES = {
    "Full-time", "Contract", "Temporary", "Part-time", "Hybrid", "Remote", "On-site"
}

ALLOWED_SOURCES = {
    "JobStreet", "LinkedIn", "MyCareersFuture", "Company Website", "Recruiter", "Referral", "Other"
}


def get_sgt_date_str() -> str:
    """Returns current date formatted as YYYY-MM-DD in Asia/Singapore (UTC+8)."""
    sgt_tz = timezone(timedelta(hours=8))
    return datetime.now(sgt_tz).strftime("%Y-%m-%d")


def find_first_blank_placeholder(sheet: openpyxl.worksheet.worksheet.Worksheet) -> Tuple[int, str]:
    """
    Finds the first pre-created placeholder row in Applications sheet.
    A placeholder row has a valid APP-xxx in Col A (Col 1), but empty data cells in Col B:Q.
    Returns (row_index, app_id).
    Raises ValueError if all 100 placeholder rows are exhausted.
    """
    for r in range(2, sheet.max_row + 1):
        app_id = sheet.cell(row=r, column=1).value
        if app_id and str(app_id).startswith("APP-"):
            # Check if company (Col C) and role (Col D) and date (Col B) are blank
            date_val = sheet.cell(row=r, column=2).value
            company_val = sheet.cell(row=r, column=3).value
            role_val = sheet.cell(row=r, column=4).value
            
            if date_val is None and company_val is None and role_val is None:
                return r, str(app_id)

    raise ValueError("All pre-created placeholder rows (APP-001..APP-100) are exhausted.")


def check_excel_duplicate(
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    job_id: str,
    confirmed_url: str
) -> Optional[str]:
    """
    Checks if job_id or confirmed_url is already present in the Applications sheet.
    Returns an error message if duplicate found, else None.
    """
    for r in range(2, sheet.max_row + 1):
        url_cell = sheet.cell(row=r, column=6).value
        notes_cell = sheet.cell(row=r, column=17).value
        
        url_str = str(url_cell) if url_cell else ""
        notes_str = str(notes_cell) if notes_cell else ""
        
        if job_id and (job_id in url_str or job_id in notes_str):
            app_id = sheet.cell(row=r, column=1).value
            return f"Job ID {job_id} already exists in Excel row {r} ({app_id})."
            
        if confirmed_url and confirmed_url in url_str:
            app_id = sheet.cell(row=r, column=1).value
            return f"Confirmed URL already exists in Excel row {r} ({app_id})."
            
    return None


def resolve_work_type(facts: dict) -> str:
    """
    Resolves the Work Type dropdown value from job facts.
    Checks employment_type first (e.g. 'Full time'), then work_mode.
    """
    if not isinstance(facts, dict):
        return "Unknown"
    emp_mapped = map_work_type(facts.get("employment_type"))
    if emp_mapped != "Unknown":
        return emp_mapped
    mode_mapped = map_work_type(facts.get("work_mode"))
    if mode_mapped != "Unknown":
        return mode_mapped
    return "Unknown"


def map_work_type(work_mode: Optional[str]) -> str:
    """
    Maps a raw work_mode / employment_type string to an allowed Work Type dropdown value.
    If missing, unmapped, or 'Not stated', returns 'Unknown'.
    """
    if not work_mode:
        return "Unknown"
    
    clean_mode = str(work_mode).strip()
    if clean_mode in ALLOWED_WORK_TYPES:
        return clean_mode
        
    # Check simple substring matching
    lower_mode = clean_mode.lower()
    if "full" in lower_mode:
        return "Full-time"
    if "contract" in lower_mode:
        return "Contract"
    if "hybrid" in lower_mode:
        return "Hybrid"
    if "remote" in lower_mode:
        return "Remote"
    if "part" in lower_mode:
        return "Part-time"
    if "temp" in lower_mode:
        return "Temporary"
    if "intern" in lower_mode:
        return "Internship"
    if "freelance" in lower_mode:
        return "Freelance"
    if "on-site" in lower_mode or "onsite" in lower_mode:
        return "On-site"
        
    return "Unknown"



def write_application_to_excel(
    excel_path: Path,
    job_data: Dict[str, Any],
    application_url: Optional[str] = None,
    custom_notes: Optional[str] = None,
    custom_work_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Writes a new application record into the first blank placeholder row in the Excel tracker.
    Uses backup copy for rollback safety.
    Returns dict with success status, assigned excel_app_id, row index, and backup_path.
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel tracker file not found at: {excel_path}")

    # Create temporary backup file before modification
    backup_fd, backup_path_str = tempfile.mkstemp(suffix=".xlsx", prefix="excel_tracker_backup_")
    os.close(backup_fd)
    backup_path = Path(backup_path_str)
    shutil.copy2(excel_path, backup_path)

    try:
        wb = openpyxl.load_workbook(excel_path, data_only=False)
        if "Applications" not in wb.sheetnames:
            raise ValueError("Sheet 'Applications' not found in workbook.")

        app_sheet = wb["Applications"]

        # 1. Extract details from job_data
        job_id = str(job_data.get("job_id", ""))
        confirmed_url = str(job_data.get("confirmed_url", ""))
        analysis_raw = job_data.get("analysis_result_json") or job_data.get("analysis") or {}
        if isinstance(analysis_raw, str):
            import json
            try:
                analysis = json.loads(analysis_raw)
            except Exception:
                analysis = {}
        elif isinstance(analysis_raw, dict):
            analysis = analysis_raw
        else:
            analysis = {}
                
        facts = analysis.get("job", {}) if isinstance(analysis, dict) else {}
        company = facts.get("company") or "Company"
        role = facts.get("role") or "Role"
        location = facts.get("location") or "Singapore"
        raw_salary = str(facts.get("salary") or "").strip()
        if not raw_salary or raw_salary.lower() in ["not stated", "none", "n/a", "unavailable", "null", "undisclosed"]:
            salary = "Undisclosed"
        else:
            salary = raw_salary



        prio = job_data.get("recommended_priority") or "Low"
        if prio not in ["High", "Medium", "Low"]:
            prio = "Low"

        # 2. Check duplicates
        dup_err = check_excel_duplicate(app_sheet, job_id, confirmed_url)
        if dup_err:
            raise ValueError(dup_err)

        # 3. Find first blank placeholder row
        row_idx, app_id = find_first_blank_placeholder(app_sheet)

        # 4. Prepare Field Values
        date_applied = get_sgt_date_str()
        source = "JobStreet"
        final_url = application_url.strip() if application_url and application_url.strip() else confirmed_url
        work_type = custom_work_type.strip() if custom_work_type and custom_work_type.strip() else resolve_work_type(facts)
        portfolio_sent = "Yes"
        status_val = "Applied"
        
        note = custom_notes.strip() if custom_notes and custom_notes.strip() else (analysis.get("tracker_note") if isinstance(analysis, dict) else "")

        # 5. Populate cells (Row row_idx, Cols 1..17)
        # Col A (1): Application ID (keep app_id)
        # Col B (2): Date Applied
        app_sheet.cell(row=row_idx, column=2, value=date_applied)
        # Col C (3): Company
        app_sheet.cell(row=row_idx, column=3, value=company)
        # Col D (4): Role
        app_sheet.cell(row=row_idx, column=4, value=role)
        # Col E (5): Source
        app_sheet.cell(row=row_idx, column=5, value=source)
        # Col F (6): Job URL (as hyperlink)
        cell_f = app_sheet.cell(row=row_idx, column=6, value=final_url)
        if final_url.startswith("http"):
            cell_f.hyperlink = final_url
        # Col G (7): Location
        app_sheet.cell(row=row_idx, column=7, value=location)
        # Col H (8): Work Type
        app_sheet.cell(row=row_idx, column=8, value=work_type)
        # Col I (9): Salary Range
        app_sheet.cell(row=row_idx, column=9, value=salary)
        # Col J (10): Status
        app_sheet.cell(row=row_idx, column=10, value=status_val)
        # Col K (11): Priority
        app_sheet.cell(row=row_idx, column=11, value=prio)
        # Col L (12): Contact / Recruiter
        # Col M (13): Follow-up Date
        # Col N (14): Next Action
        # Col O (15): Portfolio Sent
        app_sheet.cell(row=row_idx, column=15, value=portfolio_sent)
        # Col P (16): Interview Date
        # Col Q (17): Outcome / Notes
        app_sheet.cell(row=row_idx, column=17, value=note)

        # 6. Save modified workbook
        wb.save(excel_path)

        # 7. Re-open and verify write
        wb_verify = openpyxl.load_workbook(excel_path, data_only=True)
        sheet_verify = wb_verify["Applications"]
        v_company = sheet_verify.cell(row=row_idx, column=3).value
        v_role = sheet_verify.cell(row=row_idx, column=4).value
        
        if v_company != company or v_role != role:
            raise RuntimeError(f"Verification failed after saving Excel row {row_idx}.")

        return {
            "success": True,
            "excel_app_id": app_id,
            "row_index": row_idx,
            "backup_path": str(backup_path),
        }

    except Exception as exc:
        # Restore backup if error occurs
        if backup_path.exists():
            shutil.copy2(backup_path, excel_path)
            try:
                os.remove(backup_path)
            except Exception:
                pass
        raise exc


def restore_excel_backup(excel_path: Path, backup_path: Path) -> None:
    """Restores pre-execution backup file over excel_path in case of failure."""
    excel_path = Path(excel_path)
    backup_path = Path(backup_path)
    if backup_path.exists():
        shutil.copy2(backup_path, excel_path)
        try:
            os.remove(backup_path)
        except Exception:
            pass
