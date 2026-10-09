import json
import os

import requests

from career_evidence_schema import (
    CareerEvidenceCatalog,
)

from job_analysis_schema import (
    JobAnalysisResult,
)

from job_assessment_evidence_retriever import (
    retrieve_evidence_candidates,
)

from job_assessment_schema import (
    AssessmentTarget,
)


LM_STUDIO_URL = (
    "http://127.0.0.1:1234"
    "/v1/chat/completions"
)


MODEL_NAME = os.getenv(
    "JOB_ANALYSIS_MODEL",
    "openai/gpt-oss-20b",
)


REASONING_EFFORT = os.getenv(
    "JOB_ANALYSIS_REASONING_EFFORT",
    "medium",
)


REQUEST_TIMEOUT_SECONDS = int(
    os.getenv(
        "JOB_ANALYSIS_TIMEOUT_SECONDS",
        "600",
    )
)


MAX_TIMEOUT_RETRIES = 1

MAX_ADDITIONAL_EVIDENCE = 8

SYSTEM_PROMPT = """
You are analysing one job advertisement against verified candidate career evidence.

This is a decision-support task for the candidate to decide whether to apply for a job.

Use ONLY:
1. the supplied job advertisement; and
2. the supplied verified career evidence.

Hard Grounding Rules:
- NEVER invent candidate experience, skills, employment, education, certifications, projects, commercial work, or accomplishments.
- Base key matches ONLY on verified candidate evidence supplied in the prompt.
- Do NOT output internal evidence IDs (such as RESUME-001 or PORTFOLIO-020). Provide clear, natural-language factual points.

Semantic Analysis & Decision Rules:
1. Mandatory vs Preferred Requirements:
   - Give higher decision weight to explicit mandatory criteria (e.g. "must", "required", "minimum", "at least X years", "mandatory").
   - Preferred, optional, bonus, desirable, or "nice to have" items must carry significantly less weight than mandatory criteria.
2. Alternative Technologies / OR Semantics:
   - When a job advertisement lists multiple acceptable technologies, frameworks, languages, or platforms as alternatives (using words like "or", "such as", "e.g.", "for example", or "including"), satisfying one valid option is sufficient for that requirement.
   - Once a requirement containing alternatives is satisfied by one supported option, all unused alternatives MUST be completely excluded from: key_gaps, summary, tracker_note, and any reason for lowering priority or action.
   - Do NOT list the unused alternatives as candidate gaps under any circumstances.
   - Do NOT use absence of unused alternatives as a reason to lower fit.
   - Example A: "JavaScript or TypeScript" -> If JavaScript is evidenced, TypeScript is NOT a gap and MUST NOT appear in key_gaps, summary, or tracker_note.
   - Example B: "Backend technologies such as Node.js, Python, Java, .NET, or Go" -> If verified evidence supports Python, then Node.js, Java, .NET, and Go are NOT gaps and MUST NOT appear in key_gaps unless the advertisement separately states that one of them is independently mandatory.
   - Example C: "React, Next.js, Angular, or Vue" -> If verified evidence supports React, absence of Next.js, Angular, and Vue is NOT a gap.
   - Only identify a listed technology as a gap when the advertisement clearly requires that specific technology independently without alternatives.
3. Preserve Evidence Strength & Certification Wording:
   - Never exaggerate or strengthen candidate evidence beyond what was supplied.
   - If portfolio evidence does not explicitly prove live production deployment or commercial client use:
     - do NOT use "production-grade project" or "production-grade"
     - do NOT use "production experience"
     - do NOT imply live client deployment
   - If a technology is merely listed or demonstrated in portfolio/academic projects:
     - do NOT use "expertise"
     - do NOT use "strong proficiency"
     unless the supplied evidence explicitly supports that specific level.
   - Prefer grounded phrasing such as: "experience with", "hands-on project experience with", "listed skill", or "portfolio experience with".
   - Listed skill != proficiency; exposure != expertise; coursework != commercial experience; portfolio project != production/client deployment; certificate of attendance != professional certification.
   - When a requested certification is absent, state only that the requested certification is not evidenced (e.g. "No supplied evidence of CompTIA A+ or Network+; these are listed as optional/plus credentials").
   - Do NOT imply that another supplied credential is the candidate's "only" certification or describe the candidate as having "only" a certificate of attendance.
   - Preserve exact credential strength: professional certification, certificate of attendance, course completion, and training are not interchangeable.
4. Absence Wording:
   - Use "No supplied evidence of X" or "X is not evidenced in the supplied record" rather than "the candidate has no X" unless evidence explicitly proves absence.
5. Key Matches and Gaps Alignment:
   - key_matches and key_gaps must contain the major decision-relevant facts supporting priority and action.
   - If the summary identifies meaningful matches or gaps, those points must be reflected in key_matches and key_gaps. A Low/Skip result due to technical gaps must not have an empty key_gaps list.
6. Tracker Note Consistency:
   - tracker_note must be consistent with priority and action (e.g. Strategic Stretch action should state "Strategic stretch application..." or "Consider applying as strategic stretch...", not simply "Apply").
7. Primary Decision Drivers:
   - Base priority/action primarily on mandatory requirements, years of experience thresholds, eligibility constraints, core technology match, and material transferable strengths.

Output structure:
1. priority: "High", "Medium", or "Low"
   - High: Strong alignment on mandatory core requirements; manageable gaps.
   - Medium: Meaningful alignment exists; notable gaps or stretch areas remain.
   - Low: Weak overall alignment; core mandatory requirements unsupported.
2. action: "Apply", "Strategic Stretch", or "Skip"
   - Apply: Worth applying.
   - Strategic Stretch: Deliberate stretch opportunity worth trying.
   - Skip: Low alignment or critical unsupported mandatory requirements.
3. key_matches: list of concise natural-language bullet points highlighting key factual matches supporting the decision.
4. key_gaps: list of concise natural-language bullet points highlighting important missing evidence or skill gaps supporting the decision.
5. summary: concise explanation of why the job is or isn't worth the candidate's attention based on validated matches and gaps.
6. tracker_note: one concise sentence suitable for an application tracking spreadsheet, consistent with action.

Job facts:
- Extract company, role, location, work_mode, employment_type, salary, and posting_date only when supported by the ad.
- Use "Not stated" when absent.
- work_mode must be exactly: "remote", "hybrid", "on-site", "flexible", or "Not stated".

Return only the required structured JSON response.
"""


