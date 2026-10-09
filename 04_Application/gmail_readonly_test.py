from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "04_Application"

CREDENTIALS_FILE = APP_DIR / "credentials.json"
TOKEN_FILE = APP_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


from gmail_client import get_credentials


def get_header(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").casefold() == name.casefold():
            return header.get("value", "")

    return ""


def main() -> None:
    creds = get_credentials()

    service = build(
        "gmail",
        "v1",
        credentials=creds,
    )

    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            maxResults=10,
        )
        .execute()
    )

    messages = response.get(
        "messages",
        [],
    )

    print()
    print("Recent Gmail messages")
    print("=====================")
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
                format="metadata",
                metadataHeaders=[
                    "From",
                    "Subject",
                    "Date",
                ],
            )
            .execute()
        )

        headers = (
            message_data
            .get("payload", {})
            .get("headers", [])
        )

        sender = get_header(
            headers,
            "From",
        )

        subject = get_header(
            headers,
            "Subject",
        )

        date = get_header(
            headers,
            "Date",
        )

        print(f"{index}. {subject}")
        print(f"   From: {sender}")
        print(f"   Date: {date}")
        print(f"   Message ID: {message['id']}")
        print()


if __name__ == "__main__":
    main()