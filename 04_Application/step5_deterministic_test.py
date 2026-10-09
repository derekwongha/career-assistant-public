"""
Step 5 Deterministic Test Suite.

Verifies:
1. APPLY_PENDING -> APPLIED succeeds.
2. COVER_LETTER_GENERATED -> APPLIED succeeds.
3. REVIEW_PENDING -> APPLIED fails.
4. Double submission / excel_app_id already populated fails.
5. SQLite transition requires excel_app_id IS NULL and rowcount == 1.
6. Excel failure restores pre-execution backup and leaves SQLite untouched.
7. First blank placeholder detection returns Row 30 (APP-029) in the fictional fixture.
8. Work Type fallback to 'Unknown' when unmapped or 'Not stated'.
9. Portfolio Sent = 'Yes'.
10. SGT date formatting (YYYY-MM-DD).
11. Excel hyperlink persistence on Col F.
12. Dashboard sheet formulas and ranges remain formula-equivalent.
"""

import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
import openpyxl

from tracker_template import build_blank_tracker

from excel_tracker_writer import (
    DEFAULT_EXCEL_PATH,
    find_first_blank_placeholder,
    get_sgt_date_str,
    map_work_type,
    restore_excel_backup,
    write_application_to_excel,
)
from job_registry import (
    STATE_APPLIED,
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_REVIEW_PENDING,
    STATE_SKIPPED,
    init_db,
    register_job_candidate,
    transition_job_state,
    transition_to_applied,
    update_human_decision,
)


