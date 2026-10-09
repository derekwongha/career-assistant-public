import re


OPERATIONAL_CONSTRAINT_PATTERNS = (
    re.compile(
        r"\b\d+\s*days?\s+(?:work|working)\s+week\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:working\s+)?hours?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)"
        r"\s*(?:to|-|–)\s*"
        r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bprobation\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brotating\s+shifts?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnight\s+shifts?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bweekends?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bpublic\s+holidays?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bon[- ]call\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bafter[- ]hours\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwork\s+authori[sz]ation\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bright\s+to\s+work\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\beligible\s+to\s+work\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsecurity\s+clearance\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwilling\s+to\s+travel\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\btravel\s+(?:is\s+)?required\b",
        re.IGNORECASE,
    ),
)


def _extract_operational_constraints(
    job_text: str,
) -> list[str]:
    constraints = []
    seen = set()

    for raw_line in job_text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        matched = any(
            pattern.search(line)
            for pattern
            in OPERATIONAL_CONSTRAINT_PATTERNS
        )

        if not matched:
            continue

        key = " ".join(
            line.casefold().split()
        )

        if key in seen:
            continue

        seen.add(key)
        constraints.append(
            line
        )

    return constraints


def extract_explicit_metadata(
    job_text: str,
) -> dict:
    metadata = {
        "location": None,
        "employment_type": None,
        "salary": None,
        "posting_date": None,
        "other_requirements": [],
    }

    for raw_line in job_text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("Location:"):
            metadata["location"] = (
                line.removeprefix(
                    "Location:"
                ).strip()
            )

        elif line.startswith(
            "Employment type:"
        ):
            metadata["employment_type"] = (
                line.removeprefix(
                    "Employment type:"
                ).strip()
            )

        elif line.startswith("Salary:"):
            metadata["salary"] = (
                line.removeprefix(
                    "Salary:"
                ).strip()
            )

        elif line.startswith("Posted:"):
            metadata["posting_date"] = (
                line.removeprefix(
                    "Posted:"
                ).strip()
            )

    metadata["other_requirements"] = (
        _extract_operational_constraints(
            job_text
        )
    )

    return metadata