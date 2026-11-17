"""Authenticated benchmark routes; filesystem migration is an operator CLI only."""
from typing import Literal
from fastapi import Request,Query
from fastapi.responses import Response
from pydantic import Field
from screenshotlegal.research.contracts import Contract,dumps
from screenshotlegal.research.benchmark import Benchmark

class Key(Contract):
    idempotency_key:str=Field(min_length=1,max_length=200)
class Retry(Key):
    task_ids:list[str]=Field(default_factory=list,max_length=500)
class Review(Key):
    expected_version:int=Field(ge=0)
    verdict:Literal['draft','revise','pass']
    target:object=None
    question:str=Field(default='',max_length=20000)
    question_eligibility:Literal['unverified','reviewed_independent','context_required']='unverified'
    bbox_xyxy:list[float]|None=None
    region_type:Literal['unclassified_legacy_rect','message','avatar','amount','filename','other']='unclassified_legacy_rect'
    image_identity_confirmed:bool=False
    case_group:str=Field(default='',max_length=200)
    split:Literal['unassigned','development','holdout']='unassigned'
    reason:str=Field(min_length=1,max_length=10000)
    suggestions:str=Field(default='',max_length=10000)
class Comment(Key):
    body:str=Field(min_length=1,max_length=20000)
    use_for_generation:bool=True
class Prompt(Key):
    name:str=Field(min_length=1,max_length=200)
    family:Literal['kie','vqa']
    parent_id:str|None=None
    markdown:str=Field(min_length=1,max_length=50000)
    note:str=Field(min_length=1,max_length=10000)
class Publish(Key):
    dataset_id:str
    name:str=Field(min_length=1,max_length=200)
    task_ids:list[str]=Field(min_length=1,max_length=500)
class Run(Key):
    dataset_id:str
    name:str=Field(min_length=1,max_length=200)
    task_ids:list[str]=Field(min_length=1,max_length=500)
    track:Literal['kie_image','vqa_image_full','vqa_image_region','vqa_predicted_text','vqa_oracle_text']
    mode:Literal['development_reference','official_reviewed']='development_reference'
    release_id:str|None=None
    model_id:str='demo'
    prompt_id:str
    method_id:Literal['E00','E01','E05','E09','E14','E15','E16','E18','E21','E23','E24','E25']='E00'
    method_protocol:Literal['hybrid','ranked']='hybrid'
    method_variant:Literal['react','plan_and_solve','plan_and_execute']='react'
    method_attempts:int=Field(default=2,ge=1,le=3)
    method_max_output_tokens:int=Field(default=6144,ge=100,le=10000)
    max_calls:int=Field(ge=1,le=500)
    iou_threshold:float=Field(default=.6,gt=0,le=1)
    upstream_attempt_id:str|None=None
class Quality(Key):
    attempt_id:str
    dimensions:dict[str,float]
    process:str=Field(min_length=1,max_length=10000)
    findings:str=Field(min_length=1,max_length=10000)
    suggestions:str=Field(default='',max_length=10000)
    prompt_id:str|None=None
class Draft(Contract):
    expected_version:int=Field(ge=0)
    draft_id:str=Field(min_length=1,max_length=200)
    base_version:int=Field(ge=0)
    content:dict
class Rescore(Key):
    annotation_id:str|None=None
    reason:str=Field(min_length=1,max_length=10000)

