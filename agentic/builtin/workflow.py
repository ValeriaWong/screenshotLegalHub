"""Five real skills compose local tools and optional Responses stage reasoning."""
from ..contracts import Plan, TaskSpec, ReviewResult, RetryPolicy, Limits
from ..primitives import digest
from ..planning import Workflow
from ..skills import Skill, SkillRegistry
from ..model import stage_prompt
from .contracts import (CaseInput, AnalysisPlan, PlanningOutput, FactsOutput, AssessmentOutput,
                        GapsOutput, ReportData, StageMeta, Reasoning, ReasoningOutput, Citation,
                        Finding, Gap)
from .tools import register_tools, STAGES

OUTPUTS = (PlanningOutput, FactsOutput, AssessmentOutput, GapsOutput, ReportData)
ATOMIC = ('plan_case','extract_records','assess_evidence','map_gaps','compose_report')

def review_stage(output, ctx):
    case = CaseInput.model_validate(ctx._task.input)
    sources = {s.source_id:s for s in case.sources}
    problems = []
    metas = output.get('stages', [output['meta']] if 'meta' in output else [])
    if 'stages' in output and [m['stage'] for m in metas] != STAGES:
        problems.append('report must contain each of the five stages in order')
    for meta in metas:
        if meta['prompt_digest'] != digest(stage_prompt(meta['stage'])):
            problems.append('prompt fingerprint mismatch')
        reasoning = meta['reasoning']
        for finding in reasoning['findings']:
            if finding['kind']=='observation' and not any(finding['text'] in c['quote'] for c in finding['citations']):
                problems.append('semantic summaries must be labeled inference')
        for item in reasoning['findings']+reasoning['gap_proposals']:
            for citation in item['citations']:
                source = sources.get(citation['source_id'])
                if not source or citation['quote'] not in source.text:
                    problems.append('citation is not an exact excerpt of a supplied source')
    if 'plan' in output:
        plan = output['plan']
        if plan['stages']!=STAGES or not {'identity','source_quality','chronology'} <= set(plan['focus']):
            problems.append('mandatory planning scope was changed')
    if 'ledger' in output:
        facts = output['ledger']['facts']
        if len(facts)!=len(sources) or {f['source_id'] for f in facts}!=set(sources):
            problems.append('ledger must preserve every source exactly once')
        for fact in facts:
            source = sources.get(fact['source_id'])
            if not source or any(fact[k]!=v for k,v in {
                'quote':source.text,'speaker':source.speaker,'time':source.time,
                'time_precision':source.time_precision,'source_kind':source.kind,
                'source_digest':digest(source.model_dump(mode='json'))}.items()):
                problems.append('ledger source or time was changed')
    if 'gaps' in output:
        gaps = {g['gap_id']:g for g in output['gaps']['items']}
        if gaps.get('authenticity',{}).get('status')!='needs_evidence' or gaps.get('professional',{}).get('status')!='needs_review':
            problems.append('external evidence or human review cannot be closed by inference')
        if any(not set(g['source_ids']) <= set(sources) for g in gaps.values()):
            problems.append('gap references an unknown source')
    if 'assessment' in output and any(not set(c['source_ids']) <= set(sources) for c in output['assessment']['checks']):
        problems.append('assessment references an unknown source')
    if 'conclusion' in output and output['conclusion'] != output['assessment']['conclusion']:
        problems.append('report conclusion changed the reviewed determination')
    if 'case' in output and output['case']!=case.model_dump(mode='json'):
        problems.append('report changed source input')
    if problems:
        return ReviewResult(status='REWORK',score=0,findings=list(dict.fromkeys(problems)),
                            suggested_actions=['repair only grounded interpretations; preserve source ledger and unresolved gaps'])
    return ReviewResult(status='PASS',findings=['schema, exact citations and stage invariants passed; substantive interpretation still needs review'])

