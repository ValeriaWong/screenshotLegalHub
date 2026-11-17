from screenshotlegal.domain.common.models import StrictModel, Field

class RetryPolicy(StrictModel):
    max_attempts: int = Field(default=2, ge=1, le=5)
    retryable_errors: list[str] = ['TransientError', 'JSONDecodeError']
    backoff: float = Field(default=0.05, ge=0, le=30)

class PlanNode(StrictModel):
    node_id: str
    stage: int
    capability: str
    resolved_skill_id: str
    resolved_skill_version: str
    skill_digest: str
    depends_on: list[str]
    input_selectors: list[str]
    output_targets: list[str]
    required: bool = True
    review_gate: bool = False
    retry_policy: RetryPolicy = RetryPolicy()

class CasePlan(StrictModel):
    case_id: str
    matter_pack_id: str
    matter_pack_version: str
    matter_pack_digest: str
    analysis_profile: dict
    analysis_profile_digest: str
    nodes: list[PlanNode]
    edges: list[tuple[str, str]]
    compiled_at: str
    plan_digest: str
