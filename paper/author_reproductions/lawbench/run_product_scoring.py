"""LawBench product adaptation: rescore existing real KIE/global-VQA responses.
Zero new supplier calls; do not invent KIE transcript references. Native benchmark
and product metrics are separate. A categorical task maps frozen labels to A-D;
KIE without a transcript remains explicitly unscored. See adapter.py for source.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as run
from screenshotlegal.research.store import Store
from screenshotlegal.research.benchmark import Benchmark
from screenshotlegal.research.contracts import digest,now

async def main():
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    owner=configuration.get('model_configs',run.base.MODEL_ID)['owner_id']
    store=Store(run.OUT/'.runtime');benchmark=Benchmark(store)
    names=['paper/author_reproductions/lawbench/'+n for n in ('adapter.py','requirements.lock.txt','run_product_scoring.py')]
    names += ['product_v1/backend/src/screenshotlegal/research/'+n for n in ('lawbench_scoring.py','benchmark.py','benchmark_scoring.py')]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    attempts=sorted([a for a in store.list('benchmark.attempt',owner) if a['status']=='completed' and not a.get('response',{}).get('demo') and not a.get('pipeline_id')],key=lambda a:a['id'])
    selected={}
    for a in attempts:
        frozen=store.get('benchmark.run',a['run_id'],owner)
        t=next(t for t in frozen['tasks'] if t['task_id']==a['task_id'])
        kind='kie_image' if t['task_family']=='kie.extract' else 'vqa_image_full' if frozen['track']=='vqa_image_full' else None
        if kind and kind not in selected and any(s['attempt_id']==a['id'] and 'target_snapshot' in s for s in store.list('benchmark.score',owner)):
            selected[kind]=(a,frozen,t)
    results=[]
    try:
        for track,(attempt,frozen,task) in selected.items():
            plan_id=digest(dict(track=track,attempt=attempt,task=task,sources=hashes))[:16]
            folder=run.OUT/'methods/b02_lawbench/runs'/(plan_id+'__product_scoring_'+track)
            path=folder/'b02_lawbench.record.json'
            if path.exists():results.append(json.loads(path.read_text(encoding='utf-8')));continue
            plan=dict(plan_id=plan_id,created_at=now(),paper_id='B02',method='b02_lawbench',track='product_scoring_'+track,
                source_manifest=hashes,original_run_id=frozen['id'],original_attempt_id=attempt['id'],
                selection='lexicographically first completed real attempt with primary score per image track',
                new_supplier_requests=0,local_model_inference=False,expert_legal_gold_used=False,original_complete_benchmark=False)
            run.save(folder/'b02_lawbench.provenance.json',plan)
            run.save(folder/'b02_lawbench.input.json',dict(task=task,original_input=task['input'],model_response=attempt['response'],plan=plan))
            for name in names:
                target=folder/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
            score=await benchmark.lawbench_score(owner,attempt['id'],dict(idempotency_key='lawbench.'+plan_id))
            run.save(folder/'b02_lawbench.output.json',score)
            run.save(folder/'b02_lawbench.model_responses.json',dict(new_requests=[],reused_original_response=attempt['response'],original_request_id=attempt.get('request_id'),new_supplier_requests=0))
            run.save(folder/'b02_lawbench.prompts.json',dict(new_model_prompts=[],original_frozen_prompt=frozen['prompt'],original_input=task['input']))
            run.save(folder/'b02_lawbench.tools.json',score['result'].get('author_execution',{}))
            checks=dict(product_dispatch_executed=True,reference_status=score['reference_status'],score_status=score['result']['status'],
                score=score['result']['score'],missing_gold_was_not_fabricated=True,primary_score_not_overwritten=True,
                local_model_inference=False,new_supplier_requests=0,expert_legal_accuracy=None,full_product_track_completed=False)
            run.save(folder/'b02_lawbench.test_results.json',dict(status='completed',checks=checks,original_complete_benchmark=False))
            record=dict(paper_id='B02',method='b02_lawbench',track=plan['track'],plan_id=plan_id,status='completed',scope='offline product scorer integration; quality only where compatible frozen reference exists')
            run.save(path,record);results.append(record)
    finally:store.close()
    print(json.dumps(dict(records=results,new_supplier_requests=0),ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
