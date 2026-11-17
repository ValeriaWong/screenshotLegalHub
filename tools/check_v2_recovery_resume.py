"""Exercise recovery checkpoints on isolated copies of real recover decisions."""
from __future__ import annotations
import contextlib, copy, io, json, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import v2_library_authoring as author
from tools.v2_library_expansion import OUT,read,save,sha,rel


def main():
    originals={r['id']:r for r in read(OUT/'authoring_status.json')['records']}
    inputs=[]
    for p in sorted((OUT/'peer_reviews').glob('*/review.json')):
        if read(p).get('decision')=='recover':
            inputs.append({'id':p.parent.name,'review_sha256':sha(p)})
    assert inputs,'No recover decisions available for the regression check'
    root_runtime=ROOT/'.runtime';root_runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root_runtime,prefix='recovery-resume-check-') as temporary:
        sandbox=Path(temporary);records=[];before={}
        for item in inputs:
            ident=item['id'];record=copy.deepcopy(originals[ident]);original_folder=ROOT/record['authoring_path']
            folder=sandbox/'authoring'/original_folder.parent.name/ident
            shutil.copytree(original_folder,folder)
            before[ident]=author.authoring_digest(folder)
            record.update(authoring_path=rel(folder),decision='defer')
            records.append(record)
            dest=sandbox/'sources'/ident;dest.mkdir(parents=True)
            shutil.copyfile(OUT/'sources'/ident/'source.json',dest/'source.json')
            dest=sandbox/'peer_reviews'/ident;dest.mkdir(parents=True)
            for name in ['review.json','corrected.case.json','corrected.claims.json']:
                shutil.copyfile(OUT/'peer_reviews'/ident/name,dest/name)
        save(sandbox/'authoring_status.json',{'records':records,'errors':[]})
        initial=sandbox/'peer_jobs/original_recovery'
        save(initial/'assignment.json',{'records':records});(initial/'last_message.txt').write_text('Completed initial recovery authoring',encoding='utf-8')
        with patch.object(author,'OUT',sandbox),patch.object(author,'review_enabled',return_value=True),contextlib.redirect_stdout(io.StringIO()):
            author.peer_apply()
            assert not read(sandbox/'peer_application.json')['errors']
            assert len(read(sandbox/'peer_application.json')['recoveries_pending'])==len(inputs)
            assert not list((sandbox/'cases').glob('*/peer.acceptance.json'))
            for item in inputs:
                source=read(sandbox/'sources'/item['id']/'source.json')
                assert (sandbox/'cases'/item['id']/'judgment.txt').read_bytes()==source['text'].encode('utf-8')
            author.collect()
            state=read(sandbox/'authoring_status.json')
            assert not state['errors'] and len(state['records'])==len(inputs)
            assert all(r['decision']=='candidate' and r['recovery_pending_visual_review'] for r in state['records'])
            for row in state['records']:
                target=ROOT/row['case_path'];images=target/'screenshots';images.mkdir()
                Image.new('RGB',(2,2),'white').save(images/'fixture.png')
                save(target/'render.json',{'images':[{'path':'screenshots/fixture.png'}]})
                save(target/'render.state.json',{'test_fixture_only':True})
            author.peer_assign()
            assigned=list((sandbox/'peer_jobs').glob('*/assignment.json'))
            final_rows=[r for p in assigned for r in read(p)['records'] if r.get('review_stage')=='recovered_candidate_visual']
            assert len(final_rows)==len(inputs)
            author.peer_assign()
            assert len(list((sandbox/'peer_jobs').glob('*/assignment.json')))==len(assigned)
            excluded=inputs[-1]['id']
            for row in final_rows:
                review=read(sandbox/'peer_reviews'/row['id']/'review.json')
                review.update(decision='exclude' if row['id']==excluded else 'pass',
                              recovery_pending_visual_review=False,issues=[],
                              summary='Mechanical regression fixture, not a legal or visual assessment.',
                              images_inspected=[rel(ROOT/row['case_path']/'screenshots/fixture.png')])
                save(ROOT/row['peer_review_output']/'review.json',review)
            for p in assigned:
                (p.parent/'last_message.txt').write_text('Completed mechanical fixture review',encoding='utf-8')
            changed=ROOT/final_rows[0]['case_path']/'screenshots/fixture.png';saved_image=changed.read_bytes()
            changed.write_bytes(saved_image+b'changed after assignment')
            author.peer_apply()
            assert len(read(sandbox/'peer_application.json')['errors'])==1
            assert not (changed.parent.parent/'peer.acceptance.json').exists()
            changed.write_bytes(saved_image)
            author.peer_apply()
            assert not read(sandbox/'peer_application.json')['errors']
            assert not author.pending_recovery_ids()
            assert len(list((sandbox/'cases').glob('*/peer.acceptance.json')))==len(inputs)
            author.peer_apply();author.collect()
            assert not read(sandbox/'peer_application.json')['errors']
            final_state=read(sandbox/'authoring_status.json')
            assert not final_state['errors']
            assert next(r for r in final_state['records'] if r['id']==excluded)['decision']=='defer'
            assert not any(r.get('recovery_pending_visual_review') for r in final_state['records'])
            for row in records:
                assert author.authoring_digest(ROOT/row['authoring_path'])==before[row['id']]
                assert sha(sandbox/'peer_reviews'/row['id']/'review.json')==next(i['review_sha256'] for i in inputs if i['id']==row['id'])
    result={'passed':True,'checked_utc':datetime.now(timezone.utc).isoformat(),'recover_decisions':inputs,
            'checks':['materialize_without_acceptance','collect_preserves_recovery_after_resume',
                      'one_final_review_assignment_per_source','original_author_and_review_preserved',
                      'reject_changed_reviewed_png','final_review_acceptance_and_exclusion',
                      'accepted_final_review_is_idempotent','no_pending_recovery_after_completion'],
            'scope':'Isolated mechanical checkpoint regression using real source/recovery inputs and tiny fixture PNGs; not a visual/semantic legal assessment.',
            'professional_gold':False}
    save(OUT/'recovery.resume.verification.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
