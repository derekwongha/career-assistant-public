from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


WorkMode = Literal[
    "remote",
    "hybrid",
    "on-site",
    "flexible",
    "Not stated",
]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScalarField(StrictBaseModel):
    value: str


class WorkModeField(StrictBaseModel):
    value: WorkMode


class ListField(StrictBaseModel):
    value: list[str] = Field(default_factory=list)


class SourceInfo(StrictBaseModel):
    type: str
    reference: str


class JobListingFields(StrictBaseModel):
    company: ScalarField
    role: ScalarField
    location: ScalarField
    work_mode: WorkModeField
    employment_type: ScalarField
    salary: ScalarField
    posting_date: ScalarField
    job_url: ScalarField

    required_requirements: ListField
    preferred_requirements: ListField
    education_requirements: ListField
    other_requirements: ListField
    responsibilities: ListField


class JobListingExtraction(StrictBaseModel):
    source: SourceInfo
    fields: JobListingFields
    extraction_warnings: list[str]