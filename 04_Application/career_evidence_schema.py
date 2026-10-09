from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


EvidenceSourceType = Literal[
    "resume",
    "portfolio",
    "capability_matrix",
    "career_plan",
]


EvidenceState = Literal[
    "PROVEN",
    "FOUNDATION",
    "EXPOSURE",
    "NEW",
    "PROVEN / FOUNDATION",
    "NEW / EXPOSURE",
    "EXPOSURE / NEW",
    "FOUNDATION conceptually",
    "PROVEN conceptually",
    "FOUNDATION / EXPOSURE",
    "Transferable professional experience",
    "Transferable / needs adaptation",
    "NEW commercially",
    "NONE yet",
    "EXPERIMENTAL",
    "Not assessed",
]


EvidenceCategory = Literal[
    "employment",
    "education",
    "technical_skill",
    "project",
    "business_capability",
    "domain_experience",
    "tool",
    "methodology",
    "other",
]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class EvidenceSource(
    StrictBaseModel
):
    source_type: EvidenceSourceType

    source_file: str

    source_reference: str


class CareerEvidenceItem(
    StrictBaseModel
):
    evidence_id: str

    category: EvidenceCategory

    capability: str

    evidence_statement: str

    state: EvidenceState

    context: str

    limitations: list[str] = Field(
        default_factory=list
    )

    sources: list[
        EvidenceSource
    ] = Field(
        default_factory=list
    )


class CareerEvidenceCatalog(
    StrictBaseModel
):
    person_reference: str

    evidence_items: list[
        CareerEvidenceItem
    ] = Field(
        default_factory=list
    )

    extraction_warnings: list[str] = Field(
        default_factory=list
    )