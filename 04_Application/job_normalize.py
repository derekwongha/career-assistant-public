FORMAL_QUALIFICATION_TERMS = (
    "certification",
    "certificate",
    "degree",
    "diploma",
    "licence",
    "license",
)


OPERATIONAL_CONSTRAINT_TERMS = (
    "rotating shift",
    "rotating shifts",
    "night shift",
    "night shifts",
    "weekend",
    "weekends",
    "public holiday",
    "public holidays",
    "on-call",
    "on call",
    "after-hours",
    "after hours",
    "work authorisation",
    "work authorization",
    "eligible to work",
    "working hours",
)


EDUCATION_LEADING_PHRASES = (
    "candidates with ",
    "candidate with ",
    "applicants with ",
    "applicant with ",
)


CAPABILITY_LEADING_PHRASES = (
    "daily use of ",
    "regular use of ",
    "experience with ",
    "experience in ",
    "experienced in ",
    "proficient in ",
    "proficiency in ",
    "familiar with ",
    "familiarity with ",
    "knowledge of ",
    "good understanding of ",
    "strong understanding of ",
    "hands-on ",
    "hands on ",
    "ability to ",
    "able to ",
)


EDUCATION_EQUIVALENCY_MARKERS = (
    ", or equivalent ",
    " or equivalent ",
)


def _normalize_text(text: str) -> str:
    return " ".join(
        text.casefold()
        .strip()
        .rstrip(".")
        .split()
    )


def _is_formal_qualification(text: str) -> bool:
    normalized = _normalize_text(text)

    return any(
        term in normalized
        for term in FORMAL_QUALIFICATION_TERMS
    )


def _is_operational_constraint(text: str) -> bool:
    normalized = _normalize_text(text)

    return any(
        term in normalized
        for term in OPERATIONAL_CONSTRAINT_TERMS
    )


def _is_capability_requirement(text: str) -> bool:
    normalized = _normalize_text(text)

    return any(
        normalized.startswith(phrase)
        for phrase in CAPABILITY_LEADING_PHRASES
    )


def _strip_requirement_prefix(text: str) -> str:
    stripped = text.strip()

    lowered = stripped.casefold()

    if lowered.startswith("required:"):
        return stripped[
            len("required:"):
        ].strip()

    if lowered.startswith("preferred:"):
        return stripped[
            len("preferred:"):
        ].strip()

    return stripped


def _strip_education_leading_phrase(
    text: str,
) -> str:
    stripped = text.strip()
    lowered = stripped.casefold()

    for phrase in EDUCATION_LEADING_PHRASES:
        if lowered.startswith(phrase):
            return stripped[
                len(phrase):
            ].strip()

    return stripped


def _strip_education_equivalency_suffix(
    text: str,
) -> str:
    stripped = text.strip()
    lowered = stripped.casefold()

    marker_positions = []

    for marker in EDUCATION_EQUIVALENCY_MARKERS:
        position = lowered.find(marker)

        if position >= 0:
            marker_positions.append(
                position
            )

    if not marker_positions:
        return stripped

    earliest_position = min(
        marker_positions
    )

    return stripped[
        :earliest_position
    ].rstrip(" ,")


def _education_identity(
    text: str,
) -> str:
    base = _strip_requirement_prefix(
        text
    )

    base = _strip_education_leading_phrase(
        base
    )

    base = _strip_education_equivalency_suffix(
        base
    )

    return _normalize_text(
        base
    )


def _education_status(text: str) -> str | None:
    lowered = text.casefold().strip()

    if lowered.startswith("required:"):
        return "Required"

    if lowered.startswith("preferred:"):
        return "Preferred"

    return None


def _upsert_education_requirement(
    education: list[str],
    qualification: str,
    status: str,
) -> None:
    base_qualification = (
        _strip_requirement_prefix(
            qualification
        )
    )

    normalized_identity = (
        _education_identity(
            base_qualification
        )
    )

    normalized_value = (
        f"{status}: {base_qualification}"
    )

    for index, existing in enumerate(
        education
    ):
        if (
            _education_identity(
                existing
            )
            == normalized_identity
        ):
            existing_status = (
                _education_status(
                    existing
                )
            )

            if existing_status is None:
                education[index] = (
                    normalized_value
                )

            return

    education.append(
        normalized_value
    )


def _remove_items_present_in(
    source_items: list[str],
    authoritative_items: list[str],
) -> list[str]:
    authoritative_normalized = {
        _normalize_text(item)
        for item in authoritative_items
    }

    return [
        item
        for item in source_items
        if _normalize_text(item)
        not in authoritative_normalized
    ]


def _normalize_education_status(
    education: list[str],
    required_items: list[str],
    preferred_items: list[str],
) -> list[str]:
    required_lookup = {
        _education_identity(item)
        for item in required_items
        if _is_formal_qualification(item)
    }

    preferred_lookup = {
        _education_identity(item)
        for item in preferred_items
        if _is_formal_qualification(item)
    }

    normalized_education = []

    for item in education:
        existing_status = (
            _education_status(item)
        )

        if existing_status is not None:
            normalized_education.append(
                item
            )
            continue

        base_item = (
            _strip_requirement_prefix(
                item
            )
        )

        normalized_identity = (
            _education_identity(
                base_item
            )
        )

        if normalized_identity in required_lookup:
            normalized_education.append(
                f"Required: {base_item}"
            )

        elif (
            normalized_identity
            in preferred_lookup
        ):
            normalized_education.append(
                f"Preferred: {base_item}"
            )

        else:
            normalized_education.append(
                item
            )

    return normalized_education


