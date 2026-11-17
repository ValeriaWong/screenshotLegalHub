"""Apply archived root review plans; preserve before versions and old renders."""
import argparse, copy, hashlib, json, shutil, sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import read,save,normalize
from tools.v2_claim_support import validate_claims,claim_questions


def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);a=p.parse_args()
    plan_path=a.plan.resolve();out=plan_path.parent
    assert out.is_relative_to((ROOT/'datasets/v2.0.0').resolve()) and out.name.startswith('round_004')
    plan=read(plan_path);plan_hash=hashlib.sha256(plan_path.read_bytes()).hexdigest();count=0
    for entry in plan['records']:
        directory=(out/'zh'/entry['id']).resolve()
        assert directory.parent==(out/'zh').resolve()
        old_review=read(directory/'root.review.json') if (directory/'root.review.json').exists() else {'issues':[],'applied_review_plans':[]}
        if plan_hash in old_review.get('applied_review_plans',[]):continue
        version=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        archive=directory/'root.versions'/version;archive.mkdir(parents=True,exist_ok=True)
        for name in ['case.json','claims.review.json','root.review.json','status.json']:
            if (directory/name).exists():shutil.copyfile(directory/name,archive/name)
        case=read(directory/'case.json');claims=read(directory/'claims.review.json')
        if entry.get('remove_message_ids'):
            case['messages']=[m for m in case['messages'] if m['id'] not in entry['remove_message_ids']]
        case.update(entry.get('case_changes',{}))
        for ident,changes in entry.get('message_changes',{}).items():
            message=next(m for m in case['messages'] if m['id']==ident);message.update(changes)
        for ident,changes in entry.get('claim_changes',{}).items():
            q=next(q for q in claims['claims'] if q['id']==ident);q.update(changes)
        # Rebuild questions from the canonical reviewed claim set before validating.
        case['questions']=claim_questions(claims['claims'])
        original_author=case['author'];source=read(directory/'source.json')
        case,errors=normalize(case,source);assert not errors,errors
        # normalize preserves source fields; retain corrected display case number.
        before=read(archive/'case.json');case['case_no']=before['case_no'];case['author']=original_author
        normalized_claims=validate_claims(claims,case,source)
        case['questions']=claim_questions(normalized_claims)
        save(directory/'case.json',case);save(directory/'claims.review.json',{'claims':normalized_claims})
        old_review['issues'].append({'problem':entry['reason'],'change':entry.get('change_summary',entry['reason']),
                                    'plan_file':plan_path.name,'plan_sha256':plan_hash,'version':version})
        old_review.setdefault('applied_review_plans',[]).append(plan_hash)
        old_review.update(reviewer='root',professional_gold=False,independent_professional_review=False)
        save(directory/'root.review.json',old_review)
        if entry.get('message_changes') or entry.get('rerender') or entry.get('remove_message_ids') or entry.get('case_changes'):
            if (directory/'render.json').exists():
                render_archive=directory/'render.versions'/version;render_archive.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(directory/'render.json',render_archive/'render.json')
                for shot in read(directory/'render.json')['images']:
                    src=(directory/shot['path']).resolve();assert src.is_relative_to(directory)
                    target=render_archive/shot['path'];target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(src,target)
            save(directory/'status.json',{'phase':'reviewed','root_correction':plan_hash})
        count+=1
    print(json.dumps({'reviewed_cases':count},ensure_ascii=False))


if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
