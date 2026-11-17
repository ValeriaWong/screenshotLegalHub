"""Commit direct author drafts into the v2 review queue without external API calls.

Agents own disjoint case folders; root owns shared manifest/report and rendering.
"""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read,save,normalize,status


def commit(ident,author):
    directory=OUT/'zh'/ident;source=read(directory/'source.json')
    if read(directory/'status.json')['phase']=='rendered':raise ValueError('Rendered cases are immutable here')
    draft=read(directory/'direct.draft.json')
    revised=read(directory/'direct.revised.json') if (directory/'direct.revised.json').exists() else copy.deepcopy(draft)
    review=read(directory/'codex.review.json')
    if not review.get('full_judgment_read'):raise ValueError('Full judgment reading must be recorded')
    reading=read(directory/'source.reading.json')
    if reading.get('source_chars')!=len(source['text']) or reading.get('source_paragraphs')!=len(source['paragraphs']):
        raise ValueError('Source reading counts must match the full archived judgment')
    if revised.get('suitability',{}).get('decision')=='defer':
        reason=revised['suitability'].get('reason','')
        if len(reason)<25:raise ValueError('Deferral needs a case-specific source reason')
        save(directory/'deferred.candidate.json',revised)
        status(directory,'deferred',reason=reason,method='codex_agent_direct_reading',author=author)
        return
    final,errors=normalize(revised,source)
    if errors:
        save(directory/'case.validation.json',{'errors':errors});raise ValueError(errors)
    if not final.get('facts'):raise ValueError('A grounded fact ledger is required')
    final['author']=author+'; direct full-judgment reading and writing; no external API'
    final['status']='agent_authored_candidate_pending_review'
    final['second_pass_edits']=review.get('issues',[])
    audit=read(directory/'source.audit.json') if (directory/'source.audit.json').exists() else {}
    final['source_metadata_warnings']=audit.get('warnings',[])
    final['raw_source_case_no']=source['case_no']
    if source.get('parent_case_id'):final['parent_case_id']=source['parent_case_id']
    if any('案号字段' in w for w in audit.get('warnings',[])) and audit.get('case_no_from_text'):
        final['case_no']=audit['case_no_from_text']
        final['case_no_status']='recovered_from_judgment_opening_pending_identity_review'
    review.update(author=author,independent_reviewer=False,new_human_score=None,difficulty_certified=False)
    save(directory/'codex.review.json',review)
    save(directory/'case.json',final)
    save(directory/'case.checks.json',{'errors':[],'source_spans_exact':True,'human_review':False,'difficulty_certified':False})
    status(directory,'reviewed',method='codex_agent_direct_writing',author=author,
           source_spans_exact=True,difficulty_certified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('ids');p.add_argument('--author',required=True);a=p.parse_args()
    for ident in a.ids.split(','):
        commit(ident,a.author);print(ident+' committed',flush=True)
