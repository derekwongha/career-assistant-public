"""
Builds the SYNTHETIC demo data for the review dashboard.

Everything here is fictional: the candidate ("Casey Placeholder"), the
companies, the jobs and the cover letter. Nothing is read from a personal
database or workbook.

Outputs (all under examples/demo/output/, which is gitignored):
- demo_registry.sqlite   SQLite registry created with the app's own schema
- demo_tracker.xlsx      blank tracker built from scratch (no author metadata)
- cover_letters/         one demonstration cover letter

Paths stored in the database are relative to the repository root.
Run from anywhere:  python examples/demo/make_demo.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "04_Application"
sys.path.insert(0, str(APP_DIR))

from job_registry import init_db  # noqa: E402
from tracker_template import build_blank_tracker  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "output"
DB_PATH = OUT_DIR / "demo_registry.sqlite"
XLSX_PATH = OUT_DIR / "demo_tracker.xlsx"
COVER_DIR = OUT_DIR / "cover_letters"
COVER_DIR_REL = "examples/demo/output/cover_letters"  # relative to REPO_ROOT


def A(req, typ, match, ev, why):
    return {"requirement": req, "requirement_type": typ, "match_type": match,
            "evidence_ids": ev, "rationale": why}


# Fictional jobs. Evidence IDs refer to examples/synthetic_career_evidence_catalog.json.
JOBS = [
    ("99000001", "Harbourlight Digital", "Junior Full-Stack Developer", "hybrid", "S$3,800 - S$4,800",
     "High", "Apply", "REVIEW_PENDING",
     "Strong overlap on React, Django and REST APIs; main gap is cloud deployment.",
     "Strong stack match; gap on cloud deployment. Worth applying.",
     [A("React and modern JavaScript", "required", "DIRECT", ["PORTFOLIO-005"], "React frontend in a portfolio project."),
      A("Python / Django and REST APIs", "required", "DIRECT", ["PORTFOLIO-003"], "Django REST Framework API with authentication."),
      A("SQL databases", "required", "DIRECT", ["PORTFOLIO-004"], "MySQL schema design."),
      A("Version control with Git", "required", "DIRECT", ["PORTFOLIO-008"], "Git and pull requests across projects."),
      A("Stakeholder communication", "preferred", "TRANSFERABLE", ["CAPABILITY_MATRIX-009"], "Vendor and user coordination in an operations role."),
      A("AWS or similar cloud deployment", "preferred", "GAP", [], "No supplied evidence of cloud deployment.")]),
    ("99000002", "Kestrel Analytics", "Application Support Engineer", "on-site", "Not stated",
     "Medium", "Strategic Stretch", "REVIEW_PENDING",
     "Helpdesk and SQL fit; gaps in Linux administration and monitoring tools.",
     "Support background fits; lacks Linux and monitoring depth. Reasonable stretch.",
     [A("Troubleshoot user issues", "responsibility", "TRANSFERABLE", ["RESUME-009"], "Volunteer IT helpdesk."),
      A("Basic SQL", "required", "DIRECT", ["PORTFOLIO-006"], "SQL reporting queries."),
      A("Documentation", "preferred", "DIRECT", ["PORTFOLIO-009"], "Project READMEs and notes."),
      A("Linux server administration", "required", "GAP", [], "No supplied evidence of Linux administration."),
      A("Monitoring tools", "preferred", "GAP", [], "No supplied evidence of monitoring tools.")]),
    ("99000003", "Mapleleaf Logistics Tech", "Backend Developer (Python)", "remote", "S$4,000 - S$5,500",
     "Medium", "Strategic Stretch", "REVIEW_PENDING",
     "Python and API work fit; the role expects 3+ years of commercial backend work.",
     "Python/API fit; commercial-experience gap. Stretch application.",
     [A("Python backend development", "required", "DIRECT", ["CAPABILITY_MATRIX-001"], "Django projects."),
      A("REST API design", "required", "DIRECT", ["PORTFOLIO-003"], "Documented API endpoints."),
      A("3+ years commercial experience", "required", "GAP", [], "Project experience only."),
      A("Automated testing", "preferred", "DIRECT", ["PORTFOLIO-002"], "Django unit tests.")]),
    ("99000004", "Orchid Systems", "Web Developer", "hybrid", "S$3,200 - S$4,000",
     "Medium", "Apply", "REVIEW_PENDING",
     "Frontend and responsive design overlap; PHP is not in the portfolio.",
     "Frontend fit; PHP gap. Apply.",
     [A("HTML, CSS and JavaScript", "required", "DIRECT", ["PORTFOLIO-005"], "Responsive frontend."),
      A("PHP", "required", "GAP", [], "No supplied evidence of PHP.")]),
    ("99000005", "Pinecrest Software", "Low-Code Automation Engineer", "on-site", "Not stated",
     "Low", "Skip", "REVIEW_PENDING",
     "Requires a specific low-code platform with no supplied evidence.",
     "Platform-specific; skip.",
     [A("Microsoft Power Platform", "required", "GAP", [], "No supplied evidence."),
      A("Process documentation", "preferred", "TRANSFERABLE", ["CAPABILITY_MATRIX-010"], "Wrote procedures in an operations role.")]),
    ("99000006", "Quayside Health IT", "Junior Software Developer", "hybrid", "S$3,500 - S$4,500",
     "High", "Apply", "APPLY_PENDING",
     "Entry-level role that accepts project experience; React and Django align.",
     "Entry-level fit. Apply.",
     [A("React", "required", "DIRECT", ["PORTFOLIO-005"], "React project."),
      A("Django", "preferred", "DIRECT", ["PORTFOLIO-001"], "Django project.")]),
    ("99000007", "Redwood Retail Tech", "Full-Stack Developer", "hybrid", "S$4,200 - S$5,200",
     "High", "Apply", "COVER_LETTER_GENERATED",
     "Python, React and APIs align; Docker is a minor gap.",
     "Strong match. Cover letter drafted.",
     [A("React and Python", "required", "DIRECT", ["PORTFOLIO-001"], "Full-stack project."),
      A("REST APIs", "required", "DIRECT", ["PORTFOLIO-003"], "REST API project."),
      A("Docker", "preferred", "GAP", [], "Exposure only; no project uses Docker.")]),
    ("99000008", "Sunbeam Education", "Frontend Developer", "on-site", "Not stated",
     "Low", "Skip", "SKIPPED",
     "Angular-specific role; React skills transfer only partially.",
     "Angular-specific; skipped.",
     [A("Angular", "required", "GAP", [], "No supplied evidence of Angular."),
      A("JavaScript", "required", "DIRECT", ["CAPABILITY_MATRIX-004"], "React/JavaScript projects.")]),
]

COVER_LETTER = """Dear Hiring Manager,

