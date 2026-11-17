"""Verify frozen calibration bytes/coverage and gate externally completed reviews."""
import argparse, hashlib, itertools, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def rows(p): return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def local(base,value):
    target=(base/value).resolve()
    if not target.is_relative_to(base.resolve()):raise ValueError('Artifact path escapes package')
    return target

def verify_artifacts(folder):
    if (folder/'.incomplete').exists():raise ValueError('Incomplete calibration')
    manifest=rows(folder/'artifact_manifest.jsonl')
    for item in manifest:
        file=local(folder,item['path'])
        if digest(file)!=item['sha256'] or file.stat().st_size!=item['bytes']:
            raise ValueError('Artifact drift: '+item['path'])
    subsets=rows(folder/'subset_manifest.jsonl');conditions=rows(folder/'interventions.jsonl')
    if len({s['subset_id'] for s in subsets})!=len(subsets):raise ValueError('Duplicate subset ID')
    answers=rows(folder/'author_answers.reviewer_only.jsonl')
    if {a['subset_id'] for a in answers}!={s['subset_id'] for s in subsets}:raise ValueError('Missing subset answer range')
    image_count=0
    for condition in conditions:
        pages=condition['pages'];image_count+=len(pages)
        expected={
            frozenset(p['image_id'] for i,p in enumerate(pages) if mask&(1<<i)) for mask in range(2**len(pages))}
        observed=[frozenset(s['image_ids']) for s in subsets if s['condition_id']==condition['condition_id']]
        if set(observed)!=expected or len(observed)!=len(expected):raise ValueError('Subset enumeration incomplete')
    allowed={'task_id','question_id','question','scope','images','reviewer_identity','answer','citations','missing_evidence','sufficiency','minimality','alternative_supports','counterevidence','ambiguity','reviewed_at'}
    for label in ['a','b']:
        package=folder/'blind_review'/('reviewer_'+label);tasks=read(package/'tasks.json')
        if len(tasks)!=len(subsets):raise ValueError('Blind package incomplete')
        for task in tasks:
            if set(task)!=allowed:raise ValueError('Unexpected field in blind task')
            for image in task['images']:
                if set(image)!={'file','sha256'} or digest(local(package,image['file']))!=image['sha256']:
                    raise ValueError('Blind image drift')
        names={p.name for p in package.rglob('*') if p.is_file()}
        if names&{'author_answers.reviewer_only.jsonl','dependency_graphs.jsonl','author_config.snapshot.json'}:
            raise ValueError('Author information leaked into blind package')
    references=rows(folder/'source_refs.jsonl')
    base_pairs={(r['message_id'],r['image_id']) for r in references if r['variant']=='base'}
    for graph in rows(folder/'dependency_graphs.jsonl'):
        for node in graph['nodes']:
            if not all((r['message_id'],r['image_id']) in base_pairs for r in node['source_refs']):
                raise ValueError('Dependency node has an unresolved screenshot source')
    exact_quotes=0
    for fact in rows(folder/'fact_ledger.jsonl'):
        for ref in fact['source_refs']:
            if ref.get('status')=='exact_text_located':
                source=local(ROOT,ref['file'])
                if digest(source)!=ref['file_sha256'] or read(source)['text'][ref['char_start']:ref['char_end']]!=ref['quote']:
                    raise ValueError('Fact ledger source quote drift')
                exact_quotes+=1
    return dict(files=len(manifest),conditions=len(conditions),screenshots=image_count,subsets=len(subsets),exact_source_quotes=exact_quotes)

def check_review(package,template):
    identity=read(package/'reviewer.json');blockers=[]
    if not identity.get('reviewer_id'):blockers.append('reviewer_id missing')
    if identity.get('independent_of_author') is not True or identity.get('worked_without_other_review') is not True:
        blockers.append('independence declaration incomplete')
    actual=read(package/'tasks.json');expected=read(template/'tasks.json');by_id={t['task_id']:t for t in actual}
    if len(by_id)!=len(actual) or set(by_id)!={t['task_id'] for t in expected}:raise ValueError('Review task IDs differ')
    incomplete=[]
    for source in expected:
        task=by_id[source['task_id']]
        for key in ['question_id','question','scope','images']:
            if task.get(key)!=source[key]:raise ValueError('Reviewed input changed: '+source['task_id'])
        for image in task['images']:
            if digest(local(package,image['file']))!=image['sha256']:raise ValueError('Reviewed image changed')
        if not task.get('answer') or task.get('sufficiency') is None or task.get('minimality') is None or task.get('ambiguity') is None or not task.get('reviewed_at') or task.get('reviewer_identity')!=identity.get('reviewer_id'):
            incomplete.append(task['task_id'])
    groups=read(package/'case_reviews.json');original=read(template/'case_reviews.json')
    if len(groups)!=len(original):raise ValueError('Review groups differ')
    pending_groups=[]
    for group,source in zip(groups,original):
        if any(group.get(k)!=source[k] for k in ['group_id','question_id','task_ids','unit_type']):raise ValueError('Review group inputs changed')
        required=['subsets_checked','sufficient_sets','inclusion_minimal_sets','minimum_cardinality','witnesses','defeaters_checked','semantic_review','dependency_review','ambiguity_resolution']
        if any(group.get(k) is None for k in required) or group.get('status')=='unreviewed':pending_groups.append(group['group_id'])
    if incomplete:blockers.append(f'{len(incomplete)} incomplete subset reviews')
    if pending_groups:blockers.append(f'{len(pending_groups)} incomplete page-level certifications')
    return dict(reviewer_id=identity.get('reviewer_id'),blockers=blockers,complete=not blockers)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--batch',required=True);parser.add_argument('--review-a',type=Path);parser.add_argument('--review-b',type=Path)
    args=parser.parse_args();folder=local(ROOT,args.batch)
    result=dict(mechanical_status='passed',**verify_artifacts(folder))
    reviews=[check_review(supplied or folder/'blind_review'/('reviewer_'+label),folder/'blind_review'/('reviewer_'+label)) for label,supplied in [('a',args.review_a),('b',args.review_b)]]
    distinct=bool(reviews[0]['reviewer_id']) and reviews[0]['reviewer_id']!=reviews[1]['reviewer_id']
    result.update(reviews=reviews,ready_for_adjudication=distinct and all(r['complete'] for r in reviews),accepted_questions=0,
                  certification_policy='This checker verifies completeness/integrity, never grants semantic certification. Disagreements and legal scope require adjudication.',new_api_calls=0)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