class EvidenceSkills:
    def __init__(self, model=None):
        self.model = model

    async def reason(self, stage, case, ctx, code):
        receipt = None
        if self.model:
            raw = (await ctx.call_tool('stage_reasoning',dict(stage=stage,
                payload={'case':case.model_dump(mode='json'),'stage_result':code},
                repair_findings=ctx.review.findings if ctx.review and ctx.review.status=='REWORK' else []))).data
            receipt = ReasoningOutput.model_validate(raw)
            reasoning = receipt.reasoning
        else:
            first = case.sources[0]
            citation = Citation(source_id=first.source_id,quote=first.text)
            summaries = {
                'planning':'按输入问题与词面线索确定分析重点；保留身份、来源和时间检查。',
                'facts':'逐条整理调用方文本、金额提及与时间精度；不把文本声明直接认定为现实事件。',
                'assessment':'执行规划范围内的确定性检查，竞争性解释与条件语义仍属于候选判断。',
                'gaps':'代码可补齐结构和引用；证据真实性、缺失日期和专业判断仍需外部材料或人工。',
                'synthesis':'已形成可追溯的材料梳理报告，结论保留未知前提，不作确定法律认定。',
            }
            reasoning = Reasoning(focus=code.get('focus',[]),findings=[Finding(text=summaries[stage],kind='inference',
                citations=[citation],uncertainty='本阶段运行有限代码规则；未调用模型，不能替代完整语义理解或专业复核。')])
        return StageMeta(stage=stage,mode='model' if self.model else 'code',prompt_digest=digest(stage_prompt(stage)),
                         reasoning=reasoning,model_receipt=receipt)

    async def planning(self, value, ctx):
        raw = (await ctx.call_tool('plan_case',value.model_dump(mode='json'))).data
        meta = await self.reason('planning',value,ctx,raw)
        plan = AnalysisPlan.model_validate(raw)
        plan.focus = list(dict.fromkeys(plan.focus+meta.reasoning.focus))
        return PlanningOutput(plan=plan,meta=meta)

    async def facts(self, value, ctx):
        raw = (await ctx.call_tool('extract_records',value.model_dump(mode='json'))).data
        meta = await self.reason('facts',value,ctx,{'ledger':raw,'planning':ctx.dependencies['planning']['plan']})
        return FactsOutput(ledger=raw,meta=meta)

    async def assessment(self, value, ctx):
        raw = (await ctx.call_tool('assess_evidence',dict(ledger=ctx.dependencies['facts']['ledger'],
                                                       plan=ctx.dependencies['planning']['plan']))).data
        meta = await self.reason('assessment',value,ctx,{'assessment':raw,'facts':ctx.dependencies['facts']})
        return AssessmentOutput(assessment=raw,meta=meta)

    async def gaps(self, value, ctx):
        raw = (await ctx.call_tool('map_gaps',dict(ledger=ctx.dependencies['facts']['ledger'],
                                                 assessment=ctx.dependencies['assessment']['assessment']))).data
        meta = await self.reason('gaps',value,ctx,{'gaps':raw,'assessment':ctx.dependencies['assessment']})
        # Model proposals are carried forward as candidates; no inference closes evidence/human gaps.
        seen = set()
        for parent in [ctx.dependencies['planning']['meta'],ctx.dependencies['facts']['meta'],ctx.dependencies['assessment']['meta'],meta.model_dump(mode='json')]:
            for proposal in parent['reasoning']['gap_proposals']:
                key = digest(proposal)
                if key in seen:
                    continue
                seen.add(key)
                raw['items'].append(Gap(gap_id='suggested_'+key[:16],title=proposal['title'],method=proposal['method'],
                    status={'evidence':'needs_evidence','human':'needs_review'}.get(proposal['method'],'candidate'),
                    rationale='阶段推理建议，尚未独立验证；不得覆盖必要补证或人工复核项。',action=proposal['action'],
                    source_ids=list(dict.fromkeys(c['source_id'] for c in proposal['citations']))).model_dump(mode='json'))
        if self.model:
            for gap in raw['items']:
                if gap['gap_id']=='semantic':
                    gap['action']='阶段模型已运行；复核候选解释、反向材料和引用的实质支持关系。'
        return GapsOutput(gaps=raw,meta=meta)

    async def synthesis(self, value, ctx):
        arguments = {'case':value.model_dump(mode='json'),**ctx.dependencies}
        raw = (await ctx.call_tool('compose_report',arguments)).data
        meta = await self.reason('synthesis',value,ctx,{'assessment':raw['assessment'],'gaps':raw['gaps'],
                                                       'stage_findings':[s['reasoning'] for s in raw['stages']]})
        raw['stages'].append(meta.model_dump(mode='json'))
        return ReportData.model_validate(raw)

def components(model=None):
    tools, skills = register_tools(), SkillRegistry()
    if model:
        tools.register(model.tool())
    handlers = EvidenceSkills(model)
    for stage, atomic, output_model in zip(STAGES, ATOMIC, OUTPUTS):
        handler = getattr(handlers,stage)
        skills.register(Skill('evidence_'+stage,'0.2.'+digest(stage_prompt(stage))[:16],CaseInput,output_model,handler,
            tools=(atomic,'stage_reasoning') if model else (atomic,),repair=handler,rules=(review_stage,),
            description='包内证据分析阶段：'+stage,
            constraints=('exact source citations','no invented facts','bounded repair','unverified model interpretations')))
    def plan(value):
        dependencies = [[],['planning'],['planning','facts'],['planning','facts','assessment'],['planning','facts','assessment','gaps']]
        return Plan(tasks=[TaskSpec(task_id=stage,stage_id=i,skill='evidence_'+stage,
            dependencies=dependencies[i],input=value.model_dump(mode='json'),timeout_seconds=120 if model else 15,
            retry_policy=RetryPolicy(max_attempts=1)) for i,stage in enumerate(STAGES)],
            stage_timeout_seconds=360 if model else 30)
    version = '0.2.'+digest([stage_prompt(s) for s in STAGES]+([model.version] if model else []))[:16]
    return tools,skills,[Workflow('evidence_analysis',version,CaseInput,plan,
        '独立五阶段证据分析：规划、事实、争点、缺口与报告数据；保留推断和待补证项')]

def runtime_limits(model=None):
    return Limits(max_model_calls=10 if model else 0,max_tokens=2000000 if model else 0,
                  max_cost=5 if model else 0,timeout_seconds=900 if model else 60)
