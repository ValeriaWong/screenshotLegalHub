from screenshotlegal.domain.evidence.sources import DocumentSourceRef
import asyncio
import json
import warnings
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, UploadFile, File, Request, Query, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from screenshotlegal import __version__
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.application.services.workspace import Workspace
from screenshotlegal.application.services.proof import graph, matrix
from screenshotlegal.domain.common.models import CaseCreate, CaseRecord, Selection, CompileRequest, RunRequest, ReviewRequest, GateRequest, ProofGraph, MatrixRow, Entity
from screenshotlegal.domain.evidence.models import EvidenceItem, SourceRef
from screenshotlegal.domain.evidence.assessments import Party, Reconciliation, LawyerAssessment
from screenshotlegal.domain.runtime.models import CasePlan
from screenshotlegal.runtime.events import snapshot
from screenshotlegal.runtime.review_gate import resolve_gate
from screenshotlegal.application.services.auth import AuthService, AuthError
from screenshotlegal.api.documents import register_documents
from screenshotlegal.api.workbench import register_workbench
from screenshotlegal.api.research import register_research
from screenshotlegal.api.accounts import register_accounts
from screenshotlegal.api.access import install_access
from screenshotlegal.domain.settings.models import UploadResult, BatchUploadResult

class PerceptionRequest(BaseModel):
    adapter: str = 'mock'
    fixtures: dict[str,list[dict[str,Any]]] = {}
    model_id: str | None = None
    evidence_ids: list[str] | None = None

