from career_evidence_catalog_builder import (
    load_saved_career_evidence_catalog,
)

from gmail_client import (
    build_gmail_service,
)

from job_analysis_reasoner import (
    MODEL_NAME,
    REASONING_EFFORT,
    analyse_job,
)

from job_page_retriever import (
    retrieve_jobstreet_page,
)

from run_live_jobstreet_benchmark import (
    collect_jobstreet_candidates,
    get_confirmed_jobstreet_url,
)


def main() -> None:
    print()
    print(
        "Live One-Call Job Test"
    )
    print(
        "======================"
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

    service = build_gmail_service()

    candidates = (
        collect_jobstreet_candidates(
            service
        )
    )

    if not candidates:
        raise RuntimeError(
            "No JobStreet job "
            "candidates found."
        )

    catalog = (
        load_saved_career_evidence_catalog()
    )

    if not catalog.evidence_items:
        raise AssertionError(
            "Career evidence catalog is empty."
        )

    selected_candidate = None
    job_id = None
    confirmed_url = None
    page_result = None

    for candidate in candidates:
        confirmed = (
            get_confirmed_jobstreet_url(
                candidate[
                    "tracking_url"
                ]
            )
        )

        if confirmed is None:
            continue

        candidate_job_id, candidate_url = (
            confirmed
        )

        retrieval = (
            retrieve_jobstreet_page(
                candidate_url
            )
        )

        if not retrieval[
            "success"
        ]:
            continue

        cleaned_text = retrieval.get(
            "cleaned_text",
            "",
        )

        if not cleaned_text.strip():
            continue

        selected_candidate = candidate
        job_id = candidate_job_id
        confirmed_url = candidate_url
        page_result = retrieval

        break

    if (
        selected_candidate is None
        or job_id is None
        or confirmed_url is None
        or page_result is None
    ):
        raise RuntimeError(
            "No usable JobStreet job "
            "could be retrieved."
        )

    cleaned_text = (
        page_result[
            "cleaned_text"
        ]
    )

    print(
        "LIVE JOB ACQUIRED"
    )
    print(
        "-----------------"
    )

    print(
        f"Email subject: "
        f"{selected_candidate['email_subject']}"
    )

    print(
        f"Job ID: {job_id}"
    )

    print(
        f"URL: {confirmed_url}"
    )

    print(
        f"Cleaned characters: "
        f"{len(cleaned_text)}"
    )

    print()

    source_reference = (
        f"JOBSTREET-{job_id}"
    )

    analysis = analyse_job(
        job_text=cleaned_text,
        source_reference=(
            source_reference
        ),
        job_url=confirmed_url,
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
        f"Work mode: "
        f"{analysis.job.work_mode}"
    )

    print(
        f"Employment type: "
        f"{analysis.job.employment_type}"
    )

    print(
        f"Salary: "
        f"{analysis.job.salary}"
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

    print()

    print(
        f"Tracker note: "
        f"{analysis.tracker_note}"
    )

    print()

    if (
        analysis.job.job_url
        != confirmed_url
    ):
        raise AssertionError(
            "Canonical JobStreet URL "
            "was not preserved."
        )

    if (
        analysis.job.source_reference
        != source_reference
    ):
        raise AssertionError(
            "Source reference was "
            "not preserved."
        )

    if not analysis.assessments:
        raise AssertionError(
            "No job requirements "
            "were analysed."
        )

    print(
        "Gmail acquisition: PASS"
    )

    print(
        "JobStreet retrieval: PASS"
    )

    print(
        "One-call grounded analysis: PASS"
    )

    print(
        "Canonical provenance: PASS"
    )

    print()

    print(
        "Real JobStreet One-Call "
        "Analysis: PASS"
    )


if __name__ == "__main__":
    main()