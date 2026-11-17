"""Verify completeness and cited spans of alternative full-reading records."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save

def main():
    expected=checked=0;pending=[];records=[]
    for item in read(OUT/'manifest.json')['representatives']:
        d=OUT/'zh'/item['id']
        if read(d/'status.json')['phase']!='deferred':continue
        indices=set(item['alternatives'])-{item['source_index']};expected+=len(indices);seen={}
        for name in ['alternatives.review.json','root.alternatives.review.json']:
            if not (d/name).exists():continue
            review=read(d/name);assert review.get('full_judgment_read'),(item['id'],name)
            for r in review.get('alternatives',[]):
                index=r['source_index'];assert index in indices,(item['id'],index)
                s=read(d/'alternatives'/f'{index:04d}'/'source.json')
                assert r['source_chars']==len(s['text']) and r['source_paragraphs']==len(s['paragraphs']),(item['id'],index,'reading count')
                assert r.get('decision') in ['usable','defer','candidate'],(item['id'],index,'decision')
                assert len(r.get('reason',''))>=25,(item['id'],index,'reason')
                for ref in r.get('source_refs',[]):
                    first=next(p for p in s['paragraphs'] if p['id']==ref['source_id'])
                    last=next(p for p in s['paragraphs'] if p['id']==ref.get('source_end_id',ref['source_id']))
                    assert ref['quote'] in s['text'][first['char_start']:last['char_end']],(item['id'],index,'nonliteral quote')
                seen[index]=r
        checked+=len(seen);records.append({'parent_case_id':item['id'],'expected_indices':sorted(indices),'reviewed_indices':sorted(seen)})
        for index in sorted(indices-set(seen)):pending.append({'parent_case_id':item['id'],'source_index':index})
    result={'expected_alternatives_of_deferred_cases':expected,'full_reading_records_verified':checked,
        'complete':not pending,'pending':pending,'records':records,'quality_certified':False}
    save(OUT/'alternatives.verification.json',result);print({'expected':expected,'checked':checked,'pending':len(pending)})

if __name__=='__main__':main()
