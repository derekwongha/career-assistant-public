"""
Step 4 — Tailored Cover Letter Generator Engine.

Generates a tailored cover letter for a job in APPLY_PENDING state using:
- persisted cleaned job text;
- persisted job analysis;
- deterministic selected career evidence subset (reusing _select_evidence()).

Enforces strict grounding boundaries (no invented experience, no upgraded credentials).
Saves output to 05_Evaluation/cover_letters/<job_id>_cover_letter.md.
"""
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional
import requests

from career_evidence_catalog_builder import load_saved_career_evidence_catalog
from career_evidence_schema import CareerEvidenceCatalog
from job_analysis_reasoner import (
    LM_STUDIO_URL,
    MODEL_NAME,
    REASONING_EFFORT,
    REQUEST_TIMEOUT_SECONDS,
    MAX_TIMEOUT_RETRIES,
    _compact_evidence_item,
    _extract_reasoning_text,
    _response_body_for_diagnostic,
    _select_evidence,
)
from job_registry import (
    DEFAULT_DB_PATH,
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    transition_job_state,
)

COVER_LETTERS_DIR = (
    Path(__file__).resolve().parent.parent
    / "05_Evaluation"
    / "cover_letters"
)

# Candidate name used in the prompt and sign-off. Set CANDIDATE_NAME in your environment or .env.
CANDIDATE_NAME = os.environ.get("CANDIDATE_NAME", "[Candidate Name]")

COVER_LETTER_SYSTEM_PROMPT = """
You are writing a tailored job application cover letter for [CANDIDATE_NAME] based strictly on verified candidate career evidence and a specific job advertisement.

Hard Grounding Rules:
1. Use ONLY the supplied verified candidate career evidence.
2. NEVER invent candidate employment history, missing years of experience, unevidenced technologies, or certifications.
3. Do NOT describe portfolio or academic project work as commercial experience or live client deployment.
4. Do NOT upgrade listed skills to "expertise" or "strong proficiency" unless explicitly supported by evidence.
5. Do NOT upgrade a Certificate of Attendance to a professional certification.
6. Distinguish direct experience from transferable experience accurately.
7. Keep the tone professional, concise, structured, and compelling.
8. Include contact placeholder: [CANDIDATE_NAME] | Candidate

Structure:
- Salutation (Dear Hiring Manager,)
- Opening paragraph stating role title and interest based on core technical alignment
- 2 short body paragraphs emphasizing verified technical matches and relevant project/work accomplishments
- Brief concluding paragraph expressing enthusiasm for an interview
- Professional sign-off (Sincerely, [CANDIDATE_NAME])
""".replace("[CANDIDATE_NAME]", CANDIDATE_NAME)


