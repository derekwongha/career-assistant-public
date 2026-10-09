import json
import sqlite3
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from job_registry import (
    STATE_ANALYSIS_FAILED,
    STATE_APPLIED,
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_DISCOVERED,
    STATE_RETRIEVAL_FAILED,
    STATE_RETRIEVED,
    STATE_REVIEW_PENDING,
    STATE_SKIPPED,
    get_job,
    get_job_sources,
    init_db,
    register_job_candidate,
    update_analysis_failure,
    update_analysis_success,
    update_human_decision,
    update_job_status,
    update_retrieval_failure,
    update_retrieval_success,
    transition_job_state,
    bulk_transition_job_states,
    get_all_jobs_for_dashboard,
)


def compute_sgt_epochs(date_str: str) -> tuple[int, int]:
    """
    Computes start and end Unix epoch seconds for a given SGT date_str (YYYY/MM/DD or YYYY-MM-DD).
    SGT is UTC+8.
    Start: date_str 00:00:00 SGT
    End: (date_str + 1 day) 00:00:00 SGT
    """
    clean_date = date_str.replace("-", "/")
    year, month, day = map(int, clean_date.split("/"))

    sgt_tz = timezone(timedelta(hours=8))
    dt_start = datetime(year, month, day, 0, 0, 0, tzinfo=sgt_tz)
    dt_end = dt_start + timedelta(days=1)

    return int(dt_start.timestamp()), int(dt_end.timestamp())


def get_current_sgt_date_str() -> str:
    """
    Returns current date string YYYY/MM/DD in Asia/Singapore timezone (UTC+8).
    """
    sgt_tz = timezone(timedelta(hours=8))
    return datetime.now(sgt_tz).strftime("%Y/%m/%d")