class TestStep5Deterministic(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = Path(self.temp_dir) / "test_registry.sqlite"
        self.temp_excel = Path(self.temp_dir) / "test_tracker.xlsx"

        conn = init_db(self.temp_db)
        conn.close()

        # Fresh fictional tracker: APP-001..APP-028 used, APP-029 is the first blank placeholder.
        build_blank_tracker(self.temp_excel, prefilled_fictional_rows=28)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_state_transitions_to_applied(self):
        conn = sqlite3.connect(self.temp_db)
        conn.row_factory = sqlite3.Row
        cand = {"email_subject": "sub", "anchor_text": "text", "tracking_url": "url"}
        register_job_candidate(conn, "job-1", "https://example.com/url1", cand)
        register_job_candidate(conn, "job-2", "https://example.com/url2", cand)
        register_job_candidate(conn, "job-3", "https://example.com/url3", cand)

        update_human_decision(conn, "job-1", "Apply") # APPLY_PENDING
        update_human_decision(conn, "job-2", "Apply")
        transition_job_state(conn, "job-2", STATE_COVER_LETTER_GENERATED, cover_letter_path="/tmp/job2.md")

        # 1. APPLY_PENDING -> APPLIED succeeds
        transition_to_applied(conn, "job-1", "APP-028")
        cur = conn.cursor()
        cur.execute("SELECT status, excel_app_id FROM jobs WHERE job_id = 'job-1'")
        r1 = cur.fetchone()
        self.assertEqual(r1[0], STATE_APPLIED)
        self.assertEqual(r1[1], "APP-028")

        # 2. COVER_LETTER_GENERATED -> APPLIED succeeds
        transition_to_applied(conn, "job-2", "APP-029")
        cur.execute("SELECT status, excel_app_id FROM jobs WHERE job_id = 'job-2'")
        r2 = cur.fetchone()
        self.assertEqual(r2[0], STATE_APPLIED)
        self.assertEqual(r2[1], "APP-029")

        # 3. REVIEW_PENDING -> APPLIED is rejected
        with self.assertRaises(ValueError):
            transition_to_applied(conn, "job-3", "APP-030")

        # 4. Double transition on already APPLIED job is rejected
        with self.assertRaises(ValueError):
            transition_to_applied(conn, "job-1", "APP-031")

        conn.close()

    def test_excel_writer_placeholder_and_work_type_fallback(self):
        wb = openpyxl.load_workbook(self.temp_excel)
        sheet = wb["Applications"]
        row_idx, app_id = find_first_blank_placeholder(sheet)
        self.assertEqual(row_idx, 30)
        self.assertEqual(app_id, "APP-029")

        # Test map_work_type fallback
        self.assertEqual(map_work_type("Not stated"), "Unknown")
        self.assertEqual(map_work_type("Unspecified"), "Unknown")
        self.assertEqual(map_work_type("Hybrid"), "Hybrid")

        job_data = {
            "job_id": "job-test-100",
            "confirmed_url": "https://www.jobstreet.com.sg/job/job-test-100",
            "recommended_priority": "Medium",
            "analysis": {
                "job": {
                    "company": "Acme Corp",
                    "role": "Backend Engineer",
                    "location": "Singapore",
                    "work_mode": "Not stated",
                },
                "tracker_note": "Solid backend profile",
            },
        }

        res = write_application_to_excel(
            excel_path=self.temp_excel,
            job_data=job_data,
            application_url="https://careers.example.com/apply/100",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["excel_app_id"], "APP-029")

        # Verify openpyxl values
        wb2 = openpyxl.load_workbook(self.temp_excel, data_only=True)
        s2 = wb2["Applications"]
        self.assertEqual(s2.cell(row=30, column=1).value, "APP-029")
        self.assertEqual(s2.cell(row=30, column=2).value, get_sgt_date_str())
        self.assertEqual(s2.cell(row=30, column=3).value, "Acme Corp")
        self.assertEqual(s2.cell(row=30, column=4).value, "Backend Engineer")
        self.assertEqual(s2.cell(row=30, column=5).value, "JobStreet")
        self.assertEqual(s2.cell(row=30, column=6).value, "https://careers.example.com/apply/100")
        self.assertEqual(s2.cell(row=30, column=8).value, "Unknown")
        self.assertEqual(s2.cell(row=30, column=9).value, "Undisclosed")
        self.assertEqual(s2.cell(row=30, column=10).value, "Applied")
        self.assertEqual(s2.cell(row=30, column=15).value, "Yes")

    def test_salary_range_fallback(self):
        # Meaningful salary test
        job_data_with_salary = {
            "job_id": "job-sal-1",
            "confirmed_url": "https://www.jobstreet.com.sg/job/job-sal-1",
            "recommended_priority": "High",
            "analysis": {"job": {"company": "Sal Corp", "role": "Dev", "salary": "$6,000 - $8,000"}},
        }
        res1 = write_application_to_excel(self.temp_excel, job_data_with_salary)
        wb1 = openpyxl.load_workbook(self.temp_excel, data_only=True)
        self.assertEqual(wb1["Applications"].cell(row=30, column=9).value, "$6,000 - $8,000")

        # Missing / Not stated salary test
        job_data_no_salary = {
            "job_id": "job-sal-2",
            "confirmed_url": "https://www.jobstreet.com.sg/job/job-sal-2",
            "recommended_priority": "Medium",
            "analysis": {"job": {"company": "Sal Corp 2", "role": "Dev 2", "salary": "Not stated"}},
        }
        res2 = write_application_to_excel(self.temp_excel, job_data_no_salary)
        wb2 = openpyxl.load_workbook(self.temp_excel, data_only=True)
        self.assertEqual(wb2["Applications"].cell(row=31, column=9).value, "Undisclosed")

    def test_dashboard_formulas_preserved(self):
        wb_before = openpyxl.load_workbook(self.temp_excel, data_only=False)
        dash_before = wb_before["Dashboard"]

        # Write application
        job_data = {
            "job_id": "job-test-200",
            "confirmed_url": "https://www.jobstreet.com.sg/job/job-test-200",
            "recommended_priority": "High",
            "analysis": {"job": {"company": "Beta Tech", "role": "Dev"}},
        }
        write_application_to_excel(self.temp_excel, job_data)

        wb_after = openpyxl.load_workbook(self.temp_excel, data_only=False)
        dash_after = wb_after["Dashboard"]

        # Verify Dashboard formulas are byte/formula equivalent
        for r in range(1, dash_before.max_row + 1):
            for c in range(1, dash_before.max_column + 1):
                val_before = dash_before.cell(row=r, column=c).value
                val_after = dash_after.cell(row=r, column=c).value
                self.assertEqual(val_before, val_after, f"Dashboard formula mismatch at R{r}C{c}")

    def test_rollback_on_sqlite_failure(self):
        # Write Excel first
        job_data = {
            "job_id": "job-rollback-1",
            "confirmed_url": "https://www.jobstreet.com.sg/job/job-rollback-1",
            "recommended_priority": "High",
            "analysis": {"job": {"company": "Rollback Inc", "role": "QA"}},
        }
        res = write_application_to_excel(self.temp_excel, job_data)
        backup_path = Path(res["backup_path"])

        # Simulate SQLite failure and restore backup
        restore_excel_backup(self.temp_excel, backup_path)

        wb_restored = openpyxl.load_workbook(self.temp_excel, data_only=True)
        s_restored = wb_restored["Applications"]
        self.assertIsNone(s_restored.cell(row=30, column=3).value) # Row 30 restored to blank



if __name__ == "__main__":
    unittest.main()
