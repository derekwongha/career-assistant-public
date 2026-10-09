import re
from urllib.parse import urlparse


URL_PATTERN = re.compile(
    r'https?://[^\s<>"\]\)]+'
)

LINKEDIN_JOB_ID_PATTERN = re.compile(
    r"/jobs/view/(\d+)/?"
)


JOBSTREET_NON_JOB_TEXT = {
    "",
    "explore now",
    "view all matching jobs",
    "edit this alert",
    "unsubscribe from this alert",
    "privacy",
    "contact us",
    "sg.jobstreet.com",
}


def _normalize_text(text: str) -> str:
    return " ".join(
        (text or "")
        .casefold()
        .strip()
        .split()
    )


def extract_urls(text: str) -> list[str]:
    urls = URL_PATTERN.findall(
        text or ""
    )

    cleaned_urls = []
    seen = set()

    for url in urls:
        cleaned = url.rstrip(
            ".,;:'"
        )

        if cleaned not in seen:
            cleaned_urls.append(cleaned)
            seen.add(cleaned)

    return cleaned_urls


def get_domain(url: str) -> str:
    try:
        return (
            urlparse(url)
            .netloc
            .casefold()
        )
    except ValueError:
        return ""


def classify_url(url: str) -> str:
    lowered = url.casefold()
    domain = get_domain(url)

    if (
        "linkedin.com" in domain
        and "/jobs/view/" in lowered
    ):
        return "linkedin_job"

    if (
        "jobstreet.com" in domain
        or "url.jobstreet.com" in domain
    ):
        return "jobstreet_link"

    return "other"


def classify_structured_link(
    text: str,
    url: str,
) -> str:
    base_type = classify_url(
        url
    )

    if base_type == "linkedin_job":
        return "linkedin_job"

    if base_type != "jobstreet_link":
        return "other"

    normalized_text = _normalize_text(
        text
    )

    if normalized_text in JOBSTREET_NON_JOB_TEXT:
        return "jobstreet_non_job"

    if not normalized_text:
        return "jobstreet_non_job"

    return "jobstreet_job_candidate"


def extract_linkedin_job_id(
    url: str,
) -> str:
    match = LINKEDIN_JOB_ID_PATTERN.search(
        url
    )

    if not match:
        return ""

    return match.group(1)


def deduplicate_job_links(
    links: list[dict],
) -> list[dict]:
    deduplicated = []
    seen = set()

    for link in links:
        link_type = link.get(
            "type",
            ""
        )

        url = link.get(
            "href",
            ""
        )

        text = link.get(
            "text",
            ""
        )

        if link_type == "linkedin_job":
            job_id = extract_linkedin_job_id(
                url
            )

            if job_id:
                key = (
                    "linkedin",
                    job_id,
                )
            else:
                key = (
                    "linkedin",
                    url,
                )

        elif link_type == "jobstreet_job_candidate":
            key = (
                "jobstreet",
                url,
            )

        else:
            key = (
                link_type,
                text,
                url,
            )

        if key in seen:
            continue

        seen.add(key)
        deduplicated.append(
            link
        )

    return deduplicated