"""Read-only adapters for existing V2 rounds and V3 calibration candidates."""
import io
import json
from pathlib import Path
from PIL import Image
from .contracts import *
from .renderer import atomic_write

REPOSITORY = Path(__file__).resolve().parents[5]

def load(path, fallback=None):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding='utf-8-sig'))

def lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()] if path.exists() else []

class Catalog:
    def __init__(self, store, review):
        self.store,self.review=store,review

    def candidates(self, directory):
        if directory.name=='round_001':
            return list(directory.glob('*/*/curated.json'))
        cases=list(directory.glob('*/*/case.json'))
        folders={file.parent for file in cases}
        return cases+[file for file in directory.glob('*/*/source.json') if file.parent not in folders]

    def groups(self):
        result=[]
        datasets=REPOSITORY/'datasets'
        for version in ['v2.0.0','v3.0.0']:
            parent=datasets/version
            if not parent.exists():
                continue
            for directory in sorted(parent.iterdir()):
                if directory.is_dir() and (directory.name.startswith('round_') or directory.name.startswith('calibration_')):
                    cases=self.candidates(directory) if version=='v2.0.0' else list(directory.glob('cases/*/*/messages.jsonl'))
                    result.append(dict(id=directory.relative_to(REPOSITORY).as_posix(),name=version+' / '+directory.name,
                                       format='v2' if version=='v2.0.0' else 'v3',count=len(cases)))
        return result

    def assets(self, owner, directory, files):
        assets=[]
        for item in files:
            relative=item.get('path') or item.get('file')
            if not relative:
                continue
            p=(directory/relative).resolve()
            if not p.is_relative_to(directory.resolve()) or not p.is_file():
                raise ValueError('历史图片缺失或路径越界')
            data=p.read_bytes()
            if len(data)>20*1024*1024:
                raise ValueError('历史图片超过单文件限制')
            sha=digest(data)
            expected=item.get('sha256')
            if expected and expected!=sha:
                raise ValueError('历史图片哈希不符')
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            with Image.open(io.BytesIO(data)) as im:
                width,height=im.size
                mime=Image.MIME.get(im.format,'image/png')
            filename='originals/'+sha+p.suffix.lower()
            atomic_write(self.store.root/filename,data)
            asset=dict(id=sha,path=filename,sha256=sha,width=width,height=height,mime_type=mime,
                       origin=p.relative_to(REPOSITORY).as_posix())
            with self.store.tx() as db:
                if not self.store.optional('review.asset',asset['id'],owner,db):
                    self.store.put('review.asset',asset,owner,db,immutable=True)
            assets.append(dict(id=sha,sha256=sha,mime_type=mime,origin=asset['origin']))
        return assets

    def layouts(self,owner,assets,images,messages,refs=None):
        ids={m['id'] for m in messages};pages=[]
        images=[i for i in images if i.get('path') or i.get('file')]
        for number,(asset,item) in enumerate(zip(assets,images),1):
            a=self.store.get('review.asset',asset['id'],owner);boxes=[]
            candidates=item.get('messages',[])+item.get('boxes',[])
            for r in refs or []:
                if r.get('image_sha256')==a['sha256']: candidates.append(r)
            for box in candidates:
                mid=box.get('message_id');bbox=box.get('bbox')
                if 'bbox_pixels' in box:
                    x,y,w,h=box['bbox_pixels'];bbox=[x,y,x+w,y+h]
                if mid in ids and bbox and not any(b['message_id']==mid and b['bbox']==bbox for b in boxes):
                    # Invalid legacy coordinates stay unannotated, never silently remapped.
                    try: PageLayout(page=number,width=a['width'],height=a['height'],boxes=[dict(message_id=mid,bbox=bbox)])
                    except ValueError: continue
                    boxes.append(dict(message_id=mid,bbox=bbox))
            pages.append(dict(page=number,width=a['width'],height=a['height'],boxes=boxes))
        return pages

    def restore_original(self,owner,id,expected_revision,key):
        sample=self.review.sample(owner,id)
        revision=self.review.revision(owner,id,expected_revision)
        content=revision['content'];provenance=content.get('metadata',{}).get('source_manifest','')
        file=(REPOSITORY/provenance).resolve()
        if not provenance or not file.is_relative_to(REPOSITORY) or not file.is_file(): raise ValueError('缺少可核验的历史来源清单')
        raw=content['metadata'].get('legacy_case',{}).get('messages') or content['metadata'].get('legacy_messages',[])
        legacy={str(m['id']):m.get('text') or '['+m.get('kind','attachment')+']' for m in raw}
        if any(legacy.get(m['id'])!=m['text'] for m in content['messages']): raise ValueError('消息已修改，不能把旧原图冒充当前文本；请保留派生视图')
        folder=file.parent
        render=folder/('render_manifest.json' if file.name=='messages.jsonl' else 'render.json')
        data=load(render,{})
        images=data.get('pages',data.get('images',[]))
        assets=content['original_assets']
        if not assets or len(assets)!=len(images): raise ValueError('原图清单数量不一致')
        for asset,image in zip(assets,images):
            a=self.store.get('review.asset',asset['id'],owner)
            if (REPOSITORY/a.get('origin','')).resolve()!=(folder/(image.get('path') or image.get('file') or '')).resolve(): raise ValueError('原图与历史清单来源不一致')
            if image.get('sha256') and a['sha256']!=image['sha256']: raise ValueError('历史图像哈希不一致')
        refs_path=folder.parents[2]/'source_refs.jsonl' if file.name=='messages.jsonl' else None
        refs=lines(refs_path) if refs_path else []
        layout=self.layouts(owner,assets,images,content['messages'],refs)
        geometry_hash=digest([data,refs])
        return self.review.use_original(owner,id,expected_revision,layout,geometry_hash,key)

    def import_group(self, owner, group_id):
        group=next((g for g in self.groups() if g['id']==group_id),None)
        if not group:
            raise KeyError('Unknown catalog group')
        directory=REPOSITORY/group_id
        items=self.candidates(directory) if group['format']=='v2' else list(directory.glob('cases/*/*/messages.jsonl'))
        result=dict(imported=0,upgraded=0,duplicates=0,failed=[],sample_ids=[])
        for file in sorted(items):
            try:
                provenance=file.relative_to(REPOSITORY).as_posix()
                key=digest(['original_geometry.v1',provenance,digest(file.read_bytes())])
                prior=self.store.optional('review.import',key,owner)
                if prior:
                    result['duplicates']+=1
                    result['sample_ids'].append(prior['sample_id'])
                    continue
                legacy_key=digest([provenance,digest(file.read_bytes())])
                legacy=self.store.optional('review.import',legacy_key,owner)
                if legacy:
                    sample=self.review.sample(owner,legacy['sample_id'])
                    self.restore_original(owner,sample['id'],sample['revision'],'upgrade:'+key)
                    with self.store.tx() as db: self.store.put('review.import',dict(id=key,sample_id=sample['id'],provenance=provenance,created_at=now(),upgraded_from=legacy_key),owner,db,immutable=True)
                    result['upgraded']+=1;result['sample_ids'].append(sample['id']);continue
                folder=file.parent
                if group['format']=='v2':
                    case=load(file) if file.name!='source.json' else {}
                    source=load(folder/'source.json',{})
                    messages=[dict(id=str(m['id']),speaker=m.get('sender_id',m.get('speaker_id',m.get('speaker','unknown'))),
                                   text=m.get('text') or '['+m.get('kind','attachment')+']',timestamp=m.get('timestamp'),
                                   source_refs=m.get('source_refs',[])) for m in case.get('messages',[])]
                    questions=[dict(id=str(q.get('id',i)),question=q.get('question','未命名题目'),
                                    answer=q.get('answer'),gold=False,task_type=q.get('type',q.get('task','qa')),
                                    message_ids=q.get('message_ids',q.get('minimal_message_ids',[]))) for i,q in enumerate(case.get('questions',[]))]
                    images=load(folder/'render.json',{}).get('images',[])
                    assets=self.assets(owner,folder,images)
                    content=Content(title=source.get('title') or case.get('id') or folder.name,
                                    category=case.get('cause') or source.get('cause') or 'uncategorized',language=case.get('language',source.get('language','zh')),
                                    platform=case.get('platform',source.get('platform','generic')),source_text=source.get('text',''),
                                    source_refs=[dict(file=provenance,url=source.get('url'),source_sha256=source.get('source_sha256'))],
                                    kind='original' if file.name=='source.json' else 'synthetic',
                                    messages=messages,questions=questions,original_assets=assets,visual_role='original' if assets else 'auto',original_layout=self.layouts(owner,assets,images,messages),tags=[directory.name,'source_only' if file.name=='source.json' else 'historical_candidate'],
                                    metadata=dict(legacy_case=case,source={k:v for k,v in source.items() if k!='text'},source_manifest=provenance,legacy_review={name:load(folder/(name+'.json')) for name in ['self_review','question_audit','curation','feedback.user','questions.review'] if (folder/(name+'.json')).exists()}))
                else:
                    ms=lines(file); scope=folder.parent.name
                    qs=[q for q in lines(directory/'questions.jsonl') if q.get('question_id','').startswith(scope+'.')]
                    images=load(folder/'render_manifest.json',{}).get('pages',[])
                    assets=self.assets(owner,folder,images)
                    content=Content(title=scope+' / '+folder.name,category=scope,
                                    messages=[dict(id=m['id'],speaker=m.get('sender_id','unknown'),text=m.get('text') or '[attachment]',timestamp=m.get('timestamp'),source_refs=m.get('source_refs',[])) for m in ms],
                                    questions=[dict(id=q['question_id'],question=q['question'],gold=False,task_type=q.get('answerability_type','qa')) for q in qs],
                                    source_refs=[dict(file=provenance)],original_assets=assets,visual_role='original' if assets else 'auto',original_layout=self.layouts(owner,assets,images,ms,lines(directory/'source_refs.jsonl')),tags=[directory.name,folder.name,'historical_candidate'],
                                    metadata=dict(legacy_messages=ms,legacy_questions=qs,source_manifest=provenance))
                saved=self.review.create(owner,SampleCreate(dataset=group_id,content=content,note='历史适配导入；保持候选状态，不认证金标',idempotency_key='import:'+key))
                with self.store.tx() as db:
                    self.store.put('review.import',dict(id=key,sample_id=saved['sample']['id'],provenance=provenance,created_at=now()),owner,db,immutable=True)
                result['imported']+=1
                result['sample_ids'].append(saved['sample']['id'])
            except (ValueError,KeyError,OSError,TypeError) as error:
                result['failed'].append(dict(file=file.relative_to(REPOSITORY).as_posix(),error=type(error).__name__))
        return result
