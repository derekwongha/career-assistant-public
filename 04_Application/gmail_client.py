import base64
import sys
from pathlib import Path

from bs4 import BeautifulSoup
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


from google.auth.exceptions import RefreshError


def get_credentials() -> Credentials:
    creds = None

    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                TOKEN_FILE,
                SCOPES,
            )
        except Exception as exc:
            print(f"[WARNING] Could not parse cached token from {TOKEN_FILE}: {exc}")
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            print(
                f"[WARNING] Google OAuth token refresh failed ({exc}). "
                "Token may be revoked or expired. Requesting fresh authorization...",
                flush=True,
            )
            creds = None
        except Exception as exc:
            print(
                f"[WARNING] Unexpected error refreshing Google OAuth token ({exc}). "
                "Requesting fresh authorization...",
                flush=True,
            )
            creds = None

    if not creds or not creds.valid:
        print(
            "\n======================================================================\n"
            "[INFO] Google authorization required or expired.\n"
            "Launching browser for OAuth authentication...\n"
            "======================================================================\n",
            flush=True,
        )
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES,
        )

        prompt_msg = (
            "\n======================================================================\n"
            "ACTION REQUIRED: GOOGLE OAUTH AUTHORIZATION\n"
            "======================================================================\n"
            "If your web browser does not open automatically, copy and paste this URL\n"
            "into your browser to authorize access:\n\n"
            "  {url}\n\n"
            "======================================================================\n"
        )

        original_stdout = sys.stdout

        class FlushingStdout:
            def write(self, s):
                original_stdout.write(s)
                original_stdout.flush()

            def flush(self):
                original_stdout.flush()

            def __getattr__(self, name):
                return getattr(original_stdout, name)

        sys.stdout = FlushingStdout()
        try:
            creds = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message=prompt_msg,
            )
        finally:
            sys.stdout = original_stdout

    TOKEN_FILE.write_text(
        creds.to_json(),
        encoding="utf-8",
    )

    return creds


def build_gmail_service():
    creds = get_credentials()

    return build(
        "gmail",
        "v1",
        credentials=creds,
    )


def get_header(
    headers: list[dict],
    name: str,
) -> str:
    for header in headers:
        if (
            header.get("name", "").casefold()
            == name.casefold()
        ):
            return header.get("value", "")

    return ""


def _decode_body_data(data: str) -> str:
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(
            data.encode("utf-8")
        )
    except Exception:
        return ""

    return decoded.decode(
        "utf-8",
        errors="replace",
    )


def _collect_message_parts(
    part: dict,
    plain_parts: list[str],
    html_parts: list[str],
) -> None:
    mime_type = part.get(
        "mimeType",
        "",
    )

    body = part.get(
        "body",
        {},
    )

    data = body.get(
        "data",
        "",
    )

    if mime_type == "text/plain" and data:
        plain_parts.append(
            _decode_body_data(data)
        )

    elif mime_type == "text/html" and data:
        html_parts.append(
            _decode_body_data(data)
        )

    for child_part in part.get(
        "parts",
        [],
    ):
        _collect_message_parts(
            child_part,
            plain_parts,
            html_parts,
        )


def extract_html_links(
    html_text: str,
) -> list[dict]:
    if not html_text:
        return []

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    links = []
    seen = set()

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = anchor.get(
            "href",
            "",
        ).strip()

        text = anchor.get_text(
            " ",
            strip=True,
        )

        if not href:
            continue

        key = (
            text.casefold(),
            href,
        )

        if key in seen:
            continue

        seen.add(key)

        links.append(
            {
                "text": text,
                "href": href,
            }
        )

    return links


def extract_message_content(
    message_data: dict,
) -> dict:
    payload = message_data.get(
        "payload",
        {},
    )

    headers = payload.get(
        "headers",
        [],
    )

    plain_parts = []
    html_parts = []

    _collect_message_parts(
        payload,
        plain_parts,
        html_parts,
    )

    plain_text = "\n".join(
        part.strip()
        for part in plain_parts
        if part.strip()
    )

    html_text = "\n".join(
        part.strip()
        for part in html_parts
        if part.strip()
    )

    if plain_text:
        readable_body = plain_text

    elif html_text:
        soup = BeautifulSoup(
            html_text,
            "html.parser",
        )

        readable_body = soup.get_text(
            "\n",
            strip=True,
        )

    else:
        readable_body = ""

    html_links = extract_html_links(
        html_text
    )

    return {
        "message_id": message_data.get(
            "id",
            "",
        ),
        "thread_id": message_data.get(
            "threadId",
            "",
        ),
        "from": get_header(
            headers,
            "From",
        ),
        "to": get_header(
            headers,
            "To",
        ),
        "subject": get_header(
            headers,
            "Subject",
        ),
        "date": get_header(
            headers,
            "Date",
        ),
        "plain_text": plain_text,
        "html": html_text,
        "readable_body": readable_body,
        "html_links": html_links,
    }