def _compact_evidence_item(
    item,
) -> dict:
    return {
        "evidence_id": (
            item.evidence_id
        ),
        "category": (
            item.category
        ),
        "capability": (
            item.capability
        ),
        "evidence_statement": (
            item.evidence_statement
        ),
        "state": (
            item.state
        ),
        "limitations": (
            item.limitations
        ),
    }


def _select_evidence(
    job_text: str,
    catalog: CareerEvidenceCatalog,
) -> list:
    selected_by_id = {}

    # Resume evidence is sufficiently compact
    # to include in full and is the highest-
    # authority career source.
    for item in catalog.evidence_items:
        if item.evidence_id.startswith(
            "RESUME-"
        ):
            selected_by_id[
                item.evidence_id
            ] = item

    # Add the most job-relevant portfolio /
    # capability evidence using the existing
    # deterministic evidence retriever.
    synthetic_target = (
        AssessmentTarget(
            target_id="JOB-ANALYSIS",
            target_type="other",
            text=job_text,
        )
    )

    bundle = retrieve_evidence_candidates(
        target=synthetic_target,
        catalog=catalog,
        top_k=MAX_ADDITIONAL_EVIDENCE,
    )

    candidate_ids = {
        candidate.evidence_id
        for candidate in bundle.candidates
    }

    for item in catalog.evidence_items:
        if (
            item.evidence_id
            in candidate_ids
        ):
            selected_by_id[
                item.evidence_id
            ] = item

    return list(
        selected_by_id.values()
    )


def _build_user_prompt(
    job_text: str,
    source_reference: str,
    job_url: str,
    evidence_items: list,
) -> str:
    evidence_payload = [
        _compact_evidence_item(item)
        for item in evidence_items
    ]

    payload = {
        "source_reference": (
            source_reference
        ),
        "canonical_job_url": (
            job_url
        ),
        "job_advertisement": (
            job_text
        ),
        "verified_career_evidence": (
            evidence_payload
        ),
    }

    return (
        "Analyse this job using the "
        "supplied verified evidence.\n\n"
        + json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
    )





def _extract_reasoning_text(
    message: dict,
) -> str:
    """
    LM Studio / OpenAI-compatible servers may
    expose reasoning under different optional
    fields. This is used only for diagnostics.
    """

    for key in (
        "reasoning",
        "reasoning_content",
    ):
        value = message.get(key)

        if isinstance(value, str):
            return value

    return ""


def _response_body_for_diagnostic(
    response: requests.Response,
) -> str:
    """
    Return a compact representation of an HTTP
    response body for diagnostics without
    changing the request or analysis behaviour.
    """

    try:
        body = response.json()

    except requests.exceptions.JSONDecodeError:
        return response.text[:2000]

    try:
        return json.dumps(
            body,
            ensure_ascii=False,
        )[:2000]

    except (
        TypeError,
        ValueError,
    ):
        return repr(body)[:2000]


