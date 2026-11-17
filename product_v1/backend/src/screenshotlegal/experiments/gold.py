"""Evaluation-only human Gold contract. Never imported by the model input builder."""
from typing import Literal
from pydantic import Field,model_validator
from screenshotlegal.domain.common.models import StrictModel
from screenshotlegal.research.contracts import digest

class GoldClaim(StrictModel):
    label: str
    aliases: list[str] = Field(default_factory=list)
    applicability: Literal['plausible','unsupported','uncertain']

class GoldBurden(StrictModel):
    element_label: str
    role: Literal['claimant','defendant','unknown']

class CitationJudgment(StrictModel):
    output_digest: str
    fact_id: str
    citation_index: int = Field(ge=0)
    supported: bool

class CaseGold(StrictModel):
    schema_version: Literal['case-gold.v1'] = 'case-gold.v1'
    case_group_id: str
    input_digest: str
    source_file_hashes: list[str] = Field(min_length=1)
    split: Literal['development','holdout']
    status: Literal['draft','approved','adjudicated'] = 'draft'
    reviewers: list[str] = Field(default_factory=list)
    reviewed_at: str | None = None
    claims_complete: bool = False
    claims: list[GoldClaim] = Field(default_factory=list)
    burdens: list[GoldBurden] = Field(default_factory=list)
    citation_judgments: list[CitationJudgment] = Field(default_factory=list)

    @model_validator(mode='after')
    def review_contract(self):
        if self.status in {'approved','adjudicated'} and (not self.reviewers or not self.reviewed_at):raise ValueError('已审核Gold须提供审核人和时间')
        if self.status=='adjudicated' and len(set(self.reviewers))<2:raise ValueError('裁决Gold须记录至少两名参与审核人')
        labels=[c.label.strip() for c in self.claims]
        if len(labels)!=len(set(labels)):raise ValueError('Gold请求标签重复')
        aliases=[a.strip() for c in self.claims for a in [c.label,*c.aliases]]
        if len(aliases)!=len(set(aliases)):raise ValueError('Gold请求别名重复或冲突')
        if len({b.element_label.strip() for b in self.burdens})!=len(self.burdens):raise ValueError('Gold举证对象重复')
        keys=[(j.output_digest,j.fact_id,j.citation_index) for j in self.citation_judgments]
        if len(keys)!=len(set(keys)):raise ValueError('引文审核项重复')
        return self

def score_result(result,gold):
    run=result['run'];metrics=dict(claim_label_set_f1=None,burden_accuracy=None,citation_support_accuracy=None)
    response=dict(status='unscored',metrics=metrics,coverage=dict(citations_reviewed=0,citations_total=0,burdens_evaluated=0),note='Gold独立于模型输入；精确标签匹配不等于自由语义判定。')
    if run.get('demo') or run['status']!='completed':return dict(response,reason='demo_or_incomplete')
    if gold is None or gold.status not in {'approved','adjudicated'}:return dict(response,reason='no_reviewed_case_gold')
    manifest=result['input_manifest']
    if gold.input_digest!=run['input_digest'] or gold.case_group_id!=run['case_group_id'] or gold.split!=run['split'] or set(gold.source_file_hashes)!=set(manifest['source_file_hashes']):
        return dict(response,reason='gold_binding_mismatch')
    output=run['output']
    if digest(output)!=run['output_digest']:raise ValueError('输出摘要与输出不一致')
    aliases={a.strip():c.label.strip() for c in gold.claims for a in [c.label,*c.aliases]}
    expected={(c.label.strip(),c.applicability) for c in gold.claims}
    actual={(aliases.get(c['label'].strip(),c['label'].strip()),c['applicability']) for c in output['claims']}
    if gold.claims_complete and (expected or actual):metrics['claim_label_set_f1']=2*len(expected&actual)/(len(expected)+len(actual))
    # When a method receives a template, don't reward restating its burden labels.
    if not run.get('template_fields_provided') and gold.burdens:
        pred={e['label'].strip():e for e in output.get('elements',[]) if e.get('burden_origin')=='model_inferred'}
        metrics['burden_accuracy']=sum(pred.get(b.element_label.strip(),{}).get('burden_role')==b.role for b in gold.burdens)/len(gold.burdens)
        response['coverage']['burdens_evaluated']=len(gold.burdens)
    citations={(f['id'],i) for f in output['facts'] for i,_ in enumerate(f['citations'])}
    decisions=[j for j in gold.citation_judgments if j.output_digest==run['output_digest']]
    if any((j.fact_id,j.citation_index) not in citations for j in decisions):raise ValueError('引文审核引用不存在的输出位置')
    response['coverage'].update(citations_total=len(citations),citations_reviewed=len(decisions))
    if decisions:metrics['citation_support_accuracy']=sum(j.supported for j in decisions)/len(decisions)
    return dict(response,status='scored' if any(v is not None for v in metrics.values()) else 'unscored',reason='human_gold_exact_contract',gold_reviewers=gold.reviewers)
