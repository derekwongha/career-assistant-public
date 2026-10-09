from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


AssessmentTargetType = Literal[
    "required",
    "preferred",
    "education",
    "other",
    "responsibility",
]


MatchType = Literal[
    "DIRECT",
    "TRANSFERABLE",
    "PARTIAL",
    "GAP",
]


class AssessmentTarget(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    target_id: str = Field(
        min_length=1
    )

    target_type: (
        AssessmentTargetType
    )

    text: str = Field(
        min_length=1
    )


class RequirementAssessment(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    target_id: str = Field(
        min_length=1
    )

    match_type: MatchType

    evidence_ids: list[str]

    rationale: str = Field(
        min_length=1
    )

    @model_validator(
        mode="after"
    )
    def validate_evidence_usage(
        self,
    ):
        if (
            self.match_type
            == "GAP"
            and self.evidence_ids
        ):
            raise ValueError(
                "GAP assessments must "
                "not contain evidence IDs."
            )

        if (
            self.match_type
            != "GAP"
            and not self.evidence_ids
        ):
            raise ValueError(
                "DIRECT, TRANSFERABLE "
                "and PARTIAL assessments "
                "must reference at least "
                "one evidence ID."
            )

        return self


class JobAssessmentResult(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    assessments: list[
        RequirementAssessment
    ]

    assessment_warnings: list[str]

class EvidenceCandidate(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    evidence_id: str = Field(
        min_length=1
    )

    source_type: Literal[
        "resume",
        "portfolio",
        "capability_matrix",
    ]

    capability: str = Field(
        min_length=1
    )

    evidence_statement: str = Field(
        min_length=1
    )

    state: str = Field(
        min_length=1
    )

    context: str

    limitations: list[str]

    retrieval_score: int = Field(
        ge=1
    )

    category: str = Field(
        min_length=1
    )


class TargetEvidenceBundle(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    target_id: str = Field(
        min_length=1
    )

    target_type: (
        AssessmentTargetType
    )

    text: str = Field(
        min_length=1
    )

    candidates: list[
        EvidenceCandidate
    ]