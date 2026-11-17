"""Authenticated independent product routes; shared assets/jobs are accessed through contracts."""
import io
import json
import zipfile
from fastapi import Request, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from PIL import Image
from screenshotlegal.research.contracts import *
from screenshotlegal.research.store import Store, Conflict
from screenshotlegal.research.review import ReviewDesk
from screenshotlegal.research.products import DataStudio, EvaluationLab
from screenshotlegal.research.gateway import Gateway, ModelFailure, error_view
from screenshotlegal.research.worker import Worker
from screenshotlegal.research.catalog import Catalog
from screenshotlegal.research.renderer import verified, atomic_write
from screenshotlegal.research import audit
from screenshotlegal.research.operations import Operations

class AuditFilter(Contract):
    product: str = ''
    action: str = ''
    outcome: str = ''
    object_id: str = ''
    actor_id: str = ''
    since: str = ''
    until: str = ''
    q: str = Field(default='',max_length=500)
    correlation_id: str = ''
    request_id: str = ''
    cursor: int | None = Field(default=None,ge=1)
    limit: int = Field(default=50,ge=1,le=200)

class RestoreOriginalRequest(Contract):
    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1,max_length=200)

class ImportRequest(Contract):
    group_id: str

class RetryRequest(Contract):
    task_ids: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1,max_length=200)

class ProbeRequest(Contract):
    mode: str = 'text'
    sample_id: str | None = None

