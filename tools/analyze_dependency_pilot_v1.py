"""Audit preserved requests/responses against a development oracle, no legal grading."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def lines(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
def put(path,value,as_lines=False):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        if as_lines:
            for row in value:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        else:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def parse(raw):
    raw=raw.strip()
    if raw.startswith('```') and raw.endswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
    return json.loads(raw)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    run=(ROOT/args.run).resolve();run.relative_to(ROOT)
    targets=[run/'analysis.development.jsonl',run/'analysis_summary.json']
    assert not any(p.exists() for p in targets),'Analysis files already exist; do not overwrite.'
    originals={p:sha(p) for p in run.glob('*') if p.is_file()}
    spec=json.loads((run/'run.json').read_text(encoding='utf-8'))
    reqs=lines(run/'requests.jsonl')
    assert hashlib.sha256(json.dumps(reqs,ensure_ascii=False,sort_keys=True).encode()).hexdigest()==spec['requests_sha256']
    lookup={r['request_id']:r for r in reqs};expected={r['request_id']:r for r in lines(run/'expected.reviewer_only.jsonl')}
    preds=lines(run/'predictions.jsonl')
    assert len(preds)==len(lookup)==spec['planned_requests'] and len({r['request_id'] for r in preds})==len(preds)
    analyses=[];groups={}
    for r in preds:
        q=lookup[r['request_id']]
        assert r['images']==q['images'] and r['image_hashes']==q['image_hashes']
        assert r['prompt_sha256']==hashlib.sha256(q['prompt'].encode()).hexdigest()
        row={'request_id':r['request_id'],'condition':q['condition'],'task_id':q['task_id'],
             'request_status':r['status'],'author_reference_answer':expected[r['request_id']]['author_expected_answer'],
             'reference_kind':'finite_model_development_oracle_not_legal_gold','json_decoded':False,
             'numeric_legal_score':None,'professional_signoff':False,'reference_issues':[],'non_verbatim_quote_candidates':[]}
        if 'raw' in r:
            try:
                parsed=parse(r['raw']);row['json_decoded']=True;row['raw_answer']=parsed.get('answer')
                for field in ['identity_alignment','time_condition','legal_conclusion']:
                    for ref in parsed.get(field,{}).get('evidence_refs',[]):
                        valid_ids={f'P{i}' for i in range(len(q['images']))}
                        if ref.get('image_id') not in valid_ids:
                            row['reference_issues'].append({'field':field,'image_id':ref.get('image_id'),'reason':'image_not_supplied'})
                            continue
                        index=int(ref['image_id'][1:]);path=ROOT/q['images'][index]
                        case=json.loads((path.parent.parent/'case.json').read_text(encoding='utf-8'))
                        role=q['image_roles'][index]
                        texts=[m['text'] for m in case['messages'] if m['conversation_id']==role]
                        quote=ref.get('quote','')
                        if not any(quote in text for text in texts):
                            row['non_verbatim_quote_candidates'].append({'field':field,'image_id':ref['image_id'],'quote':quote,
                                'status':'needs_manual_review_not_automatic_semantic_error'})
            except (ValueError,TypeError,AttributeError):row['json_decode_issue']=True
        row['development_label_agreement_on_valid_response']=(r['answer']==row['author_reference_answer']) if r['status']=='ok' else None
        analyses.append(row)
        condition=q['condition'];group=('full' if condition=='full' else 'single' if condition.startswith('single_') else
            'remove_one' if condition.startswith('without_') else condition)
        groups.setdefault(group,[]).append(row)
    for path,digest in spec['source_hashes'].items():assert sha(ROOT/path)==digest
    summary={'protocol':spec['protocol'],'requests':len(preds),'status_counts':dict(Counter(r['status'] for r in preds)),
        'groups':{},'image_not_supplied_reference_count':sum(len(r['reference_issues']) for r in analyses),
        'non_verbatim_quote_candidates':sum(len(r['non_verbatim_quote_candidates']) for r in analyses),
        'numeric_legal_scores':None,'professional_signoff':False,'independent_semantic_review':'pending',
        'source_hashes_verified':len(spec['source_hashes']),'raw_files_unchanged':True,'api_calls_in_analysis':0}
    for name,rows in groups.items():
        valid=[r for r in rows if r['request_status']=='ok']
        summary['groups'][name]={'planned':len(rows),'valid':len(valid),
            'agreed_with_development_reference':sum(r['development_label_agreement_on_valid_response'] for r in valid),
            'disagreement_request_ids':[r['request_id'] for r in valid if not r['development_label_agreement_on_valid_response']],
            'non_valid_request_ids':[r['request_id'] for r in rows if r['request_status']!='ok']}
    put(targets[0],analyses,as_lines=True)
    assert all(sha(path)==digest for path,digest in originals.items())
    put(targets[1],summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
