"""Generic deterministic, conservative skills. All legal templates live in Matter Packs."""
from screenshotlegal.domain.common.models import Entity, SkillResult

def entity(id, kind, title, refs=None, status='proposed', **details):
    return Entity(id=id, kind=kind, title=title, source_refs=refs or [], status=status, details=details)

class DeterministicSkill:
    def __init__(self, manifest):
        self.manifest = manifest

    async def run(self, context, input):
        p = input.values
        cap = self.manifest.capability
        result=[]
        if cap == 'evidence.perceive':
            result=[entity('perception','perception','已读取持久化感知结果',count=len(p['messages']))]
        elif cap == 'fact.observe':
            result=[entity('observed.'+r['id'],'fact',r['quote'],[r['id']],status='observed',epistemic_status='observed',note='原文记录，未认证事实真实发生',evidence_id=r['evidence_id']) for r in p['source_refs']]
        elif cap == 'timeline.build':
            result=[entity('event.'+m['id'],'event',m['text'],m['source_refs'],timestamp=m['timestamp'],party=m['speaker'],event_type=m['event_type'],message_id=m['id']) for m in p['messages']]
        elif cap == 'matter.route':
            result=[entity('matter.candidate','matter_candidate',p['matter']['manifest']['name_zh'],basis='用户选择；候选并非法律结论')]
        elif cap == 'claim.identify':
            for claim in p['matter']['claims']:
                result.append(entity('claim.'+claim['id'],'claim',claim['title'],remedy=claim['remedy']))
                for element in claim['elements']:
                    result.append(entity(element['id'],'element',element['title'],claim_id='claim.'+claim['id']))
        elif cap == 'fact.instantiate':
            for claim in p['matter']['claims']:
                for el in claim['elements']:
                    for fact in el['facts']:
                        result.append(entity('fact.'+fact['id'],'fact',p['case']['title']+'：'+fact['question'],status='unknown',template_id=fact['id'],element_id=el['id'],claim_id='claim.'+claim['id']))
        elif cap == 'burden.assign':
            templates={f['id']:f for c in p['matter']['claims'] for el in c['elements'] for f in el['facts']}
            result=[entity('burden.'+f['id'],'burden',templates[f['details']['template_id']]['burden'],fact_id=f['id'],authority_ids=templates[f['details']['template_id']]['authority_ids']) for f in p['facts']]
        elif cap == 'evidence.map':
            templates={f['id']:f for c in p['matter']['claims'] for el in c['elements'] for f in el['facts']}
            for fact in p['facts']:
                template=templates[fact['details']['template_id']]
                for msg in [*p['messages'], *[dict(id=r['id'],text=r['quote'],source_refs=[r['id']],evidence_id=r['evidence_id']) for r in p['source_refs'] if r.get('source_kind')=='document']]:
                    relation = 'contradicts' if any(s in msg['text'] for s in template['negative_signals']) else 'supports' if any(s in msg['text'] for s in template['signals']) else None
                    if relation:
                        result.append(entity('link.'+fact['id']+'.'+msg['id'],'evidence_link',msg['text'],msg['source_refs'],fact_id=fact['id'],evidence_id=msg['evidence_id'],relation=relation,strength='weak',rationale='确定性关键词线索，需人工结合原始记录核实；不等同证明成立'))
        elif cap == 'evidence.strength':
            for fact in p['facts']:
                links=[l for l in p['evidence_links'] if l['details']['fact_id']==fact['id']]
                support=any(l['details']['relation']=='supports' for l in links)
                oppose=any(l['details']['relation']=='contradicts' for l in links)
                status='mixed' if support and oppose else 'supported' if support else 'contradicted' if oppose else 'unknown'
                result.append(entity('strength.'+fact['id'],'strength','待核实的证据线索强度',status=status,fact_id=fact['id'],strength='weak' if links else 'unknown'))
        elif cap == 'evidence.gap':
            templates={f['id']:f for c in p['matter']['claims'] for el in c['elements'] for f in el['facts']}
            for fact in p['facts']:
                template=templates[fact['details']['template_id']]
                # Chat-only corroboration never substitutes for expected original records.
                result.append(entity('gap.'+fact['id'],'gap','补充：'+'、'.join(template['expected_evidence']),fact_id=fact['id'],element_id=fact['details']['element_id'],claim_id=fact['details']['claim_id'],why_needed=template['question'],suggested_evidence_type=template['expected_evidence'],priority='high',authority_ids=template['authority_ids']))
        elif cap == 'contradiction.detect':
            for fact in p['facts']:
                links=[l for l in p['evidence_links'] if l['details']['fact_id']==fact['id']]
                yes=[l for l in links if l['details']['relation']=='supports'];no=[l for l in links if l['details']['relation']=='contradicts']
                if yes and no:
                    result.append(entity('conflict.'+fact['id'],'contradiction','同一事项存在不一致陈述',list(dict.fromkeys(yes[0]['source_refs']+no[0]['source_refs'])),status='mixed',fact_a=fact['id'],fact_b=fact['id'],evidence_a=yes[0]['details']['evidence_id'],evidence_b=no[0]['details']['evidence_id'],conflict_type='inconsistent_statement',severity='high',explanation=yes[0]['title']+' / '+no[0]['title']))
        elif cap in ['strategy.generate','adversarial.analyze','strategy.verify']:
            graph=p['proof_graph']
            facts=[e for e in graph if e['kind']=='fact'];gaps=[e for e in graph if e['kind']=='gap'];conflicts=[e for e in graph if e['kind']=='contradiction'];links=[e for e in graph if e['kind']=='evidence_link']
            refs=list(dict.fromkeys(r for l in links for r in l['source_refs']))
            if not refs:
                result=[]
            elif cap=='strategy.generate':
                result=[entity('strategy.1','strategy','先核实款项性质及交付，再整理本金请求',refs,supporting_fact_ids=[f['id'] for f in facts],risk_fact_ids=[c['details']['fact_a'] for c in conflicts],gap_ids=[g['id'] for g in gaps],counterargument_ids=[c['id'] for c in conflicts],description='根据已形成的证据关系补充原始流水、完整聊天及还款记录；冲突事项进入人工核实，暂不作胜诉概率判断。')]
            elif cap=='adversarial.analyze':
                result=[entity('defense.'+c['id'],'defense','核实相反陈述及可能抗辩',c['source_refs'],fact_id=c['details']['fact_a'],contradiction_id=c['id']) for c in conflicts]
            else:
                ids={e['id'] for e in graph};strategies=[e for e in graph if e['kind']=='strategy']
                for strategy in strategies:
                    targets=sum((strategy['details'].get(k,[]) for k in ['supporting_fact_ids','risk_fact_ids','gap_ids','counterargument_ids']),[])
                    if any(t not in ids for t in targets):
                        raise ValueError('Ungrounded strategy target')
                result=[entity('verification','verification','策略结构引用检查通过；法律判断仍待人审',refs,verified_target_ids=[s['id'] for s in strategies])]
        else:
            raise ValueError('No builtin implementation for capability')
        return SkillResult(entities=result, warnings=['确定性演示分析；所有法律规则及输出均未经专家审核'], requires_review=False)