def register_research(app, workspace):
    store=Store(workspace.settings.data_dir)
    review=ReviewDesk(store)
    gateway=Gateway(store,workspace)
    studio=DataStudio(store,review,gateway)
    evaluation=EvaluationLab(store,review,gateway)
    catalog=Catalog(store,review)
    operations=Operations(store)
    worker=Worker(store,review,gateway,evaluation)
    app.state.research=dict(store=store,review=review,studio=studio,evaluation=evaluation,gateway=gateway,worker=worker,catalog=catalog)

    from .screenshot_review import register_screenshot_review
    register_screenshot_review(app,store,review)

    from .benchmark import register_benchmark
    register_benchmark(app,store,gateway,worker)
    from .agent_evaluation import register_agent_evaluation
    register_agent_evaluation(app,workspace,store,gateway,worker)

    @app.middleware('http')
    async def audit_request(request,call_next):
        request_id=uid('request')
        product=next((p for p in ['review','studio','evaluation','settings'] if request.url.path.startswith('/v1/'+p)),None)
        if request.url.path.startswith('/v1/research/'): product=product or 'review'
        if request.url.path.endswith('/workbench'): product='workbench'
        token=audit.context.set(dict(request_id=request_id,correlation_id=request_id,product=product))
        try:
            response=await call_next(request)
            user=getattr(request.state,'user',None)
            if user and request.method in ['POST','PUT','DELETE','PATCH'] and product and response.status_code>=400:
                try:
                    with store.tx() as db:
                        audit.emit(db,user.id,'request.rejected','request',request.url.path,outcome='rejected',event_key='rejected:'+request_id,details={'status_code':response.status_code},reason='请求被拒绝')
                except Exception: audit.log.exception('Could not persist request rejection')
            response.headers['X-Research-Request-ID']=request_id
            return response
        finally: audit.context.reset(token)

    def owner(request):
        return request.state.user.id

    def relay_operations(user):
        with store.tx() as db:
            for e in workspace.operation_events(user):
                ctx=audit.context.set(dict(actor_id=e['actor_id'],actor_type=e['actor_type'],product=e['product'],request_id=e.get('request_id'),correlation_id=e.get('correlation_id')))
                try: audit.emit(db,user,e['action'],e['object_type'],e['object_id'],event_key='external:'+e['id'],changes=e['changes'],reason=e['reason'],occurred_at=e['occurred_at'],details={'source_contract':e['contract'],'source_event_id':e['id']})
                finally: audit.context.reset(ctx)

    @app.get('/v1/evaluation/leaderboard')
    def leaderboard_view(request:Request,scope:str='official',family:str='all',cohort_id:str='',sort:str='score',offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),q:str=Query('',max_length=200),category:str='all',comparison:str='models',include_baseline:bool=False,include_active:bool=False,include_catalogue:bool=False,model_id:str='',method_id:str=''):
        from screenshotlegal.research.leaderboard import leaderboard
        from screenshotlegal.research.leaderboard_taxonomy import method_info,categories
        registry=app.state.research['agent_experiments'].registry
        # Reuse the credential-free settings view; never freeze or call a model.
        models=[dict(config_id=m.id,name=m.name,model=m.model_name,supports_vision=m.supports_vision,
                     enabled=m.allow_external_egress,configured=m.has_api_key)
                for m in workspace.preferences(owner(request)).models()]
        methods=[]
        for m in registry.public()['candidates']:
            available=bool(m.get('steps'))
            frozen=registry.method(m['id']) if available else m
            info=method_info(dict(method=frozen))
            refs=[p for p in registry.papers if p['paper_id'] in frozen.get('references',[])]
            methods.append(dict(info,categories=categories('agent','case_analysis',info),available=available,
                                sources=[url for p in refs for url in p.get('sources',[])]))
        return leaderboard(store,owner(request),scope=scope,family=family,cohort_id=cohort_id,sort=sort,offset=offset,limit=limit,q=q,category=category,comparison=comparison,include_baseline=include_baseline,include_active=include_active,model_id=model_id,method_id=method_id,inventory=dict(models=models,methods=methods) if include_catalogue else None,
            case_access=lambda cid:app.state.auth.access(request.state.user,cid),
            agent_versions=dict(implementation_digest=app.state.research['agent_experiments'].registry.code_digest,registry_digest=app.state.research['agent_experiments'].registry.digest))

    @app.get('/v1/research/operations')
    def operation_list(request:Request,kind:str='',q:str='',flow_id:str='',offset:int=0,limit:int=50):
        return operations.rows(owner(request),kind,q,flow_id,offset,limit)

    @app.get('/v1/research/resolve')
    def resolve_operation(request:Request,object_id:str):
        try:return operations.resolve(owner(request),object_id)
        except KeyError:
            try:
                workspace.preferences(owner(request)).owned(object_id)
                return dict(id=object_id,kind='settings.model',href='/evaluation.html?models=1')
            except KeyError:
                from urllib.parse import urlencode
                case=workspace.repo.optional('cases',object_id)
                if case:
                    app.state.auth.access(request.state.user,object_id)
                    return dict(id=object_id,kind='workbench.case',href='/?'+urlencode({'case':object_id}))
                run=workspace.repo.optional('analysis_runs',object_id)
                if run:
                    app.state.auth.access(request.state.user,run['case_id'])
                    return dict(id=object_id,kind='workbench.run',href='/?'+urlencode({'case':run['case_id']}))
                raise KeyError('对象不存在或无访问权限')

    @app.get('/v1/research/operations/{kind}/{id}')
    def operation_detail(kind:str,id:str,request:Request):
        return operations.get(owner(request),kind,id)

    @app.get('/v1/research/flows/{id}/artifacts/{name}')
    def flow_artifact(id:str,name:str,request:Request):
        file=operations.artifact(owner(request),id,name)
        with store.tx() as db:audit.emit(db,owner(request),'research.flow.artifact_downloaded','research.flow',id,details={'flow_id':id,'filename':name},reason='下载已校验流程产物')
        return FileResponse(file,filename=name,media_type='application/octet-stream')

    @app.get('/v1/research/audit-events')
    def audit_events(request:Request,filters:AuditFilter=Depends()):
        relay_operations(owner(request))
        data=filters.model_dump();limit=data.pop('limit')
        return audit.query(store,owner(request),limit=limit,**data)

    @app.get('/v1/research/audit-summary')
    def audit_summary(request:Request,filters:AuditFilter=Depends(),group_by:str="day"):
        relay_operations(owner(request))
        data=filters.model_dump();data.pop('limit')
        return audit.summary(store,owner(request),group_by=group_by,**data)

    @app.get('/v1/research/audit-events/export')
    def audit_export(request:Request,filters:AuditFilter=Depends(),format:str="json"):
        user=owner(request);relay_operations(user);data=filters.model_dump();data.pop('limit');data.pop('cursor')
        where,args=audit.filters(user,**data)
        with store.read() as db:
            rows=[audit.unpack(r) for r in db.execute('SELECT * FROM audit_events WHERE '+where+' ORDER BY seq',args)]
        with store.tx() as db: audit.emit(db,user,'audit.export','audit','filtered',details={'filters':data,'count':len(rows)})
        if format=='log': return Response('\n'.join(r['formatted_log'] for r in rows),media_type='text/plain',headers={'Content-Disposition':'attachment; filename="operation-audit.log"'})
        if format!='json': raise ValueError('仅支持json/log导出')
        return Response(dumps(rows),media_type='application/json',headers={'Content-Disposition':'attachment; filename="operation-audit.json"'})

    @app.get('/v1/research/audit-events/{id}')
    def audit_detail(id:str,request:Request):
        with store.read() as db:
            row=db.execute('SELECT * FROM audit_events WHERE id=? AND owner=?',(id,owner(request))).fetchone()
            if not row: raise KeyError('Audit event not found')
            return audit.unpack(row)


    @app.get('/v1/review/samples')
    def samples(request:Request):
        return review.list_samples(owner(request))

    @app.post('/v1/review/samples',status_code=201)
    def create_sample(request:Request,payload:SampleCreate):
        return review.create(owner(request),payload)

    @app.get('/v1/review/samples/{id}')
    def sample(id:str,request:Request):
        return review.detail(owner(request),id)

    @app.put('/v1/review/samples/{id}')
    def edit_sample(id:str,request:Request,payload:SampleEdit):
        return review.edit(owner(request),id,payload)

    @app.post('/v1/review/samples/{id}/upgrade-renderer',status_code=201)
    def upgrade_renderer(id:str,request:Request,payload:RendererUpgrade):
        return review.upgrade_renderer(owner(request),id,payload)

    @app.post('/v1/review/samples/{id}/restore-original',status_code=201)
    def restore_original(id:str,request:Request,payload:RestoreOriginalRequest):
        return catalog.restore_original(owner(request),id,payload.expected_revision,payload.idempotency_key)

    @app.post('/v1/review/samples/{id}/comments',status_code=201)
    def add_comment(id:str,request:Request,payload:CommentSave):
        return review.comment(owner(request),id,payload)

    @app.post('/v1/review/samples/{id}/comments/{comment_id}/process',status_code=201)
    def process_comment(id:str,comment_id:str,request:Request,payload:CommentProcess):
        return review.process_comment(owner(request),id,comment_id,payload)

    @app.get('/v1/review/samples/{id}/judgment')
    def judgment(id:str,request:Request):
        detail=review.detail(owner(request),id)
        content=detail['revision']['content']
        text=content.get('source_text','')
        return dict(sample_id=id,revision=detail['sample']['revision'],text=text,
                    available=bool(text.strip()),sha256=digest(text) if text.strip() else None,
                    references=content.get('source_refs',[]))

    @app.get('/v1/review/samples/{id}/draft')
    def draft(id:str,request:Request):
        user=owner(request)
        review.sample(user,id)
        return store.optional('review.draft',id+':'+user,user)

    @app.put('/v1/review/samples/{id}/draft')
    def save_draft(id:str,request:Request,payload:DraftSave):
        return review.save_draft(owner(request),id,payload)

    @app.delete('/v1/review/samples/{id}/draft')
    def delete_draft(id:str,request:Request,payload:DraftSave):
        user=owner(request)
        with store.tx() as db:
            review.sample(user,id,db)
            row=store.optional('review.draft',id+':'+user,user,db)
            if row and (row['version']!=payload.expected_version or row['draft_id']!=payload.draft_id):
                raise Conflict('草稿已更新，不能清除其他编辑内容')
            db.execute("DELETE FROM records WHERE kind='review.draft' AND id=? AND owner=?",(id+':'+user,user))
        return dict(ok=True)

    @app.post('/v1/review/samples/{id}/quality',status_code=201)
    def quality(id:str,request:Request,payload:QualitySave):
        return review.quality(owner(request),id,payload)

    @app.post('/v1/review/samples/{id}/quality-runs',status_code=201)
    def quality_run(id:str,request:Request,payload:QualityRun):
        user=owner(request)
        cached=store.cached(user,'quality.run:'+id,payload.idempotency_key,payload.model_dump())
        if cached is not None:
            return cached
        model=gateway.freeze(user,payload.model_id,vision=payload.coverage!='text')
        return review.queue_quality(user,id,payload,model)

    @app.get('/v1/review/quality')
    def qualities(request:Request):
        return store.list('review.quality',owner(request))

    def register_prompts(prefix,purpose):
        @app.get('/v1/'+prefix+'/prompts')
        def prompts(request:Request):
            return review.prompts(owner(request),purpose)
        @app.post('/v1/'+prefix+'/prompts',status_code=201)
        def prompt(request:Request,payload:PromptSave):
            return review.save_prompt(owner(request),purpose,payload)
        @app.get('/v1/'+prefix+'/prompts/export')
        def export_prompts(request:Request,name:str):
            with store.tx() as db: audit.emit(db,owner(request),purpose+'.prompt.export','prompt',name)
            return Response(review.prompt_markdown(owner(request),purpose,name),media_type='text/markdown',
                            headers={'Content-Disposition':'attachment; filename="prompt-history.md"'})
    register_prompts('review','review')
    register_prompts('studio','studio')

    @app.get('/v1/review/catalog')
    def groups():
        return catalog.groups()

    @app.post('/v1/review/import')
    def import_group(request:Request,payload:ImportRequest):
        return catalog.import_group(owner(request),payload.group_id)

    @app.post('/v1/review/assets',status_code=201)
    async def upload_original(request:Request,file:UploadFile=File()):
        user=owner(request)
        data=await file.read(workspace.settings.max_upload_bytes+1)
        await file.close()
        if len(data)>workspace.settings.max_upload_bytes:
            raise HTTPException(413,'图片超过单文件限制')
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ['PNG','JPEG','WEBP']:
                    raise ValueError('仅支持 PNG/JPEG/WebP')
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                width,height=image.size
                mime=Image.MIME[image.format]
                suffix={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}[image.format]
        except (OSError,ValueError,Image.DecompressionBombError):
            raise HTTPException(422,'无法验证图片') from None
        sha=digest(data)
        asset=dict(id=sha,path='originals/'+sha+suffix,sha256=sha,width=width,height=height,mime_type=mime,origin='upload')
        atomic_write(store.root/asset['path'],data)
        with store.tx() as db:
            old=store.optional('review.asset',sha,user,db)
            if not old:
                store.put('review.asset',asset,user,db,immutable=True)
        return dict(id=sha,sha256=sha,mime_type=mime,origin='upload')

    @app.get('/v1/review/assets/{id}')
    def original(id:str,request:Request):
        asset=store.get('review.asset',id,owner(request))
        return FileResponse(verified(store.root,asset),media_type=asset['mime_type'],
                            headers={'Cache-Control':'private, max-age=31536000, immutable','X-Content-Type-Options':'nosniff'})

    @app.get('/v1/review/manifests/{id}')
    def manifest(id:str,request:Request):
        return store.get('review.manifest',id,owner(request))

    @app.get('/v1/review/manifests/{id}/pages/{page}')
    def image(id:str,page:int,request:Request):
        manifest=store.get('review.manifest',id,owner(request))
        asset=next((a for a in manifest['pages'] if a['page']==page),None)
        if not asset:
            raise KeyError('Page not found')
        return FileResponse(verified(store.root,asset),media_type=asset['mime_type'],
                            headers={'Cache-Control':'private, max-age=31536000, immutable','ETag':'"'+asset['sha256']+'"','X-Content-Type-Options':'nosniff'})

    @app.post('/v1/review/releases',status_code=201)
    def release(request:Request,payload:ReleaseCreate):
        return review.create_release(owner(request),payload)

    @app.get('/v1/review/releases')
    @app.get('/v1/evaluation/releases')
    def releases(request:Request):
        return review.releases(owner(request))

    @app.get('/v1/studio/sources')
    def sources(request:Request):
        return review.list_samples(owner(request))

    @app.get('/v1/studio/comparison')
    def comparison(request:Request):
        return review.comparison(owner(request))

    @app.get('/v1/studio/feedback')
    def studio_feedback(request:Request,source_sample_id:str):
        return studio.feedback(owner(request),source_sample_id)

    @app.post('/v1/studio/batches',status_code=201)
    def create_batch(request:Request,payload:BatchCreate):
        return studio.create_batch(owner(request),payload)

    @app.get('/v1/studio/batches')
    def batches(request:Request):
        user=owner(request)
        rows=studio.batches(user)
        for row in rows:
            states=[]
            for sid in row['sample_ids']:
                s=review.sample(user,sid)
                j=store.job(s['render_job_id'],user)
                states.append(j['status'])
            row['render_statuses']=states
            row['package_ready']=len(states)==row['count'] and all(s=='completed' for s in states)
            if row['status']=='completed':
                row['status']='ready_to_package' if row['package_ready'] else 'rendering'
        return rows

    @app.get('/v1/studio/batches/{id}/export')
    def export_batch(id:str,request:Request):
        user=owner(request)
        batch=store.get('studio.batch',id,user)
        if len(batch['sample_ids'])!=batch['count']:
            raise Conflict('生成尚未全部完成')
        buffer=io.BytesIO()
        manifest=dict(contract=CONTRACT,batch_id=id,created_at=now(),samples=[])
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('batch.json',dumps(batch))
            archive.writestr('prompt-history.md',review.prompt_markdown(user,'studio',batch['prompt']['name']))
            archive.writestr('generation-job.json',dumps({k:v for k,v in store.job(batch['job_id'],user).items() if k!='lease_token'}))
            for sid in batch['sample_ids']:
                detail=review.detail(user,sid)
                s=detail['sample']
                render=store.get('review.manifest',s.get('published_manifest') or '',user)
                if render['revision']!=s['revision']:
                    raise Conflict('当前样本版本尚未完成渲染')
                archive.writestr(sid+'/review-history.json',dumps(detail))
                for job in detail['jobs']:
                    archive.writestr(sid+'/jobs/'+job['id']+'.json',dumps({k:v for k,v in store.job(job['id'],user).items() if k!='lease_token'}))
                archive.writestr(sid+'/render-manifest.json',dumps(render))
                for page in render['pages']:
                    archive.writestr(sid+'/'+str(page['page'])+'.png',verified(store.root,page).read_bytes())
                manifest['samples'].append(dict(id=sid,revision=s['revision'],text_hash=render['text_hash'],manifest_hash=render['sha256']))
            archive.writestr('manifest.json',dumps(manifest))
        data=buffer.getvalue()
        sha=digest(data)
        atomic_write(store.root/('packages/'+sha+'.zip'),data)
        with store.tx() as db:
            store.put('studio.package',dict(id=uid('package'),batch_id=id,sha256=sha,manifest=manifest,created_at=now()),user,db,immutable=True)
        return Response(data,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="'+id+'.zip"'})

    @app.post('/v1/evaluation/runs',status_code=201)
    def create_evaluation(request:Request,payload:EvaluationCreate):
        return evaluation.create_run(owner(request),payload)

    @app.get('/v1/evaluation/history')
    def evaluation_history(request:Request,category:Literal['all','formal','trial','capability','benchmark']='all',offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
        from screenshotlegal.research.history import history
        return history(store,owner(request),category,offset,limit)

    @app.get('/v1/evaluation/runs')
    def evaluation_runs(request:Request):
        return evaluation.runs(owner(request))

    @app.get('/v1/evaluation/runs/{id}')
    def evaluation_results(id:str,request:Request):
        return evaluation.results(owner(request),id)

    @app.get('/v1/evaluation/runs/{id}/export')
    def evaluation_export(id:str,request:Request,failures_only:bool=False):
        result=evaluation.results(owner(request),id)
        with store.tx() as db: audit.emit(db,owner(request),'evaluation.export','evaluation.run',id,details={'run_id':id,'release_id':result['run']['release_id'],'sample_ids':result['run']['frozen_sample_ids'],'failures_only':failures_only})
        if failures_only:
            result['attempts']=[a for a in result['attempts'] if a['status'] in ['failed','unknown','cancelled']]
        return Response(dumps(result),media_type='application/json',headers={'Content-Disposition':'attachment; filename="'+id+'.json"'})

    @app.post('/v1/evaluation/runs/{id}/retry',status_code=201)
    def retry_evaluation(id:str,request:Request,payload:RetryRequest):
        return evaluation.retry(owner(request),id,payload.task_ids,payload.idempotency_key)

    @app.post('/v1/evaluation/models/{id}/test')
    async def probe(id:str,request:Request,payload:ProbeRequest):
        user=owner(request)
        if payload.mode not in ['text','image']:
            raise HTTPException(422,'mode must be text/image')
        model=gateway.freeze(user,id,vision=payload.mode=='image')
        messages=[dict(role='user',content='Reply OK')]
        if payload.mode=='image':
            if not payload.sample_id:
                raise ValueError('请先选择一条已渲染样本')
            sample=review.sample(user,payload.sample_id)
            manifest=store.get('review.manifest',sample.get('published_manifest') or '',user)
            from screenshotlegal.research.gateway import request_messages
            messages=request_messages(store,dict(question='简要描述图片中一处可见内容',images=manifest['pages'][:1]))
        started=now()
        try:
            response=await gateway.call(user,model,messages,'probe',uid('probe'))
            result=dict(id=uid('probe'),model_snapshot=model,mode=payload.mode,success=True,latency_ms=response['latency_ms'],created_at=started,response=response,scope='capability',sample_id=payload.sample_id)
        except ModelFailure as error:
            result=dict(id=uid('probe'),model_snapshot=model,mode=payload.mode,success=False,error=error_view(error),created_at=started,scope='capability',sample_id=payload.sample_id)
        with store.tx() as db:
            store.put('evaluation.probe',result,user,db,immutable=True)
        return result

    @app.get('/v1/research/jobs')
    def jobs(request:Request):
        return store.jobs(owner(request))

    @app.get('/v1/research/jobs/{id}')
    def job(id:str,request:Request):
        return {k:v for k,v in store.job(id,owner(request)).items() if k!='lease_token'}

    @app.post('/v1/research/jobs/{id}/cancel')
    def cancel(id:str,request:Request):
        user=owner(request)
        with store.tx() as db:
            row=store.job(id,user,db)
            if row['kind']=='benchmark_pipeline': raise ValueError('请从按图流程停止，不能绕过依赖单独取消子任务')
            if row['status'] in ['queued','running']:
                row['cancel_requested']=True
                store.save_job(db,row)
            return {k:v for k,v in row.items() if k!='lease_token'}

    @app.post('/v1/research/jobs/{id}/retry',status_code=201)
    def retry_job(id:str,request:Request,payload:RetryRequest):
        user=owner(request)
        with store.tx() as db:
            old=store.job(id,user,db)
            if old['kind'] in ['evaluation','benchmark','benchmark_pipeline']:
                raise ValueError('评测须从运行的失败范围创建重试')
            if old['status'] not in ['failed','unknown','cancelled','completed']:
                raise Conflict('任务仍在进行')
            def action():
                row=store.enqueue(db,user,old['kind'],old['payload'])
                row['parent_job_id']=id
                row['checkpoints']=old['checkpoints']
                store.save_job(db,row)
                if old['kind']=='generate':
                    batch=store.get('studio.batch',old['payload']['batch_id'],user,db)
                    batch.update(job_id=row['id'],status='queued')
                    store.put('studio.batch',batch,user,db)
                if old['kind']=='render':
                    sample=review.sample(user,old['payload']['sample_id'],db)
                    if sample['revision']==old['payload']['revision']['number']:
                        sample['render_job_id']=row['id']
                        store.put('review.sample',sample,user,db)
                return row
            return store.idem(db,user,'job.retry:'+id,payload.idempotency_key,{},action)
    return worker
