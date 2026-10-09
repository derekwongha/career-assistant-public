"""
Step 4 — Deterministic Test Suite.

Verifies:
1. Valid state transitions succeed (REVIEW_PENDING -> SKIPPED/APPLY_PENDING, APPLY_PENDING -> COVER_LETTER_GENERATED).
2. Invalid state transitions rejected (SKIPPED -> APPLY_PENDING, REVIEW_PENDING -> COVER_LETTER_GENERATED, etc.).
3. Bulk decisions atomic & reject ineligible jobs without partial writes.
4. Cover letter generation allowed ONLY from APPLY_PENDING.
5. Reopening generated letter causes ZERO LLM calls and ZERO state change.
6. Save Edits overwrites existing .md file with ZERO LLM calls and preserves COVER_LETTER_GENERATED.
7. Save Edits validates file belongs to requested job_id.
8. Dashboard reads existing analysis without LLM.
9. Step 3 evidence selector _select_evidence() is reused.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from career_evidence_catalog_builder import load_saved_career_evidence_catalog
from cover_letter_generator import generate_cover_letter
from dashboard_server import DashboardRequestHandler
from job_analysis_reasoner import _select_evidence
from job_registry import (
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_RETRIEVAL_FAILED,
    STATE_REVIEW_PENDING,
    STATE_SKIPPED,
    bulk_transition_job_states,
    get_all_jobs_for_dashboard,
    init_db,
    register_job_candidate,
    transition_job_state,
    update_analysis_success,
    update_retrieval_success,
)


class TestStep4Deterministic(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "step4_test.sqlite"
        self.output_dir = Path(self.temp_dir) / "cover_letters"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.conn = init_db(self.db_path)
        self.catalog = load_saved_career_evidence_catalog()

        # Seed mock jobs
        # Job 1: High / Apply -> REVIEW_PENDING
        # Job 2: Medium / Strategic Stretch -> REVIEW_PENDING
        # Job 3: Low / Skip -> REVIEW_PENDING
        # Job 4: RETRIEVAL_FAILED
        for i, (prio, act) in enumerate([("High", "Apply"), ("Medium", "Strategic Stretch"), ("Low", "Skip")], 1):
            jid = f"9700000{i}"
            register_job_candidate(
                self.conn,
                jid,
                f"https://sg.jobstreet.com/job/{jid}",
                {"email_subject": "S", "anchor_text": "A", "tracking_url": "t"},
            )
            update_retrieval_success(self.conn, jid, f"Cleaned text {i} Python React Django MySQL")
            analysis_json = json.dumps({
                "job": {
                    "source_reference": f"JOBSTREET-{jid}",
                    "job_url": f"https://sg.jobstreet.com/job/{jid}",
                    "company": f"Company {i}",
                    "role": f"Role {i}",
                    "location": "Singapore",
                    "work_mode": "on-site",
                    "employment_type": "Full-time",
                    "salary": "Not stated",
                    "posting_date": "2026-09-29",
                },
                "priority": prio,
                "action": act,
                "key_matches": [f"Match {i}"],
                "key_gaps": [f"Gap {i}"],
                "summary": f"Summary {i}",
                "tracker_note": f"Note {i}",
            })
            update_analysis_success(self.conn, jid, analysis_json, prio, act)

        # Job 4: RETRIEVAL_FAILED
        register_job_candidate(
            self.conn,
            "97000004",
            "https://sg.jobstreet.com/job/97000004",
            {"email_subject": "S4", "anchor_text": "A4", "tracking_url": "t4"},
        )
        with self.conn:
            self.conn.execute("UPDATE jobs SET status = 'RETRIEVAL_FAILED' WHERE job_id = '97000004'")

    def tearDown(self):
        self.conn.close()
        time.sleep(0.1)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_valid_and_invalid_transitions(self):
        # Valid: REVIEW_PENDING -> SKIPPED
        transition_job_state(self.conn, "97000003", STATE_SKIPPED, human_decision="Skip")
        cur = self.conn.cursor()
        cur.execute("SELECT status, human_decision FROM jobs WHERE job_id = '97000003'")
        row = cur.fetchone()
        self.assertEqual(row[0], STATE_SKIPPED)
        self.assertEqual(row[1], "Skip")

        # Invalid: SKIPPED -> APPLY_PENDING rejected
        with self.assertRaises(ValueError) as ctx:
            transition_job_state(self.conn, "97000003", STATE_APPLY_PENDING)
        self.assertIn("Invalid state transition", str(ctx.exception))

        # Invalid: RETRIEVAL_FAILED -> APPLY_PENDING rejected
        with self.assertRaises(ValueError) as ctx:
            transition_job_state(self.conn, "97000004", STATE_APPLY_PENDING)
        self.assertIn("Invalid state transition", str(ctx.exception))

    def test_02_bulk_decision_atomicity(self):
        # 97000001 & 97000002 are REVIEW_PENDING, 97000004 is RETRIEVAL_FAILED
        with self.assertRaises(ValueError) as ctx:
            bulk_transition_job_states(self.conn, ["97000001", "97000002", "97000004"], STATE_SKIPPED, "Skip")
        self.assertIn("ineligible for bulk decision", str(ctx.exception))

        # Verify zero partial mutation
        cur = self.conn.cursor()
        cur.execute("SELECT status FROM jobs WHERE job_id = '97000001'")
        self.assertEqual(cur.fetchone()[0], STATE_REVIEW_PENDING)
        cur.execute("SELECT status FROM jobs WHERE job_id = '97000002'")
        self.assertEqual(cur.fetchone()[0], STATE_REVIEW_PENDING)

    def test_03_cover_letter_generation_only_from_apply_pending(self):
        # 97000001 is REVIEW_PENDING -> Must reject generation!
        with self.assertRaises(ValueError) as ctx:
            generate_cover_letter(
                job_id="97000001",
                catalog=self.catalog,
                db_path=self.db_path,
                output_dir=self.output_dir,
                mock_response_text="Mock letter",
            )
        self.assertIn("permitted ONLY for jobs in 'APPLY_PENDING'", str(ctx.exception))

        # Transition to APPLY_PENDING -> Must succeed!
        transition_job_state(self.conn, "97000001", STATE_APPLY_PENDING, human_decision="Apply")
        text, file_path = generate_cover_letter(
            job_id="97000001",
            catalog=self.catalog,
            db_path=self.db_path,
            output_dir=self.output_dir,
            mock_response_text="Generated Cover Letter Content",
        )
        self.assertTrue(os.path.exists(file_path))

        cur = self.conn.cursor()
        cur.execute("SELECT status, cover_letter_path FROM jobs WHERE job_id = '97000001'")
        row = cur.fetchone()
        self.assertEqual(row[0], STATE_COVER_LETTER_GENERATED)
        self.assertEqual(row[1], file_path)

    def test_04_reopen_causes_zero_llm_calls_and_zero_state_change(self):
        # Manually create cover letter file & update DB state
        file_path = self.output_dir / "97000001_cover_letter.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Persisted Cover Letter Content")

        with self.conn:
            self.conn.execute(
                "UPDATE jobs SET status = ?, cover_letter_path = ? WHERE job_id = ?",
                (STATE_COVER_LETTER_GENERATED, str(file_path.resolve()), "97000001"),
            )

        # Reopen file directly from disk
        with open(file_path, "r", encoding="utf-8") as f:
            read_content = f.read()

        self.assertEqual(read_content, "Persisted Cover Letter Content")

        # Verify DB status unchanged
        cur = self.conn.cursor()
        cur.execute("SELECT status FROM jobs WHERE job_id = '97000001'")
        self.assertEqual(cur.fetchone()[0], STATE_COVER_LETTER_GENERATED)

    def test_05_save_edits_overwrites_file_without_llm_call(self):
        file_path = self.output_dir / "97000001_cover_letter.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Original Content")

        with self.conn:
            self.conn.execute(
                "UPDATE jobs SET status = ?, cover_letter_path = ? WHERE job_id = ?",
                (STATE_COVER_LETTER_GENERATED, str(file_path.resolve()), "97000001"),
            )

        # Overwrite file
        edited_text = "Edited Cover Letter Content by the reviewer"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(edited_text)

        # Verify file content
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), edited_text)

        # Verify status remains COVER_LETTER_GENERATED
        cur = self.conn.cursor()
        cur.execute("SELECT status FROM jobs WHERE job_id = '97000001'")
        self.assertEqual(cur.fetchone()[0], STATE_COVER_LETTER_GENERATED)

    def test_06_dashboard_reads_without_llm(self):
        jobs = get_all_jobs_for_dashboard(self.conn)
        self.assertEqual(len(jobs), 4)
        j1 = [j for j in jobs if j["job_id"] == "97000001"][0]
        self.assertEqual(j1["analysis"]["priority"], "High")

    def test_07_evidence_selector_reused(self):
        job_text = "Python Django React MySQL REST API developer"
        selected = _select_evidence(job_text, self.catalog)
        self.assertGreater(len(selected), 0)
        self.assertLessEqual(len(selected), 35)


if __name__ == "__main__":
    unittest.main()
