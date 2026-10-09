from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from job_page_cleaner import (
    clean_jobstreet_page_text,
)


PAGE_TIMEOUT_MS = 30000


def retrieve_jobstreet_page(
    url: str,
) -> dict:
    result = {
        "success": False,
        "requested_url": url,
        "final_url": "",
        "status_code": None,
        "page_title": "",
        "raw_text": "",
        "cleaned_text": "",
        "error": "",
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False,
            )

            page = browser.new_page(
                viewport={
                    "width": 1440,
                    "height": 1000,
                }
            )

            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT_MS,
                )

                result["final_url"] = page.url

                if response is not None:
                    result["status_code"] = (
                        response.status
                    )

                try:
                    page.wait_for_load_state(
                        "networkidle",
                        timeout=10000,
                    )
                except PlaywrightTimeoutError:
                    pass

                result["page_title"] = (
                    page.title()
                )

                body_text = page.locator(
                    "body"
                ).inner_text(
                    timeout=10000
                )

                raw_text = "\n".join(
                    line.strip()
                    for line
                    in body_text.splitlines()
                    if line.strip()
                )

                cleaned_text = (
                    clean_jobstreet_page_text(
                        raw_text
                    )
                )

                result["raw_text"] = (
                    raw_text
                )

                result["cleaned_text"] = (
                    cleaned_text
                )

                result["success"] = (
                    result["status_code"] == 200
                    and bool(cleaned_text)
                )

                if not result["success"]:
                    code = result["status_code"]
                    if code in (404, 410):
                        result["error"] = f"HTTP {code}: Permanent failure (page not found or listing expired)"
                    elif code is not None and code != 200:
                        result["error"] = f"HTTP {code}: Retrieval failed"
                    elif not cleaned_text:
                        result["error"] = "Empty cleaned text after page render"

            finally:
                browser.close()

    except Exception as exc:
        result["error"] = str(
            exc
        )

    return result