"""Product-owned source contract; parser IDs never replace original evidence identity."""
import math
from typing import Literal
from pydantic import Field, model_validator
from screenshotlegal.domain.common.models import StrictModel, digest

class FrozenSource(StrictModel):
    id: str
    schema_version: str = 'source-ref.v2'
    source_role: Literal['primary_case_evidence'] = 'primary_case_evidence'
    evidence_id: str
    source_sha256: str
    text: str
    source_kind: Literal['message','document']
    message_id: str | None = None
    parse_run_id: str | None = None
    parse_snapshot_id: str | None = None
    profile_digest: str | None = None
    parser_revision: str | None = None
    block_id: str | None = None
    page_no: int | None = Field(default=None,ge=1)
    page_kind: Literal['physical_page','logical_unit','image'] = 'image'
    bbox: list[float] | None = None
    coordinate_space: Literal['pixels','normalized_1000'] | None = None
    frame_width: float | None = Field(default=None,gt=0)
    frame_height: float | None = Field(default=None,gt=0)
    text_digest: str
    char_unit: Literal['unicode_code_point'] = 'unicode_code_point'
    text_match: Literal['exact'] = 'exact'
    spatial_resolution: Literal['region','page','logical_unit','none'] = 'none'
    source_locator: str
    original_url: str
    preview_url: str | None = None
    speaker: str | None = None
    timestamp: str | None = None
    review_status: Literal['unreviewed','verified','rejected','stale'] = 'unreviewed'

    @model_validator(mode='after')
    def coordinate_contract(self):
        if self.bbox is not None:
            box=self.bbox
            if len(box)!=4 or any(not math.isfinite(v) for v in box) or not (0<=box[0]<box[2] and 0<=box[1]<box[3]):
                raise ValueError('Invalid source rectangle')
            if self.coordinate_space is None: raise ValueError('Rectangle requires a coordinate frame')
            width,height=(1000,1000) if self.coordinate_space=='normalized_1000' else (self.frame_width,self.frame_height)
            if width is None or height is None or box[2]>width or box[3]>height: raise ValueError('Rectangle outside its coordinate frame')
        return self

class DocumentSourceRef(FrozenSource):
    quote: str = ''
    evidence_page: int | None = Field(default=None,ge=1)


def freeze_sources(workspace,documents,case_id,document_ids,*,include_messages=True):
    sources=[];hashes=set();snapshots=[];assets=[]
    evidence={e['id']:e for e in workspace.evidence(case_id)}
    refs={r['id']:r for r in workspace.repo.list('source_refs',case_id=case_id)}
    for message in workspace.active_messages(case_id) if include_messages else []:
        item=evidence[message['evidence_id']]
        workspace.storage.verified_path(item);hashes.add(item['sha256'])
        for rid in message['source_refs']:
            ref=refs[rid];text=ref['quote']
            if text not in message['text']:raise ValueError('转录来源与文本不一致')
            sources.append(FrozenSource(id=rid,evidence_id=item['id'],source_sha256=item['sha256'],text=text,
                source_kind='message',message_id=message['id'],bbox=ref.get('bbox'),
                coordinate_space='pixels' if ref.get('bbox') else None,frame_width=item.get('width'),frame_height=item.get('height'),
                spatial_resolution='region' if ref.get('bbox') else 'none',text_digest=digest(text),
                speaker=message.get('speaker'),timestamp=message.get('timestamp'),
                source_locator='case:'+case_id+'/source:'+rid,
                original_url='/v1/cases/'+case_id+'/evidence/'+item['id']+'/file').model_dump())
    for document_id in document_ids:
        row=documents.store.get(case_id,document_id);documents.source(row)
        snapshot=documents.store.freeze(case_id,document_id)
        snapshots.append({k:v for k,v in snapshot.items() if k!='blocks'});hashes.add(snapshot['source_sha256'])
        assets.append(dict(id=snapshot['evidence_id'],case_id=case_id,filename=row['filename'],sha256=row['sha256'],mime_type=row['mime_type'],kind='document',original_url='/v1/cases/'+case_id+'/documents/'+document_id+'/file'))
        for block in snapshot['blocks']:
            if block['type'] in ['image','chart']:continue
            rid='dref.'+snapshot['id']+'.'+block['id']
            logical=row['suffix'] in {'.docx','.xlsx','.pptx','.txt','.md','.csv'}
            sources.append(FrozenSource(id=rid,evidence_id=snapshot['evidence_id'],source_sha256=snapshot['source_sha256'],
                text=block['text'],source_kind='document',parse_run_id=snapshot['parse_run_id'],parse_snapshot_id=snapshot['id'],
                profile_digest=snapshot.get('profile_digest'),parser_revision=snapshot['parser'],
                block_id=block['id'],page_no=block['page'],page_kind='logical_unit' if logical else 'image' if row['suffix'] in {'.png','.jpg','.jpeg','.webp'} else 'physical_page',
                bbox=block.get('bbox'),coordinate_space=block.get('coordinate_space'),
                spatial_resolution='region' if block.get('bbox') else 'logical_unit' if logical else 'page',
                text_digest=digest(block['text']),source_locator='case:'+case_id+'/parse:'+snapshot['id']+'/block:'+block['id'],
                original_url='/v1/cases/'+case_id+'/documents/'+document_id+'/file',
                preview_url='/v1/cases/'+case_id+'/documents/'+document_id+'/pages/'+str(block['page'])+'/image').model_dump())
    return dict(sources=sources,documents=snapshots,assets=assets,source_file_hashes=sorted(hashes),perception_digest=digest(sources))
