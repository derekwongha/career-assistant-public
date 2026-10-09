import json
import os

import requests

from job_listing_schema import JobListingExtraction
from job_metadata import extract_explicit_metadata
from job_normalize import normalize_job_listing


LM_STUDIO_URL = (
    "http://127.0.0.1:1234"
    "/v1/chat/completions"
)


MODEL_NAME = os.getenv(
    "JOB_EXTRACTION_MODEL",
    "openai/gpt-oss-20b",
)


REQUEST_TIMEOUT_SECONDS = int(
    os.getenv(
        "JOB_EXTRACTION_TIMEOUT_SECONDS",
        "300",
    )
)


MAX_TIMEOUT_RETRIES = 1


PROMPT_INSTRUCTIONS = """
You are extracting structured facts from a job advertisement.
Reason briefly and directly. Do not deliberate repeatedly over the same classification.
Return the JSON as soon as the source facts have been classified.

Return ONLY valid JSON matching the exact schema provided below.

Do not:
- assess candidate fit;
- compare the job with a resume or portfolio;
- recommend Apply or Skip;
- infer missing information;
- invent skills, qualifications, experience, locations, salary, or duties.

GENERAL RULES

1. Extract only information explicitly supported by the advertisement.

2. Scalar fields:
- If stated, return the stated value.
- If absent, return exactly "Not stated".
- Never return an empty string.

3. Array fields:
- Include only explicitly supported items.
- Use [] if none are stated.
- Every array item MUST be a plain string.
- Do NOT return objects, dictionaries, or nested JSON
  inside any array field.

4. Preserve technology, product, company, qualification, and location names accurately.

5. Do not duplicate the same requirement across multiple requirement categories unless the advertisement explicitly states separate requirements.

FIELD RULES

company:
- Hiring company name.

role:
- Official job title.

location:
- Geographic location only.

work_mode:
- Return exactly one of:
  "remote"
  "hybrid"
  "on-site"
  "flexible"
  "Not stated"
- Do not put geographic locations here.

employment_type:
- Full time, part time, contract, internship, etc.

salary:
- Compensation exactly as stated, or "Not stated".

posting_date:
- Posting date or relative posting age exactly as stated, or "Not stated".

job_url:
- Job URL if explicitly provided, otherwise "Not stated".

required_requirements:
- Include all candidate requirements that are mandatory or clearly expected.
- This may include years or types of experience, technical skills, tools and technologies,
  knowledge, communication, analytical, interpersonal or working capabilities.
- Do not separate skills from experience.

preferred_requirements:
- Include candidate requirements explicitly described as preferred, desirable,
  advantageous, nice to have, or good to have.

education_requirements:
- Include degrees, diplomas, certifications, licences and other formal qualifications.
- Preserve whether each is required or preferred.
- Return each qualification as a single string.
- Example:
  "Required: Degree in Computer Science or related field"
- Do NOT return:
  {"degree": "...", "type": "required"}

other_requirements:
- Include non-skill/non-experience constraints such as work authorization,
  working hours or shifts, travel, security clearance, physical requirements,
  or location constraints.

responsibilities:
- Include the main duties and work activities.
- Do not convert responsibilities into candidate requirements unless separately stated.

extraction_warnings:
- Use only when wording is genuinely ambiguous or conflicting.
- Do not guess.
"""


def _build_prompt(
    job_text: str,
    source_reference: str,
) -> str:
    schema = f"""
Use this exact structure:

{{
  "source": {{
    "type": "user_supplied_job_description",
    "reference": "{source_reference}"
  }},
  "fields": {{
    "company": {{"value": ""}},
    "role": {{"value": ""}},
    "location": {{"value": ""}},
    "work_mode": {{"value": ""}},
    "employment_type": {{"value": ""}},
    "salary": {{"value": ""}},
    "posting_date": {{"value": ""}},
    "job_url": {{"value": ""}},
    "required_requirements": {{"value": []}},
    "preferred_requirements": {{"value": []}},
    "education_requirements": {{"value": []}},
    "other_requirements": {{"value": []}},
    "responsibilities": {{"value": []}}
  }},
  "extraction_warnings": []
}}
"""

    return (
        PROMPT_INSTRUCTIONS
        + "\n"
        + schema
        + "\nJOB ADVERTISEMENT:\n\n"
        + job_text.strip()
    )


def _repair_list_item(
    item,
) -> str | None:
    if isinstance(
        item,
        str,
    ):
        cleaned = item.strip()

        return (
            cleaned
            if cleaned
            else None
        )

    if not isinstance(
        item,
        dict,
    ):
        return None

    requirement_type = (
        item.get("type")
    )

    content_keys = (
        "degree",
        "qualification",
        "requirement",
        "text",
        "value",
        "description",
    )

    content = None

    for key in content_keys:
        candidate = item.get(
            key
        )

        if (
            isinstance(
                candidate,
                str,
            )
            and candidate.strip()
        ):
            content = (
                candidate.strip()
            )

            break

    if content is None:
        return None

    if (
        isinstance(
            requirement_type,
            str,
        )
        and requirement_type.strip()
    ):
        normalized_type = (
            requirement_type
            .strip()
            .casefold()
        )

        if (
            normalized_type
            == "required"
        ):
            return (
                f"Required: {content}"
            )

        if (
            normalized_type
            == "preferred"
        ):
            return (
                f"Preferred: {content}"
            )

    return content


