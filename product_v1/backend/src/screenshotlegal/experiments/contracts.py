from datetime import date
from typing import Literal
from pydantic import Field, model_validator
from screenshotlegal.domain.common.models import StrictModel

class EvaluationBudget(StrictModel):
    max_input_tokens: int = Field(default=200000,ge=100,le=1000000)
    max_output_tokens: int = Field(default=12000,ge=100,le=200000)
    max_model_calls: int = Field(default=8,ge=1,le=30)
    max_tool_calls: int = Field(default=8,ge=0,le=50)
    max_wall_time_s: int = Field(default=180,ge=5,le=1800)
    max_output_per_call: int = Field(default=2000,ge=100,le=10000)

class MethodOptions(StrictModel):
    legalagentbench_variant: Literal['react','plan_and_solve','plan_and_execute'] = 'react'
    lmad_protocol: Literal['hybrid','ranked'] = 'hybrid'
    lmad_rounds: int = Field(default=3,ge=1,le=3)
    lmad_max_facts: int = Field(default=2,ge=1,le=2)
    refinement_rounds: int = Field(default=2,ge=1,le=3)
    retrieval_rounds: int = Field(default=3,ge=1,le=8)
    chunk_chars: int = Field(default=4000,ge=500,le=20000)

class InferenceOptions(StrictModel):
    # Explicit research control; omitted means the provider's existing default.
    enable_thinking: bool | None = None

class ExperimentCreate(StrictModel):
    case_id: str
    name: str = Field(min_length=1,max_length=200)
    goal: str = Field(default='整理材料中的待证事实、支持与反证，明确不确定性并逐条引用原文。',min_length=1,max_length=3000)
    method_ids: list[str] = Field(min_length=1,max_length=21)
    model_id: str = 'demo'
    law_effective_date: date
    allow_draft_matter: bool = False
    debate_rounds: int = Field(default=1,ge=0,le=3)
    retrieval_top_k: int = Field(default=5,ge=1,le=10)
    method_options: MethodOptions = Field(default_factory=MethodOptions)
    inference_options: InferenceOptions = Field(default_factory=InferenceOptions)
    expected_input_digest: str | None = None
    model_revision: str = Field(default='',max_length=200)
    document_ids: list[str] = Field(default_factory=list,max_length=30)
    case_group_id: str = Field(min_length=1,max_length=200)
    split: Literal['development','holdout'] = 'development'
    budget: EvaluationBudget = Field(default_factory=EvaluationBudget)
    idempotency_key: str = Field(min_length=1,max_length=200)
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.method_ids))!=len(self.method_ids) or len(set(self.document_ids))!=len(self.document_ids):
            raise ValueError('方法与资料不能重复选择')
        return self

from screenshotlegal.domain.evidence.sources import FrozenSource as SourceAnchor

class Citation(StrictModel):
    source_ref_id: str
    quote: str = Field(min_length=1,max_length=10000)
    start: int = Field(ge=0,description="冻结原文Unicode字符起点（包含），建议复制citation_units中的位置")
    end: int = Field(ge=1,description="冻结原文Unicode字符终点（不包含），必须满足text[start:end]等于quote")

class Fact(StrictModel):
    id: str = Field(min_length=1,max_length=200)
    statement: str = Field(min_length=1,max_length=10000)
    epistemic_status: Literal['observed','inferred','uncertain'] = 'uncertain'
    citations: list[Citation] = Field(min_length=1,max_length=20,description="每项事实至少一条逐字原文引用；无原文依据的缺失信息放在uncertainties，不创建无引用事实")

class Claim(StrictModel):
    id: str = Field(min_length=1,max_length=200)
    label: str = Field(min_length=1,max_length=2000)
    applicability: Literal['plausible','unsupported','uncertain'] = 'uncertain'
    fact_ids: list[str] = Field(default_factory=list,max_length=100)
    template_id: str | None = None

class EvidenceLink(StrictModel):
    fact_id: str
    source_ref_id: str
    relation: Literal['supports','contradicts','context']
    quote: str = Field(min_length=1,max_length=10000)

class Element(StrictModel):
    id: str = Field(min_length=1,max_length=200)
    label: str = Field(min_length=1,max_length=2000)
    claim_id: str
    fact_ids: list[str] = Field(default_factory=list,max_length=100)
    status: Literal['supported','contradicted','unknown'] = 'unknown'
    burden_role: Literal['claimant','defendant','unknown'] = 'unknown'
    template_id: str | None = None
    burden_origin: Literal['model_inferred','provided_rule','unknown'] = 'unknown'

class CaseAnalysisOutput(StrictModel):
    summary: str = Field(min_length=1,max_length=30000)
    claims: list[Claim] = Field(default_factory=list,max_length=100)
    elements: list[Element] = Field(default_factory=list,max_length=200)
    facts: list[Fact] = Field(default_factory=list,max_length=200)
    evidence_links: list[EvidenceLink] = Field(default_factory=list,max_length=500)
    uncertainties: list[str] = Field(default_factory=list,max_length=100)
    @model_validator(mode='after')
    def graph_integrity(self):
        ids=[f.id for f in self.facts]
        if len(set(ids))!=len(ids) or len({c.id for c in self.claims})!=len(self.claims): raise ValueError('重复实体 ID')
        if any(fid not in ids for c in self.claims for fid in c.fact_ids): raise ValueError('请求引用未知事实')
        if any(e.claim_id not in {c.id for c in self.claims} or any(fid not in ids for fid in e.fact_ids) for e in self.elements): raise ValueError('要件引用未知实体')
        if len({e.id for e in self.elements})!=len(self.elements): raise ValueError('要件 ID 重复')
        if any(e.fact_id not in ids for e in self.evidence_links): raise ValueError('证据关联引用未知事实')
        return self
