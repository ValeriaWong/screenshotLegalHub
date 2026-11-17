"""Apply the context-reviewed short-quote targets; retain the audit snapshot."""
import copy,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save
from tools.v2_root_review import revise

def main():
    report=read(OUT/'peer.short_quotes.review.json');by_case=defaultdict(list);applied=[]
    for issue in report['issues']:
        assert issue['model_confirmed_after_full_paragraph_read'] and issue['decision']=='misaligned_unique_target'
        by_case[issue['case_id']].append(issue)
    for ident,issues in by_case.items():
        d=OUT/'zh'/ident;s=read(d/'source.json');c=copy.deepcopy(read(d/'case.json'));notes=[]
        for issue in issues:
            target=issue['target_ref'];start,end=target['char_start'],target['char_end']
            assert s['text'][start:end]==issue['text']==target['quote']
            p=next(p for p in s['paragraphs'] if p['id']==target['source_id'])
            assert p['char_start']<=start<end<=p['char_end']
            assert target['surrounding_original'] in s['text']
            for mid in issue['message_ids']:
                m=next(m for m in c['messages'] if m['id']==mid);assert m['text']==issue['text']
                refs=[r for r in m['source_refs'] if r['quote']==issue['text']];assert len(refs)==1
                ref=refs[0]
                ref.update(source_id=target['source_id'],char_start=start,char_end=end,paragraph_ids=[target['source_id']])
                ref.pop('source_end_id',None)
                applied.append({'case_id':ident,'message_id':mid,'target':{k:target[k] for k in ['source_id','quote','char_start','char_end']}})
            notes.append({'severity':'major','message_ids':issue['message_ids'],'problem':issue['reason'],
                'change':'按完整段落中的说话人/日期上下文校正来源字符坐标；保持原话、时间与说话人不变。详见../../peer.short_quotes.review.json。'})
        print(ident,revise(d,c,notes))
    save(OUT/'peer.short_quotes.corrections.json',{'review':'peer.short_quotes.review.json','applied_targets':applied,'model_review_not_human':True})

if __name__=='__main__':main()
