"""Resolve authorized frozen sources without following mutable parser output."""
from pydantic import Field
from screenshotlegal.domain.common.models import StrictModel, digest

class ResolveRequest(StrictModel):
    source_ref_id: str = Field(min_length=1,max_length=300)
    analysis_run_id: str | None = None
    quote: str | None = Field(default=None,max_length=10000)
    start: int | None = Field(default=None,ge=0)
    end: int | None = Field(default=None,ge=0)

def resolve_source(workspace,documents,case_id,request):
    if request.analysis_run_id:
        run=workspace.repo.get('analysis_runs',request.analysis_run_id)
        if run['case_id']!=case_id:raise KeyError('来源运行不属于本案')
        ref=next((r for r in run['input_snapshot']['source_refs'] if r['id']==request.source_ref_id),None)
        if ref is None:raise KeyError('来源不属于本次冻结输入')
    else:
        ref=workspace.repo.get('source_refs',case_id+':'+request.source_ref_id)
    text=ref['text'] if 'text' in ref else ref['quote']
    if ref.get('source_kind')=='document':
        snapshot=documents.store.snapshot(case_id,ref['parse_snapshot_id'])
        block=next((b for b in snapshot['blocks'] if b['id']==ref['block_id']),None)
        if block is None or block['text']!=text or digest(text)!=ref['text_digest']:
            raise ValueError('冻结来源与解析快照不一致')
        row=documents.store.get(case_id,snapshot['document_id'])
        if row['sha256']!=ref['source_sha256']:raise ValueError('来源原件身份不一致')
        documents.source(row)
        source=dict(ref)
    else:
        item=workspace.repo.get('evidence_items',case_id+':'+ref['evidence_id'])
        workspace.storage.verified_path(item)
        source=dict(ref,text=text,text_digest=digest(text),source_sha256=item['sha256'],
                    original_url='/v1/cases/'+case_id+'/evidence/'+item['id']+'/file',
                    coordinate_space='pixels' if ref.get('bbox') else None,
                    source_locator='case:'+case_id+'/source:'+ref['id'],
                    spatial_resolution='region' if ref.get('bbox') else 'none')
    quote=request.quote;matches=[]
    if request.start is not None or request.end is not None:
        if request.start is None or request.end is None or not 0<=request.start<request.end<=len(text):raise ValueError('引用字符范围无效')
        if quote is not None and text[request.start:request.end]!=quote:raise ValueError('引文与指定字符范围不一致')
        matches=[dict(start=request.start,end=request.end,quote=text[request.start:request.end])]
    elif quote:
        start=0
        while (index:=text.find(quote,start))>=0:
            matches.append(dict(start=index,end=index+len(quote),quote=quote));start=index+1
    status='not_requested' if quote is None and request.start is None else 'exact' if len(matches)==1 else 'ambiguous' if matches else 'unresolved'
    return dict(source=source,text_match=status,matches=matches,char_unit='unicode_code_point',
                spatial_resolution=source.get('spatial_resolution','none'),
                limitation='文本定位不代表原图OCR或法律命题已经人工认证')
