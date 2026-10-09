from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


RequirementType = Literal[
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


PriorityLevel = Literal[
    "High",
    "Medium",
    "Low",
]


RecommendedAction = Literal[
    "Apply",
    "Strategic Stretch",
    "Skip",
]


WorkMode = Literal[
    "remote",
    "hybrid",
    "on-site",
    "flexible",
    "Not stated",
]


class StrictBaseModel(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )


class JobFacts(
    StrictBaseModel
):
    source_reference: str = Field(
        min_length=1
    )

    job_url: str = Field(
        min_length=1
    )

    company: str = Field(
        min_length=1
    )

    role: str = Field(
        min_length=1
    )

    location: str = Field(
        min_length=1
    )

    work_mode: WorkMode

    employment_type: str = Field(
        min_length=1
    )

    salary: str = Field(
        min_length=1
    )

    posting_date: str = Field(
        min_length=1
    )


class JobAnalysisResult(
    StrictBaseModel
):
    job: JobFacts

    priority: PriorityLevel

    action: RecommendedAction

    key_matches: list[str] = Field(
        default_factory=list
    )

    key_gaps: list[str] = Field(
        default_factory=list
    )

    summary: str = Field(
        min_length=1
    )

    tracker_note: str = Field(
        min_length=1
    )

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_schema(
        cls, data: object
    ) -> object:
        if not isinstance(data, dict):
            return data

        if (
            "assessments" in data
            and "key_matches" not in data
        ):
            assessments = data.pop(
                "assessments", []
            )
            matches = []
            gaps = []
            for a in assessments:
                req = a.get(
                    "requirement", ""
                )
                match_type = a.get(
                    "match_type", ""
                )
                rat = a.get(
                    "rationale", ""
                )
                if match_type in (
                    "DIRECT",
                    "TRANSFERABLE",
                    "PARTIAL",
                ):
                    matches.append(
                        f"{req}: {rat}"
                    )
                elif match_type == "GAP":
                    gaps.append(
                        f"{req}: {rat}"
                    )
            data["key_matches"] = (
                matches
                or [
                    "Legacy analysis resurfaced."
                ]
            )
            data["key_gaps"] = gaps
            data["summary"] = data.pop(
                "rationale",
                "Legacy analysis resurfaced.",
            )
            data.pop(
                "analysis_warnings", None
            )

        return data