I am writing to apply for the Full-Stack Developer position at Redwood Retail Tech.
I have built portfolio projects with Django, Django REST Framework, React and MySQL,
including a REST API with token-based authentication.

(Demonstration letter: the candidate, company and projects are fictional.)

Sincerely,
Casey Placeholder
"""

NOW = "2026-01-05T09:00:00+00:00"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = init_db(DB_PATH)
    for (jid, co, role, wm, sal, pri, act, status, summary, note, assess) in JOBS:
        url = f"https://example.com/jobs/{jid}"
        analysis = {
            "job": {"source_reference": f"DEMO-{jid}", "job_url": url, "company": co, "role": role,
                    "location": "Singapore", "work_mode": wm, "employment_type": "Full time",
                    "salary": sal, "posting_date": "1d ago"},
            "assessments": assess,
            "summary": summary,
            "key_matches": [a["requirement"] for a in assess if a["match_type"] in ("DIRECT", "PARTIAL")][:4],
            "key_gaps": [a["requirement"] for a in assess if a["match_type"] in ("GAP", "TRANSFERABLE")][:3],
            "priority": pri, "action": act, "rationale": summary, "tracker_note": note,
            "analysis_warnings": [],
        }
        cover_rel = None
        if status == "COVER_LETTER_GENERATED":
            (COVER_DIR / f"{jid}_cover_letter.md").write_text(COVER_LETTER, encoding="utf-8")
            cover_rel = f"{COVER_DIR_REL}/{jid}_cover_letter.md"
        decision = {"SKIPPED": "Skip", "APPLY_PENDING": "Apply", "COVER_LETTER_GENERATED": "Apply"}.get(status)
        conn.execute(
            "INSERT INTO jobs (job_id, source_reference, confirmed_url, first_seen, last_seen, status, "
            "cleaned_text, analysis_result_json, recommended_priority, recommended_action, human_decision, "
            "cover_letter_path, excel_app_id, last_error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (jid, f"DEMO-{jid}", url, NOW, NOW, status, f"Demonstration listing text for {co} (fictional).",
             json.dumps(analysis), pri, act, decision, cover_rel, None, None),
        )
        conn.execute(
            "INSERT INTO job_sources (job_id, seen_at, email_subject, email_date, email_sender, anchor_text, "
            "tracking_url) VALUES (?,?,?,?,?,?,?)",
            (jid, NOW, "Demo job alert", NOW, "alerts@example.com", role, url),
        )
    conn.commit()
    conn.close()

    if XLSX_PATH.exists():
        XLSX_PATH.unlink()
    build_blank_tracker(XLSX_PATH)

    print("Synthetic demo data ready:")
    print(f"  {DB_PATH.relative_to(REPO_ROOT)}")
    print(f"  {XLSX_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
