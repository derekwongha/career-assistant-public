from gmail_client import (
    build_gmail_service,
    extract_message_content,
)


MESSAGE_LIMIT = 3
PREVIEW_LENGTH = 1500


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
    print("Gmail message-content test")
    print("==========================")
    print()

    if not messages:
        print("No messages found.")
        return

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

        body = extracted[
            "readable_body"
        ].strip()

        preview = body[
            :PREVIEW_LENGTH
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
            f"   Date: "
            f"{extracted['date']}"
        )

        print(
            f"   Message ID: "
            f"{extracted['message_id']}"
        )

        print()
        print("   BODY PREVIEW")
        print("   ------------")

        if preview:
            print(preview)
        else:
            print(
                "[No readable body extracted]"
            )

        print()
        print("=" * 70)
        print()


if __name__ == "__main__":
    main()