from career_evidence_catalog_builder import (
    load_saved_career_evidence_catalog,
)

from job_analysis_reasoner import (
    MODEL_NAME,
    REASONING_EFFORT,
    analyse_job,
)


TEST_JOB_TEXT = """
Example Automation Pte. Ltd.

Backend Developer

Singapore

Full time

The successful candidate will design and
develop backend services and REST APIs.

Requirements:
- Experience developing backend applications.
- Experience with Python and Django.
- Experience working with relational databases.
- Experience using Git.
- Experience administering Kubernetes clusters.
- Diploma or Degree in Engineering, Computer
  Science, or related discipline.

Responsibilities:
- Develop and maintain backend services.
- Build and integrate REST APIs.
- Document technical workflows.
"""


def main() -> None:
    print()
    print(
        "One-Call Job Analysis Test"
    )
    print(
        "=========================="
    )
    print()

    print(
        f"Model: {MODEL_NAME}"
    )

    print(
        f"Reasoning effort: "
        f"{REASONING_EFFORT}"
    )

    print()

    catalog = (
        load_saved_career_evidence_catalog()
    )

    if not catalog.evidence_items:
        raise AssertionError(
            "Career evidence catalog is empty."
        )

    analysis = analyse_job(
        job_text=TEST_JOB_TEXT,
        source_reference=(
            "ONE-CALL-TEST-001"
        ),
        job_url=(
            "https://example.com/"
            "job/ONE-CALL-TEST-001"
        ),
        catalog=catalog,
    )

    print(
        "JOB"
    )
    print(
        "---"
    )

    print(
        f"Company: "
        f"{analysis.job.company}"
    )

    print(
        f"Role: "
        f"{analysis.job.role}"
    )

    print(
        f"Location: "
        f"{analysis.job.location}"
    )

    print(
        f"Employment type: "
        f"{analysis.job.employment_type}"
    )

    print()

    print(
        "ASSESSMENTS"
    )
    print(
        "-----------"
    )

    for item in (
        analysis.assessments
    ):
        print(
            f"[{item.requirement_type}] "
            f"{item.match_type}"
        )

        print(
            f"  {item.requirement}"
        )

        print(
            f"  Evidence: "
            f"{item.evidence_ids}"
        )

        print(
            f"  Why: "
            f"{item.rationale}"
        )

    print()

    print(
        "RECOMMENDATION"
    )
    print(
        "--------------"
    )

    print(
        f"Priority: "
        f"{analysis.priority}"
    )

    print(
        f"Action: "
        f"{analysis.action}"
    )

    print(
        f"Rationale: "
        f"{analysis.rationale}"
    )

    print(
        f"Tracker note: "
        f"{analysis.tracker_note}"
    )

    print()

    assessment_text = " ".join(
        item.requirement.lower()
        for item in (
            analysis.assessments
        )
    )

    if (
        "kubernetes"
        not in assessment_text
    ):
        raise AssertionError(
            "Kubernetes requirement "
            "was not analysed."
        )

    kubernetes_items = [
        item
        for item in (
            analysis.assessments
        )
        if (
            "kubernetes"
            in item.requirement.lower()
        )
    ]

    if not kubernetes_items:
        raise AssertionError(
            "Kubernetes assessment "
            "was not found."
        )

    if (
        kubernetes_items[0]
        .match_type
        != "GAP"
    ):
        raise AssertionError(
            "Kubernetes should remain "
            "a verified GAP."
        )

    if (
        not analysis.assessments
    ):
        raise AssertionError(
            "No requirements were "
            "analysed."
        )

    print(
        "Evidence catalog load: PASS"
    )

    print(
        "Structured output: PASS"
    )

    print(
        "Evidence-ID validation: PASS"
    )

    print(
        "Known Kubernetes gap: PASS"
    )

    print()

    print(
        "One-Call Job Analysis v1: PASS"
    )


if __name__ == "__main__":
    main()