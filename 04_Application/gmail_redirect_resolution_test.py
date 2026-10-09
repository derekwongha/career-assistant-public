from gmail_client import (
    build_gmail_service,
    extract_message_content,
)

from job_link_resolver import (
    resolve_job_link,
)

from url_extractor import (
    classify_structured_link,
    deduplicate_job_links,
)


MESSAGE_LIMIT = 10
RESOLVE_LIMIT = 3


def main() -> None:
    service = build_gmail_service()

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
                    "text": link[
                        "text"
                    ],
                    "href": link[
                        "href"
                    ],
                }
            )

            if (
                len(candidates)
                >= RESOLVE_LIMIT
            ):
                break

        if (
            len(candidates)
            >= RESOLVE_LIMIT
        ):
            break

    print()
    print("Controlled JobStreet redirect test")
    print("==================================")
    print()

    if not candidates:
        print(
            "No JobStreet candidates found."
        )
        return

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        print(
            f"{index}. "
            f"{candidate['text']}"
        )

        print(
            f"   Email: "
            f"{candidate['email_subject']}"
        )

        result = resolve_job_link(
            candidate["href"]
        )

        print(
            f"   Success: "
            f"{result['success']}"
        )

        print(
            f"   HTTP status: "
            f"{result['status_code']}"
        )

        print(
            f"   Redirects: "
            f"{len(result['redirect_chain'])}"
        )

        print(
            f"   Final URL: "
            f"{result['final_url']}"
        )

        print(
            f"   Final domain allowed: "
            f"{result['final_domain_allowed']}"
        )

        if result.get(
            "content_type"
        ):
            print(
                f"   Content-Type: "
                f"{result['content_type']}"
            )

        if result["error"]:
            print(
                f"   Error: "
                f"{result['error']}"
            )

        print()

        for step_number, step in enumerate(
            result["redirect_chain"],
            start=1,
        ):
            print(
                f"      Redirect "
                f"{step_number}:"
            )

            print(
                f"         "
                f"{step['status_code']} "
                f"{step['url']}"
            )

            print(
                f"         Location: "
                f"{step['location']}"
            )

        print()
        print("=" * 70)
        print()


if __name__ == "__main__":
    main()