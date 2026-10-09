import json
import re
from pathlib import Path

from gmail_client import (
    build_gmail_service,
    extract_message_content,
)

from job_extractor import (
    extract_job_listing,
)

from job_link_resolver import (
    resolve_job_link,
)

from job_page_retriever import (
    retrieve_jobstreet_page,
)

from url_extractor import (
    classify_structured_link,
    deduplicate_job_links,
)


MESSAGE_LIMIT = 10
BENCHMARK_LIMIT = 3

JOBSTREET_JOB_URL_PATTERN = re.compile(
    r"^https://sg\.jobstreet\.com/job/(\d+)"
)

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

OUTPUT_DIR = (
    PROJECT_ROOT
    / "05_Evaluation"
    / "Live_JobStreet_Extraction_Benchmark"
)


def collect_jobstreet_candidates(
    service,
) -> list[dict]:
    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            maxResults=MESSAGE_LIMIT,
        )
        .execute()
    )

    messages = response.get(
        "messages",
        [],
    )

    candidates = []

    for message in messages:
        message_data = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message["id"],
                format="full",
            )
            .execute()
        )

        extracted = extract_message_content(
            message_data
        )

        job_links = []

        for link in extracted["html_links"]:
            link_type = classify_structured_link(
                text=link["text"],
                url=link["href"],
            )

            if (
                link_type
                != "jobstreet_job_candidate"
            ):
                continue

            job_links.append(
                {
                    "text": link["text"],
                    "href": link["href"],
                    "type": link_type,
                }
            )

        job_links = deduplicate_job_links(
            job_links
        )

        for link in job_links:
            candidates.append(
                {
                    "email_subject": extracted[
                        "subject"
                    ],
                    "email_from": extracted[
                        "from"
                    ],
                    "anchor_text": link[
                        "text"
                    ],
                    "tracking_url": link[
                        "href"
                    ],
                }
            )

    return candidates


def get_confirmed_jobstreet_url(
    tracking_url: str,
) -> tuple[str, str] | None:
    resolution = resolve_job_link(
        tracking_url
    )

    final_url = resolution.get(
        "final_url",
        "",
    )

    if not resolution.get(
        "final_domain_allowed",
        False,
    ):
        return None

    match = JOBSTREET_JOB_URL_PATTERN.match(
        final_url
    )

    if match is None:
        return None

    job_id = match.group(1)

    confirmed_url = (
        f"https://sg.jobstreet.com/job/"
        f"{job_id}"
    )

    return (
        job_id,
        confirmed_url,
    )