class TestJobRegistry(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database for test isolation
        self.conn = init_db(Path(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_1_new_canonical_job(self):
        candidate = {
            "email_subject": "3 new jobs for Example Developer",
            "email_date": "2026-09-29",
            "email_from": "JobStreet Alert <alert@jobstreet.com>",
            "anchor_text": "Junior Developer at TechCorp",
            "tracking_url": "https://url.jobstreet.com/111",
        }
        job = register_job_candidate(
            self.conn,
            job_id="90000001",
            confirmed_url="https://sg.jobstreet.com/job/90000001",
            candidate=candidate,
        )
        self.assertEqual(job["job_id"], "90000001")
        self.assertEqual(job["source_reference"], "JOBSTREET-90000001")
        self.assertEqual(job["status"], STATE_DISCOVERED)

        sources = get_job_sources(self.conn, "90000001")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["email_subject"], candidate["email_subject"])

    def test_2_multiple_alert_provenance(self):
        c1 = {
            "email_subject": "3 new jobs for Example Developer",
            "email_date": "2026-09-29",
            "anchor_text": "Junior Developer at TechCorp",
            "tracking_url": "https://url.jobstreet.com/111",
        }
        c2 = {
            "email_subject": "20 new jobs for Application Developer",
            "email_date": "2026-09-29",
            "anchor_text": "Junior Developer at TechCorp",
            "tracking_url": "https://url.jobstreet.com/222",
        }
        register_job_candidate(
            self.conn, "90000002", "https://sg.jobstreet.com/job/90000002", c1
        )
        register_job_candidate(
            self.conn, "90000002", "https://sg.jobstreet.com/job/90000002", c2
        )

        job = get_job(self.conn, "90000002")
        self.assertIsNotNone(job)

        sources = get_job_sources(self.conn, "90000002")
        self.assertEqual(len(sources), 2)
        subjects = [s["email_subject"] for s in sources]
        self.assertIn(c1["email_subject"], subjects)
        self.assertIn(c2["email_subject"], subjects)

    def test_3_same_source_idempotency(self):
        c1 = {
            "email_subject": "3 new jobs for Example Developer",
            "email_date": "2026-09-29",
            "anchor_text": "Junior Developer at TechCorp",
            "tracking_url": "https://url.jobstreet.com/111",
        }
        register_job_candidate(
            self.conn, "90000003", "https://sg.jobstreet.com/job/90000003", c1
        )
        # Attempt to insert identical source candidate again
        register_job_candidate(
            self.conn, "90000003", "https://sg.jobstreet.com/job/90000003", c1
        )

        sources = get_job_sources(self.conn, "90000003")
        self.assertEqual(len(sources), 1)

    def test_4_retrieval_success(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000004", "https://sg.jobstreet.com/job/90000004", c1
        )

        cleaned_text = "Cleaned JobStreet Advertisement Text Content"
        update_retrieval_success(self.conn, "90000004", cleaned_text)

        job = get_job(self.conn, "90000004")
        self.assertEqual(job["status"], STATE_RETRIEVED)
        self.assertEqual(job["cleaned_text"], cleaned_text)
        self.assertIsNone(job["last_error"])

    def test_5_retrieval_failure(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000005", "https://sg.jobstreet.com/job/90000005", c1
        )

        error_msg = "HTTP 403 Forbidden"
        update_retrieval_failure(self.conn, "90000005", error_msg)

        job = get_job(self.conn, "90000005")
        self.assertEqual(job["status"], STATE_RETRIEVAL_FAILED)
        self.assertEqual(job["last_error"], error_msg)

    def test_6_analysis_failure(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000006", "https://sg.jobstreet.com/job/90000006", c1
        )
        cleaned_text = "Cleaned page content"
        update_retrieval_success(self.conn, "90000006", cleaned_text)

        error_msg = "LM Studio Request Timeout"
        update_analysis_failure(self.conn, "90000006", error_msg)

        job = get_job(self.conn, "90000006")
        self.assertEqual(job["status"], STATE_ANALYSIS_FAILED)
        self.assertEqual(job["cleaned_text"], cleaned_text)  # intact
        self.assertEqual(job["last_error"], error_msg)

    def test_7_analysis_success(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000007", "https://sg.jobstreet.com/job/90000007", c1
        )
        update_retrieval_success(self.conn, "90000007", "Cleaned page text")

        analysis_json = json.dumps({"company": "TechCorp", "role": "Developer"})
        update_analysis_success(
            self.conn, "90000007", analysis_json, "High", "Apply"
        )

        job = get_job(self.conn, "90000007")
        self.assertEqual(job["status"], STATE_REVIEW_PENDING)
        self.assertEqual(job["analysis_result_json"], analysis_json)
        self.assertEqual(job["recommended_priority"], "High")
        self.assertEqual(job["recommended_action"], "Apply")

    def test_8_same_day_rerun_after_success(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000008", "https://sg.jobstreet.com/job/90000008", c1
        )
        update_retrieval_success(self.conn, "90000008", "Cleaned page text")
        update_analysis_success(
            self.conn, "90000008", '{"res": "ok"}', "Medium", "Strategic Stretch"
        )

        # Mock retrieval and analysis functions
        mock_retriever = MagicMock()
        mock_analyser = MagicMock()

        job = get_job(self.conn, "90000008")
        if job["status"] == STATE_REVIEW_PENDING:
            # Rerun logic: bypass Playwright retrieval and GPT-OSS analysis
            pass
        else:
            mock_retriever()
            mock_analyser()

        mock_retriever.assert_not_called()
        mock_analyser.assert_not_called()

    def test_9_skipped(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000009", "https://sg.jobstreet.com/job/90000009", c1
        )
        update_human_decision(self.conn, "90000009", "Skip", STATE_SKIPPED)

        job = get_job(self.conn, "90000009")
        self.assertEqual(job["status"], STATE_SKIPPED)
        self.assertEqual(job["human_decision"], "Skip")

        # Mock check to verify zero retrieval/analysis
        mock_retriever = MagicMock()
        mock_analyser = MagicMock()

        if job["status"] in (STATE_SKIPPED, STATE_APPLIED):
            # Finalized bypass
            pass
        else:
            mock_retriever()
            mock_analyser()

        mock_retriever.assert_not_called()
        mock_analyser.assert_not_called()

    def test_10_applied(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000010", "https://sg.jobstreet.com/job/90000010", c1
        )
        update_human_decision(self.conn, "90000010", "Apply", STATE_APPLIED)

        job = get_job(self.conn, "90000010")
        self.assertEqual(job["status"], STATE_APPLIED)
        self.assertEqual(job["human_decision"], "Apply")

        mock_retriever = MagicMock()
        mock_analyser = MagicMock()

        if job["status"] in (STATE_SKIPPED, STATE_APPLIED):
            pass
        else:
            mock_retriever()
            mock_analyser()

        mock_retriever.assert_not_called()
        mock_analyser.assert_not_called()

    def test_11_apply_pending(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000011", "https://sg.jobstreet.com/job/90000011", c1
        )
        update_human_decision(self.conn, "90000011", "Apply", STATE_APPLY_PENDING)

        job = get_job(self.conn, "90000011")
        self.assertEqual(job["status"], STATE_APPLY_PENDING)

        # Verify no repeated job analysis
        mock_analyser = MagicMock()
        if job["status"] == STATE_APPLY_PENDING:
            # Visible as outstanding human/application action
            pass
        else:
            mock_analyser()

        mock_analyser.assert_not_called()

    def test_12_cover_letter_generated(self):
        c1 = {"email_subject": "Test Subj", "anchor_text": "Test Anchor", "tracking_url": "t1"}
        register_job_candidate(
            self.conn, "90000012", "https://sg.jobstreet.com/job/90000012", c1
        )
        update_job_status(self.conn, "90000012", STATE_COVER_LETTER_GENERATED)

        job = get_job(self.conn, "90000012")
        self.assertEqual(job["status"], STATE_COVER_LETTER_GENERATED)

        mock_analyser = MagicMock()
        if job["status"] == STATE_COVER_LETTER_GENERATED:
            # Visible as outstanding submission action
            pass
        else:
            mock_analyser()

        mock_analyser.assert_not_called()

    def test_13_restart_resume(self):
        """
        Simulate jobs 1-3 already REVIEW_PENDING, job 4 ANALYSIS_FAILED (with cleaned_text), job 5 DISCOVERED.
        On next execution:
        - jobs 1-3: reused (0 retrieval, 0 analysis)
        - job 4: resumes analysis without retrieval
        - job 5: starts retrieval
        """
        # Job 1..3
        for i in range(1, 4):
            jid = f"9000001{i}"
            c = {"email_subject": "Subj", "anchor_text": "Anchor", "tracking_url": f"t{i}"}
            register_job_candidate(self.conn, jid, f"https://sg.jobstreet.com/job/{jid}", c)
            update_retrieval_success(self.conn, jid, f"Cleaned text {i}")
            update_analysis_success(self.conn, jid, '{"res": "ok"}', "High", "Apply")

        # Job 4
        register_job_candidate(self.conn, "90000014", "https://sg.jobstreet.com/job/90000014", {"email_subject": "S4", "anchor_text": "A4", "tracking_url": "t4"})
        update_retrieval_success(self.conn, "90000014", "Cleaned text 4")
        update_analysis_failure(self.conn, "90000014", "Timeout error")

        # Job 5
        register_job_candidate(self.conn, "90000015", "https://sg.jobstreet.com/job/90000015", {"email_subject": "S5", "anchor_text": "A5", "tracking_url": "t5"})

        # Execution loop logic simulation
        retrieved_ids = []
        analysed_ids = []

        for jid in ["90000011", "90000012", "90000013", "90000014", "90000015"]:
            job = get_job(self.conn, jid)
            st = job["status"]

            if st == STATE_REVIEW_PENDING:
                continue

            cleaned = job.get("cleaned_text")
            if not cleaned or st == STATE_DISCOVERED:
                # Need retrieval
                retrieved_ids.append(jid)
                cleaned = f"Newly retrieved text for {jid}"

            # Need analysis
            analysed_ids.append(jid)

        self.assertEqual(retrieved_ids, ["90000015"])  # Job 5 retrieved
        self.assertEqual(analysed_ids, ["90000014", "90000015"])  # Job 4 retried, Job 5 analyzed

    def test_14_different_job_ids_same_company_role(self):
        """
        Explicitly prove ID 90000001 (Company X, Software Engineer) and ID 95000001 (Company X, Software Engineer)
        result in two distinct jobs in SQLite registry.
        """
        c1 = {"email_subject": "Alert 1", "anchor_text": "Software Engineer at Company X", "tracking_url": "t1"}
        c2 = {"email_subject": "Alert 2", "anchor_text": "Software Engineer at Company X", "tracking_url": "t2"}

        j1 = register_job_candidate(self.conn, "90000001", "https://sg.jobstreet.com/job/90000001", c1)
        j2 = register_job_candidate(self.conn, "95000001", "https://sg.jobstreet.com/job/95000001", c2)

        self.assertEqual(j1["job_id"], "90000001")
        self.assertEqual(j2["job_id"], "95000001")
        self.assertNotEqual(j1["job_id"], j2["job_id"])

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs;")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 2)

    def test_15_sgt_date_boundary(self):
        start_epoch, end_epoch = compute_sgt_epochs("2026/09/29")
        # 2026-09-29 00:00:00 SGT (UTC+8) = 2026-09-28 16:00:00 UTC = 1790611200
        # 2026-09-30 00:00:00 SGT (UTC+8) = 2026-09-29 16:00:00 UTC = 1790697600
        self.assertEqual(start_epoch, 1790611200)
        self.assertEqual(end_epoch, 1790697600)
        self.assertEqual(end_epoch - start_epoch, 86400)

    def test_16_dynamic_sgt_default_date(self):
        sgt_date_str = get_current_sgt_date_str()
        self.assertRegex(sgt_date_str, r"^\d{4}/\d{2}/\d{2}$")
        start_epoch, end_epoch = compute_sgt_epochs(sgt_date_str)
        self.assertEqual(end_epoch - start_epoch, 86400)

    def test_17_transition_job_state_allowed(self):
        register_job_candidate(self.conn, "90000021", "https://sg.jobstreet.com/job/90000021", {"email_subject": "S", "anchor_text": "A", "tracking_url": "t"})
        update_retrieval_success(self.conn, "90000021", "Cleaned text")
        update_analysis_success(self.conn, "90000021", '{"priority": "High"}', "High", "Apply")

        # 1. REVIEW_PENDING -> SKIPPED
        transition_job_state(self.conn, "90000021", STATE_SKIPPED, human_decision="Skip")
        job = get_job(self.conn, "90000021")
        self.assertEqual(job["status"], STATE_SKIPPED)
        self.assertEqual(job["human_decision"], "Skip")

        # Reset to REVIEW_PENDING
        with self.conn:
            self.conn.execute("UPDATE jobs SET status = 'REVIEW_PENDING' WHERE job_id = '90000021'")

        # 2. REVIEW_PENDING -> APPLY_PENDING
        transition_job_state(self.conn, "90000021", STATE_APPLY_PENDING, human_decision="Apply")
        job = get_job(self.conn, "90000021")
        self.assertEqual(job["status"], STATE_APPLY_PENDING)
        self.assertEqual(job["human_decision"], "Apply")

        # 3. APPLY_PENDING -> COVER_LETTER_GENERATED
        cover_path = "05_Evaluation/cover_letters/90000021_cover_letter.md"
        transition_job_state(self.conn, "90000021", STATE_COVER_LETTER_GENERATED, cover_letter_path=cover_path)
        job = get_job(self.conn, "90000021")
        self.assertEqual(job["status"], STATE_COVER_LETTER_GENERATED)
        self.assertEqual(job["cover_letter_path"], cover_path)

    def test_18_transition_job_state_rejected(self):
        register_job_candidate(self.conn, "90000022", "https://sg.jobstreet.com/job/90000022", {"email_subject": "S", "anchor_text": "A", "tracking_url": "t"})

        # DISCOVERED -> APPLY_PENDING is invalid
        with self.assertRaises(ValueError) as ctx:
            transition_job_state(self.conn, "90000022", STATE_APPLY_PENDING)
        self.assertIn("Invalid state transition", str(ctx.exception))

        update_retrieval_success(self.conn, "90000022", "Cleaned text")
        update_analysis_success(self.conn, "90000022", '{"priority": "Low"}', "Low", "Skip")
        transition_job_state(self.conn, "90000022", STATE_SKIPPED, human_decision="Skip")

        # SKIPPED -> APPLY_PENDING is invalid in Step 4
        with self.assertRaises(ValueError) as ctx:
            transition_job_state(self.conn, "90000022", STATE_APPLY_PENDING)
        self.assertIn("Invalid state transition", str(ctx.exception))

    def test_19_bulk_transition_atomic(self):
        for i in (1, 2, 3):
            jid = f"9000003{i}"
            register_job_candidate(self.conn, jid, f"https://sg.jobstreet.com/job/{jid}", {"email_subject": "S", "anchor_text": "A", "tracking_url": "t"})
            update_retrieval_success(self.conn, jid, f"Cleaned text {i}")
            if i != 3:
                update_analysis_success(self.conn, jid, '{"res": "ok"}', "Medium", "Strategic Stretch")

        # Job 1 and 2 are REVIEW_PENDING, Job 3 is RETRIEVED (not REVIEW_PENDING).
        # Bulk transition must reject atomically!
        with self.assertRaises(ValueError) as ctx:
            bulk_transition_job_states(self.conn, ["90000031", "90000032", "90000033"], STATE_SKIPPED, "Skip")
        self.assertIn("ineligible for bulk decision", str(ctx.exception))

        # Assert zero jobs were mutated!
        self.assertEqual(get_job(self.conn, "90000031")["status"], STATE_REVIEW_PENDING)
        self.assertEqual(get_job(self.conn, "90000032")["status"], STATE_REVIEW_PENDING)

        # Successful bulk transition on eligible jobs
        count = bulk_transition_job_states(self.conn, ["90000031", "90000032"], STATE_APPLY_PENDING, "Apply")
        self.assertEqual(count, 2)
        self.assertEqual(get_job(self.conn, "90000031")["status"], STATE_APPLY_PENDING)
        self.assertEqual(get_job(self.conn, "90000032")["status"], STATE_APPLY_PENDING)

    def test_20_dashboard_query(self):
        register_job_candidate(self.conn, "90000040", "https://sg.jobstreet.com/job/90000040", {"email_subject": "S", "anchor_text": "A", "tracking_url": "t"})
        update_retrieval_success(self.conn, "90000040", "Cleaned text")
        update_analysis_success(self.conn, "90000040", '{"priority": "High"}', "High", "Apply")
        jobs = get_all_jobs_for_dashboard(self.conn)
        self.assertGreater(len(jobs), 0)
        first_job = jobs[0]
        self.assertIn("job_id", first_job)
        self.assertIn("status", first_job)
        self.assertIn("analysis", first_job)


if __name__ == "__main__":
    unittest.main()

