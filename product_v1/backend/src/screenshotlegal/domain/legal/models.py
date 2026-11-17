from typing import Literal
from screenshotlegal.domain.common.models import StrictModel, Field

class MatterManifest(StrictModel):
    id: str
    name_zh: str
    name_en: str
    jurisdiction: str
    practice_area: str
    version: str
    schema_version: Literal[1]
    status: Literal['draft', 'reviewed', 'deprecated']
    valid_from: str | None = None
    valid_to: str | None = None
    expert_review: dict
    required_capabilities: list[str]

class SkillManifest(StrictModel):
    id: str
    capability: str
    version: str
    schema_version: Literal[1]
    executor_type: Literal['python']
    applies_to: dict[str, list[str]]
    input_schema: list[str]
    output_schema: list[str]
    grounding: dict[str, bool]
    dependencies: list[str]
    side_effects: bool = False
    trust: dict[str, str] = {'level': 'external_untrusted'}
    permissions: dict[str, bool]
    stage: int = Field(ge=1, le=8)


class AuthorityReview(StrictModel):
    status: Literal['unreviewed','approved','rejected','stale'] = 'unreviewed'
    reviewer: str | None = None
    reviewed_at: str | None = None
    reviewed_digest: str | None = None

class AuthoritySource(StrictModel):
    id: str
    type: str
    title: str
    article: str
    jurisdiction: str
    valid_from: str | None = None
    valid_to: str | None = None
    source_url: str
    source_digest: str | None = None
    verification_status: Literal['verified','unverified','expired','unknown']
    source_role: Literal['normative_authority','case_precedent','legal_guide'] = 'normative_authority'
    text: str | None = None
    review: AuthorityReview = Field(default_factory=AuthorityReview)

class GuideFactor(StrictModel):
    id: str
    label: str
    guide_source_ids: list[str] = Field(min_length=1)

class GuideIssue(StrictModel):
    id: str
    label: str
    factors: list[GuideFactor] = Field(min_length=1)
