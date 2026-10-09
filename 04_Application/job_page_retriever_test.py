from job_page_retriever import (
    retrieve_jobstreet_page,
)


import os
import sys

# Live test: set JOBSTREET_TEST_URL to a public JobStreet job page you are allowed to fetch.
TEST_URL = os.environ.get("JOBSTREET_TEST_URL", "")
if not TEST_URL:
    sys.exit("Set JOBSTREET_TEST_URL to run this live retrieval test.")


def main() -> None:
    result = retrieve_jobstreet_page(
        TEST_URL
    )

    print()
    print("Reusable JobStreet retriever test")
    print("=================================")
    print()

    print(
        f"Success: "
        f"{result['success']}"
    )

    print(
        f"HTTP status: "
        f"{result['status_code']}"
    )

    print(
        f"Final URL: "
        f"{result['final_url']}"
    )

    print(
        f"Page title: "
        f"{result['page_title']}"
    )

    print(
        f"Raw characters: "
        f"{len(result['raw_text'])}"
    )

    print(
        f"Cleaned characters: "
        f"{len(result['cleaned_text'])}"
    )

    if result["error"]:
        print(
            f"Error: "
            f"{result['error']}"
        )

    print()
    print("CLEANED TEXT PREVIEW")
    print("--------------------")
    print(
        result["cleaned_text"][
            :3000
        ]
    )


if __name__ == "__main__":
    main()