def _repair_structural_output(
    parsed_result: dict,
) -> dict:
    fields = parsed_result.get(
        "fields"
    )

    if not isinstance(
        fields,
        dict,
    ):
        return parsed_result

    misplaced_warnings = fields.get(
        "extraction_warnings"
    )

    if (
        misplaced_warnings is not None
        and "extraction_warnings"
        not in parsed_result
    ):
        parsed_result[
            "extraction_warnings"
        ] = misplaced_warnings

        del fields[
            "extraction_warnings"
        ]

    list_field_names = (
        "required_requirements",
        "preferred_requirements",
        "education_requirements",
        "other_requirements",
        "responsibilities",
    )

    for field_name in (
        list_field_names
    ):
        field_data = fields.get(
            field_name
        )

        if not isinstance(
            field_data,
            dict,
        ):
            continue

        values = field_data.get(
            "value"
        )

        if not isinstance(
            values,
            list,
        ):
            continue

        repaired_values = []

        for item in values:
            repaired_item = (
                _repair_list_item(
                    item
                )
            )

            if (
                repaired_item
                is not None
            ):
                repaired_values.append(
                    repaired_item
                )

            else:
                raise ValueError(
                    "Unsupported structured "
                    "list item returned by "
                    "job extraction model in "
                    f"{field_name}: "
                    f"{item!r}"
                )

        field_data[
            "value"
        ] = repaired_values

    return parsed_result


def _merge_unique_items(
    existing_items: list[str],
    new_items: list[str],
) -> list[str]:
    merged = []
    seen = set()

    for item in (
        existing_items
        + new_items
    ):
        cleaned = item.strip()

        if not cleaned:
            continue

        key = " ".join(
            cleaned.casefold().split()
        )

        if key in seen:
            continue

        seen.add(key)

        merged.append(
            cleaned
        )

    return merged


def _apply_metadata_override(
    extraction: JobListingExtraction,
    metadata: dict,
) -> JobListingExtraction:
    for field_name in (
        "location",
        "employment_type",
        "salary",
        "posting_date",
    ):
        metadata_value = metadata.get(
            field_name
        )

        if metadata_value is not None:
            getattr(
                extraction.fields,
                field_name,
            ).value = metadata_value

    deterministic_other_requirements = (
        metadata.get(
            "other_requirements",
            [],
        )
    )

    extraction.fields.other_requirements.value = (
        _merge_unique_items(
            extraction.fields
            .other_requirements
            .value,
            deterministic_other_requirements,
        )
    )

    return extraction


def _apply_source_provenance(
    extraction: JobListingExtraction,
    source_type: str,
    source_reference: str,
) -> JobListingExtraction:
    extraction.source.type = (
        source_type
    )

    extraction.source.reference = (
        source_reference
    )

    return extraction


def extract_job_listing(
    job_text: str,
    source_reference: str,
    source_type: str = (
        "user_supplied_job_description"
    ),
) -> JobListingExtraction:
    metadata = extract_explicit_metadata(
        job_text
    )

    prompt = _build_prompt(
        job_text=job_text,
        source_reference=source_reference,
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0,
    }

    for attempt in range(
        MAX_TIMEOUT_RETRIES + 1
    ):
        try:
            response = requests.post(
                LM_STUDIO_URL,
                json=payload,
                timeout=(
                    REQUEST_TIMEOUT_SECONDS
                ),
            )

            response.raise_for_status()

            break

        except requests.exceptions.ReadTimeout:
            if (
                attempt
                >= MAX_TIMEOUT_RETRIES
            ):
                raise

    api_response = response.json()

    try:
        model_content = (
            api_response[
                "choices"
            ][0][
                "message"
            ][
                "content"
            ]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise ValueError(
            "LM Studio response "
            "structure is invalid."
        ) from exc

    if not isinstance(
        model_content,
        str,
    ):
        raise ValueError(
            "LM Studio returned "
            "non-text content."
        )

    try:
        parsed_result = json.loads(
            model_content
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Job extraction model "
            "returned invalid JSON."
        ) from exc

    if not isinstance(
        parsed_result,
        dict,
    ):
        raise ValueError(
            "Job extraction model "
            "returned JSON that is "
            "not an object."
        )

    parsed_result = (
        _repair_structural_output(
            parsed_result
        )
    )

    validated_result = (
        JobListingExtraction.model_validate(
            parsed_result
        )
    )

    validated_result = (
        _apply_source_provenance(
            validated_result,
            source_type=source_type,
            source_reference=source_reference,
        )
    )

    validated_result = (
        _apply_metadata_override(
            validated_result,
            metadata,
        )
    )

    validated_result = (
        normalize_job_listing(
            validated_result
        )
    )

    return validated_result