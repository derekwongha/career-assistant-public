"""
Unit tests for Step 4 Dashboard Server REST API endpoints.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
import requests

from dashboard_server import create_server
from job_registry import (
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_REVIEW_PENDING,
    STATE_SKIPPED,
    init_db,
    register_job_candidate,
    update_analysis_success,
    update_retrieval_success,
)


class TestDashboardServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = Path(cls.temp_dir) / "test_dashboard.sqlite"
        cls.cover_dir = Path(cls.temp_dir) / "cover_letters"
        cls.cover_dir.mkdir(parents=True, exist_ok=True)
        cls.conn = init_db(cls.db_path)

        # Populate test jobs
        for i in (1, 2, 3):
            jid = f"9800000{i}"
            prio = "High" if i == 1 else ("Medium" if i == 2 else "Low")
            act = "Apply" if i == 1 else ("Strategic Stretch" if i == 2 else "Skip")
            register_job_candidate(
                cls.conn,
                jid,
                f"https://sg.jobstreet.com/job/{jid}",
                {"email_subject": "S", "anchor_text": "A", "tracking_url": "t"},
            )
            update_retrieval_success(cls.conn, jid, f"Cleaned text {i}")
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
            update_analysis_success(cls.conn, jid, analysis_json, prio, act)

        cls.port = 8089
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = create_server(cls.port, db_path=cls.db_path)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.conn.close()
        time.sleep(0.1)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_get_jobs_endpoint(self):
        res = requests.get(f"{self.base_url}/api/jobs")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        jobs = data["jobs"]
        self.assertEqual(len(jobs), 3)
        self.assertEqual(jobs[0]["recommended_priority"], "High")

    def test_02_single_decide_endpoint(self):
        # Apply on 98000001
        payload = {"job_id": "98000001", "decision": "Apply"}
        res = requests.post(f"{self.base_url}/api/jobs/decide", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["new_status"], STATE_APPLY_PENDING)

        # Skip on 98000003
        payload = {"job_id": "98000003", "decision": "Skip"}
        res = requests.post(f"{self.base_url}/api/jobs/decide", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["new_status"], STATE_SKIPPED)

    def test_03_invalid_transition_rejected(self):
        # 98000003 is SKIPPED -> Transition to APPLY_PENDING is invalid
        payload = {"job_id": "98000003", "decision": "Apply"}
        res = requests.post(f"{self.base_url}/api/jobs/decide", json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertIn("Invalid state transition", data["error"])

    def test_04_bulk_decide_endpoint_success_and_rejection(self):
        # Reset 98000003 to REVIEW_PENDING in DB
        with self.conn:
            self.conn.execute("UPDATE jobs SET status = 'REVIEW_PENDING' WHERE job_id = '98000003'")

        # 98000002 and 98000003 are REVIEW_PENDING
        payload = {"job_ids": ["98000002", "98000003"], "decision": "Skip"}
        res = requests.post(f"{self.base_url}/api/jobs/bulk-decide", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 2)

        # 98000001 is APPLY_PENDING -> Bulk decide including it must fail!
        payload = {"job_ids": ["98000001"], "decision": "Skip"}
        res = requests.post(f"{self.base_url}/api/jobs/bulk-decide", json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertIn("ineligible", data["error"])

    def test_05_cover_letter_read_and_save_without_llm(self):
        # Setup cover letter file manually
        cover_file = self.cover_dir / "98000001_cover_letter.md"
        with open(cover_file, "w", encoding="utf-8") as f:
            f.write("# Cover Letter 98000001\nOriginal text.")

        with self.conn:
            self.conn.execute(
                "UPDATE jobs SET status = ?, cover_letter_path = ? WHERE job_id = ?",
                (STATE_COVER_LETTER_GENERATED, str(cover_file.resolve()), "98000001"),
            )

        # Test Read Endpoint
        res = requests.get(f"{self.base_url}/api/cover-letter/read?job_id=98000001")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("Original text", data["content"])

        # Test Save Edits Endpoint
        save_payload = {"job_id": "98000001", "content": "# Cover Letter 98000001\nEdited text by the reviewer."}
        res = requests.post(f"{self.base_url}/api/cover-letter/save", json=save_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])

        # Verify disk content updated
        with open(cover_file, "r", encoding="utf-8") as f:
            edited_disk_content = f.read()
        self.assertEqual(edited_disk_content, "# Cover Letter 98000001\nEdited text by the reviewer.")

        # Verify DB status remains COVER_LETTER_GENERATED
        cur = self.conn.cursor()
        cur.execute("SELECT status FROM jobs WHERE job_id = '98000001'")
        self.assertEqual(cur.fetchone()[0], STATE_COVER_LETTER_GENERATED)


if __name__ == "__main__":
    unittest.main()
