"""Preserve two independent review exports and queue disagreements, no auto-certification."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERDICTS={'pending','satisfied','not_satisfied','not_established','ambiguous_question'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def put(path,value,lines=False):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        if lines:
            for row in value:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        else:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def merge(packet_dir,path_a,path_b):
    mapping=[json.loads(s) for s in (packet_dir/'blind_mapping.reviewer_only.jsonl').read_text(encoding='utf-8').splitlines()]
    joined={};reviewers=[]
    for slot,path in [('A',path_a),('B',path_b)]:
        export=json.loads(path.read_text(encoding='utf-8'))
        assert export['packet_id']==f'dependency_pilot_v1_reviewer_{slot}'
        reviewer=export.get('reviewer');assert isinstance(reviewer,str) and reviewer.strip(),'Reviewer identifier required.'
        reviewers.append(reviewer.strip())
        packet=json.loads((packet_dir/f'packet_{slot}.blind.json').read_text(encoding='utf-8'))
        expected={r['blind_id']:r for r in packet['items']}
        rows=export['items'];assert len(rows)==len(expected)==192
        assert len({r['blind_id'] for r in rows})==len(rows)
        aliases={r['blind_id']:r for r in mapping if r['reviewer_slot']==slot}
        for row in rows:
            ident=row['blind_id'];assert ident in expected
            assert row['image_hashes']==expected[ident]['image_hashes']
            assert row['verdict'] in VERDICTS
            bind=aliases[ident];key=(bind['task_id'],tuple(bind['roles']))
            joined.setdefault(key,{})[slot]={'reviewer':reviewer,'original_blind_id':ident,'review':row}
    assert len(set(reviewers))==2,'Two different reviewer identifiers are required.'
    merged=[]
    for (task,roles),pair in joined.items():
        assert set(pair)=={'A','B'}
        va,vb=pair['A']['review']['verdict'],pair['B']['review']['verdict']
        notes_complete=all(all(isinstance(p['review'].get(k),str) and p['review'][k].strip()
                               for k in ['facts','evidence','scope']) for p in pair.values())
        state=('pending' if 'pending' in [va,vb] else
               'return_for_question_revision' if 'ambiguous_question' in [va,vb] else
               'needs_adjudication' if va!=vb else
               'incomplete_review_notes' if not notes_complete else 'agreement_recorded')
        merged.append({'task_id':task,'roles':list(roles),'independent_reviews':pair,'state':state,
                       'semantic_certification':'pending_adjudication_and_minimality_review',
                       'professional_legal_certification':'not_granted'})
    return merged


def main():
    p=argparse.ArgumentParser();p.add_argument('--packets',required=True);p.add_argument('--review-a',required=True)
    p.add_argument('--review-b',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    packet_dir=Path(args.packets).resolve();a=Path(args.review_a).resolve();b=Path(args.review_b).resolve()
    out=Path(args.output).resolve();out.relative_to(ROOT)
    if out.exists():raise FileExistsError('Use a new output directory; independent reviews are immutable.')
    hashes={str(path):sha(path) for path in [a,b]}
    rows=merge(packet_dir,a,b)
    out.mkdir(parents=True,exist_ok=False)
    put(out/'merged_reviews.jsonl',rows,lines=True)
    put(out/'adjudication_queue.jsonl',[r for r in rows if r['state']!='agreement_recorded'],lines=True)
    counts={state:sum(r['state']==state for r in rows) for state in sorted({r['state'] for r in rows})}
    put(out/'summary.json',{'subset_pairs':len(rows),'states':counts,'input_export_hashes':hashes,
        'input_exports_unchanged':all(sha(Path(path))==digest for path,digest in hashes.items()),
        'automatic_certification':False,'professional_signoff':False})
    print(json.dumps({'subset_pairs':len(rows),'states':counts,'automatic_certification':False},ensure_ascii=False))


if __name__=='__main__':main()
