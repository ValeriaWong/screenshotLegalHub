"""Explicit local migration. No legacy entrypoint imports, credentials or model calls."""
import base64
import hashlib
import io
import json
import mimetypes
from collections import Counter,defaultdict
from pathlib import Path
from PIL import Image
from .contracts import digest,now
from .renderer import atomic_write
from . import audit,benchmark_legacy as legacy


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def jsonl(path): return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
def safe(base,name):
    p=(Path(base)/name).resolve()
    if not p.is_relative_to(Path(base).resolve()) or not p.is_file(): raise ValueError('来源路径不合法或不存在')
    return p

def blob(store,data,suffix='.json'):
    sha=digest(data);path='benchmarks/blobs/'+sha+suffix
    atomic_write(store.root/path,data)
    return dict(path=path,sha256=sha,bytes=len(data))

def import_legacy(store,owner,source,preparation,workspace):
    source=Path(source).resolve();preparation=Path(preparation).resolve();workspace=Path(workspace).resolve()
    inventory=jsonl(preparation/'inventory.jsonl');plans=jsonl(preparation/'task_manifest.jsonl')
    if len({p['task_id'] for p in plans})!=len(plans): raise ValueError('重复迁移任务ID')
    snapshot=digest(inventory);dataset_id='benchmark.'+snapshot[:24]
    old=store.optional('benchmark.dataset',dataset_id,owner)
    if old: return old
    index={r['path']:r for r in inventory};sourcefiles={}
    # Verify the complete original snapshot before committing any business record.
    for row in inventory:
        p=safe(source,row['path']);data=p.read_bytes()
        if digest(data)!=row['sha256'] or len(data)!=row['bytes']: raise ValueError('源文件已变化：'+row['path'])
        if p.suffix.lower() in ['.json','.jsonl','.md','.py'] and p.name.lower() not in ['config.json']:
            sourcefiles[row['path']]=blob(store,data,p.suffix.lower())
    attrs=read_json(source/'extracted_all_rect_attrs.json')
    candidates=read_json(preparation/'missing-assets-candidates.json')
    candidates={r['name']:r for r in candidates}
    restart={r['name']:r for r in read_json(workspace/'reports/restart/images_manifest.json')}
    assets={};aliases={};candidate_count=0
    for name in sorted({p['asset_ref']['logical_image_name'] for p in plans}):
        rel='images/'+name;origin='source_image_present';provenance={'path':rel,'sha256':index.get(rel,{}).get('sha256')}
        if rel in index:
            p=safe(source,rel);data=p.read_bytes();expected=index[rel]['sha256']
        else:
            c=candidates.get(name)
            if not c or not c.get('candidate_manifest_hash_verified'): raise ValueError('没有已核对的候选：'+name)
            p=safe(workspace,c['current_project_candidate']);data=p.read_bytes();expected=restart[name]['sha256']
            if c['current_project_candidate'] not in [restart[name]['path'],*restart[name].get('aliases',[])]: raise ValueError('候选来源不在历史清单内')
            origin='candidate_identity_unverified';candidate_count+=1
            provenance=dict(path=c['current_project_candidate'],sha256=expected,manifest='reports/restart/images_manifest.json',manifest_sha256=digest((workspace/'reports/restart/images_manifest.json').read_bytes()))
        if digest(data)!=expected: raise ValueError('原图哈希变化：'+name)
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            width,height=im.size;mime=Image.MIME[im.format];suffix={ 'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(im.format)
            if not suffix: raise ValueError('不支持的原图格式')
        path='originals/'+expected+suffix;atomic_write(store.root/path,data)
        assets[name]=dict(id=expected,path=path,sha256=expected,width=width,height=height,mime_type=mime,origin=origin,provenance=provenance,logical_image_name=name,split_group='bytes:'+expected)
        # Exact legacy data-URL aliases only use source images, sorted like the original loader.
        if origin=='source_image_present':
            dmime=mimetypes.guess_type(name)[0] or 'application/octet-stream';url='data:'+dmime+';base64,'+base64.b64encode(data).decode()
            alias='dataurl_'+hashlib.sha1(url.encode()).hexdigest()[:16]+'.'+('jpg' if dmime.endswith('jpeg') else dmime.split('/')[-1])
            aliases[alias]=name
    grouped=defaultdict(list);notes=[];tasks=[]
    mapping=read_json(preparation/'field_mapping.json');labels={x['source_label']:x for x in mapping['label_mappings']}
    vocab={label:sorted({str(r.get('answer')) for r in attrs if r.get('label')==label and r.get('answer') is not None}) for label,m in labels.items() if m['answer_kind']=='categorical'}
    for p in plans:
        task=dict(p);name=p['asset_ref']['logical_image_name'];task['dataset_id']=dataset_id
        task['image_name']=name;task['asset']=assets[name]
        if p['migration_record_type']=='kie_candidate':
            task.update(answer_kind='kie',question='提取整张聊天截图的对话名称及所有消息，保留时间、说话人、内容、消息框、图片、转账与文件字段。',target=None,output_schema='kie-output.v1')
        else:
            raw=attrs[int(p['source_ref']['json_pointer'][1:])];task['legacy_raw']=raw
            task['target']=raw.get('answer');task['answer_kind']=labels[p['source_label']]['answer_kind']
            task['question']='识别以下字段：'+p['source_label']+'。字段定义：'+labels[p['source_label']]['rule']+'。仅根据输入回答，不足时明确未知。'
            if p['source_label'] in vocab:
                task['allowed_values']=vocab[p['source_label']];task['question']+=' 候选标签：'+json.dumps(task['allowed_values'],ensure_ascii=False)
            task['output_schema']='vqa-answer.v1'
        task['asset_status']=assets[name]['origin'];task['reference_status']='legacy_unverified'
        if p['migration_record_type']=='review_note': notes.append(task)
        else: tasks.append(task)
        grouped[name].append(task)
    files={name:blob(store,json.dumps(rows,ensure_ascii=False,allow_nan=False).encode()) for name,rows in grouped.items()}
    taskfile=blob(store,json.dumps(tasks,ensure_ascii=False,allow_nan=False).encode())
    # Keep all raw attempts and final views as separate historical records, including errors.
    historical=[]
    for row in read_json(preparation/'historical-runs.json'):
        data=read_json(source/row['path']);items=data.get('items',[])
        historical.append(dict(id='benchmark.history.'+digest([dataset_id,row['path']])[:24],dataset_id=dataset_id,name=row['path'],created_at=now(),historical_timestamp=data.get('timestamp'),status='imported',role='derived_final_view' if '__final_bbox' in row['path'] else 'raw_attempts',model=data.get('model'),summary=row,raw=sourcefiles[row['path']],usage=None,cost=None,provider_request_id=None,scope='historical_import'))
    evidence=sourcefiles.get('Qwen2.5-VL-32B-Instruct_evidence_outputs.json')
    if evidence:
        historical.append(dict(id='benchmark.history.'+digest([dataset_id,'evidence'])[:24],dataset_id=dataset_id,name='旧证据形式问答（非金标）',created_at=now(),status='imported',role='evidence_predictions',summary=dict(rows=len(read_json(source/'Qwen2.5-VL-32B-Instruct_evidence_outputs.json'))),raw=evidence,usage=None,cost=None,scope='historical_import'))
    final_name='output/d9ba389bd2b84d45b4ac787fd8147088-f0/Qwen_Qwen2.5-VL-32B-Instruct__final_bbox.json'
    parsed=legacy.load_structured(str(source/final_name),aliases);rects=legacy.load_rects(str(source/'extracted_all_rect_attrs.json'))
    details=legacy.compute_best_matches(rects,parsed);saved=read_json(source/'iou_match_report.json')['details']
    # JSON normalization converts tuple coordinates like the saved report.
    if json.loads(json.dumps(details,ensure_ascii=False))!=saved: raise ValueError('旧IoU回放不一致，迁移回滚')
    replay=blob(store,json.dumps(dict(details=details,source_prediction=sourcefiles[final_name],scorer_version='legacy-association-iou.v1',threshold=.6),ensure_ascii=False).encode())
    row=dict(id=dataset_id,name='旧工作流 KIE + VQA',created_at=now(),status='needs_review',snapshot_sha256=snapshot,source_directory=str(source),source_inventory=blob(store,json.dumps(inventory,ensure_ascii=False).encode()),source_files=sourcefiles,prepared_mapping=blob(store,(preparation/'field_mapping.json').read_bytes()),prepared_protocol=blob(store,(preparation/'scoring_protocol.json').read_bytes()),images=assets,legacy_aliases=aliases,importer_version='legacy-kie-vqa-import.v1',image_files=files,tasks=taskfile,counts=dict(source_files=len(inventory),images=len(assets),source_images=len(assets)-candidate_count,candidate_images=candidate_count,unique_image_hashes=len({a['sha256'] for a in assets.values()}),preparation_rows=len(plans),tasks=len(tasks),vqa=sum(t['task_family']!='kie.extract' for t in tasks),kie=sum(t['task_family']=='kie.extract' for t in tasks),review_notes=len(notes),legacy_iou=len(details),legacy_iou_pass=sum(d['best_iou']>=.6 for d in details),human_reviewed=0),replay=replay,formal_scoring_ready=False,split='unassigned',new_model_calls=0)
    with store.tx() as db:
        # Single SQLite transaction publishes the already verified immutable blobs.
        old=store.optional('benchmark.dataset',dataset_id,owner,db)
        if old: return old
        for asset in assets.values():
            if not store.optional('review.asset',asset['id'],owner,db):
                public={k:asset[k] for k in ['id','path','sha256','width','height','mime_type']};public['origin']='legacy_migration'
                store.put('review.asset',public,owner,db,immutable=True)
        for h in historical: store.put('benchmark.history',h,owner,db,immutable=True)
        for n in notes:
            store.put('benchmark.comment',dict(id=dataset_id+':'+n['task_id'],dataset_id=dataset_id,image_name=n['image_name'],task_id=n['task_id'],body=n['target'],source_ref=n['source_ref'],created_at=now(),source_actor='unknown',editor=owner,method='legacy_import',use_for_generation=True),owner,db,immutable=True)
        store.put('benchmark.dataset',row,owner,db,immutable=True)
        audit.emit(db,owner,'benchmark.import.completed','benchmark.dataset',dataset_id,details=row['counts'],reason='完整快照迁移；未认证旧参考，不调用模型')
    return row
