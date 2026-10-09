from gmail_client import (
    build_gmail_service,
    extract_message_content,
)

from url_extractor import (
    classify_structured_link,
    deduplicate_job_links,
)


MESSAGE_LIMIT = 10


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

    print()
    print("Gmail job-link candidate test")
    print("=============================")
    print()

    for index, message in enumerate(
        messages,
        start=1,
    ):
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

            if link_type not in {
                "linkedin_job",
                "jobstreet_job_candidate",
            }:
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

        print(
            f"{index}. "
            f"{extracted['subject']}"
        )

        print(
            f"   From: "
            f"{extracted['from']}"
        )

        print(
            f"   Job-link candidates: "
            f"{len(job_links)}"
        )

        for job_number, link in enumerate(
            job_links,
            start=1,
        ):
            print(
                f"   {job_number}. "
                f"[{link['type']}]"
            )

            print(
                f"      TEXT="
                f"{link['text']!r}"
            )

            print(
                f"      URL="
                f"{link['href']}"
            )

        print()
        print("=" * 70)
        print()


if __name__ == "__main__":
    main()