from urllib.parse import urlparse

import requests


REQUEST_TIMEOUT = 20

ALLOWED_START_DOMAINS = {
    "url.jobstreet.com",
}

ALLOWED_FINAL_DOMAIN_SUFFIXES = (
    "jobstreet.com",
)


def _get_hostname(url: str) -> str:
    try:
        return (
            urlparse(url)
            .hostname
            or ""
        ).casefold()
    except ValueError:
        return ""


def is_allowed_start_url(
    url: str,
) -> bool:
    hostname = _get_hostname(
        url
    )

    return hostname in ALLOWED_START_DOMAINS


def is_allowed_final_url(
    url: str,
) -> bool:
    hostname = _get_hostname(
        url
    )

    if not hostname:
        return False

    for suffix in ALLOWED_FINAL_DOMAIN_SUFFIXES:
        if (
            hostname == suffix
            or hostname.endswith(
                "." + suffix
            )
        ):
            return True

    return False


def resolve_job_link(
    url: str,
) -> dict:
    if not is_allowed_start_url(url):
        return {
            "success": False,
            "original_url": url,
            "final_url": "",
            "status_code": None,
            "redirect_chain": [],
            "final_domain_allowed": False,
            "error": "Start URL is not an approved JobStreet tracking domain.",
        }

    try:
        response = requests.get(
            url,
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            stream=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
        )

        redirect_chain = []

        for item in response.history:
            redirect_chain.append(
                {
                    "status_code": item.status_code,
                    "url": item.url,
                    "location": item.headers.get(
                        "Location",
                        "",
                    ),
                }
            )

        final_url = response.url

        return {
            "success": True,
            "original_url": url,
            "final_url": final_url,
            "status_code": response.status_code,
            "redirect_chain": redirect_chain,
            "final_domain_allowed": is_allowed_final_url(
                final_url
            ),
            "content_type": response.headers.get(
                "Content-Type",
                "",
            ),
            "error": "",
        }

    except requests.RequestException as exc:
        return {
            "success": False,
            "original_url": url,
            "final_url": "",
            "status_code": None,
            "redirect_chain": [],
            "final_domain_allowed": False,
            "error": str(exc),
        }