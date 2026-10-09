from gmail_client import (
    build_gmail_service,
    extract_message_content,
)

from url_extractor import (
    classify_url,
    extract_urls,
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
    print("Gmail URL extraction test")
    print("=========================")
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

        urls = extract_urls(
            extracted["readable_body"]
        )

        classified_urls = [
            (
                url,
                classify_url(url),
            )
            for url in urls
        ]

        job_urls = [
            (
                url,
                url_type,
            )
            for url, url_type
            in classified_urls
            if url_type != "other"
        ]

        print(
            f"{index}. "
            f"{extracted['subject']}"
        )

        print(
            f"   From: "
            f"{extracted['from']}"
        )

        print(
            f"   Message ID: "
            f"{extracted['message_id']}"
        )

        print(
            f"   Total URLs: "
            f"{len(urls)}"
        )

        print(
            f"   Candidate job URLs: "
            f"{len(job_urls)}"
        )

        for url, url_type in job_urls:
            print(
                f"   [{url_type}] "
                f"{url}"
            )

        print()
        print("=" * 70)
        print()


if __name__ == "__main__":
    main()