def _deduplicate_education_requirements(
    education: list[str],
) -> list[str]:
    deduplicated = []
    identity_to_index = {}

    for item in education:
        identity = _education_identity(
            item
        )

        if identity not in identity_to_index:
            identity_to_index[
                identity
            ] = len(
                deduplicated
            )

            deduplicated.append(
                item
            )

            continue

        existing_index = (
            identity_to_index[
                identity
            ]
        )

        existing = deduplicated[
            existing_index
        ]

        existing_status = (
            _education_status(
                existing
            )
        )

        new_status = (
            _education_status(
                item
            )
        )

        if (
            existing_status is None
            and new_status is not None
        ):
            deduplicated[
                existing_index
            ] = item

        elif (
            existing_status is not None
            and new_status is None
        ):
            continue

        elif (
            existing_status
            == new_status
        ):
            if len(item) > len(existing):
                deduplicated[
                    existing_index
                ] = item

        else:
            # Required and Preferred are meaningfully
            # different statuses, so preserve both.
            deduplicated.append(
                item
            )

    return deduplicated


def normalize_formal_qualifications(
    extraction,
):
    fields = extraction.fields

    original_required = list(
        fields.required_requirements.value
    )

    original_preferred = list(
        fields.preferred_requirements.value
    )

    education = list(
        fields.education_requirements.value
    )

    required_remaining = []

    for item in original_required:
        if _is_formal_qualification(
            item
        ):
            _upsert_education_requirement(
                education,
                item,
                "Required",
            )
        else:
            required_remaining.append(
                item
            )

    preferred_remaining = []

    for item in original_preferred:
        if _is_formal_qualification(
            item
        ):
            _upsert_education_requirement(
                education,
                item,
                "Preferred",
            )
        else:
            preferred_remaining.append(
                item
            )

    education = (
        _normalize_education_status(
            education=education,
            required_items=original_required,
            preferred_items=original_preferred,
        )
    )

    education = (
        _deduplicate_education_requirements(
            education
        )
    )

    fields.required_requirements.value = (
        required_remaining
    )

    fields.preferred_requirements.value = (
        preferred_remaining
    )

    fields.education_requirements.value = (
        education
    )

    return extraction


def normalize_operational_constraints(
    extraction,
):
    fields = extraction.fields

    required = list(
        fields.required_requirements.value
    )

    other = list(
        fields.other_requirements.value
    )

    normalized_other = {
        _normalize_text(item)
        for item in other
    }

    required_remaining = []

    for item in required:
        if _is_operational_constraint(
            item
        ):
            normalized_item = (
                _normalize_text(
                    item
                )
            )

            if (
                normalized_item
                not in normalized_other
            ):
                other.append(
                    item
                )

                normalized_other.add(
                    normalized_item
                )

        else:
            required_remaining.append(
                item
            )

    fields.required_requirements.value = (
        required_remaining
    )

    fields.other_requirements.value = (
        other
    )

    return extraction


def normalize_misclassified_capabilities(
    extraction,
):
    fields = extraction.fields

    required = list(
        fields.required_requirements.value
    )

    other = list(
        fields.other_requirements.value
    )

    normalized_required = {
        _normalize_text(item)
        for item in required
    }

    other_remaining = []

    for item in other:
        if (
            _is_capability_requirement(item)
            and not _is_operational_constraint(item)
        ):
            normalized_item = (
                _normalize_text(
                    item
                )
            )

            if (
                normalized_item
                not in normalized_required
            ):
                required.append(
                    item
                )

                normalized_required.add(
                    normalized_item
                )

        else:
            other_remaining.append(
                item
            )

    fields.required_requirements.value = (
        required
    )

    fields.other_requirements.value = (
        other_remaining
    )

    return extraction


def normalize_category_duplicates(
    extraction,
):
    fields = extraction.fields

    required = list(
        fields.required_requirements.value
    )

    other = list(
        fields.other_requirements.value
    )

    responsibilities = list(
        fields.responsibilities.value
    )

    required = _remove_items_present_in(
        source_items=required,
        authoritative_items=other,
    )

    required = _remove_items_present_in(
        source_items=required,
        authoritative_items=responsibilities,
    )

    fields.required_requirements.value = (
        required
    )

    return extraction


def normalize_job_listing(
    extraction,
):
    extraction = (
        normalize_formal_qualifications(
            extraction
        )
    )

    extraction = (
        normalize_operational_constraints(
            extraction
        )
    )

    extraction = (
        normalize_misclassified_capabilities(
            extraction
        )
    )

    extraction = (
        normalize_category_duplicates(
            extraction
        )
    )

    return extraction