def _perform_one_inference_attempt(
    payload: dict,
    source_reference: str,
    job_url: str,
    evidence_items: list,
) -> JobAnalysisResult:
    """
    Send one inference request to LM Studio
    (applying the existing timeout-retry
    logic), parse and Pydantic-validate the
    response, and apply canonical field overrides.

    Raises:
      requests.exceptions.ReadTimeout
        when all MAX_TIMEOUT_RETRIES are
        exhausted.
      ValueError for HTTP errors, JSON/schema
        parse failures, or empty content.
    """
    response = None

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

            if not response.ok:
                raise ValueError(
                    "LM Studio rejected the "
                    "job-analysis request. "
                    f"HTTP status="
                    f"{response.status_code}, "
                    f"body="
                    f"{_response_body_for_diagnostic(response)!r}"
                )

            break

        except requests.exceptions.ReadTimeout:
            if (
                attempt
                >= MAX_TIMEOUT_RETRIES
            ):
                raise

    if response is None:
        raise RuntimeError(
            "LM Studio request did not "
            "produce a response."
        )

    try:
        api_response = response.json()

    except requests.exceptions.JSONDecodeError as exc:
        raise ValueError(
            "LM Studio returned a "
            "non-JSON HTTP response. "
            f"HTTP status="
            f"{response.status_code}, "
            f"body="
            f"{response.text[:2000]!r}"
        ) from exc

    try:
        choice = (
            api_response[
                "choices"
            ][0]
        )

        message = (
            choice[
                "message"
            ]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise ValueError(
            "LM Studio response "
            "structure is invalid. "
            f"Response="
            f"{api_response!r}"
        ) from exc

    model_content = (
        message.get(
            "content"
        )
    )

    if (
        not isinstance(
            model_content,
            str,
        )
        or not model_content.strip()
    ):
        finish_reason = (
            choice.get(
                "finish_reason"
            )
        )

        reasoning_text = (
            _extract_reasoning_text(
                message
            )
        )

        usage = (
            api_response.get(
                "usage"
            )
        )

        raise ValueError(
            "LM Studio returned empty "
            "visible content. "
            f"finish_reason="
            f"{finish_reason!r}, "
            f"reasoning_chars="
            f"{len(reasoning_text)}, "
            f"usage={usage!r}"
        )

    try:
        parsed_result = json.loads(
            model_content
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Job analysis model "
            "returned invalid JSON. "
            f"finish_reason="
            f"{choice.get('finish_reason')!r}, "
            f"raw_content="
            f"{model_content[:2000]!r}"
        ) from exc

    analysis = (
        JobAnalysisResult
        .model_validate(
            parsed_result
        )
    )

    # These values are deterministic inputs
    # supplied by Python. Never allow the
    # model to replace the canonical values.
    analysis.job.source_reference = (
        source_reference
    )

    analysis.job.job_url = (
        job_url
    )

    return analysis


def analyse_job(
    job_text: str,
    source_reference: str,
    job_url: str,
    catalog: CareerEvidenceCatalog,
) -> JobAnalysisResult:
    if not job_text.strip():
        raise ValueError(
            "job_text must not be empty."
        )

    evidence_items = _select_evidence(
        job_text=job_text,
        catalog=catalog,
    )

    if not evidence_items:
        raise ValueError(
            "No career evidence was "
            "selected for job analysis."
        )

    user_prompt = _build_user_prompt(
        job_text=job_text,
        source_reference=(
            source_reference
        ),
        job_url=job_url,
        evidence_items=evidence_items,
    )

    response_schema = (
        JobAnalysisResult
        .model_json_schema()
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "temperature": 0,
        "reasoning_effort": (
            REASONING_EFFORT
        ),
        # GPT-OSS-20B with reasoning_effort=medium
        # generates a large internal reasoning trace
        # before emitting structured JSON content.
        # max_tokens in LM Studio is a TOTAL token
        # budget (prompt + reasoning + visible content).
        # With ~4068 prompt tokens and ~3219 reasoning
        # tokens at medium effort, 8192 left only ~905
        # tokens for visible content — too few to
        # complete the full JSON (finish_reason='length').
        # 16384 gives ~9248 tokens for reasoning+content,
        # which comfortably covers the full output.
        "max_tokens": 16384,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": (
                    "job_analysis"
                ),
                "strict": True,
                "schema": (
                    response_schema
                ),
            },
        },
    }

    return _perform_one_inference_attempt(
        payload=payload,
        source_reference=source_reference,
        job_url=job_url,
        evidence_items=evidence_items,
    )