def create_app(settings=None, repo=None):
    settings=settings or Settings()
    settings.data_dir.mkdir(parents=True,exist_ok=True)
    repo=repo or Repository(settings.database_url)
    workspace=Workspace(settings,repo)
    auth=AuthService(repo,settings)
    @asynccontextmanager
    async def lifespan(app):
        if settings.host!='127.0.0.1' and not settings.session_secure_cookie:
            warnings.warn('远程部署请使用 HTTPS 并设置 SESSION_SECURE_COOKIE=true')
        for run in repo.list('analysis_runs'):
            if run['status']=='RUNNING':
                run.update(status='INTERRUPTED',error='Server restarted; create a new analysis run')
                repo.put('analysis_runs',run['id'],run,run['case_id'])
        research_task=asyncio.create_task(research_worker.loop())
        document_task=asyncio.create_task(document_service.loop())
        try:
            yield
        finally:
            research_task.cancel()
            document_task.cancel()
            from contextlib import suppress
            with suppress(asyncio.CancelledError):
                await research_task
            with suppress(asyncio.CancelledError):
                await document_task
            await workspace.runtime.close()
    app=FastAPI(title='ScreenshotLegal',version=__version__,lifespan=lifespan)
    app.state.workspace=workspace
    app.state.auth=auth
    install_access(app,auth,repo)
    register_accounts(app,auth,workspace,settings)
    register_workbench(app,workspace,auth)
    document_service=register_documents(app,workspace)
    research_worker=register_research(app,workspace)
    @app.exception_handler(AuthError)
    async def auth_error(request,error):
        return JSONResponse(status_code=error.status,content={'detail':error.message})
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):
        return JSONResponse(status_code=422,content={'detail':'Invalid request','errors':[{'loc':e['loc'],'msg':e['msg'],'type':e['type']} for e in error.errors()]})
    @app.exception_handler(KeyError)
    async def missing(request,error):
        return JSONResponse(status_code=404,content={'detail':'Resource not found'})
    @app.exception_handler(ValueError)
    async def invalid(request,error):
        return JSONResponse(status_code=409,content={'detail':str(error)})
    @app.exception_handler(PermissionError)
    async def forbidden(request,error):
        return JSONResponse(status_code=403,content={'detail':str(error)})
    @app.get('/health')
    @app.get('/v1/health')
    def health():
        with repo.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text('SELECT 1 FROM cases LIMIT 1'))
        return {'status':'ok'}
    @app.get('/version')
    @app.get('/v1/version')
    def version():
        return {'version':__version__}
    @app.post('/v1/cases',response_model=CaseRecord,status_code=201)
    def create_case(request:CaseCreate,http_request:Request):
        return workspace.create_case(request,http_request.state.user.id)
    @app.get('/v1/cases',response_model=list[CaseRecord])
    def cases(request:Request):
        return [dict(c,access_role=auth.case_role(request.state.user,c)) for c in repo.list('cases') if auth.case_role(request.state.user,c)]
    @app.get('/v1/cases/{id}',response_model=CaseRecord)
    def get_case(id:str,request:Request):
        return auth.access(request.state.user,id)
    @app.get('/v1/evidence/formats')
    def formats():
        return dict(formats=[f for f in workspace.storage.registry.formats() if f['mime_type'] in settings.allowed_mime_types],max_files=settings.max_batch_files,max_file_bytes=settings.max_upload_bytes,max_batch_bytes=settings.max_batch_bytes)
    @app.post('/v1/cases/{id}/evidence',response_model=EvidenceItem)
    async def upload(id:str,file:UploadFile=File()):
        content=await file.read(settings.max_upload_bytes+1)
        return workspace.upload(id,file.filename or 'evidence',file.content_type,content)
    @app.post('/v1/cases/{id}/evidence/batch',response_model=BatchUploadResult)
    async def upload_batch(id:str,files:list[UploadFile]=File()):
        if not files or len(files)>settings.max_batch_files:
            raise HTTPException(413,detail='Too many files in one batch')
        results=[];total=0
        known={e['id'] for e in workspace.evidence(id)}
        for index,file in enumerate(files):
            filename=file.filename or 'evidence'
            try:
                if total>=settings.max_batch_bytes:
                    raise ValueError('Batch size limit reached; upload remaining files separately')
                content=await file.read(min(settings.max_upload_bytes+1,settings.max_batch_bytes-total+1))
                total+=len(content)
                if total>settings.max_batch_bytes:
                    raise ValueError('Batch size limit reached; upload remaining files separately')
                item=workspace.upload(id,filename,file.content_type,content)
                status='duplicate' if item.id in known else 'uploaded'
                known.add(item.id)
                results.append(UploadResult(index=index,filename=filename,status=status,evidence=item))
            except ValueError as error:
                results.append(UploadResult(index=index,filename=filename,status='failed',error=str(error)))
            finally:
                await file.close()
        return BatchUploadResult(results=results,uploaded=sum(r.status=='uploaded' for r in results),duplicates=sum(r.status=='duplicate' for r in results),failed=sum(r.status=='failed' for r in results))
    @app.get('/v1/cases/{id}/evidence',response_model=list[EvidenceItem])
    def evidence(id:str):
        return workspace.evidence(id)
    @app.get('/v1/cases/{id}/evidence/{evidence_id}/file')
    def evidence_file(id:str,evidence_id:str):
        item=repo.get('evidence_items',id+':'+evidence_id)
        return FileResponse(workspace.storage.verified_path(item),media_type=item['mime_type'],filename=item['filename'],content_disposition_type='inline',headers={'X-Content-Type-Options':'nosniff'})
    @app.get('/v1/cases/{id}/source-refs',response_model=list[SourceRef | DocumentSourceRef])
    def sources(id:str):
        repo.get('cases',id)
        return repo.list('source_refs',case_id=id)
    @app.get('/v1/cases/{id}/parties',response_model=list[Party])
    def parties(id:str):
        repo.get('cases',id)
        return [Party(id=p['id'],name=p['name'],identity_status=p.get('identity_status',p.get('status','unreviewed')),source_refs=p.get('source_refs',[])) for p in repo.list('parties',case_id=id)]
    @app.post('/v1/cases/{id}/reconciliations',response_model=Reconciliation)
    def reconcile(id:str,request:Reconciliation):
        return workspace.reconcile(id,request)
    @app.get('/v1/cases/{id}/reconciliations',response_model=list[Reconciliation])
    def reconciliations(id:str):
        repo.get('cases',id)
        return repo.list('reconciliations',case_id=id)
    @app.get('/v1/cases/{id}/lawyer-assessments',response_model=list[LawyerAssessment])
    def assessments(id:str):
        repo.get('cases',id)
        return repo.list('lawyer_assessments',case_id=id)
    @app.post('/v1/cases/{id}/perception/runs')
    async def perceive(id:str,request:PerceptionRequest,http_request:Request):
        return await workspace.perceive(id,request.adapter,request.fixtures,request.model_id,http_request.state.user.id,request.evidence_ids)
    @app.get('/v1/cases/{id}/search')
    def search(id:str,q:str=Query(max_length=200)):
        repo.get('cases',id)
        return workspace.retriever.search(id,q)
    @app.get('/v1/cases/{id}/matter-candidates')
    def candidates(id:str):
        repo.get('cases',id)
        return [dict(id=p['manifest']['id'],version=p['manifest']['version'],name_zh=p['manifest']['name_zh'],name_en=p['manifest']['name_en'],status=p['manifest']['status'],expert_review=p['manifest']['expert_review']) for p in workspace.matters.packs.values()]
    @app.put('/v1/cases/{id}/matter-selection')
    def select(id:str,request:Selection):
        return workspace.select_matter(id,request)
    @app.post('/v1/cases/{id}/analysis/compile',response_model=CasePlan)
    def compile(id:str,request:CompileRequest):
        return workspace.compile(id,request.overrides)
    @app.get('/v1/cases/{id}/case-plan',response_model=CasePlan)
    def plan(id:str):
        return repo.get('case_plans',id)
    @app.post('/v1/cases/{id}/analysis/runs')
    async def run(id:str,request:RunRequest):
        return workspace.start_run(id,request)
    @app.get('/v1/cases/{id}/analysis/runs')
    def runs(id:str):
        repo.get('cases',id)
        return repo.list('analysis_runs',case_id=id)
    @app.get('/v1/runs/{run_id}')
    def get_run(run_id:str):
        return snapshot(repo,run_id)
    @app.get('/v1/runs/{run_id}/events')
    async def events(run_id:str,request:Request):
        initial=snapshot(repo,run_id)
        async def stream():
            # Cursor first, then snapshot: no event can fall between these operations.
            cursor=max((e['sequence'] for e in repo.list('run_events',run_id=run_id)),default=0)
            state=snapshot(repo,run_id)
            yield 'event: state-snapshot\ndata: '+json.dumps(state,ensure_ascii=False)+'\n\n'
            while not await request.is_disconnected():
                try:
                    user=auth.current(request.cookies.get('screenshotlegal_session'))
                    auth.access(user,state['run']['case_id'])
                except AuthError:
                    return
                for e in sorted(repo.list('run_events',run_id=run_id),key=lambda e:e['sequence']):
                    if e['sequence']>cursor:
                        cursor=e['sequence']
                        yield f"id: {cursor}\nevent: {e['event']}\ndata: {json.dumps(e['data'],ensure_ascii=False)}\n\n"
                if repo.get('analysis_runs',run_id)['status'] in ['COMPLETED','FAILED','INTERRUPTED']:
                    return
                yield ': heartbeat\n\n'
                await asyncio.sleep(0.2)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    @app.post('/v1/runs/{run_id}/review-gates/{gate_id}')
    async def gate(run_id:str,gate_id:str,request:GateRequest):
        result=resolve_gate(repo,run_id,gate_id,request.action)
        workspace.runtime.schedule(run_id)
        return result
    @app.get('/v1/cases/{id}/proof-graph',response_model=ProofGraph)
    def proof(id:str,run_id:str|None=None):
        if run_id and repo.get('analysis_runs',run_id)['case_id']!=id:
            raise KeyError('Run belongs to another case')
        return graph(repo,id,run_id)
    @app.get('/v1/cases/{id}/proof-matrix',response_model=list[MatrixRow])
    def proof_matrix(id:str):
        return matrix(repo,id)
    def projection(kind):
        def endpoint(id:str)->list[Entity]:
            return [e for e in graph(repo,id).entities if e.kind==kind]
        return endpoint
    for path,kind in [('timeline','event'),('claims','claim'),('contradictions','contradiction'),('gaps','gap'),('strategy','strategy')]:
        app.add_api_route('/v1/cases/{id}/'+path,projection(kind),methods=['GET'],response_model=list[Entity],name=path)
    @app.post('/v1/cases/{id}/reviews')
    def review(id:str,request:ReviewRequest,http_request:Request):
        return workspace.review(id,request.model_copy(update={'reviewer':http_request.state.user.username}))
    @app.get('/v1/cases/{id}/reviews')
    def reviews(id:str):
        repo.get('cases',id)
        return repo.list('review_decisions',case_id=id)
    @app.get('/v1/matter-packs')
    def matters():
        return list(workspace.matters.packs.values())
    @app.get('/v1/skills')
    def skills():
        return [dict(**s.model_dump(),digest=workspace.skills.digests[s.id]) for s in workspace.skills.skills.values()]
    @app.post('/v1/demo')
    async def demo(request:Request):
        from screenshotlegal.cli.seed import seed
        return await seed(workspace,request.state.user.id)
    return app

app=create_app()
