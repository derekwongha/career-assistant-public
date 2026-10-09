JOBSTREET_LEADING_NOISE = {
    "Skip to content",
    "Jobstreet",
    "Job search",
    "People search",
    "Career advice",
    "Companies",
    "Sign in",
    "Employer site",
}

JOBSTREET_INLINE_NOISE = {
    "View all jobs",
    "Quick apply",
    "Save",
}

JOBSTREET_END_MARKERS = (
    "Unlock job insights",
    "Employer questions",
    "Report this job advert",
    "Report this job ad",
    "Featured jobs",
    "What can I earn as",
    "Job seekers",
)


def _clean_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in (text or "").splitlines()
        if line.strip()
    ]


def clean_jobstreet_page_text(
    text: str,
) -> str:
    lines = _clean_lines(text)

    if not lines:
        return ""

    cleaned_lines = []
    content_started = False

    for line in lines:
        if line.startswith(
            "By continuing to use our platform"
        ):
            continue

        if (
            not content_started
            and line in JOBSTREET_LEADING_NOISE
        ):
            continue

        if line in JOBSTREET_INLINE_NOISE:
            continue

        if any(
            line.startswith(marker)
            for marker in JOBSTREET_END_MARKERS
        ):
            break

        content_started = True

        cleaned_lines.append(
            line
        )

    return "\n".join(
        cleaned_lines
    )