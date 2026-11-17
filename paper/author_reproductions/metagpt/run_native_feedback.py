"""One bounded author review after actual native game failures; <=100 shared A04 cap.
No manual source fix. Save first native result, observed failure, author response,
and edited working copy separately. Does not claim autonomous original QA parity.
"""
import ast,asyncio,copy,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as shared
from screenshotlegal.research.store import Store
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.research.gateway import error_view
from screenshotlegal.method_reproductions.author_bridge import stream_author
async def main():
    original=shared.OUT/'methods/e22_metagpt/runs/46d2f9262b31af56__native'
    baseline=json.loads((original/'e22_metagpt.output.json').read_text(encoding='utf-8'))
    failures=json.loads((original/'e22_metagpt.native_functional_before_feedback.json').read_text(encoding='utf-8'))
    if failures['all_passed']:raise ValueError('No observed failure to repair')
    files=baseline['output']['files'];code=files['snake_game/snake_game/snake.py']
    context='Original development context:\n'+files['snake_game/docs/system_design.md']+'\n'+files['snake_game/docs/api_spec_and_tasks.md']+'\nCurrent game consumer:\n'+files['snake_game/snake_game/game.py']+'\nObserved actual test failures:\n'+json.dumps(failures,ensure_ascii=False)
    request=dict(filename='snake.py',code=code,context=context)
    script=Path(__file__).with_name('native_feedback_adapter.py')
    plan_id=digest(dict(input=request,adapter=script.read_text(encoding='utf-8'),loader=script.with_name('loader.py').read_text(encoding='utf-8')))[:16]
    directory=shared.OUT/'methods/e22_metagpt/runs'/(plan_id+'__native_feedback')
    request['runtime']=str(directory/'.runtime/author')
    shared.save(directory/'e22_metagpt.input.json',request)
    shared.save(directory/'e22_metagpt.provenance.json',dict(plan_id=plan_id,created_at=now(),original_native_record=str((original/'e22_metagpt.record.json').relative_to(ROOT)),
        manual_trigger='Functional probe selected snake.py and supplied measured failures to original WriteCodeReview',original_autonomous_qa_pipeline=False))
    # No separate track record: this follow-up belongs to native validation, not a product track.
    if (directory/'e22_metagpt.output.json').exists():raise ValueError('Existing follow-up output is retained')
    config=shared.base.ReadOnlyConfiguration(ROOT/'product_v1/data');model_config=config.get('model_configs',shared.base.MODEL_ID);owner=model_config['owner_id']
    auth=json.loads((shared.OUT/'authorization.json').read_text(encoding='utf-8'));store=Store(shared.OUT/'.runtime')
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),config,owner)
    gateway=shared.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),config,owner,100,auth['historical_counts']);gateway.paper='A04'
    model=gateway.freeze(owner,shared.base.MODEL_ID);trace=[]
    async def handle(event):
        if event['event']=='tool':return dict(ok=True)
        if trace:raise ValueError('Only one author review request is allowed in this follow-up')
        sid=plan_id+'.A04.native_feedback.'+event['stage']
        item=dict(stage=event['stage'],request_id=sid,messages=event['messages'],original_parameters=event['original_parameters'],status='calling_model')
        trace.append(item);shared.save(directory/'e22_metagpt.model_responses.json',trace)
        try:response=await gateway.call(owner,model,event['messages'],'author_metagpt_native_feedback',sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));shared.save(directory/'e22_metagpt.model_responses.json',trace);raise
        item.update(status='completed',response=response);shared.save(directory/'e22_metagpt.model_responses.json',trace)
        return response
    try:
        result=await stream_author(ROOT/'paper/.author_envs/metagpt/Scripts/python.exe',script,request,handle)
        ast.parse(result['output'],filename='snake.py')
        shared.save(directory/'e22_metagpt.output.json',result)
        working=original/'.runtime/utf8_project/snake_game/snake_game/snake.py'
        if working.read_bytes().decode('utf-8').replace('\r\r\n','\r\n')!=code:raise ValueError('Working copy already changed; preserve prior output')
        (directory/'before_snake.py').write_bytes(code.encode('utf-8'))
        (directory/'after_snake.py').write_bytes(result['output'].encode('utf-8'))
        working.write_text(result['output'],encoding='utf-8')
        print(json.dumps(dict(status='author_review_applied_to_working_copy',plan_id=plan_id,used=gateway.count('A04'),new_supplier_requests=1)))
    finally:
        shared.save(directory/'e22_metagpt.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace]);store.close()
if __name__=='__main__':asyncio.run(main())
