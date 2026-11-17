"""Text evidence is supplied by the caller, never loaded from an older application."""
from typing import Literal
from pydantic import Field, model_validator
from ..primitives import StrictModel
from ..contracts import ID

Focus = Literal['identity', 'chronology', 'amounts', 'alternatives', 'source_quality']
Stage = Literal['planning', 'facts', 'assessment', 'gaps', 'synthesis']

class Source(StrictModel):
    source_id: ID
    text: str = Field(min_length=1, max_length=4000)
    speaker: str = Field(default='未核实主体', min_length=1, max_length=120)
    time: str | None = Field(default=None, max_length=40)
    time_precision: Literal['day', 'month', 'unknown'] = 'unknown'
    kind: Literal['chat', 'document', 'bank_record'] = 'chat'
    locator: str = Field(default='调用方文本', max_length=200)

    @model_validator(mode='after')
    def valid_time(self):
        from datetime import date
        import re
        if self.time_precision == 'unknown':
            if self.time is not None:
                raise ValueError('unknown precision requires null time')
        elif self.time_precision == 'day':
            if not self.time or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', self.time):
                raise ValueError('day requires ISO date')
            date.fromisoformat(self.time)
        else:
            if not self.time or not re.fullmatch(r'\d{4}-\d{2}', self.time):
                raise ValueError('month requires YYYY-MM')
            date.fromisoformat(self.time + '-01')
        return self

class CaseInput(StrictModel):
    case_id: ID
    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=2000)
    sources: list[Source] = Field(min_length=1, max_length=64)
    synthetic: bool = False

    @model_validator(mode='after')
    def unique_ids(self):
        if len({s.source_id for s in self.sources}) != len(self.sources):
            raise ValueError('duplicate source ID')
        return self

class Citation(StrictModel):
    source_id: ID
    quote: str = Field(min_length=1, max_length=4000)

class Finding(StrictModel):
    text: str = Field(min_length=1, max_length=1500)
    kind: Literal['observation', 'inference']
    citations: list[Citation] = Field(min_length=1, max_length=12)
    uncertainty: str = Field(min_length=1, max_length=1000)

class GapProposal(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    action: str = Field(min_length=1, max_length=1000)
    citations: list[Citation] = Field(min_length=1, max_length=12)
    method: Literal['code', 'prompt', 'model', 'evidence', 'human']

class Reasoning(StrictModel):
    focus: list[Focus] = Field(default_factory=list, max_length=5)
    findings: list[Finding] = Field(default_factory=list, max_length=24)
    questions: list[str] = Field(default_factory=list, max_length=12)
    gap_proposals: list[GapProposal] = Field(default_factory=list, max_length=12)

class ReasoningInput(StrictModel):
    stage: Stage
    payload: dict
    repair_findings: list[str] = Field(default_factory=list, max_length=24)

class ReasoningOutput(StrictModel):
    reasoning: Reasoning
    provider_response_id: str = Field(max_length=256)
    model: str = Field(max_length=200)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float = Field(ge=0, allow_inf_nan=False)

class AnalysisPlan(StrictModel):
    objective: str
    focus: list[Focus]
    stages: list[Stage]
    acceptance: list[str]

class Fact(StrictModel):
    source_id: ID
    quote: str
    speaker: str
    time: str | None
    time_precision: Literal['day', 'month', 'unknown']
    source_kind: Literal['chat', 'document', 'bank_record']
    labels: list[str]
    amounts: list[str]
    source_digest: str

class Ledger(StrictModel):
    facts: list[Fact]
    undated_sources: list[ID]
    note: str

class Check(StrictModel):
    check_id: ID
    title: str
    status: Literal['observed', 'candidate', 'unknown']
    detail: str
    source_ids: list[ID]

class Assessment(StrictModel):
    checks: list[Check]
    conclusion: str
    determination: Literal['insufficient'] = 'insufficient'

class Gap(StrictModel):
    gap_id: ID
    title: str
    method: Literal['code', 'prompt', 'model', 'evidence', 'human']
    status: Literal['completed', 'candidate', 'needs_evidence', 'needs_review']
    rationale: str
    action: str
    source_ids: list[ID]

class Gaps(StrictModel):
    items: list[Gap]

class StageMeta(StrictModel):
    stage: Stage
    mode: Literal['code', 'model']
    prompt_digest: str
    reasoning: Reasoning
    model_receipt: ReasoningOutput | None = None

class PlanningOutput(StrictModel):
    plan: AnalysisPlan
    meta: StageMeta

class FactsOutput(StrictModel):
    ledger: Ledger
    meta: StageMeta

class AssessmentInput(StrictModel):
    ledger: Ledger
    plan: AnalysisPlan

class AssessmentOutput(StrictModel):
    assessment: Assessment
    meta: StageMeta

class GapsInput(StrictModel):
    ledger: Ledger
    assessment: Assessment

class GapsOutput(StrictModel):
    gaps: Gaps
    meta: StageMeta

class ReportData(StrictModel):
    case: CaseInput
    plan: AnalysisPlan
    ledger: Ledger
    assessment: Assessment
    gaps: Gaps
    stages: list[StageMeta]
    conclusion: str
    determination: Literal['insufficient'] = 'insufficient'

class ReportInput(StrictModel):
    case: CaseInput
    planning: PlanningOutput
    facts: FactsOutput
    assessment: AssessmentOutput
    gaps: GapsOutput
