"""Pipeline commands expose plans and individual units, never credential material."""
from typing import Literal
from fastapi import Request, Query
from fastapi.responses import Response
from pydantic import Field
from screenshotlegal.research.contracts import Contract, dumps
from screenshotlegal.research.benchmark_pipeline import Pipeline
from screenshotlegal.research.operations import public

class Plan(Contract):
    idempotency_key:str=Field(min_length=1,max_length=200)
    dataset_id:str
    name:str=Field(min_length=1,max_length=200)
    task_ids:list[str]=Field(default_factory=list,max_length=20000)
    image_names:list[str]=Field(default_factory=list,max_length=2000)
    all_tasks:bool=False
    model_id:str='demo'
    kie_prompt_id:str=''
    vqa_prompt_id:str=''
    mode:Literal['development_reference','official_reviewed']='development_reference'
    release_id:str|None=None
    max_calls:int=Field(ge=1,le=30000)
    iou_threshold:float=Field(default=.6,ge=.6,le=.6)
    regional_controls:bool=False
    allow_unverified_assets:bool=False

class Command(Contract):
    idempotency_key:str=Field(min_length=1,max_length=200)
    reason:str=Field(min_length=1,max_length=10000)

class Nodes(Command):
    node_ids:list[str]=Field(default_factory=list,max_length=20000)

class Retry(Nodes):
    max_calls:int=Field(ge=1,le=30000)

class Rescore(Command):
    annotation_ids:dict[str,str]=Field(default_factory=dict)

def register_pipeline(app,benchmark,worker):
    pipeline=Pipeline(benchmark);worker.pipeline=pipeline;benchmark.pipeline=pipeline;app.state.research['pipeline']=pipeline
    def owner(r):return r.state.user.id
    @app.post('/v1/evaluation/benchmark-pipelines/default-prompts')
    def defaults(request:Request):
        from screenshotlegal.research.benchmark import DEFAULTS
        result=[]
        for family in ['kie','vqa']:
            name='按图流程默认'+family.upper()
            rows=[r for r in benchmark.prompts(owner(request)) if r['family']==family and r['name']==name]
            result.append(rows[0] if rows else benchmark.save_prompt(owner(request),dict(name=name,family=family,parent_id=None,markdown=DEFAULTS[family],note='初始化按图流程答题规则；后续修改保留Markdown版本',idempotency_key='pipeline-default:'+family+':v1')))
        return result
    @app.post('/v1/evaluation/benchmark-pipelines/preview')
    def preview(request:Request,payload:Plan):return public(pipeline.preview(owner(request),payload.model_dump()))
    @app.post('/v1/evaluation/benchmark-pipelines',status_code=201)
    def create(request:Request,payload:Plan):return public(pipeline.create(owner(request),payload.model_dump()))
    @app.get('/v1/evaluation/benchmark-pipelines')
    def list_runs(request:Request):return public(pipeline.list(owner(request)))
    @app.get('/v1/evaluation/benchmark-pipelines/{id}')
    def detail(id:str,request:Request,offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),image_key:str='',score_set_id:str=''):
        return public(pipeline.detail(owner(request),id,offset,limit,image_key,score_set_id))
    @app.get('/v1/evaluation/benchmark-pipelines/{id}/samples')
    def samples(id:str,request:Request,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
        return public(pipeline.sample_results(owner(request),id,offset,limit))
    @app.get('/v1/evaluation/benchmark-pipelines/{id}/nodes/{node_id}')
    def node(id:str,node_id:str,request:Request):return public(pipeline.node_detail(owner(request),id,node_id))
    @app.post('/v1/evaluation/benchmark-pipelines/{id}/stop')
    def stop(id:str,request:Request,payload:Command):
        result=pipeline.stop(owner(request),id,payload.model_dump());pipeline.persist_report(owner(request),id);return result
    @app.post('/v1/evaluation/benchmark-pipelines/{id}/resume-local')
    def resume(id:str,request:Request,payload:Nodes):return pipeline.resume_local(owner(request),id,payload.model_dump())
    @app.post('/v1/evaluation/benchmark-pipelines/{id}/reconcile-responses')
    def reconcile(id:str,request:Request,payload:Nodes):
        result=pipeline.reconcile(owner(request),id,payload.model_dump());pipeline.persist_report(owner(request),id);return result
    @app.post('/v1/evaluation/benchmark-pipelines/{id}/retry',status_code=201)
    def retry(id:str,request:Request,payload:Retry):return pipeline.retry(owner(request),id,payload.model_dump())
    @app.post('/v1/evaluation/benchmark-pipelines/{id}/rescore',status_code=201)
    def rescore(id:str,request:Request,payload:Rescore):
        result=pipeline.rescore(owner(request),id,payload.model_dump());pipeline.persist_report(owner(request),id,result['id']);return result
    @app.get('/v1/evaluation/benchmark-pipelines/{id}/export')
    def export(id:str,request:Request,score_set_id:str=''):
        return Response(dumps(public(pipeline.export(owner(request),id,score_set_id))),media_type='application/json',headers={'Content-Disposition':'attachment; filename="pipeline-results.json"'})
