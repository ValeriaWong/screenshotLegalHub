"""Publish the exact source blockers and alternative-reading records."""
from pathlib import Path
import sys
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save

def main():
    records=[];states=Counter();manifest=read(OUT/'manifest.json')
    rendered_alternatives={}
    for item in manifest.get('supplemental_representatives',[]):
        if read(OUT/'zh'/item['id']/'status.json')['phase']=='rendered':
            rendered_alternatives.setdefault(item['parent_case_id'],[]).append(item['id'])
    for item in manifest['representatives']:
        d=OUT/'zh'/item['id'];state=read(d/'status.json');states[state['phase']]+=1
        if state['phase']!='deferred':continue
        audit=read(d/'source.audit.json');source=read(d/'source.json')
        alternatives=[]
        for name in ['alternatives.review.json','root.alternatives.review.json']:
            if (d/name).exists():alternatives.extend(read(d/name).get('alternatives',[]))
        records.append({'id':item['id'],'cause':item['cause'],'title':source['title'],
            'case_no_display':audit.get('recovered_fields',{}).get('case_no') or source['case_no'],
            'reason':state['reason'],'alternative_indices':[i for i in item['alternatives'] if i!=item['source_index']],
            'alternative_reviews':alternatives,'rendered_alternative_ids':rendered_alternatives.get(item['id'],[]),'primary_source_unchanged':True})
    remaining=[r for r in records if not r['rendered_alternative_ids']]
    save(OUT/'source_gaps.json',{'records':records,'phase_counts':dict(states),'unprocessed_labels':states['source_prepared'],
        'labels_still_without_candidate':len(remaining),'labels_recovered_by_alternative':len(records)-len(remaining),
        'scope':'local historical source pool, not the national cause catalog','source_content_fabricated':False})
    lines=['# 第三轮来源缺口','',
        f'当前 {len(records)} 宗原代表暂缓，其中 {len(records)-len(remaining)} 种标签已由独立候补生成截图，仍有 {len(remaining)} 种标签缺少可生成内容的来源。原代表阶段为 {dict(states)}。','',
        '本项目可以依据判决生成可能的聊天场景，但不能把“提交过微信截图”直接写成具体确认、拒绝或付款。优先换用披露更多对话细节的同案由判决；无需为了补齐案由而制作原文没有依据的核心证据。不同判决保持独立，不拼接成同一案。','',
        '候补阅读完整性见 [alternatives.verification.json](alternatives.verification.json)。原代表的暂缓记录与全文始终保留；即使候补可生成，也不会覆盖原代表。','']
    for r in records:
        ident=r['id'];d=OUT/'zh'/ident
        lines+=['## '+ident+' · '+r['case_no_display'],'',r['cause'],'',r['title'],'',
            '缺口：'+r['reason'],'',f'[原代表全文](zh/{ident}/judgment.txt) · [阅读约束](zh/{ident}/source.reading.json) · [暂缓记录](zh/{ident}/status.json)','']
        if r['rendered_alternative_ids']:
            lines+=['此标签已有独立候补候选：'+ ' · '.join(f'[{a}截图及来源](zh/{a}/review.html)' for a in r['rendered_alternative_ids'])+'。原代表继续保留暂缓。','']
        else:lines+=['此标签仍缺可用候选。','']
        if not r['alternative_indices']:lines+=['本地同标签没有其他判决。','']
        else:
            seen={a['source_index']:a for a in r['alternative_reviews']}
            for index in r['alternative_indices']:
                a=seen.get(index)
                lines += [f'- 候补 {index}：[全文](zh/{ident}/alternatives/{index:04d}/judgment.txt)。'+
                    (f"全文已读，{a['decision']}：{a['reason']}" if a else '全文待复核。')]
            lines+=['']
        for name in ['alternatives.review.json','root.alternatives.review.json']:
            if (d/name).exists():lines+=[f'[候补逐份复核及原文依据：{name}](zh/{ident}/{name})','']
    (OUT/'SOURCE_GAPS.md').write_text('\n'.join(lines),encoding='utf-8');print({'source_gaps':len(records)})

if __name__=='__main__':main()