def register_benchmark(app,store,gateway,worker):
    benchmark=Benchmark(store,gateway);worker.benchmark=benchmark;app.state.research['benchmark']=benchmark
    from .benchmark_pipeline import register_pipeline
    register_pipeline(app,benchmark,worker)
    def owner(request): return request.state.user.id
    @app.get('/v1/evaluation/benchmarks')
    @app.get('/v1/review/benchmarks')
    def datasets(request:Request): return benchmark.datasets(owner(request))
    @app.get('/v1/evaluation/benchmarks/{id}/samples')
    def samples(id:str,request:Request,q:str='',offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
        return benchmark.sample_rows(owner(request),id,q,offset,limit)
    @app.get('/v1/evaluation/benchmarks/{id}/tasks')
    @app.get('/v1/review/benchmarks/{id}/tasks')
    def tasks(id:str,request:Request,image_name:str='',q:str='',family:str='',offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
        return benchmark.task_rows(owner(request),id,image_name,q,family,offset,limit)
    @app.get('/v1/review/benchmarks/{id}/tasks/{task_id}')
    def task(id:str,task_id:str,request:Request): return benchmark.detail(owner(request),id,task_id)
    @app.put('/v1/review/benchmarks/{id}/tasks/{task_id}')
    def review(id:str,task_id:str,request:Request,payload:Review): return benchmark.save_review(owner(request),id,task_id,payload.model_dump())
    @app.post('/v1/review/benchmarks/{id}/tasks/{task_id}/comments',status_code=201)
    def comment(id:str,task_id:str,request:Request,payload:Comment): return benchmark.comment(owner(request),id,task_id,payload.model_dump())
    @app.get('/v1/review/benchmarks/{id}/tasks/{task_id}/draft')
    def draft(id:str,task_id:str,request:Request):
        benchmark.task(owner(request),id,task_id)
        return store.optional('benchmark.draft',id+':'+task_id,owner(request))
    @app.put('/v1/review/benchmarks/{id}/tasks/{task_id}/draft')
    def save_draft(id:str,task_id:str,request:Request,payload:Draft):
        from screenshotlegal.research.contracts import now
        from screenshotlegal.research.store import Conflict
        benchmark.task(owner(request),id,task_id)
        if len(dumps(payload.content))>300000: raise ValueError('草稿过大')
        with store.tx() as db:
            key=id+':'+task_id;old=store.optional('benchmark.draft',key,owner(request),db)
            if (old['version'] if old else 0)!=payload.expected_version: raise Conflict('其他页面已保存草稿；当前输入保留，请比对')
            row=dict(id=key,dataset_id=id,task_id=task_id,version=payload.expected_version+1,draft_id=payload.draft_id,base_version=payload.base_version,content=payload.content,updated_at=now())
            store.put('benchmark.draft',row,owner(request),db);return row
    @app.get('/v1/evaluation/benchmarks/{id}/history')
    def histories(id:str,request:Request):
        benchmark.dataset(owner(request),id)
        return [r for r in store.list('benchmark.history',owner(request)) if r['dataset_id']==id]
    @app.get('/v1/evaluation/benchmark-runs/{id}/details')
    def replay_details(id:str,request:Request,image_name:str='',offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
        r=store.get('benchmark.run',id,owner(request))
        if r['mode']!='legacy_replay': raise ValueError('仅离线回放有旧IoU明细')
        rows=benchmark.load(r['result'])['details'];rows=[v for v in rows if not image_name or v['image']==image_name]
        return dict(items=rows[offset:offset+limit],total=len(rows),next_offset=offset+limit if offset+limit<len(rows) else None)
    @app.post('/v1/review/benchmark-quality',status_code=201)
    def quality(request:Request,payload:Quality): return benchmark.quality(owner(request),payload.model_dump())
    @app.get('/v1/review/benchmark-attempts')
    def review_attempts(request:Request,dataset_id:str,task_id:str):
        benchmark.task(owner(request),dataset_id,task_id)
        return [a for a in store.list('benchmark.attempt',owner(request)) if a['dataset_id']==dataset_id and a['task_id']==task_id and a['status']=='completed']
    @app.get('/v1/studio/benchmark-feedback')
    def feedback(request:Request,dataset_id:str):
        benchmark.dataset(owner(request),dataset_id)
        # Only reviewed development bindings are eligible; never expose held-out feedback to generation.
        annotations={a['id']:a for a in store.list('benchmark.annotation',owner(request)) if a['dataset_id']==dataset_id}
        heads={h['task_id']:annotations[h['annotation_id']] for h in store.list('benchmark.review',owner(request)) if h['dataset_id']==dataset_id}
        result=[]
        for r in store.list('benchmark.comment',owner(request)):
            if r['dataset_id']!=dataset_id or not r.get('use_for_generation'): continue
            a=annotations.get(r.get('annotation_id')) if r.get('annotation_id') else heads.get(r['task_id'])
            if a and a['split']=='development': result.append(dict(r,feedback_annotation_id=a['id'],feedback_binding_sha256=a['sha256']))
        return result
    @app.get('/v1/evaluation/task-prompts')
    def prompts(request:Request): return benchmark.prompts(owner(request))
    @app.post('/v1/evaluation/task-prompts',status_code=201)
    def prompt(request:Request,payload:Prompt): return benchmark.save_prompt(owner(request),payload.model_dump())
    @app.get('/v1/evaluation/task-prompts/export')
    def prompt_export(request:Request,name:str):
        from screenshotlegal.research import audit
        rows=sorted([p for p in benchmark.prompts(owner(request)) if p['name']==name],key=lambda p:p['version'])
        if not rows: raise KeyError('Prompt不存在')
        with store.tx() as db:audit.emit(db,owner(request),'benchmark.prompt.export','evaluation.task_prompt',rows[-1]['id'],details={'name':name,'versions':len(rows)},reason='导出答题Prompt Markdown迭代历史')
        return Response('\n\n'.join('# '+r['name']+' · '+r['family']+' · v'+str(r['version'])+'\n\n'+'父版本：'+str(r['parent_id'])+'\n\n修改原因：'+r['note']+'\n\n'+r['markdown'] for r in rows),media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="task-prompt-history.md"'})
    @app.post('/v1/review/benchmark-releases',status_code=201)
    def publish(request:Request,payload:Publish): return benchmark.publish(owner(request),payload.model_dump())
    @app.get('/v1/evaluation/benchmark-releases')
    @app.get('/v1/review/benchmark-releases')
    def releases(request:Request): return [{k:r[k] for k in ['id','name','dataset_id','created_at','sha256']}|dict(task_ids=[e['task']['task_id'] for e in r['entries']]) for r in store.list('benchmark.release',owner(request))]
    @app.get('/v1/evaluation/benchmarks/{id}/input')
    def preview(id:str,task_id:str,track:str,request:Request,upstream_attempt_id:str|None=None):
        t=benchmark.freeze_task(owner(request),id,task_id,track,upstream_id=upstream_attempt_id)
        return dict(input=t['input'],input_hash=t['input_hash'],reference_status=t['reference_status'])
    @app.post('/v1/evaluation/benchmarks/{id}/replay',status_code=201)
    def replay(id:str,request:Request,payload:Key): return benchmark.replay(owner(request),id,payload.model_dump())
    @app.post('/v1/evaluation/benchmark-runs',status_code=201)
    def run(request:Request,payload:Run): return benchmark.create_run(owner(request),payload.model_dump())
    @app.get('/v1/evaluation/benchmark-runs')
    def runs(request:Request): return [{k:v for k,v in r.items() if k not in ['tasks','model','prompt']} for r in store.list('benchmark.run',owner(request))]
    @app.get('/v1/evaluation/benchmark-runs/{id}')
    def result(id:str,request:Request): return benchmark.results(owner(request),id)
    @app.post('/v1/evaluation/benchmark-attempts/{id}/lawbench-score',status_code=201)
    async def lawbench_score(id:str,request:Request,payload:Key): return await benchmark.lawbench_score(owner(request),id,payload.model_dump())
    @app.post('/v1/evaluation/benchmark-attempts/{id}/legalbench-score',status_code=201)
    async def legalbench_score(id:str,request:Request,payload:Key): return await benchmark.legalbench_score(owner(request),id,payload.model_dump())
    @app.post('/v1/evaluation/benchmark-runs/{id}/rescore',status_code=201)
    def rescore(id:str,request:Request,payload:Rescore): return benchmark.rescore(owner(request),id,payload.model_dump())
    @app.post('/v1/evaluation/benchmark-runs/{id}/retry',status_code=201)
    def retry(id:str,request:Request,payload:Retry): return benchmark.retry(owner(request),id,payload.model_dump())
    @app.get('/v1/evaluation/benchmark-runs/{id}/export')
    def export(id:str,request:Request):
        data=benchmark.results(owner(request),id)
        from screenshotlegal.research import audit
        with store.tx() as db:audit.emit(db,owner(request),'benchmark.results.export','benchmark.run',id,details={'dataset_id':data['run']['dataset_id'],'run_id':id},reason='导出任务快照与全部评分/响应版本')
        if data['run']['mode']=='legacy_replay': data['legacy_replay']=benchmark.load(data['run']['result'])
        from screenshotlegal.research.operations import public
        name=data['run'].get('method',{}).get('name','benchmark-results')
        return Response(dumps(public(data)),media_type='application/json',headers={'Content-Disposition':'attachment; filename="'+name+'.'+id+'.json"'})
    @app.get('/v1/evaluation/benchmarks/{id}/history/{history_id}')
    def historical(id:str,history_id:str,request:Request,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
        benchmark.dataset(owner(request),id);r=store.get('benchmark.history',history_id,owner(request))
        if r['dataset_id']!=id: raise KeyError('历史记录不属于本数据集')
        raw=benchmark.load(r['raw']);rows=raw['items'] if isinstance(raw,dict) else raw
        items=[dict(raw=row,prediction_ref=history_id+':'+str(i)) for i,row in enumerate(rows[offset:offset+limit],offset)]
        return dict(history=r,items=items,total=len(rows),next_offset=offset+limit if offset+limit<len(rows) else None)
