"""
Unit tests for Step 4 Cover Letter Generator Component.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from career_evidence_catalog_builder import load_saved_career_evidence_catalog
from cover_letter_generator import (
    COVER_LETTER_SYSTEM_PROMPT,
    _build_cover_letter_user_prompt,
    generate_cover_letter,
)
from job_analysis_reasoner import _select_evidence
from job_registry import (
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_REVIEW_PENDING,
    STATE_SKIPPED,
    init_db,
    register_job_candidate,
    transition_job_state,
    update_analysis_success,
    update_retrieval_success,
)


class TestCoverLetterGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_registry.sqlite"
        self.output_dir = Path(self.temp_dir) / "cover_letters"
        self.conn = init_db(self.db_path)
        self.catalog = load_saved_career_evidence_catalog()

        # Insert test job in REVIEW_PENDING
        register_job_candidate(
            self.conn,
            "99000001",
            "https://sg.jobstreet.com/job/99000001",
            {"email_subject": "S", "anchor_text": "A", "tracking_url": "t"},
        )
        update_retrieval_success(self.conn, "99000001", "Python React Full Stack Developer job text")
        analysis_json = json.dumps({
            "job": {
                "source_reference": "JOBSTREET-99000001",
                "job_url": "https://sg.jobstreet.com/job/99000001",
                "company": "Bluefin Example Consulting",
                "role": "Junior Full-Stack Developer",
                "location": "Katong",
                "work_mode": "on-site",
                "employment_type": "Full-time",
                "salary": "Not stated",
                "posting_date": "2026-09-29",
            },
            "priority": "High",
            "action": "Apply",
            "key_matches": ["React frontend", "Python backend"],
            "key_gaps": ["No AWS cloud"],
            "summary": "Strong core alignment.",
            "tracker_note": "Apply as high priority.",
        })
        update_analysis_success(self.conn, "99000001", analysis_json, "High", "Apply")

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.temp_dir)

    def test_generation_only_from_apply_pending(self):
        # Current status is REVIEW_PENDING -> Must reject!
        with self.assertRaises(ValueError) as ctx:
            generate_cover_letter(
                job_id="99000001",
                catalog=self.catalog,
                db_path=self.db_path,
                output_dir=self.output_dir,
                mock_response_text="Mock letter content",
            )
        self.assertIn("permitted ONLY for jobs in 'APPLY_PENDING'", str(ctx.exception))

        # Update to SKIPPED -> Must reject!
        transition_job_state(self.conn, "99000001", STATE_SKIPPED, human_decision="Skip")
        with self.assertRaises(ValueError) as ctx:
            generate_cover_letter(
                job_id="99000001",
                catalog=self.catalog,
                db_path=self.db_path,
                output_dir=self.output_dir,
                mock_response_text="Mock letter content",
            )
        self.assertIn("permitted ONLY for jobs in 'APPLY_PENDING'", str(ctx.exception))

    def test_mock_generation_success_and_state_transition(self):
        # Transition to APPLY_PENDING
        with self.conn:
            self.conn.execute("UPDATE jobs SET status = 'REVIEW_PENDING' WHERE job_id = '99000001'")
        transition_job_state(self.conn, "99000001", STATE_APPLY_PENDING, human_decision="Apply")

        mock_text = "# Cover Letter\nDear Hiring Manager,\n\nI am writing to apply for the Junior Full-Stack Developer role at Bluefin Example Consulting..."
        letter_content, file_path = generate_cover_letter(
            job_id="99000001",
            catalog=self.catalog,
            db_path=self.db_path,
            output_dir=self.output_dir,
            mock_response_text=mock_text,
        )

        self.assertEqual(letter_content, mock_text)
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            saved_content = f.read()
        self.assertEqual(saved_content, mock_text)

        # Check DB status updated to COVER_LETTER_GENERATED
        cur = self.conn.cursor()
        cur.execute("SELECT status, cover_letter_path FROM jobs WHERE job_id = '99000001'")
        row = cur.fetchone()
        self.assertEqual(row["status"], STATE_COVER_LETTER_GENERATED)
        self.assertEqual(row["cover_letter_path"], file_path)

    def test_evidence_selector_reused(self):
        job_text = "Python React Django MySQL REST API Agile developer"
        evidence = _select_evidence(job_text, self.catalog)
        self.assertGreater(len(evidence), 0)
        self.assertLessEqual(len(evidence), 35)

    def test_grounding_prompt_rules(self):
        self.assertIn("NEVER invent candidate employment history", COVER_LETTER_SYSTEM_PROMPT)
        self.assertIn("Do NOT describe portfolio or academic project work as commercial experience", COVER_LETTER_SYSTEM_PROMPT)
        self.assertIn("Do NOT upgrade listed skills to \"expertise\"", COVER_LETTER_SYSTEM_PROMPT)
        self.assertIn("Do NOT upgrade a Certificate of Attendance to a professional certification", COVER_LETTER_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
