import sys
import unittest
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "04_Application"))

import daily_job_batch
import job_registry


class TestMissedDayCatchUpAndBoundedAnalysis(unittest.TestCase):

    def setUp(self):
        self.conn = job_registry.init_db(Path(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_default_max_analyses_per_run_is_25(self):
        self.assertEqual(daily_job_batch.MAX_ANALYSES_PER_RUN, 25)

    def test_no_prior_acquisition_marker_scans_today_only(self):
        today = "2026-10-03"
        start, end, scan_days, warning = daily_job_batch.compute_acquisition_date_range(
            today, None
        )
        self.assertEqual(start, "2026-10-03")
        self.assertEqual(end, "2026-10-03")
        self.assertEqual(scan_days, 1)
        self.assertIsNone(warning)

    def test_last_successful_yesterday_scans_today_only(self):
        today = "2026-10-03"
        last = "2026-10-02"
        start, end, scan_days, warning = daily_job_batch.compute_acquisition_date_range(
            today, last
        )
        self.assertEqual(start, "2026-10-03")
        self.assertEqual(end, "2026-10-03")
        self.assertEqual(scan_days, 1)
        self.assertIsNone(warning)

    def test_last_successful_3_days_ago_scans_3_days(self):
        today = "2026-10-03"
        last = "2026-09-30"
        start, end, scan_days, warning = daily_job_batch.compute_acquisition_date_range(
            today, last
        )
        self.assertEqual(start, "2026-10-01")
        self.assertEqual(end, "2026-10-03")
        self.assertEqual(scan_days, 3)
        self.assertIsNone(warning)

    def test_same_day_rerun_scans_today_safely(self):
        today = "2026-10-03"
        last = "2026-10-03"
        start, end, scan_days, warning = daily_job_batch.compute_acquisition_date_range(
            today, last
        )
        self.assertEqual(start, "2026-10-03")
        self.assertEqual(end, "2026-10-03")
        self.assertEqual(scan_days, 1)
        self.assertIsNone(warning)

    def test_30_day_gap_allowed(self):
        today = "2026-10-31"
        last = "2026-10-01"
        start, end, scan_days, warning = daily_job_batch.compute_acquisition_date_range(
            today, last
        )
        self.assertEqual(start, "2026-10-02")
        self.assertEqual(end, "2026-10-31")
        self.assertEqual(scan_days, 30)
        self.assertIsNone(warning)

    def test_greater_than_30_day_gap_invokes_operator_warning_with_recovery_command(self):
        today = "2026-11-15"
        last = "2026-09-30"  # 46 days gap
        start, end, scan_days, warning = daily_job_batch.compute_acquisition_date_range(
            today, last
        )
        self.assertEqual(end, "2026-11-15")
        self.assertEqual(scan_days, 30)
        self.assertIsNotNone(warning)
        self.assertIn("Automatic catch-up is limited to 30 days", warning)
        self.assertIn("--start-date", warning)
        self.assertIn("--end-date", warning)

    def test_18_eligible_jobs_all_processed(self):
        for idx in range(1, 19):
            job_id = f"1800{idx:02d}"
            job_registry.register_job_candidate(
                self.conn,
                job_id=job_id,
                confirmed_url=f"https://www.jobstreet.com.sg/job/{job_id}",
                candidate={"anchor_text": f"Role {idx}", "tracking_url": "http://test"},
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 18)
        eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(eligible), 18)

        for job in eligible:
            job_registry.update_analysis_success(
                self.conn,
                job_id=job["job_id"],
                analysis_result_json='{"mock": true}',
                recommended_priority="High",
                recommended_action="Pursue",
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 0)

    def test_25_eligible_jobs_all_processed(self):
        for idx in range(1, 26):
            job_id = f"2500{idx:02d}"
            job_registry.register_job_candidate(
                self.conn,
                job_id=job_id,
                confirmed_url=f"https://www.jobstreet.com.sg/job/{job_id}",
                candidate={"anchor_text": f"Role {idx}", "tracking_url": "http://test"},
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 25)
        eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(eligible), 25)

        for job in eligible:
            job_registry.update_analysis_success(
                self.conn,
                job_id=job["job_id"],
                analysis_result_json='{"mock": true}',
                recommended_priority="Medium",
                recommended_action="Pursue",
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 0)

    def test_26_eligible_jobs_capped_at_25_one_remains(self):
        for idx in range(1, 27):
            job_id = f"2600{idx:02d}"
            job_registry.register_job_candidate(
                self.conn,
                job_id=job_id,
                confirmed_url=f"https://www.jobstreet.com.sg/job/{job_id}",
                candidate={"anchor_text": f"Role {idx}", "tracking_url": "http://test"},
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 26)
        eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(eligible), 25)

        for job in eligible:
            job_registry.update_analysis_success(
                self.conn,
                job_id=job["job_id"],
                analysis_result_json='{"mock": true}',
                recommended_priority="Medium",
                recommended_action="Pursue",
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 1)

    def test_60_eligible_jobs_same_day_runs_continuation(self):
        for idx in range(1, 61):
            job_id = f"6000{idx:02d}"
            ts = f"2026-10-03T10:00:{idx:02d}Z"
            job_registry.register_job_candidate(
                self.conn,
                job_id=job_id,
                confirmed_url=f"https://www.jobstreet.com.sg/job/{job_id}",
                candidate={"anchor_text": f"Role {idx}", "tracking_url": "http://test"},
                timestamp_iso=ts,
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 60)

        # Run 1: 25 processed, 35 remain
        run1_eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(run1_eligible), 25)
        for job in run1_eligible:
            job_registry.update_analysis_success(
                self.conn, job["job_id"], '{"mock": true}', "High", "Pursue"
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 35)

        # Run 2: 25 processed, 10 remain
        run2_eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(run2_eligible), 25)
        for job in run2_eligible:
            job_registry.update_analysis_success(
                self.conn, job["job_id"], '{"mock": true}', "High", "Pursue"
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 10)

        # Run 3: 10 processed, 0 remain
        run3_eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(run3_eligible), 10)
        for job in run3_eligible:
            job_registry.update_analysis_success(
                self.conn, job["job_id"], '{"mock": true}', "High", "Pursue"
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 0)

    def test_zero_new_gmail_jobs_processes_existing_backlog(self):
        for idx in range(1, 6):
            job_id = f"7000{idx:02d}"
            job_registry.register_job_candidate(
                self.conn,
                job_id=job_id,
                confirmed_url=f"https://www.jobstreet.com.sg/job/{job_id}",
                candidate={"anchor_text": f"Role {idx}", "tracking_url": "http://test"},
            )
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 5)
        # Fetching eligible jobs works regardless of new Gmail arrivals
        eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(eligible), 5)

    def test_permanent_404_not_reselected(self):
        # 1. Permanent 404 failure
        job_registry.register_job_candidate(
            self.conn,
            job_id="40400001",
            confirmed_url="https://www.jobstreet.com.sg/job/40400001",
            candidate={"anchor_text": "404 Job", "tracking_url": "http://test"},
        )
        job_registry.update_retrieval_failure(
            self.conn,
            job_id="40400001",
            error_msg="HTTP 404: Permanent failure (page not found or listing expired)",
        )

        # 2. Transient retrieval failure
        job_registry.register_job_candidate(
            self.conn,
            job_id="50000001",
            confirmed_url="https://www.jobstreet.com.sg/job/50000001",
            candidate={"anchor_text": "500 Job", "tracking_url": "http://test"},
        )
        job_registry.update_retrieval_failure(
            self.conn,
            job_id="50000001",
            error_msg="HTTP 500: Temporary Server Error",
        )

        # 3. Discovered job
        job_registry.register_job_candidate(
            self.conn,
            job_id="10000001",
            confirmed_url="https://www.jobstreet.com.sg/job/10000001",
            candidate={"anchor_text": "Normal Job", "tracking_url": "http://test"},
        )

        # Eligible should be 2 (50000001 and 10000001), 40400001 excluded
        self.assertEqual(job_registry.count_eligible_jobs_for_analysis(self.conn), 2)
        eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        eligible_ids = [j["job_id"] for j in eligible]
        self.assertNotIn("40400001", eligible_ids)
        self.assertIn("50000001", eligible_ids)
        self.assertIn("10000001", eligible_ids)

    def test_human_decided_states_preserved(self):
        human_states = [
            job_registry.STATE_REVIEW_PENDING,
            job_registry.STATE_SKIPPED,
            job_registry.STATE_APPLY_PENDING,
            job_registry.STATE_COVER_LETTER_GENERATED,
            job_registry.STATE_APPLIED,
        ]
        for idx, state in enumerate(human_states, start=1):
            job_id = f"8000{idx:02d}"
            job_registry.register_job_candidate(
                self.conn,
                job_id=job_id,
                confirmed_url=f"https://www.jobstreet.com.sg/job/{job_id}",
                candidate={"anchor_text": f"Human Job {idx}", "tracking_url": "http://test"},
            )
            job_registry.update_job_status(self.conn, job_id=job_id, status=state)

            # Re-registering candidate must NOT reset state
            job_registry.register_job_candidate(
                self.conn,
                job_id=job_id,
                confirmed_url=f"https://www.jobstreet.com.sg/job/{job_id}",
                candidate={"anchor_text": f"Human Job {idx}", "tracking_url": "http://test"},
            )
            rec = job_registry.get_job(self.conn, job_id)
            self.assertEqual(rec["status"], state)

        # None of the human-decided jobs should be eligible for LLM re-analysis
        eligible = job_registry.get_eligible_jobs_for_analysis(self.conn, limit=25)
        self.assertEqual(len(eligible), 0)

    def test_custom_date_range_cli(self):
        test_db = Path("scratch/test_range.sqlite")
        if test_db.exists():
            test_db.unlink()
        try:
            with patch(
                "daily_job_batch.collect_candidates_for_range",
                return_value=([], 1, 1, "query"),
            ), patch(
                "daily_job_batch.build_gmail_service", return_value=MagicMock()
            ):
                res = daily_job_batch.run_stage_3a(
                    start_date_str="2026-08-01",
                    end_date_str="2026-08-10",
                    db_path=test_db,
                )
            self.assertEqual(res["start_date"], "2026-08-01")
            self.assertEqual(res["end_date"], "2026-08-10")
            self.assertEqual(res["scan_days"], 10)
        finally:
            if test_db.exists():
                test_db.unlink()

    def test_singapore_timezone_boundary_epochs(self):
        date_str = "2026-10-01"
        start_epoch, end_epoch = daily_job_batch.compute_sgt_epochs(date_str)

        expected_start = int(
            datetime(2026, 9, 30, 16, 0, 0, tzinfo=timezone.utc).timestamp()
        )
        expected_end = int(
            datetime(2026, 10, 1, 16, 0, 0, tzinfo=timezone.utc).timestamp()
        )

        self.assertEqual(start_epoch, expected_start)
        self.assertEqual(end_epoch, expected_end)
        self.assertEqual(end_epoch - start_epoch, 86400)

    def test_stage_3a_unique_counter_semantics(self):
        mock_candidates = [
            {
                "email_subject": "Alert 1",
                "email_from": "test@jobstreet.com",
                "email_date": "2026-10-03",
                "anchor_text": "Role 1",
                "tracking_url": "https://www.jobstreet.com.sg/job/11111111",
            },
            {
                "email_subject": "Alert 2",
                "email_from": "test@jobstreet.com",
                "email_date": "2026-10-03",
                "anchor_text": "Role 2",
                "tracking_url": "https://www.jobstreet.com.sg/job/22222222",
            },
            {
                "email_subject": "Alert 3",
                "email_from": "test@jobstreet.com",
                "email_date": "2026-10-03",
                "anchor_text": "Role 1 Duplicate",
                "tracking_url": "https://www.jobstreet.com.sg/job/11111111",
            },
        ]
        test_db = Path("scratch/test_counters.sqlite")
        if test_db.exists():
            test_db.unlink()
        try:
            with patch(
                "daily_job_batch.collect_candidates_for_range",
                return_value=(mock_candidates, 1, 1, "query"),
            ), patch(
                "daily_job_batch.get_confirmed_jobstreet_url",
                side_effect=lambda url: (url.split("/")[-1], url),
            ), patch(
                "daily_job_batch.build_gmail_service", return_value=MagicMock()
            ):
                res = daily_job_batch.run_stage_3a(
                    batch_date_str="2026-10-03", db_path=test_db
                )

            self.assertEqual(res["raw_candidates"], 3)
            self.assertEqual(res["intra_batch_duplicates"], 1)
            self.assertEqual(res["unique_jobs_count"], 2)
            self.assertEqual(res["new_unique_jobs_registered"], 2)
            self.assertEqual(res["previously_known_unique_jobs"], 0)

            # Second run with Candidate 1 (previously known) and Candidate 3 (new)
            mock_candidates_run2 = [
                mock_candidates[0],
                {
                    "email_subject": "Alert 4",
                    "email_from": "test@jobstreet.com",
                    "email_date": "2026-10-03",
                    "anchor_text": "Role 3",
                    "tracking_url": "https://www.jobstreet.com.sg/job/33333333",
                },
            ]
            with patch(
                "daily_job_batch.collect_candidates_for_range",
                return_value=(mock_candidates_run2, 1, 1, "query"),
            ), patch(
                "daily_job_batch.get_confirmed_jobstreet_url",
                side_effect=lambda url: (url.split("/")[-1], url),
            ), patch(
                "daily_job_batch.build_gmail_service", return_value=MagicMock()
            ):
                res2 = daily_job_batch.run_stage_3a(
                    batch_date_str="2026-10-03", db_path=test_db
                )

            self.assertEqual(res2["raw_candidates"], 2)
            self.assertEqual(res2["intra_batch_duplicates"], 0)
            self.assertEqual(res2["unique_jobs_count"], 2)
            self.assertEqual(res2["previously_known_unique_jobs"], 1)
            self.assertEqual(res2["new_unique_jobs_registered"], 1)
        finally:
            if test_db.exists():
                test_db.unlink()

    def test_stage_3b_timing_calculations(self):
        durations = [87.8, 153.8, 226.0]
        stats = daily_job_batch.compute_stage_3b_timing_stats(
            job_durations=durations,
            total_elapsed_seconds=467.6,
            remaining_backlog=70,
            max_analyses=25,
        )
        self.assertEqual(stats["jobs_processed"], 3)
        self.assertEqual(stats["elapsed_seconds"], 467.6)
        self.assertEqual(stats["average_seconds_per_job"], 155.9)
        self.assertEqual(stats["fastest_seconds"], 87.8)
        self.assertEqual(stats["slowest_seconds"], 226.0)
        self.assertEqual(stats["median_seconds"], 153.8)
        self.assertEqual(stats["remaining_backlog"], 70)
        self.assertEqual(stats["estimated_additional_runs"], 3)

    def test_zero_jobs_timing_stats(self):
        stats = daily_job_batch.compute_stage_3b_timing_stats(
            job_durations=[],
            total_elapsed_seconds=0.0,
            remaining_backlog=70,
            max_analyses=25,
        )
        self.assertEqual(stats["jobs_processed"], 0)
        self.assertEqual(stats["elapsed_seconds"], 0.0)
        self.assertIsNone(stats["average_seconds_per_job"])
        self.assertIsNone(stats["fastest_seconds"])
        self.assertIsNone(stats["slowest_seconds"])
        self.assertIsNone(stats["median_seconds"])
        self.assertEqual(stats["remaining_backlog"], 70)
        self.assertEqual(stats["estimated_additional_runs"], 3)

    def test_daily_report_json_timing_section(self):
        test_dir = Path("scratch/test_report_dir")
        test_dir.mkdir(parents=True, exist_ok=True)
        try:
            acq = {
                "start_date": "2026-10-03",
                "end_date": "2026-10-03",
                "scan_days": 1,
                "gmail_query": "query",
                "messages_fetched": 1,
                "raw_candidates": 2,
                "unresolved": [],
                "intra_batch_duplicates": 0,
                "unique_jobs": [{"job_id": "1"}],
                "previously_known_unique_jobs": 0,
                "new_unique_jobs_registered": 1,
            }
            accounting = {
                "eligible_backlog_before": 10,
                "max_analyses_limit": 25,
                "analysed_this_run": 1,
                "remaining_backlog": 9,
                "retrieval_failures": 0,
                "analysis_failures": 0,
            }
            timing_stats = daily_job_batch.compute_stage_3b_timing_stats(
                job_durations=[150.0],
                total_elapsed_seconds=150.0,
                remaining_backlog=9,
                max_analyses=25,
            )
            daily_job_batch._write_report(
                batch_date_str="2026-10-03",
                acquisition=acq,
                successful=[],
                retrieval_failures=[],
                analysis_failures=[],
                accounting=accounting,
                timing_stats=timing_stats,
                output_dir=test_dir,
            )
            json_file = test_dir / "daily_report_2026-10-03.json"
            self.assertTrue(json_file.exists())
            import json
            data = json.loads(json_file.read_text(encoding="utf-8"))
            self.assertIn("stage_3b_runtime", data)
            self.assertEqual(data["stage_3b_runtime"]["jobs_processed"], 1)
            self.assertEqual(data["stage_3b_runtime"]["average_seconds_per_job"], 150.0)
            self.assertEqual(data["stage_3b_runtime"]["remaining_backlog"], 9)
            self.assertEqual(data["stage_3b_runtime"]["estimated_additional_runs"], 1)
        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)


if __name__ == "__main__":
    unittest.main()
