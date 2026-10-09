from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from job_page_cleaner import (
    clean_jobstreet_page_text,
)


import os
import sys

# Live test: set JOBSTREET_TEST_URL to a public JobStreet job page you are allowed to fetch.
TEST_URL = os.environ.get("JOBSTREET_TEST_URL", "")
if not TEST_URL:
    sys.exit("Set JOBSTREET_TEST_URL to run this live retrieval test.")

PAGE_TIMEOUT_MS = 30000
PREVIEW_LENGTH = 5000


def main() -> None:
    print()
    print("JobStreet browser retrieval test")
    print("===============================")
    print()

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
                TEST_URL,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT_MS,
            )

            print(
                f"Requested URL: {TEST_URL}"
            )

            print(
                f"Final URL: {page.url}"
            )

            if response is not None:
                print(
                    f"HTTP status: "
                    f"{response.status}"
                )
            else:
                print(
                    "HTTP status: unavailable"
                )

            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=10000,
                )
            except PlaywrightTimeoutError:
                print(
                    "Network idle timeout: "
                    "continuing with loaded content."
                )

            title = page.title()

            print(
                f"Page title: {title}"
            )

            body_text = page.locator(
                "body"
            ).inner_text(
                timeout=10000
            )

            cleaned_text = clean_jobstreet_page_text(
                body_text
            )

            print()
            print(
                f"Extracted characters: "
                f"{len(cleaned_text)}"
            )

            print()
            print("PAGE TEXT PREVIEW")
            print("-----------------")

            if cleaned_text:
                print(
                    cleaned_text[
                        :PREVIEW_LENGTH
                    ]
                )
            else:
                print(
                    "[No readable page text extracted]"
                )

        except PlaywrightTimeoutError as exc:
            print(
                "Page load timed out."
            )
            print(
                f"Error: {exc}"
            )

        except Exception as exc:
            print(
                "Browser retrieval failed."
            )
            print(
                f"Error: {exc}"
            )

        finally:
            print()
            print(
                "Closing browser."
            )

            browser.close()


if __name__ == "__main__":
    main()