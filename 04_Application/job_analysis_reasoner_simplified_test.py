"""
Step 3E-S2 & S2.1 — Deterministic unit tests for simplified job analysis contract
and real evidence selection regression testing.
ALL tests use mocks/stubs for network/LLM calls. Zero LM Studio calls. Zero Playwright. Zero DB writes.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch
import requests

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import job_analysis_reasoner as reasoner
from job_analysis_reasoner import (
    MAX_ADDITIONAL_EVIDENCE,
    MAX_TIMEOUT_RETRIES,
    _perform_one_inference_attempt,
    _select_evidence,
    analyse_job,
)
from job_analysis_schema import (
    JobAnalysisResult,
    JobFacts,
)
from career_evidence_schema import CareerEvidenceItem
from career_evidence_catalog_builder import load_saved_career_evidence_catalog


def _make_evidence_item(evidence_id="RESUME-001"):
    return CareerEvidenceItem(
        evidence_id=evidence_id,
        category="technical_skill",
        capability=f"Capability {evidence_id}",
        evidence_statement="Stub evidence.",
        state="PROVEN",
        context="Technical Skills",
        limitations=[],
    )


STUB_EVIDENCE_ITEMS = [_make_evidence_item("RESUME-001")]


def _make_simplified_analysis(key_matches=None, key_gaps=None):
    return JobAnalysisResult(
        job=JobFacts(
            source_reference="TEST-001",
            job_url="https://example.com/job/1",
            company="Acme Pte Ltd",
            role="Software Engineer",
            location="Singapore",
            work_mode="on-site",
            employment_type="Full time",
            salary="Not stated",
            posting_date="Not stated",
        ),
        priority="High",
        action="Apply",
        key_matches=key_matches or ["5+ years Python development experience"],
        key_gaps=key_gaps if key_gaps is not None else ["No evidence of AWS deployment"],
        summary="Strong overall alignment for backend engineering role.",
        tracker_note="Python backend role - high priority.",
    )


def _ok_response(analysis):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {
        "choices": [
            {
                "message": {"content": analysis.model_dump_json()},
                "finish_reason": "stop",
            }
        ]
    }
    return resp


def _analyse_job_with_stub_evidence(**kwargs):
    with patch.object(reasoner, "_select_evidence", return_value=STUB_EVIDENCE_ITEMS):
        return analyse_job(**kwargs)


class TestSimplifiedSchema(unittest.TestCase):

    def test_1_valid_simplified_result_parses(self):
        analysis = _make_simplified_analysis()
        self.assertEqual(analysis.priority, "High")
        self.assertEqual(analysis.action, "Apply")
        self.assertEqual(len(analysis.key_matches), 1)

    def test_2_priority_enum_enforced(self):
        d = _make_simplified_analysis().model_dump()
        d["priority"] = "INVALID"
        with self.assertRaises(ValueError):
            JobAnalysisResult.model_validate(d)

    def test_3_action_enum_enforced(self):
        d = _make_simplified_analysis().model_dump()
        d["action"] = "INVALID"
        with self.assertRaises(ValueError):
            JobAnalysisResult.model_validate(d)

    def test_4_key_matches_accepts_concise_strings(self):
        matches = ["Python expertise", "FastAPI microservices", "SQL database design"]
        analysis = _make_simplified_analysis(key_matches=matches)
        self.assertEqual(analysis.key_matches, matches)

    def test_5_key_gaps_can_be_empty(self):
        analysis = _make_simplified_analysis(key_gaps=[])
        self.assertEqual(analysis.key_gaps, [])

    def test_6_no_evidence_ids_required_in_output(self):
        analysis = _make_simplified_analysis()
        dump = analysis.model_dump()
        self.assertNotIn("evidence_ids", dump)
        self.assertNotIn("assessments", dump)

    def test_legacy_json_deserialization_compatibility(self):
        legacy_data = {
            "job": {
                "source_reference": "JOBSTREET-12345",
                "job_url": "https://sg.jobstreet.com/job/12345",
                "company": "Test Co",
                "role": "Developer",
                "location": "Singapore",
                "work_mode": "hybrid",
                "employment_type": "Full time",
                "salary": "Not stated",
                "posting_date": "1d ago",
            },
            "assessments": [
                {
                    "requirement": "Python 3 years",
                    "requirement_type": "required",
                    "match_type": "DIRECT",
                    "evidence_ids": ["RESUME-001"],
                    "rationale": "Direct match in resume.",
                },
                {
                    "requirement": "Kubernetes",
                    "requirement_type": "preferred",
                    "match_type": "GAP",
                    "evidence_ids": [],
                    "rationale": "No K8s experience found.",
                },
            ],
            "priority": "Medium",
            "action": "Strategic Stretch",
            "rationale": "Overall good potential.",
            "tracker_note": "Track in sheet.",
        }
        res = JobAnalysisResult.model_validate(legacy_data)
        self.assertEqual(res.priority, "Medium")
        self.assertEqual(res.action, "Strategic Stretch")
        self.assertEqual(res.summary, "Overall good potential.")
        self.assertIn("Python 3 years: Direct match in resume.", res.key_matches)
        self.assertIn("Kubernetes: No K8s experience found.", res.key_gaps)


class TestSimplifiedReasoner(unittest.TestCase):

    def test_7_no_evidence_validation_retry_and_8_normal_first_response(self):
        good = _make_simplified_analysis()
        with patch.object(reasoner, "_perform_one_inference_attempt", return_value=good) as mock:
            result = _analyse_job_with_stub_evidence(
                job_text="Python engineer required in Singapore.",
                source_reference="TEST-001",
                job_url="https://example.com/job/1",
                catalog=MagicMock(),
            )
        self.assertEqual(result, good)
        self.assertEqual(mock.call_count, 1, "Normal first response requires exactly 1 attempt")

    def test_9_timeout_retry_succeeds_in_2_http_calls(self):
        good = _make_simplified_analysis()
        with patch("job_analysis_reasoner.requests.post") as mock_post:
            mock_post.side_effect = [requests.exceptions.ReadTimeout(), _ok_response(good)]
            result = _perform_one_inference_attempt(
                payload={"model": "test", "messages": []},
                source_reference="TEST-001",
                job_url="https://example.com/job/1",
                evidence_items=STUB_EVIDENCE_ITEMS,
            )
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result.job.role, "Software Engineer")

    def test_10_two_timeouts_raises_read_timeout_after_2_http_calls(self):
        with patch("job_analysis_reasoner.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ReadTimeout()
            with self.assertRaises(requests.exceptions.ReadTimeout):
                _perform_one_inference_attempt(
                    payload={"model": "test", "messages": []},
                    source_reference="TEST-001",
                    job_url="https://example.com/job/1",
                    evidence_items=STUB_EVIDENCE_ITEMS,
                )
        self.assertEqual(mock_post.call_count, 2)

    def test_11_non_timeout_inference_error_not_retried(self):
        with patch("job_analysis_reasoner.requests.post") as mock_post:
            bad_resp = MagicMock()
            bad_resp.ok = False
            bad_resp.status_code = 500
            bad_resp.json.return_value = {"error": "Internal Server Error"}
            mock_post.return_value = bad_resp
            with self.assertRaises(ValueError):
                _perform_one_inference_attempt(
                    payload={"model": "test", "messages": []},
                    source_reference="TEST-001",
                    job_url="https://example.com/job/1",
                    evidence_items=STUB_EVIDENCE_ITEMS,
                )
        self.assertEqual(mock_post.call_count, 1, "500 Server Error must NOT be retried")


class TestRealEvidenceSelection(unittest.TestCase):
    """Step 3E-S2.1: Real _select_evidence() regression tests."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_saved_career_evidence_catalog()
        cls.resume_ids = [
            item.evidence_id
            for item in cls.catalog.evidence_items
            if item.evidence_id.startswith("RESUME-")
        ]

    def test_1_resume_evidence_included_in_full(self):
        job_text = "Senior Python Backend Engineer with PostgreSQL and Docker experience in Singapore."
        selected = _select_evidence(job_text=job_text, catalog=self.catalog)
        selected_ids = [item.evidence_id for item in selected]

        for rid in self.resume_ids:
            self.assertIn(rid, selected_ids, f"Resume item {rid} must be included in _select_evidence")

    def test_2_additional_evidence_selection_deterministic(self):
        job_text = "Senior Python Backend Engineer with PostgreSQL and Docker experience in Singapore."
        selected_1 = _select_evidence(job_text=job_text, catalog=self.catalog)
        selected_2 = _select_evidence(job_text=job_text, catalog=self.catalog)

        ids_1 = [item.evidence_id for item in selected_1]
        ids_2 = [item.evidence_id for item in selected_2]

        self.assertEqual(ids_1, ids_2, "Repeated evidence selection calls must be 100% deterministic")

    def test_3_max_additional_evidence_limit_enforced(self):
        job_text = "Senior Python Backend Engineer with PostgreSQL and Docker experience in Singapore."
        selected = _select_evidence(job_text=job_text, catalog=self.catalog)
        selected_ids = [item.evidence_id for item in selected]

        non_resume_ids = [sid for sid in selected_ids if not sid.startswith("RESUME-")]
        self.assertLessEqual(
            len(non_resume_ids),
            MAX_ADDITIONAL_EVIDENCE,
            f"Non-resume items must not exceed MAX_ADDITIONAL_EVIDENCE ({MAX_ADDITIONAL_EVIDENCE})"
        )

    def test_4_different_jobs_produce_different_relevant_evidence(self):
        job_python = "Python Django PostgreSQL REST API developer"
        job_data = "Data Analyst PowerBI SQL Tableau reporting dashboard"

        sel_python = _select_evidence(job_text=job_python, catalog=self.catalog)
        sel_data = _select_evidence(job_text=job_data, catalog=self.catalog)

        non_resume_python = [i.evidence_id for i in sel_python if not i.evidence_id.startswith("RESUME-")]
        non_resume_data = [i.evidence_id for i in sel_data if not i.evidence_id.startswith("RESUME-")]

        # Both should select relevant additional items based on JD content
        self.assertNotEqual(non_resume_python, non_resume_data)


if __name__ == "__main__":
    unittest.main()