def save_case(
    job_id: str,
    source_text: str,
    extraction,
    metadata: dict,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_file = (
        OUTPUT_DIR
        / f"JOBSTREET-{job_id}_source.txt"
    )

    extraction_file = (
        OUTPUT_DIR
        / f"JOBSTREET-{job_id}_extraction.json"
    )

    metadata_file = (
        OUTPUT_DIR
        / f"JOBSTREET-{job_id}_acquisition.json"
    )

    source_file.write_text(
        source_text,
        encoding="utf-8",
    )

    extraction_file.write_text(
        extraction.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    metadata_file.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    print()
    print("Live JobStreet 3-job benchmark")
    print("==============================")
    print()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    service = build_gmail_service()

    candidates = collect_jobstreet_candidates(
        service
    )

    print(
        f"Email-level candidates found: "
        f"{len(candidates)}"
    )

    print()

    completed_cases = []
    seen_job_ids = set()

    for candidate in candidates:
        if (
            len(completed_cases)
            >= BENCHMARK_LIMIT
        ):
            break

        confirmed = (
            get_confirmed_jobstreet_url(
                candidate[
                    "tracking_url"
                ]
            )
        )

        if confirmed is None:
            continue

        job_id, confirmed_url = confirmed

        if job_id in seen_job_ids:
            continue

        seen_job_ids.add(
            job_id
        )

        case_number = (
            len(completed_cases) + 1
        )

        print(
            f"Case {case_number}: "
            f"JOBSTREET-{job_id}"
        )

        print(
            f"Email text: "
            f"{candidate['anchor_text']}"
        )

        print(
            f"Confirmed URL: "
            f"{confirmed_url}"
        )

        print(
            "Retrieving page..."
        )

        page_result = retrieve_jobstreet_page(
            confirmed_url
        )

        print(
            f"Browser success: "
            f"{page_result['success']}"
        )

        print(
            f"HTTP status: "
            f"{page_result['status_code']}"
        )

        print(
            f"Cleaned characters: "
            f"{len(page_result['cleaned_text'])}"
        )

        if not page_result["success"]:
            print(
                f"Retrieval error: "
                f"{page_result['error']}"
            )
            print()
            continue

        cleaned_text = page_result[
            "cleaned_text"
        ]

        print(
            "Running frozen extractor..."
        )

        try:
            extraction = extract_job_listing(
                job_text=cleaned_text,
                source_reference=(
                    f"JOBSTREET-{job_id}"
                ),
                source_type=(
                    "jobstreet_job_listing"
                ),
            )
        except Exception as exc:
            print(
                f"Extraction failed: "
                f"{exc}"
            )
            print()
            continue

        # The acquisition pipeline knows
        # the canonical job URL with certainty.
        extraction.fields.job_url.value = (
            confirmed_url
        )

        acquisition_metadata = {
            "job_id": job_id,
            "confirmed_url": confirmed_url,
            "email_subject": candidate[
                "email_subject"
            ],
            "email_from": candidate[
                "email_from"
            ],
            "email_anchor_text": candidate[
                "anchor_text"
            ],
            "page_title": page_result[
                "page_title"
            ],
            "http_status": page_result[
                "status_code"
            ],
            "raw_character_count": len(
                page_result[
                    "raw_text"
                ]
            ),
            "cleaned_character_count": len(
                cleaned_text
            ),
        }

        save_case(
            job_id=job_id,
            source_text=cleaned_text,
            extraction=extraction,
            metadata=acquisition_metadata,
        )

        completed_cases.append(
            {
                "job_id": job_id,
                "role": extraction.fields.role.value,
                "company": extraction.fields.company.value,
                "other_requirements": (
                    extraction.fields
                    .other_requirements
                    .value
                ),
                "education_requirements": (
                    extraction.fields
                    .education_requirements
                    .value
                ),
            }
        )

        print(
            f"Role: "
            f"{extraction.fields.role.value}"
        )

        print(
            f"Company: "
            f"{extraction.fields.company.value}"
        )

        print(
            f"Other requirements: "
            f"{len(extraction.fields.other_requirements.value)}"
        )

        print(
            f"Education requirements: "
            f"{len(extraction.fields.education_requirements.value)}"
        )

        print(
            "Saved benchmark files."
        )

        print()
        print("-" * 70)
        print()

    summary_file = (
        OUTPUT_DIR
        / "benchmark_summary.json"
    )

    summary_file.write_text(
        json.dumps(
            completed_cases,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("BENCHMARK COMPLETE")
    print("==================")
    print()

    print(
        f"Completed cases: "
        f"{len(completed_cases)}/"
        f"{BENCHMARK_LIMIT}"
    )

    print(
        f"Output folder:"
    )

    print(
        OUTPUT_DIR
    )

    print()

    for index, case in enumerate(
        completed_cases,
        start=1,
    ):
        print(
            f"{index}. "
            f"JOBSTREET-{case['job_id']}"
        )

        print(
            f"   Role: "
            f"{case['role']}"
        )

        print(
            f"   Company: "
            f"{case['company']}"
        )

        print(
            f"   Other requirements: "
            f"{len(case['other_requirements'])}"
        )

        print(
            f"   Education requirements: "
            f"{len(case['education_requirements'])}"
        )

        print()


if __name__ == "__main__":
    main()