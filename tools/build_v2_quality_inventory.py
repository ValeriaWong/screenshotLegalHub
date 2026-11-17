"""Expose review priorities; counts and literal checks are not quality scores."""
import sys,re
from pathlib import Path
from collections import Counter
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save,processing_items

PRIORITY_LABELS={
    'unknown_chronology_cannot_be_scored_as_exact_time_recovery':'日期未披露：不用于精确时间恢复',
    'no_verbatim_dialogue_fact_paraphrase_requires_naturalness_review':'无聊天原话：复核事实转写和自然感',
    'single_image_case_does_not_demonstrate_cross_page_reasoning':'单图：未体现跨页推理',
    'question_numeric_context_review_not_automatic_leak_verdict':'数值题上下文筛查：查看专项复核，合理算术不算泄漏',
    'metadata_or_cause_label_review':'来源字段或案由标签需核对',
    'original_medium_differs_review_reconstruction_disclosure':'通信载体或语音转写：核对重建说明',
    'very_sparse_dialogue_coverage_only_not_ready_for_hardness_evaluation':'对话稀疏：仅覆盖候选，未达到困难集要求',
    'multiple_crops_of_one_message_are_not_multiple_reasoning_hops':'一条消息多张滚动图：不算多跳推理',
    'unresolved_source_attribution_not_ready_for_speaker_gold':'说话人来源冲突：不能作为唯一主体金标'}

def main():
    records=[];flags=Counter()
    for item in processing_items():
        d=OUT/'zh'/item['id'];state=read(d/'status.json')
        r={'id':item['id'],'cause':item['cause'],'phase':state['phase'],'review_priorities':[]}
        if state['phase']=='deferred':
            r.update(reason=state.get('reason'),alternative_source_indices=[i for i in item['alternatives'] if i!=item['source_index']])
            if (d/'alternatives.review.json').exists():r['alternative_review']=read(d/'alternatives.review.json')
            if (d/'root.alternatives.review.json').exists():r['root_alternative_review']=read(d/'root.alternatives.review.json')
        if state['phase']=='rendered':
            c=read(d/'case.json');render=read(d/'render.json')
            origins=Counter(m['origin_type'] for m in c['messages'])
            r.update(messages=len(c['messages']),images=len(render['images']),conversations=len(c['conversations']),
                origin_counts=dict(origins),questions=len(c['questions']),
                unknown_dates=sum(not m.get('timestamp') and not m.get('time_label') for m in c['messages']),
                synthetic_minute_messages=sum(m.get('minute_basis')=='synthetic_layout_only' and bool(m.get('timestamp')) for m in c['messages']),
                quoted_non_wechat_media=[m['id'] for m in c['messages'] if m.get('original_medium')],
                source_metadata_warnings=c.get('source_metadata_warnings',[]),
                source_ambiguities=c.get('source_ambiguities',[]),
                scroll_crop_pages=sum(bool(i.get('scroll_fragment')) for i in render['images']))
            if r['images']==1:r['review_priorities'].append('single_image_case_does_not_demonstrate_cross_page_reasoning')
            if r['messages']<4:r['review_priorities'].append('very_sparse_dialogue_coverage_only_not_ready_for_hardness_evaluation')
            if not origins['verbatim_quote']:r['review_priorities'].append('no_verbatim_dialogue_fact_paraphrase_requires_naturalness_review')
            if r['unknown_dates']:r['review_priorities'].append('unknown_chronology_cannot_be_scored_as_exact_time_recovery')
            if r['quoted_non_wechat_media']:r['review_priorities'].append('original_medium_differs_review_reconstruction_disclosure')
            if r['source_metadata_warnings']:r['review_priorities'].append('metadata_or_cause_label_review')
            if r['source_ambiguities']:r['review_priorities'].append('unresolved_source_attribution_not_ready_for_speaker_gold')
            if r['scroll_crop_pages']:r['review_priorities'].append('multiple_crops_of_one_message_are_not_multiple_reasoning_hops')
            visible=' '.join(p['name'] for p in c['participants'])+' '+' '.join(conv['title'] for conv in c['conversations'])+' '+' '.join(m.get('text','')+' '+str(m.get('attachment',{}).get('rows',[]))+' '+str(m.get('transfer',{}).get('amount',''))+' '+(m.get('timestamp') or m.get('time_label') or '') for m in c['messages'])
            shown_numbers={Decimal(n) for n in re.findall(r'\d+(?:\.\d+)?',visible.replace(',',''))}
            r['question_numeric_review_leads']=[]
            for q in c['questions']:
                missing=[n for n in re.findall(r'\d+(?:\.\d+)?',q['question'].replace(',','')) if Decimal(n) not in shown_numbers]
                if missing:r['question_numeric_review_leads'].append({'id':q['id'],'question':q['question'],'numbers':missing})
            if r['question_numeric_review_leads']:r['review_priorities'].append('question_numeric_context_review_not_automatic_leak_verdict')
        for flag in r['review_priorities']:flags[flag]+=1
        records.append(r)
    save(OUT/'quality_inventory.json',{'records':records,'priority_counts':dict(flags),
        'human_scores':None,'difficulty_certified':False,'purpose':'review routing, not automated acceptance or hardness certification'})
    shortlist=[r for r in records if r.get('images',0)>=2 and r.get('conversations',0)>=2 and r.get('origin_counts',{}).get('verbatim_quote',0)>=4]
    save(OUT/'review_shortlist.json',{'selection_rule':'at least 2 screenshots, 2 conversations, 4 verbatim messages; order by verbatim message count',
        'records':sorted(shortlist,key=lambda r:r['origin_counts']['verbatim_quote'],reverse=True),
        'difficulty_certified':False,'purpose':'prioritize user review; not an automatically accepted benchmark split'})
    lines=['# 第三轮质量复核清单','',
        '本轮先完成案由覆盖候选。多张截图可能只是滚动长原话，不能据此认定多跳难度。逐字引用核验只能验证来源，不证明对话自然或题目够难。人工确认后再进入更严格的难度筛选。','',
        '详细机器可读记录：[quality_inventory.json](quality_inventory.json)。优先级统计：'+str(dict(flags))+'。','',
        '| 案件 | 来源标签末级 | 状态 | 图 / 消息 / 原话 | 优先复核 |','|---|---|---|---|---|']
    for r in records:
        title=r['cause'].split('>')[-1].replace('\n',' / ').replace('|','/')
        count=f"{r.get('images','—')} / {r.get('messages','—')} / {r.get('origin_counts',{}).get('verbatim_quote','—')}"
        link=f"zh/{r['id']}/review.html" if r['phase']=='rendered' else f"zh/{r['id']}/status.json"
        note='；'.join(PRIORITY_LABELS.get(p,p) for p in r['review_priorities']) or r.get('reason','无上述筛查标记，仍待人工复审')
        lines.append(f"| [{r['id']}]({link}) | {title} | {r['phase']} | {count} | {note.replace('|','/')} |")
    (OUT/'QUALITY_REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print({'processed':len(records),'priority_counts':dict(flags)})

if __name__=='__main__':main()
