import re

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

JOBSTREET_JOB_URL_PATTERN = re.compile(
    r"^https://sg\.jobstreet\.com/job/(\d+)"
)


def find_first_jobstreet_candidate(
    service,
) -> dict | None:
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

        if not job_links:
            continue

        first_link = job_links[0]

        return {
            "email_subject": extracted[
                "subject"
            ],
            "email_from": extracted[
                "from"
            ],
            "anchor_text": first_link[
                "text"
            ],
            "tracking_url": first_link[
                "href"
            ],
        }

    return None


def main() -> None:
    print()
    print("Live Gmail -> JobStreet -> Extraction test")
    print("==========================================")
    print()

    service = build_gmail_service()

    candidate = find_first_jobstreet_candidate(
        service
    )

    if candidate is None:
        print(
            "No JobStreet job candidate found."
        )
        return

    print(
        f"Email subject: "
        f"{candidate['email_subject']}"
    )

    print(
        f"From: "
        f"{candidate['email_from']}"
    )

    print(
        f"Email job text: "
        f"{candidate['anchor_text']}"
    )

    print()
    print("1. Resolving tracking URL...")
    print()

    resolution = resolve_job_link(
        candidate["tracking_url"]
    )

    final_url = resolution[
        "final_url"
    ]

    print(
        f"Redirect resolved: "
        f"{resolution['success']}"
    )

    print(
        f"Final URL: "
        f"{final_url}"
    )

    print(
        f"Final domain allowed: "
        f"{resolution['final_domain_allowed']}"
    )

    match = JOBSTREET_JOB_URL_PATTERN.match(
        final_url
    )

    if (
        not resolution[
            "final_domain_allowed"
        ]
        or match is None
    ):
        print()
        print(
            "Final URL is not a confirmed "
            "JobStreet job-detail URL."
        )
        return

    job_id = match.group(1)

    confirmed_url = (
        f"https://sg.jobstreet.com/job/"
        f"{job_id}"
    )

    print(
        f"Confirmed job ID: "
        f"{job_id}"
    )

    print()
    print("2. Retrieving job page...")
    print()

    page_result = retrieve_jobstreet_page(
        confirmed_url
    )

    print(
        f"Browser retrieval success: "
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
        return

    if not page_result[
        "cleaned_text"
    ]:
        print(
            "No cleaned job text available."
        )
        return

    print()
    print("3. Sending cleaned job text")
    print("   to frozen Job Extraction v1...")
    print()

    source_reference = (
        f"JOBSTREET-{job_id}"
    )

    extraction = extract_job_listing(
        job_text=page_result[
            "cleaned_text"
        ],
        source_reference=source_reference,
        source_type=(
            "jobstreet_job_listing"
        ),
    )

    # The page URL is known deterministically
    # from the acquisition pipeline.
    # Do not ask the LLM to infer it.
    extraction.fields.job_url.value = (
        confirmed_url
    )

    print("STRUCTURED EXTRACTION")
    print("---------------------")
    print()

    print(
        extraction.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()