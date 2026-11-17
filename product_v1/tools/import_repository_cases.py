"""Synchronize all repository dataset case versions into the product database.

Default is a read-only preflight. --apply backs up SQLite, then adds deterministic,
admin-owned cases. Existing cases and reviews are never overwritten or removed.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.application.services.workspace import Workspace
from screenshotlegal.domain.common.models import CaseRecord, digest, now
from screenshotlegal.plugins.perception.adapters import normalize

NOTICE = '研究资料，标注未获专业认证；材料性质及使用范围见来源说明。导入不产生法律结论。'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def lines(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]


def sha(content):
    return hashlib.sha256(content).hexdigest()


def safe(root, path):
    value = (root / path).resolve(strict=True)
    if not value.is_relative_to(root.resolve()):
        raise ValueError('Dataset path escapes repository: '+str(path))
    return value


def objects(value, pointer=''):
    if isinstance(value, dict):
        yield pointer, value
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                yield from objects(child, pointer+'/'+str(key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            if isinstance(child, (dict, list)):
                yield from objects(child, pointer+'/'+str(i))


def is_case(obj):
    return (isinstance(obj.get('participants'), list) and isinstance(obj.get('conversations'), list)
            and isinstance(obj.get('messages'), list)
            and all(isinstance(m, dict) and isinstance(m.get('text'), str) and m.get('id') for m in obj['messages']))


def visible_text(message):
    text = message.get('text', '')
    if message.get('kind')=='transfer' and isinstance(message.get('transfer'), dict):
        transfer=message['transfer']
        label={'expired':'已过期','received':'已被接收'}.get(transfer.get('receipt_status'),'转账')
        return '¥'+format(float(transfer['amount']),',.2f')+'\n'+label+'\n微信转账'
    if message.get('kind')=='file':
        kind=message.get('file_type','文档')
        text+='\n'+(kind if kind in ['文档','视频','音频','图片'] else kind+' 文档')
    attachment=message.get('attachment')
    if message.get('kind')=='attachment_excerpt' and isinstance(attachment,dict):
        parts=[attachment.get('title','')]
        for row in attachment.get('rows',[]):
            parts.append(' '.join(str(cell) for cell in row))
        parts.extend([attachment.get('footer',''),text])
        text='\n'.join(p for p in parts if p)
    if message.get('original_medium')=='voice_transcription_in_judgment':
        text='语音转文字\n'+text
    return text.strip()


def imported_timestamp(message):
    value = message.get('timestamp')
    if not value: return None
    # Layout minutes, scenario dates and uncertain dates must not become historical timestamps.
    basis = str(message.get('date_basis', ''))
    if basis in {'source_day', 'source_date', 'explicit_source_date'}:
        return str(value)[:10]
    return None


def discover(root, legacy_corpus=None):
    root = root.resolve()
    files = sorted(p for p in (root/'datasets').rglob('*') if p.is_file() and 'work' not in p.relative_to(root/'datasets').parts)
    signature = [(p.relative_to(root).as_posix(), p.stat().st_size, p.stat().st_mtime_ns) for p in files]
    parsed = {}; candidates = []; sources = defaultdict(list); source_objects = {}; ledgers = []
    errors = []
    for path in files:
        if path.suffix not in {'.json', '.jsonl'}: continue
        rel = path.relative_to(root).as_posix()
        try: value = load(path) if path.suffix == '.json' else lines(path)
        except (ValueError, UnicodeError) as exc:
            errors.append(dict(path=rel, error=str(exc))); continue
        parsed[rel] = value
        if path.name == 'execution_state.json' and isinstance(value, dict):
            ledgers.extend(dict(row, ledger=rel) for row in value.get('records', []))
        for pointer, obj in objects(value):
            if isinstance(obj.get('judgment_text'), str) and obj['judgment_text'].strip():
                text = obj['judgment_text']; key = sha(text.encode('utf-8'))
                sources[key].append(rel+'#'+pointer)
                source_objects.setdefault(key, dict(text=text,case_no=obj.get('neutral_citation'),title=obj.get('title'),language='en',jurisdiction='England and Wales',url=obj.get('html_link')))
            if isinstance(obj.get('text'), str) and obj.get('paragraphs') and ('case_no' in obj or 'judgment_text_sha256' in obj):
                key = sha(obj['text'].encode('utf-8'))
                alias = rel+('#'+pointer if pointer else '')
                sources[key].append(alias); source_objects.setdefault(key, obj)
            if is_case(obj):
                candidates.append(dict(path=rel, pointer=pointer, obj=obj))
    if errors: raise ValueError('Unparsed dataset JSON: '+json.dumps(errors, ensure_ascii=False))
    status_by_source = defaultdict(list); status_by_directory = defaultdict(list)
    for row in ledgers:
        key = row.get('judgment_text_sha256')
        status = {k:row[k] for k in ('ledger','source_index','new_sample_status','peer_round_action','auxiliary_only','artifact_directory') if k in row}
        if key: status_by_source[key].append(status)
        if row.get('artifact_directory'): status_by_directory[row['artifact_directory'].rstrip('/')].append(status)
    latest_ledger = max((r['ledger'] for r in ledgers), default='')
    def source_state(key):
        recent = [r for r in status_by_source[key] if r['ledger']==latest_ledger]
        if not recent: return '未列入当前轮清单'
        row=recent[-1]; action=row.get('peer_round_action')
        return {'withdraw':'已撤回，历史版本仅供追溯','confirm_gap':'来源缺口','auxiliary':'辅助材料','auxiliary_only':'辅助材料','recover':'已恢复为候选，未专业认证','pass':'候选样本，未专业认证','revise':'修订候选，未专业认证'}.get(action, '来源缺口' if row.get('new_sample_status')=='source_gap' else '候选样本，未专业认证')
    bundles = {}
    def add(kind, fingerprint, alias, title, metadata, assets, message_rows):
        key = 'repo.'+kind+'.'+fingerprint[:32]
        if key in bundles:
            bundles[key]['aliases'].append(alias)
            return
        bundles[key] = dict(id=key, kind=kind, fingerprint=fingerprint, aliases=[alias], title=title,
                            metadata=metadata, assets=assets, message_rows=message_rows)
    for key, aliases in sorted(sources.items()):
        obj = source_objects[key]
        metadata = {k:obj[k] for k in ('case_no','title','language','cause','jurisdiction','url','source_index') if k in obj}
        metadata.update(source_sha256=key, source_status=status_by_source[key],current_source_status=source_state(key), status='来源原文档案，是否有截图见各样本版本')
        title = '[原文] '+str(obj.get('case_no') or obj.get('title') or obj.get('id') or key[:12])
        add('source', key, aliases[0], title, metadata,
            [dict(name='判决原文.txt', mime='text/plain', content=obj['text'].encode('utf-8'), rows=[])], [])
        bundles['repo.source.'+key[:32]]['aliases'] = sorted(set(aliases))
    used_renders=set()
    for candidate in candidates:
        rel = candidate['path']; obj = candidate['obj']; path = root/rel
        directory = path.parent
        render_path = directory/'render.json'
        # Only the actual rendered case/final can use neighboring image boxes. Drafts may differ.
        render = parsed.get(render_path.relative_to(root).as_posix()) if path.name in {'case.json','final.json'} and not candidate['pointer'] else None
        assets = []; rows = []; render_identity = []
        by_id = {m['id']:m for m in obj['messages']}
        if len(by_id) != len(obj['messages']): raise ValueError('Duplicate message ID: '+rel)
        people = {p.get('id'):p.get('name') or p.get('display_name') or p.get('id') for p in obj['participants']}
        skipped = []
        if isinstance(render, dict):
            used_renders.add(render_path.relative_to(root).as_posix())
            for index, image in enumerate(render.get('images', [])):
                image_rel = image.get('path') or image.get('file')
                source = safe(root, directory.relative_to(root)/image_rel)
                content = source.read_bytes(); actual = sha(content)
                if image.get('sha256') and image['sha256'] != actual: raise ValueError('Image digest differs: '+str(source))
                boxes = image.get('boxes', image.get('messages', [])); located = []
                for box in boxes:
                    mid = box['message_id']
                    if mid not in by_id: raise ValueError('Unresolved render message: '+rel+':'+mid)
                    bbox = box.get('bbox_pixels', box.get('bbox'))
                    if bbox is None: raise ValueError('Missing image bbox: '+rel)
                    if 'bbox_pixels' in box:
                        x,y,w,h = bbox; bbox = [x,y,x+w,y+h]
                    if image.get('scroll_fragment') or box.get('same_message_scroll_crop'):
                        skipped.append(dict(message_id=mid, image=source.relative_to(root).as_posix(), reason='partial_scroll_crop; full author text retained separately'))
                        continue
                    m = by_id[mid]
                    located.append(dict(legacy_id=mid,text=visible_text(m),speaker=people.get(m.get('sender_id'),m.get('sender_id') or 'unknown'),
                                        timestamp=imported_timestamp(m),bbox=bbox,page=image.get('evidence_page',image.get('page'))))
                assets.append(dict(name=directory.name+'_'+source.name,mime='image/png',content=content,rows=located,path=source.relative_to(root).as_posix()))
                render_identity.append(dict(hash=actual, boxes=boxes, page=image.get('page'), evidence_page=image.get('evidence_page'), scroll_fragment=image.get('scroll_fragment')))
        metadata = {k:obj[k] for k in ('id','language','platform','cause','case_no','status','source_mode','not_judgment_reconstruction','limitations','constraints','suitability') if k in obj}
        source = parsed.get((directory/'source.json').relative_to(root).as_posix())
        if isinstance(source, dict) and isinstance(source.get('text'), str):
            source_key = sha(source['text'].encode('utf-8')); metadata['source_sha256'] = source_key
            metadata['source_case_id'] = 'repo.source.'+source_key[:32]
            metadata['source_case_no'] = source.get('case_no')
            metadata['source_status'] = status_by_source[source_key]
            metadata['current_source_status'] = source_state(source_key)
        metadata['selection_status'] = [r for r in status_by_directory.get(directory.relative_to(root).as_posix(), []) if r['ledger']==latest_ledger]
        metadata['archive_state'] = ('当前账本选中版本（仍须专业复核）' if metadata['selection_status'] else '历史/作者版本；不是当前验收候选')
        metadata['partial_messages_not_transcribed'] = skipped
        # Keep author dialogue separate from screenshot transcription; excludes answers/facts/reviewer labels.
        dialogue = dict(notice=NOTICE, participants=obj['participants'],conversations=obj['conversations'],messages=obj['messages'])
        assets.append(dict(name='作者对话稿（非原始聊天证据）.txt',mime='text/plain',content=json.dumps(dialogue,ensure_ascii=False,indent=2).encode('utf-8'),rows=[]))
        origin = rel.split('/snapshot/')[-1]
        collection_identity = '/'.join(origin.split('/')[:3])
        fingerprint = digest(dict(collection=collection_identity,case=obj, rendered=render_identity))
        alias = rel+('#'+candidate['pointer'] if candidate['pointer'] else '')
        version = next((part for part in path.parts if part.startswith('round_') or part.startswith('dependency_')),path.parent.name)
        title = '['+version+'] '+str(obj.get('case_no') or metadata.get('source_case_no') or obj.get('id') or path.parent.name)
        add('sample', fingerprint, alias, title, metadata, assets, rows)
    # Old render.versions snapshots can outlive their precise author case. Keep the
    # original images and manifest without borrowing a different revision's text.
    for rel,render in sorted(parsed.items()):
        if Path(rel).name!='render.json' or rel in used_renders or not isinstance(render,dict) or not isinstance(render.get('images'),list): continue
        directory=(root/rel).parent; assets=[]; identity=[]
        for image in render['images']:
            source=safe(root,directory.relative_to(root)/(image.get('path') or image.get('file')))
            content=source.read_bytes()
            if image.get('sha256') and sha(content)!=image['sha256']: raise ValueError('Archived image changed: '+str(source))
            assets.append(dict(name=directory.name+'_'+source.name,mime='image/png',content=content,rows=[],path=source.relative_to(root).as_posix()))
            identity.append(sha(content))
        assets.append(dict(name='历史渲染清单（非当前转录）.txt',mime='text/plain',content=json.dumps(render,ensure_ascii=False,indent=2).encode('utf-8'),rows=[]))
        origin=rel.split('/snapshot/')[-1]; collection='/'.join(origin.split('/')[:3])
        fingerprint=digest(dict(collection=collection,render=render,images=identity))
        add('render',fingerprint,rel,'[历史渲染] '+origin.split('/')[2]+' / '+origin.split('/')[4]+' / '+directory.name,
            dict(status='历史渲染档案；精确作者版本尚未关联，保留原图与框，不借用其他修订稿转录',collection=collection),assets,[])
    # Native V3 condition packages use JSONL and xyxy pixels, not the V2 render format.
    for manifest in sorted((root/'datasets').rglob('render_manifest.json')):
        directory = manifest.parent
        message_path = directory/'messages.jsonl'
        if not message_path.is_file(): continue
        collection = next((p for p in directory.parents if (p/'case_scope.json').is_file()),None)
        if collection is None: raise ValueError('V3 scope missing: '+str(directory))
        scenario = directory.parent.name; variant = directory.name
        scope = next(s for s in load(collection/'case_scope.json') if s['case_id']==scenario)
        messages = lines(message_path); by_id = {m['id']:m for m in messages}
        refs = [r for r in lines(collection/'source_refs.jsonl') if r.get('conversation_id')==scenario and r.get('variant')==variant]
        assets = []; identity = []
        for page in load(manifest)['pages']:
            source = safe(root,directory.relative_to(root)/page['file']); content=source.read_bytes()
            if sha(content)!=page['sha256']: raise ValueError('V3 image digest differs: '+str(source))
            located=[]
            for ref in refs:
                if ref['image_id'] != page['image_id']: continue
                if ref['message_id'] not in by_id: raise ValueError('V3 missing message')
                m=by_id[ref['message_id']]
                located.append(dict(legacy_id=m['id'],text=visible_text(m),speaker=m.get('sender_id','unknown'),timestamp=None,bbox=ref['bbox'],page=ref.get('evidence_page')))
            assets.append(dict(name=scenario+'_'+variant+'_'+source.name,mime='image/png',content=content,rows=located,path=source.relative_to(root).as_posix()))
            identity.append(dict(hash=sha(content),refs=located))
        if {r['legacy_id'] for a in assets for r in a['rows']} != set(by_id): raise ValueError('V3 incomplete message locations')
        metadata=dict(scope,variant=variant,status='合成校准条件；作者版本，未独立专业认证',collection=collection.name)
        fingerprint=digest(dict(collection=collection.relative_to(root).as_posix(),scope=scope,messages=messages,images=identity))
        add('v3',fingerprint,manifest.relative_to(root).as_posix(),'['+collection.name+'] '+scenario+' / '+variant,metadata,assets,[])
    # Legacy runtime corpus is exported read-only from the old index by the inventory task.
    legacy_path=safe(root,legacy_corpus) if legacy_corpus else root/'reports/admin_case_inventory_20261024/legacy-corpora.json'
    if legacy_path.is_file():
        stat=legacy_path.stat(); signature.append((legacy_path.relative_to(root).as_posix(),stat.st_size,stat.st_mtime_ns))
        legacy=load(legacy_path)
        if legacy.get('validation_errors'): raise ValueError('Legacy inventory has unresolved validation errors')
        from PIL import Image
        from io import BytesIO
        for legacy_id,corpus in sorted(legacy['cases'].items()):
            assets=[]; referenced=set()
            for image in corpus['images']:
                source=safe(root,image['file']); stat=source.stat(); signature.append((source.relative_to(root).as_posix(),stat.st_size,stat.st_mtime_ns)); content=source.read_bytes()
                if sha(content)!=image['sha256']: raise ValueError('Legacy image changed: '+image['file'])
                with Image.open(BytesIO(content)) as decoded: mime=Image.MIME.get(decoded.format)
                located=[]
                for record in corpus['records']:
                    if record.get('kind')!='message': continue
                    for ref in record.get('source_refs',[]):
                        if ref['image_id']!=image['image_id']: continue
                        located.append(dict(legacy_id=record['id'],text=record['text'],speaker=record.get('person') or 'unknown',timestamp=None,
                                            bbox=ref.get('bbox'),coordinate_space=ref.get('coordinate_space','pixels'),page=ref.get('evidence_page')))
                        referenced.add(record['id'])
                assets.append(dict(name=source.name,mime=mime,content=content,rows=located,path=image['file']))
            if referenced!={r['id'] for r in corpus['records'] if r.get('kind')=='message'}: raise ValueError('Unresolved legacy message: '+legacy_id)
            assets.append(dict(name='历史导入档案（含未复核标注）.txt',mime='text/plain',content=json.dumps(corpus,ensure_ascii=False,indent=2).encode('utf-8'),rows=[]))
            fingerprint=digest(dict(legacy_case_id=legacy_id,corpus=corpus))
            legacy_metadata={k:v for k,v in corpus['metadata'].items() if k!='historical_quiz_tasks'}
            legacy_metadata['archived_quiz_tasks']=len(corpus['metadata'].get('historical_quiz_tasks',[]))
            locator=corpus['metadata'].get('source_corpus') or 'blocks/retriever/artifacts/index.sqlite3#case='+legacy_id
            add('legacy',fingerprint,locator,'[旧库] '+legacy_id,
                dict(legacy_metadata,status='历史图像；转录/事件含未复核模型预测，不能视为事实金标',events_archived_not_asserted=sum(r.get('kind')=='event' for r in corpus['records'])),assets,[])
    return sorted(bundles.values(),key=lambda b:(b['kind'],b['aliases'][0])), signature


def prepare(workspace, bundle, owner):
    metadata=dict(bundle['metadata'],notice=NOTICE,kind=bundle['kind'],fingerprint=bundle['fingerprint'],source_paths=sorted(set(bundle['aliases'])))
    summary = json.dumps(metadata,ensure_ascii=False,indent=2)
    case = CaseRecord(id=bundle['id'],title=bundle['title'][:200],description=(NOTICE+'\n'+summary)[:10000],created_at=now(),owner_id=owner)
    assets=list(bundle['assets'])+[dict(name='来源与版本说明.txt',mime='text/plain',content=summary.encode('utf-8'),rows=[])]
    uploads={}; messages=[]; refs=[]
    from screenshotlegal.domain.evidence.models import EvidenceItem
    for index,asset in enumerate(assets):
        content=asset['content']; result=workspace.storage.registry.prepare(asset['name'],asset['mime'],content)
        if len(content)>workspace.settings.max_upload_bytes: raise ValueError('Asset too large')
        actual=sha(content)
        item=EvidenceItem(id='ev.'+actual[:24],case_id=case.id,filename=asset['name'][:200],mime_type=result.mime,sha256=actual,
                          storage_path=case.id+'/'+actual+'.'+result.extension,size_bytes=len(content),width=result.width,height=result.height,kind=result.kind)
        uploads.setdefault(item.id,(item,content))
        for row_index,row in enumerate(asset['rows']):
            normalized=normalize(item.model_dump(),[row])
            mid='msg.'+digest([case.id,index,row_index,row])[:24]; rid='ref.'+mid
            messages.append(normalized.messages[0].model_copy(update={'id':mid,'source_refs':[rid]}).model_dump())
            refs.append(normalized.source_refs[0].model_copy(update={'id':rid,'message_id':mid}).model_dump())
    records=[('cases',case.id,case.model_dump(),case.id,'',True)]
    for table,values in [('evidence_items',[u[0].model_dump() for u in uploads.values()]),('messages',messages),('source_refs',refs)]:
        records.extend((table,case.id+':'+v['id'],v,case.id,'',True) for v in values)
    for eid in uploads:
        selection=dict(perception_id='repository.'+case.id,message_ids=[m['id'] for m in messages if m['evidence_id']==eid])
        records.append(('active_perceptions',case.id+':'+eid,selection,case.id,'',False))
    return case,uploads,messages,records


def apply_one(workspace, prepared):
    case,uploads,messages,records=prepared
    if workspace.repo.optional('cases',case.id):
        existing=workspace.repo.list('evidence_items',case_id=case.id)
        known={item['sha256'] for item in existing}
        for item in existing: workspace.storage.verified_path(item)
        missing=[(item,content) for item,content in uploads.values() if item.sha256 not in known]
        if any(item.filename!='来源与版本说明.txt' for item,_ in missing):
            raise ValueError('Existing import has missing assets: '+case.id)
        if not missing: return 'existing'
        # New source aliases/status add a provenance revision without editing human case data,
        # transcriptions, active selections, reviews or the search index.
        new_files=[]
        try:
            additions=[]
            for item,content in missing:
                path=workspace.storage.path(item.storage_path)
                if not path.exists(): new_files.append(path)
                workspace.storage.save(case.id,item.filename,item.mime_type,content)
                additions.append(('evidence_items',case.id+':'+item.id,item.model_dump(),case.id,'',True))
            workspace.repo.batch(additions)
        except BaseException:
            for path in new_files:
                if path.parent!=workspace.storage.path(case.id) or path.is_symlink(): raise RuntimeError('Unsafe provenance rollback')
                path.unlink(missing_ok=True)
            raise
        return 'updated_provenance'
    directory=workspace.storage.path(case.id)
    if directory.exists(): raise ValueError('Orphan import directory needs reconciliation: '+str(directory))
    try:
        for item,content in uploads.values(): workspace.storage.save(case.id,item.filename,item.mime_type,content)
        with workspace.repo.engine.begin() as connection:
            workspace.repo.batch(records,connection=connection)
            workspace.retriever.index(case.id,messages,connection=connection)
    except BaseException:
        if directory.exists():
            if directory.resolve().parent!=workspace.storage.root or directory.is_symlink(): raise RuntimeError('Unsafe rollback directory')
            shutil.rmtree(directory)
        raise
    return 'created'


def sync(root, workspace, owner, report_path, apply=False, legacy_corpus=None):
    user=workspace.repo.get('auth_users',owner)
    if user.get('role')!='admin' or not user.get('enabled'): raise ValueError('Owner must be an enabled admin')
    bundles,signature=discover(root,legacy_corpus) if legacy_corpus else discover(root)
    prepared=[prepare(workspace,b,owner) for b in bundles]
    # Refuse a mixed filesystem snapshot before touching the live data.
    current_paths={p.relative_to(root).as_posix() for p in (root/'datasets').rglob('*') if p.is_file() and 'work' not in p.relative_to(root/'datasets').parts}
    if current_paths!={rel for rel,_,_ in signature if rel.startswith('datasets/')} :
        raise ValueError('Dataset file set changed during preflight')
    for rel,size,mtime in signature:
        stat=(root/rel).stat()
        if (stat.st_size,stat.st_mtime_ns)!=(size,mtime): raise ValueError('Dataset changed during preflight: '+rel)
    report=dict(schema='repository.admin.sync.v1',created_at=now(),applied=apply,data_dir=str(workspace.settings.data_dir),
                owner=owner,inventory_counts=dict(Counter(b['kind'] for b in bundles)),case_versions=len(bundles),
                aliases=sum(len(b['aliases']) for b in bundles),existing_cases_before=len(workspace.repo.list('cases')),
                images=sum(1 for p in prepared for item,_ in p[1].values() if item.kind=='image'),
                evidence_items=sum(len(p[1]) for p in prepared),messages=sum(len(p[2]) for p in prepared),
                backup=None,results=[],unresolved=[])
    if apply:
        backup=workspace.settings.data_dir/'backups'/('before-repository-sync-'+now().replace(':','').replace('+','')+'-'+uuid4().hex[:8]+'.sqlite3')
        backup.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(workspace.settings.data_dir/'screenshotlegal.sqlite3') as source:
            with sqlite3.connect(backup) as destination: source.backup(destination)
        report['backup']=str(backup)
    try:
        for bundle,value in zip(bundles,prepared):
            result=apply_one(workspace,value) if apply else 'validated'
            report['results'].append(dict(case_id=bundle['id'],kind=bundle['kind'],title=value[0].title,aliases=bundle['aliases'],
                                          fingerprint=bundle['fingerprint'],images=sum(1 for i,_ in value[1].values() if i.kind=='image'),
                                          messages=len(value[2]),result=result))
        report['result_counts']=dict(Counter(r['result'] for r in report['results']))
        report['cases_after']=len(workspace.repo.list('cases'))
        if apply:
            from screenshotlegal.application.services.auth import AuthService
            from screenshotlegal.domain.settings.auth import UserView
            auth=AuthService(workspace.repo,workspace.settings)
            # No session or password data is used for this ownership/visibility check.
            admin=UserView.model_validate({k:user[k] for k in UserView.model_fields if k in user})
            report['admin_visible_cases']=sum(bool(auth.case_role(admin,c)) for c in workspace.repo.list('cases'))
    except BaseException as exc:
        report['unresolved'].append(dict(error=str(exc)))
        raise
    finally:
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--owner',default='admin')
    parser.add_argument('--legacy-corpus',type=Path,help='Read-only legacy export within --repo-root; defaults to the 20261024 audited export if present')
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    settings=Settings(**({'data_dir':args.data_dir.resolve()} if args.data_dir else {}))
    workspace=Workspace(settings,Repository(settings.database_url))
    try:
        report=sync(args.repo_root.resolve(),workspace,args.owner,args.report.resolve(),args.apply,args.legacy_corpus)
        print(json.dumps({k:v for k,v in report.items() if k not in {'results'}},ensure_ascii=False,indent=2))
    finally: workspace.repo.engine.dispose()


if __name__=='__main__': main()
