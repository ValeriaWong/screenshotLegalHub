"""L-MAD: real native-paper example and binary-KIE-VQA/case adaptation.
Selected MALLM components execute; L-MAD author code/checkpoints are not claimed.
All variants share durable L10 <=100 requests, including failures and history.
Source/fidelity/original I/O and exact scope: algorithm.py/specification.lock.json.
"""
import argparse,asyncio,copy,hashlib,json,sqlite3,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as run
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.store import Store
from screenshotlegal.research.benchmark import Benchmark,DEFAULTS
from screenshotlegal.research import benchmark_scoring
from screenshotlegal.research.gateway import error_view,ModelFailure
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.method_reproductions.paper_bridge import execute
from screenshotlegal.method_reproductions.e09_l_mad import run_task
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.experiments.engine import visible_input,SYSTEM_POLICY,validate_output

async def main(track,protocol,do_execute=False,case_max_facts=2):
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    owner=configuration.get('model_configs',run.base.MODEL_ID)['owner_id']
    authorization=json.loads((run.OUT/'authorization.json').read_text(encoding='utf-8'))
    if authorization['limit_per_paper']!=100:raise ValueError('Existing per-paper authorization cap changed')
    store=Store(run.OUT/'.runtime');benchmark=Benchmark(store)
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=run.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,authorization['historical_counts'])
    gateway.paper='L10';model=gateway.freeze(owner,run.base.MODEL_ID)
    evaluation={};lineage={}
    if track=='native':
        original=json.loads((HERE/'native_inputs/paper_illustration.json').read_text(encoding='utf-8'))
        request=dict(premise=original['premise'],hypothesis=original['hypothesis'],protocol=protocol,rounds=3,
            max_calls=18 if protocol=='ranked' else 9,scope=original['scope'])
        evaluation=dict(reference=original['reference'],reference_sent_to_model=False,scope=original['scope'])
        lineage=dict(input_id=original['id'],selection='exact published Section 2.1 illustration; not a COLIEE dataset sample')
    elif track=='vqa_predicted_text':
        attempts=sorted([a for a in store.list('benchmark.attempt',owner) if a['status']=='completed' and not a.get('response',{}).get('demo') and (a.get('parsed') or {}).get('conversation')],key=lambda a:a['id'])
        upstream=attempts[0];dataset=benchmark.dataset(owner,upstream['dataset_id']);tasks=benchmark.load(dataset['tasks'])
        chosen=next(t for t in tasks if not t.get('region_id') and t.get('source_label')=='group_chat_or_private_chat' and len(t.get('allowed_values') or [])==2)
        task=benchmark.freeze_task(owner,dataset['id'],chosen['task_id'],'vqa_predicted_text',upstream_id=upstream['id'])
        request=dict(messages=[dict(role='system',content=DEFAULTS['vqa']),dict(role='user',content=json.dumps(task['input'],ensure_ascii=False))])
        evaluation=dict(task=task,target=task['target'],reference_status=task['reference_status'])
        lineage=dict(upstream_attempt_id=upstream['id'],upstream_response_hash=digest(upstream['response']),
            selection='existing binary group/private whole-image question; no reference/output selection',source_context='frozen_predicted_KIE_only')
    else:
        path=ROOT/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:frozen=json.loads(db.execute("SELECT body FROM records WHERE kind='agent.input' ORDER BY id LIMIT 1").fetchone()[0])
        visible=visible_input(frozen,'E09');request=dict(input=visible,case_max_facts=case_max_facts)
        lineage=dict(original_frozen_input_id=frozen['id'],selection='first previously authorized frozen case; no expert Gold or prior output')
    unit_cap=(18 if protocol=='ranked' else 9) if track=='native' else (36 if protocol=='ranked' else 18) if track=='vqa_predicted_text' else (2+(18 if protocol=='ranked' else 9)*case_max_facts)
    names=['paper/author_reproductions/l_mad/'+n for n in ('algorithm.py','mallm_components.py','product_adapter.py','run_validation.py','specification.lock.json','paper_prompts.json','example_paper.tex','paper_v1.pdf','requirements.lock.txt','native_inputs/paper_illustration.json')]
    names+=['product_v1/backend/src/screenshotlegal/method_reproductions/'+n for n in ('e09_l_mad.py','lmad_bridge.py','paper_bridge.py','author_bridge.py')]
    names+=['product_v1/backend/src/screenshotlegal/experiments/'+n for n in ('engine.py','registry.py')]
    upstream_source=next(s for s in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')) if s['name']=='mallm')
    names += [upstream_source['local_path']+'/'+n for n in upstream_source['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(track=track,protocol=protocol,request=request,evaluation=evaluation,lineage=lineage,model=model,sources=hashes))[:16]
    directory=run.OUT/'methods/e09_l_mad/runs'/(plan_id+'__'+track+'__'+protocol)
    plan=dict(plan_id=plan_id,created_at=now(),paper_id='L10',method='e09_l_mad',track=track,variant=protocol,
        source_kind='paper_specification_with_cited_upstream_components',LMAD_author_code_executed=False,source_manifest=hashes,
        model=model,lineage=lineage,local_model_inference=False,maximum_additional_requests=unit_cap,cap_per_paper=100,
        original_complete_benchmark=False,expert_legal_gold_used=False)
    run.save(directory/'e09_l_mad.input.json',dict(request=request,evaluation_only=evaluation,plan=plan))
    if not (directory/'e09_l_mad.provenance.json').exists():run.save(directory/'e09_l_mad.provenance.json',plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
        target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,track=track,variant=protocol,used=gateway.count('L10'),unit_cap=unit_cap)));store.close();return
    path=directory/'e09_l_mad.record.json'
    if path.exists():print(json.dumps(dict(status='existing_record_retained',path=str(path.relative_to(ROOT)))));store.close();return
    initial=gateway.count('L10')
    if initial+unit_cap>100:raise ValueError('Remaining shared paper budget cannot cover the bounded unit')
    trace=[];artifacts=[];tools=[];checks={};output=None
    record=dict(paper_id='L10',method='e09_l_mad',track=track,variant=protocol,plan_id=plan_id,status='running')
    run.save(path,record)
    async def raw(stage,messages,parameters):
        if gateway.count('L10')-initial>=unit_cap:raise ModelFailure('budget','Bounded paper unit cap reached')
        effective=copy.deepcopy(model);effective['parameters'].update(temperature=parameters['temperature'],max_tokens=parameters['max_tokens'])
        sid=plan_id+'.L10.'+track+'.'+protocol+'.'+stage
        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=effective['parameters'],status='calling_model')
        trace.append(item);run.save(directory/'e09_l_mad.model_responses.json',trace)
        try:response=await gateway.call(owner,effective,messages,'paper_lmad_'+track,sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));run.save(directory/'e09_l_mad.model_responses.json',trace);raise
        item.update(status='completed',response=response);run.save(directory/'e09_l_mad.model_responses.json',trace)
        return response
    async def artifact(name,result):artifacts.append(result);run.save(directory/'e09_l_mad.author_artifacts.json',artifacts)
    async def tool(action,result):tools.append(dict(action=action,result=result))
    async def generic(*args):raise ValueError('Old staged/adversarial E09 baseline must not run')
    try:
        if track=='native':
            result=await execute('l_mad',request,raw,tool)
            predicted=result['output']['answer']
            output=dict(prediction=predicted,reference=evaluation['reference'],correct=predicted==evaluation['reference'],execution=result)
            checks=dict(published_native_task_executed=True,scope=evaluation['scope'],correct=output['correct'],
                strict_main_label_parsed=predicted in ('Y','N'),reference_sent_to_model=False,protocol=protocol)
        elif track=='vqa_predicted_text':
            result=await run_task(request['messages'],raw,tool_trace=tool,protocol=protocol)
            output=dict(prediction=result['output'],execution=result,score=benchmark_scoring.score(evaluation['task'],result['output'],evaluation['target'],evaluation['task']['asset']['width'],evaluation['task']['asset']['height']))
            checks=dict(binary_product_VQA_completed=True,reference_status=evaluation['reference_status'],score=output['score'],non_entailment_not_treated_as_opposite=True)
        else:
            output=await run_method('E09',visible,frozen['sources'],generic,generic,SYSTEM_POLICY,lambda:{},
                dict(max_model_calls=unit_cap,lmad_protocol=protocol,lmad_rounds=3,lmad_max_facts=case_max_facts),raw_call=raw,author_record=artifact)
            output=validate_output(output,frozen);result=artifacts[0]
            checks=dict(case_product_schema_valid=True,literal_citations_valid=True,verified_fact_set_preserved=True,legal_accuracy=None)
        record.update(status='completed')
        if track!='case_product':await artifact('l_mad',result)
        checks.update(local_model_inference=False,source_kind='paper_specification_with_cited_upstream_components',LMAD_author_code_executed=False,expert_legal_accuracy=None)
    except Exception as error:record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record['per_paper_requests_including_history']=gateway.count('L10')
        run.save(path,record);run.save(directory/'e09_l_mad.output.json',output)
        run.save(directory/'e09_l_mad.prompts.json',[dict(stage=t['stage'],messages=t['messages']) for t in trace])
        run.save(directory/'e09_l_mad.tools.json',tools)
        run.save(directory/'e09_l_mad.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,track=track,variant=protocol,total_paper_requests=record['per_paper_requests_including_history'],path=str(directory.relative_to(ROOT))),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track',choices=['native','vqa_predicted_text','case_product'],required=True);p.add_argument('--protocol',choices=['hybrid','ranked'],default='hybrid');p.add_argument('--execute',action='store_true');p.add_argument('--case-max-facts',type=int,choices=[1,2],default=2)
    a=p.parse_args();asyncio.run(main(a.track,a.protocol,a.execute,a.case_max_facts))
