import re

from career_evidence_schema import (
    CareerEvidenceCatalog,
)

from job_assessment_schema import (
    AssessmentTarget,
    EvidenceCandidate,
    TargetEvidenceBundle,
)


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "can",
    "for",
    "from",
    "have",
    "in",
    "is",
    "it",
    "knowledge",
    "of",
    "or",
    "the",
    "to",
    "with",
    "ability",
    "able",
    "experience",
    "experienced",
    "familiar",
    "familiarity",
    "preferred",
    "required",
    "strong",
}


TOKEN_NORMALIZATION = {
    "apis": "api",
    "applications": "application",
    "databases": "database",
    "issues": "issue",
    "requirements": "requirement",
    "systems": "system",
    "technologies": "technology",
    "workflows": "workflow",
    "interfaces": "interface",
    "integrations": "integration",
    "operations": "operation",
    "skills": "skill",
    "tools": "tool",
}


SOURCE_PRIORITY = {
    "resume": 3,
    "portfolio": 2,
    "capability_matrix": 1,
}


def _normalise_text(
    text: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        text.lower(),
    ).strip()


def _tokenise(
    text: str,
) -> set[str]:
    raw_tokens = re.findall(
        r"[a-z0-9+#]+",
        text.lower(),
    )

    tokens = set()

    for token in raw_tokens:
        token = TOKEN_NORMALIZATION.get(
            token,
            token,
        )

        if token in STOPWORDS:
            continue

        if len(token) <= 1:
            continue

        tokens.add(
            token
        )

    return tokens


def _target_bigrams(
    text: str,
) -> set[str]:
    tokens = [
        TOKEN_NORMALIZATION.get(
            token,
            token,
        )
        for token in re.findall(
            r"[a-z0-9+#]+",
            text.lower(),
        )
        if (
            TOKEN_NORMALIZATION.get(
                token,
                token,
            )
            not in STOPWORDS
        )
        and len(
            TOKEN_NORMALIZATION.get(
                token,
                token,
            )
        ) > 1
    ]

    return {
        f"{tokens[index]} "
        f"{tokens[index + 1]}"
        for index in range(
            len(tokens) - 1
        )
    }


def _score_field(
    target_terms: set[str],
    field_text: str,
    weight: int,
) -> int:
    field_terms = _tokenise(
        field_text
    )

    overlap = (
        target_terms
        & field_terms
    )

    return (
        len(overlap)
        * weight
    )


def _score_evidence_item(
    target: AssessmentTarget,
    item,
) -> int:
    target_terms = _tokenise(
        target.text
    )

    score = 0

    score += _score_field(
        target_terms=target_terms,
        field_text=item.capability,
        weight=6,
    )

    score += _score_field(
        target_terms=target_terms,
        field_text=(
            item.evidence_statement
        ),
        weight=4,
    )

    score += _score_field(
        target_terms=target_terms,
        field_text=item.context,
        weight=2,
    )

    for limitation in (
        item.limitations
    ):
        score += _score_field(
            target_terms=target_terms,
            field_text=limitation,
            weight=1,
        )

    evidence_text = _normalise_text(
        " ".join(
            [
                item.capability,
                item.evidence_statement,
                item.context,
                *item.limitations,
            ]
        )
    )

    target_bigrams = (
        _target_bigrams(
            target.text
        )
    )

    for bigram in target_bigrams:
        if bigram in evidence_text:
            score += 5

    return score


def retrieve_evidence_candidates(
    target: AssessmentTarget,
    catalog: CareerEvidenceCatalog,
    top_k: int = 8,
) -> TargetEvidenceBundle:
    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    scored_items = []

    for item in (
        catalog.evidence_items
    ):
        if (
            target.target_type
            == "education"
            and item.category
            != "education"
        ):
            continue

        score = _score_evidence_item(
            target=target,
            item=item,
        )

        if score <= 0:
            continue

        if len(item.sources) != 1:
            raise ValueError(
                "Evidence item must have "
                "exactly one source: "
                f"{item.evidence_id}"
            )

        source_type = (
            item.sources[0]
            .source_type
        )

        scored_items.append(
            (
                score,
                SOURCE_PRIORITY.get(
                    source_type,
                    0,
                ),
                item.evidence_id,
                item,
                source_type,
            )
        )

    scored_items.sort(
        key=lambda row: (
            -row[0],
            -row[1],
            row[2],
        )
    )

    selected = (
        scored_items[:top_k]
    )

    candidates = []

    for (
        score,
        _source_priority,
        _evidence_id,
        item,
        source_type,
    ) in selected:
        candidates.append(
            EvidenceCandidate(
                evidence_id=(
                    item.evidence_id
                ),
                source_type=(
                    source_type
                ),
                category=(
                    item.category
                ),
                capability=(
                    item.capability
                ),
                evidence_statement=(
                    item.evidence_statement
                ),
                state=item.state,
                context=item.context,
                limitations=list(
                    item.limitations
                ),
                retrieval_score=score,
            )
        )

    return TargetEvidenceBundle(
        target_id=target.target_id,
        target_type=target.target_type,
        text=target.text,
        candidates=candidates,
    )


def retrieve_for_targets(
    targets: list[
        AssessmentTarget
    ],
    catalog: CareerEvidenceCatalog,
    top_k: int = 8,
) -> list[
    TargetEvidenceBundle
]:
    return [
        retrieve_evidence_candidates(
            target=target,
            catalog=catalog,
            top_k=top_k,
        )
        for target in targets
    ]