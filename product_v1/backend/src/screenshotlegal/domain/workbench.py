"""Contracts for the end-user workbench MVP."""
from typing import Literal
from pydantic import Field, field_validator
from screenshotlegal.domain.common.models import StrictModel, CaseRecord
from screenshotlegal.domain.evidence.models import EvidenceItem

class CaseEdit(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=10000)
    notes: str = Field(default="", max_length=50000)
    expected_revision: int = Field(ge=0)

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        if not value.strip():
            raise ValueError("Case title is required")
        return value.strip()

class TimelineEntry(StrictModel):
    id: str
    kind: Literal["event", "message", "evidence"]
    title: str
    timestamp: str | None = None
    time_label: str | None = None
    source_refs: list[str] = []
    evidence_ids: list[str] = []
    review_status: str = "unreviewed"

class WorkbenchSnapshot(StrictModel):
    case: CaseRecord
    evidence: list[EvidenceItem]
    timeline: list[TimelineEntry]

class PresentationPreview(StrictModel):
    request_id: str
    case_id: str
    status: Literal["mock"] = "mock"
    provider: Literal["mock"] = "mock"
    case_revision: int
    evidence_count: int
    timeline_count: int
    message: str
    download_url: str | None = None