def _build_cover_letter_user_prompt(
    job_facts: dict[str, Any],
    analysis: dict[str, Any],
    selected_evidence: list[Any],
) -> str:
    compact_evidence = [_compact_evidence_item(item) for item in selected_evidence]

    payload = {
        "job_details": {
            "company": job_facts.get("company", "Company"),
            "role": job_facts.get("role", "Software Engineer"),
            "location": job_facts.get("location", "Singapore"),
            "source_reference": job_facts.get("source_reference", ""),
            "job_url": job_facts.get("job_url", ""),
        },
        "job_analysis_summary": {
            "key_matches": analysis.get("key_matches", []),
            "key_gaps": analysis.get("key_gaps", []),
            "summary": analysis.get("summary", ""),
        },
        "verified_candidate_evidence": compact_evidence,
    }

    return (
        "Write a tailored cover letter for this job using ONLY the supplied verified candidate evidence.\n\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )


def generate_cover_letter(
    job_id: str,
    catalog: Optional[CareerEvidenceCatalog] = None,
    db_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    mock_response_text: Optional[str] = None,
) -> tuple[str, str]:
    """
    Generates a tailored cover letter for a job in APPLY_PENDING status.
    One intentional LM Studio call per request.
    Saves markdown output to 05_Evaluation/cover_letters/<job_id>_cover_letter.md.
    Updates SQLite state to COVER_LETTER_GENERATED.

    Returns:
      (cover_letter_text, file_path_str)
    """
    target_db = db_path or DEFAULT_DB_PATH
    target_out_dir = output_dir or COVER_LETTERS_DIR
    target_out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_db))
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()
    cur.execute(
        """
        SELECT job_id, source_reference, confirmed_url, status, cleaned_text, analysis_result_json
        FROM jobs
        WHERE job_id = ?;
        """,
        (job_id,),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        raise ValueError(f"Job ID '{job_id}' not found in database.")

    current_status = row["status"]
    if current_status != STATE_APPLY_PENDING:
        conn.close()
        raise ValueError(
            f"Cover letter generation is permitted ONLY for jobs in '{STATE_APPLY_PENDING}' status. "
            f"Job '{job_id}' is currently in '{current_status}' status."
        )

    cleaned_text = row["cleaned_text"] or ""
    analysis_json_str = row["analysis_result_json"] or "{}"
    try:
        analysis_data = json.loads(analysis_json_str)
    except Exception:
        analysis_data = {}

    job_facts = analysis_data.get("job", {})
    if not job_facts:
        job_facts = {
            "company": "Company",
            "role": "Role",
            "location": "Singapore",
            "source_reference": row["source_reference"],
            "job_url": row["confirmed_url"],
        }

    # Load Catalog & Reuse Deterministic Step 3 evidence selector
    active_catalog = catalog or load_saved_career_evidence_catalog()
    selected_evidence = _select_evidence(cleaned_text, active_catalog)

    # If mock_response_text is provided (for deterministic unit tests), bypass network HTTP call
    if mock_response_text:
        letter_content = mock_response_text
    else:
        user_prompt = _build_cover_letter_user_prompt(
            job_facts=job_facts,
            analysis=analysis_data,
            selected_evidence=selected_evidence,
        )

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": COVER_LETTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": 16384,
            "reasoning_effort": REASONING_EFFORT,
        }

        response = None
        for attempt in range(MAX_TIMEOUT_RETRIES + 1):
            try:
                response = requests.post(
                    LM_STUDIO_URL,
                    json=payload,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                if not response.ok:
                    raise ValueError(
                        f"LM Studio cover letter request failed. Status={response.status_code}, body={_response_body_for_diagnostic(response)!r}"
                    )
                break
            except requests.exceptions.ReadTimeout:
                if attempt >= MAX_TIMEOUT_RETRIES:
                    conn.close()
                    raise

        if response is None:
            conn.close()
            raise RuntimeError("LM Studio request produced no response.")

        api_res = response.json()
        try:
            choice = api_res["choices"][0]
            letter_content = choice["message"]["content"]
        except Exception as exc:
            conn.close()
            raise ValueError(f"Invalid LM Studio response structure: {api_res!r}") from exc

        if not letter_content or not letter_content.strip():
            reasoning = _extract_reasoning_text(choice.get("message", {}))
            conn.close()
            raise ValueError(
                f"LM Studio returned empty visible cover letter content. reasoning_chars={len(reasoning)}"
            )

    # Save cover letter to markdown file
    out_filename = f"{job_id}_cover_letter.md"
    out_filepath = target_out_dir / out_filename

    with open(out_filepath, "w", encoding="utf-8") as f:
        f.write(letter_content)

    rel_or_abs_path = str(out_filepath.resolve())

    # Update SQLite state to COVER_LETTER_GENERATED
    transition_job_state(
        conn,
        job_id=job_id,
        target_status=STATE_COVER_LETTER_GENERATED,
        human_decision="Apply",
        cover_letter_path=rel_or_abs_path,
    )

    conn.close()
    return (letter_content, rel_or_abs_path)
