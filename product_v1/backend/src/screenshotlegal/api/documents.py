"""Case-scoped document commands and immutable source queries."""
import asyncio
from fastapi import Request, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from screenshotlegal.documents.service import Documents
from screenshotlegal.documents.contracts import ParseOptions,ReadRange
from screenshotlegal.documents.reading import read_snapshot
from screenshotlegal.domain.evidence.documents import EvidenceDocument,ParseRun,ParseJobView,ParserCapabilities
from screenshotlegal.application.services.source_resolution import ResolveRequest,resolve_source

class Window(BaseModel):
    pages: int = Field(default=3,ge=1,le=10)
class ParseJob(Window):
    all_pages: bool = False
class Note(BaseModel):
    expected_revision: int = Field(ge=0)
    text: str = Field(max_length=50000)
    cursor: int = Field(ge=0)
class Analyze(BaseModel):
    offset: int = Field(ge=0)
    limit: int = Field(default=5,ge=1,le=20)
    model_id: str = Field(min_length=1)
    instruction: str = Field(default='概括本段事实、关键数据及不确定项，并引用原文。',max_length=3000)

def register_documents(app,workspace):
    service=Documents(workspace);app.state.documents=service
    prefix='/v1/cases/{case_id}/documents'
    @app.get('/v1/document-parsers',response_model=list[ParserCapabilities])
    def parsers():
        from screenshotlegal.documents.parsers import capabilities
        return capabilities()
    @app.get(prefix)
    def listing(case_id:str): return [service.public(row) for row in service.store.list(case_id)]
    @app.post(prefix,status_code=201)
    async def upload(case_id:str,file:UploadFile=File()):
        try:return service.ingest(case_id,file.filename or '',await file.read(workspace.settings.max_upload_bytes+1))
        finally:await file.close()
    @app.post(prefix+'/from-evidence/{evidence_id}',status_code=201)
    def existing(case_id:str,evidence_id:str):
        evidence=workspace.repo.get('evidence_items',case_id+':'+evidence_id)
        return service.ingest(case_id,evidence['filename'],workspace.storage.verified_path(evidence).read_bytes())
    @app.post(prefix+'/{doc_id}/parse-runs',status_code=201)
    def new_parse(case_id:str,doc_id:str,payload:ParseOptions):
        old=service.store.get(case_id,doc_id)
        return service.ingest(case_id,old['filename'],service.source(old).read_bytes(),payload.model_dump())
    @app.get('/v1/cases/{case_id}/document-snapshots/{snapshot_id}')
    def parse_snapshot(case_id:str,snapshot_id:str):return service.store.snapshot(case_id,snapshot_id)
    @app.post('/v1/cases/{case_id}/document-snapshots/{snapshot_id}/read')
    def read_frozen(case_id:str,snapshot_id:str,payload:ReadRange):
        return read_snapshot(service.store.snapshot(case_id,snapshot_id),payload)
    @app.get(prefix+'/{doc_id}')
    def read(case_id:str,doc_id:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),q:str=Query('',max_length=200)):
        return service.read(case_id,doc_id,offset,limit,q)
    @app.post(prefix+'/{doc_id}/parse-next')
    async def parse(case_id:str,doc_id:str,payload:Window):
        # Compatibility endpoint. The UI uses durable parse-jobs.
        return await asyncio.to_thread(service.parse_next,case_id,doc_id,payload.pages)
    @app.post(prefix+'/{doc_id}/parse-jobs',status_code=202,response_model=ParseJobView)
    def parse_job(case_id:str,doc_id:str,payload:ParseJob,request:Request):
        return service.store.submit_job(case_id,doc_id,payload.pages,payload.all_pages,request.state.user.id)
    @app.get('/v1/cases/{case_id}/document-jobs/{job_id}',response_model=ParseJobView)
    def job_status(case_id:str,job_id:str):return service.store.job(case_id,job_id)
    @app.post('/v1/cases/{case_id}/document-jobs/{job_id}/cancel',response_model=ParseJobView)
    def cancel_job(case_id:str,job_id:str):return service.store.cancel_job(case_id,job_id)
    @app.get(prefix+'/{doc_id}/file')
    def original(case_id:str,doc_id:str):
        row=service.store.get(case_id,doc_id)
        return FileResponse(service.source(row),media_type=row['mime_type'],filename=row['filename'],content_disposition_type='inline',headers={'X-Content-Type-Options':'nosniff'})
    @app.get(prefix+'/{doc_id}/pages/{page}/image')
    def preview(case_id:str,doc_id:str,page:int):
        path,mime=service.preview(case_id,doc_id,page)
        return FileResponse(path,media_type=mime,headers={'X-Content-Type-Options':'nosniff'})
    @app.put(prefix+'/{doc_id}/note')
    def note(case_id:str,doc_id:str,payload:Note,request:Request):
        row=service.store.get(case_id,doc_id)
        if payload.cursor>row['blocks']:raise ValueError('阅读位置超出已解析范围')
        return service.store.save_note(doc_id,'reading',payload.expected_revision,payload.text,payload.cursor,request.state.user.id)
    @app.post(prefix+'/{doc_id}/analyses')
    async def analyze(case_id:str,doc_id:str,payload:Analyze,request:Request):
        return await service.analyze(request.state.user,case_id,doc_id,payload.offset,payload.limit,payload.model_id,payload.instruction)
    @app.post('/v1/cases/{case_id}/resolve-source')
    def source(case_id:str,payload:ResolveRequest):return resolve_source(workspace,service,case_id,payload)
    @app.post(prefix+'/{doc_id}/publish')
    def publish(case_id:str,doc_id:str,request:Request):return service.publish(case_id,doc_id,request.state.user.id)
    @app.get(prefix+'/{doc_id}/parse-run',response_model=ParseRun)
    def parse_run(case_id:str,doc_id:str):
        row=service.public(service.store.get(case_id,doc_id))
        return ParseRun(id=row.get('parse_run_id',row['id']),evidence_id=row.get('evidence_id') or 'document.'+row['id'],
            source_sha256=row['sha256'],profile_digest=row.get('profile_digest','legacy'),parser=row['parser'],
            status=row['status'],parsed_units=row['parsed_pages'],total_units=row['total_pages'],artifacts=row.get('artifacts',[]))
    @app.get(prefix+'/{doc_id}/evidence-document',response_model=EvidenceDocument)
    def evidence_document(case_id:str,doc_id:str):
        row=service.store.get(case_id,doc_id);snapshot=service.store.freeze(case_id,doc_id)
        return EvidenceDocument(case_id=case_id,evidence_id=snapshot['evidence_id'],parse_run_id=snapshot['parse_run_id'],
            snapshot_id=snapshot['id'],source_sha256=snapshot['source_sha256'],parser=snapshot['parser'],profile_digest=snapshot['profile_digest'],
            page_kind='physical_page' if row['suffix']=='.pdf' else 'logical_unit',pages=snapshot['pages'],blocks=[dict(b,locator=b.get('locator') or 'document:'+doc_id+'/page:'+str(b['page'])+'/block:'+str(b['ordinal'])) for b in snapshot['blocks']])
    @app.get('/v1/cases/{case_id}/citation-ledger')
    def ledger(case_id:str,run_id:str|None=None):
        from screenshotlegal.application.services.proof import graph
        if run_id and workspace.repo.get('analysis_runs',run_id)['case_id']!=case_id:raise KeyError('运行不属于本案')
        value=graph(workspace.repo,case_id,run_id)
        return dict(analysis_run_id=value.analysis_run_id,bindings=value.citation_bindings)
    @app.get('/v1/cases/{case_id}/source-search')
    def source_search(case_id:str,q:str=Query(min_length=1,max_length=200),document_id:str|None=None):
        rows=[]
        for message in workspace.retriever.search(case_id,q):
            rows.append(dict(kind='message',text=message['text'],source_ref_ids=message['source_refs'],message_id=message['id']))
        publications=[p for p in service.store.publications(case_id) if p['status']=='published']
        selected={}
        for publication in sorted(publications,key=lambda p:p['created_at'],reverse=True):
            key=publication['sources'][0]['evidence_id'] if publication['sources'] else publication['document_id']
            selected.setdefault(key,publication)
        choices=[dict(document_id=document_id)] if document_id else list(selected.values())
        for choice in choices:
            current_id=choice['document_id'];row=service.store.get(case_id,current_id)
            publication=next((p for p in publications if p['document_id']==current_id),None)
            refs={r['block_id']:r for r in publication['sources']} if publication else {}
            for block in service.store.blocks(current_id,limit=50,q=q):
                ref=refs.get(block['id'])
                rows.append(dict(kind='document',document_id=current_id,parse_run_id=row.get('parse_run_id',row['id']),
                                 text=block['text'],block_id=block['id'],page=block['page'],locator=block['locator'],
                                 publication_id=publication['id'] if publication else None,
                                 source_ref_ids=[ref['id']] if ref else [],published=bool(publication)))
        return dict(items=rows,document_id=document_id)
    return service
