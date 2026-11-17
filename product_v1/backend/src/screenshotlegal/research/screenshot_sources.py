"""Repository adapters with explicit provenance inventory and non-silent exclusions."""
import copy
import io
import json
import random
from pathlib import Path
from PIL import Image
from .catalog import REPOSITORY, load, Catalog
from .contracts import digest
from .renderer import atomic_write, verified
from .screenshot_review import project

A_FILE = 'projects/ScreenshotLegalBench_v2/process_local_evaluator/image_structured_info.json'

class ScreenshotSources:
    def __init__(self, store, review, repository=REPOSITORY):
        self.store, self.review, self.root = store, review, Path(repository)

    def inventory(self, owner):
        entries = []
        file = self.root/A_FILE
        if file.exists():
            entries.append(dict(id='legacy-kie',dataset='A',title='历史 KIE 对话 JSON · 标注等级待核实',path=A_FILE,
                                annotation_level='unverified',eligible=True,
                                reason='文件未提供逐条人工核对证明，不能等同于论文 143 图评估集；仅作为旧标注待审核。'))
        automatic=self.root/'projects/ScreenshotLegalBench_v2/process_local_evaluator/Qwen2.5-VL-32B-Instruct_evidence_outputs.json'
        if automatic.exists():
            entries.append(dict(id='model-output',dataset='A',title='历史模型预测输出',path=automatic.relative_to(self.root).as_posix(),
                                annotation_level='automatic_prediction',eligible=False,reason='自动模型预测，不是人工精标，保留在历史评测结果中，不直接充当审核金标。'))
        label = self.root/'projects/ScreenshotLegalBench_v2/screenshot_legal_annotations.json'
        if label.exists():
            entries.append(dict(id='labelu',dataset='A',title='LabelU 人工标注工具导出 · VQA/区域标注',path=str(label.relative_to(self.root)),
                                annotation_level='human_tool_export_unverified',eligible=False,
                                reason='人工工具导出不等于完整 KIE 精标，需在原有 KIE/VQA 工作区按任务审核。'))
        for split in ['train','val','test']:
            file=self.root/f'projects/wechat_screen_vqa_dataset/{split}.json'
            if file.exists():
                raw=load(file,{})
                entries.append(dict(id='coco-'+split,dataset='A',title=split+' · 检测区域格式',path=str(file.relative_to(self.root)),
                                    annotation_level='annotation_export_unverified',eligible=False,
                                    images=len(raw.get('images',[])),annotations=len(raw.get('annotations',[])),
                                    reason='COCO 区域标注，不是 KIE 对话 JSON，不能按 split 名称推断人工精标。'))
        entries.append(dict(id='thesis-training',dataset='A',title='论文 KIE 自动粗标训练集',annotation_level='automatic_preannotation',eligible=False,
                            reason='论文记载 39,477 条训练消息；本次未找到可对应且带完整来源证明的训练 JSON，不并入当前审核清单。'))
        for directory in sorted((self.root/'datasets/v2.0.0').glob('round_*')):
            if directory.is_dir():
                relative=directory.relative_to(self.root).as_posix()
                entries.append(dict(id='repo:'+relative,dataset='B',title='v2.0.0 / '+directory.name+' · 合成截图',
                                    annotation_level='synthetic',eligible=True,path=relative,reason='按截图逐页映射，原始 case/source/render JSON 全字段保留。'))
        samples=self.review.list_samples(owner)
        count=sum(1 for s in samples if s.get('published_manifest'))
        if count:
            entries.append(dict(id='studio',dataset='B',title='研究库已有合成样本',annotation_level='synthetic',eligible=True,
                                reason='只纳入已有截图、明确 synthetic 的样本；原文和模拟分别标记。'))
        return entries

    def asset(self, path, expected=None):
        path=Path(path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError('图片路径超出仓库')
        data=path.read_bytes()
        if len(data)>20*1024*1024:
            raise ValueError('图片超过 20 MiB')
        sha=digest(data)
        if expected and sha!=expected:
            raise ValueError('图片哈希与清单不一致')
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width,height=image.size
            suffix={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}.get(image.format)
            if not suffix:
                raise ValueError('不支持的图片格式')
            return dict(path='originals/'+sha+suffix,sha256=sha,width=width,height=height,mime_type=Image.MIME[image.format],source_path=str(path))

    def make_item(self, dataset, raw, keys, asset, ref, level, excerpt='', indices=None):
        json.dumps(raw,allow_nan=False)
        messages=project(raw,keys,indices)
        return dict(dataset=dataset,original_json=copy.deepcopy(raw),message_path=keys,messages=messages,
                    speakers=list(dict.fromkeys(m['speaker'] for m in messages)),asset=asset,source_ref=ref,
                    source_sha256=digest(raw),annotation_level=level,judgment_excerpt=excerpt,synthetic=dataset=='B',
                    judgment_ref=(raw.get('source') or {}).get('case_no',''),source_url=(raw.get('source') or {}).get('url',''))

    def prepare(self,owner,source_id):
        entry=next((e for e in self.inventory(owner) if e['id']==source_id and e['eligible']),None)
        if not entry:
            raise ValueError('该来源不支持聊天消息审核')
        items=[];errors=[];source_records=0
        def collect(ref, fn):
            try: items.extend(fn())
            except (ValueError,KeyError,TypeError,OSError,IndexError) as error:
                errors.append(dict(source=ref,reason=str(error)))
        if source_id=='legacy-kie':
            assets={r['name']:r for r in load(self.root/'reports/restart/images_manifest.json',[])}
            raw=load(self.root/A_FILE,[])
            source_records=len(raw)
            for index,row in enumerate(raw):
                ref=A_FILE+'#/'+str(index)
                def convert(row=row,ref=ref):
                    name=Path(row.get('image_url','').replace('\\','/')).name
                    if name not in assets:
                        raise ValueError('未找到对应图片，不能猜配')
                    image=assets[name]
                    return [self.make_item('A',row,['structured_info','conversation'],self.asset(self.root/image['path'],image['sha256']),ref,'unverified')]
                collect(ref,convert)
        elif source_id.startswith('repo:'):
            directory=self.root/entry['path']
            candidates=sorted(Catalog(self.store,self.review).candidates(directory))
            source_records=len(candidates)
            for file in candidates:
                ref=file.relative_to(self.root).as_posix()
                def convert(file=file,ref=ref):
                    case=load(file,{})
                    source=load(file.parent/'source.json',{})
                    render=load(file.parent/'render.json',{})
                    raw=dict(case=case,source=source,render=render)
                    if not case.get('messages'):
                        raise ValueError('无生成对话')
                    pages=render.get('images',[])
                    if not pages:
                        raise ValueError('缺少截图清单')
                    result=[]
                    for page in pages:
                        boxes=page.get('messages',[])+page.get('boxes',[])
                        ids=page.get('message_ids') or [b['message_id'] for b in boxes]
                        ids=list(dict.fromkeys(ids))
                        if not ids:
                            raise ValueError('缺少截图与消息映射')
                        indices=[i for i,m in enumerate(case['messages']) if m['id'] in ids]
                        if set(ids)-{case['messages'][i]['id'] for i in indices}:
                            raise ValueError('截图引用了不存在的消息')
                        quotes=[]
                        source_text=source.get('text','')
                        for i in indices:
                            for r in case['messages'][i].get('source_refs',[]):
                                quote=r.get('quote','')
                                if quote and quote in source_text and quote not in quotes:
                                    quotes.append(quote)
                        excerpt='\n'.join(quotes)[:500] or source_text[:500]
                        image_path=page.get('path') or page.get('file')
                        if not image_path:
                            raise ValueError('缺少截图文件路径')
                        item=self.make_item('B',raw,['case','messages'],self.asset(file.parent/image_path,page.get('sha256')),
                                            ref+'#page='+str(page.get('page',page.get('evidence_page',len(result)+1))),'synthetic',excerpt,indices)
                        # Render boxes describe the original screenshot; use them only for display side.
                        for message in item['messages']:
                            box=next((b.get('bbox') for b in boxes if b.get('message_id')==message['id'] and b.get('bbox')),None)
                            if message['side_inferred'] and isinstance(box,list) and len(box)==4 and all(isinstance(v,(int,float)) for v in box):
                                message['side']='right' if (box[0]+box[2])/2 > item['asset']['width']/2 else 'left'
                        result.append(item)
                    return result
                collect(ref,convert)
        else:
            for sample in self.review.list_samples(owner):
                if not sample.get('published_manifest'):
                    continue
                revision=self.review.revision(owner,sample['id'],sample['revision'])
                content=revision['content']
                if content['kind']!='synthetic':
                    continue
                source_records+=1
                ref=sample['id']+':'+str(sample['revision'])
                def convert(sample=sample,revision=revision,content=content,ref=ref):
                    manifest=self.store.get('review.manifest',sample['published_manifest'],owner)
                    result=[]
                    for page in manifest['pages']:
                        file=verified(self.store.root,page)
                        ids={b['message_id'] for b in page['boxes']}
                        indices=[i for i,m in enumerate(content['messages']) if m['id'] in ids]
                        if not indices:
                            raise ValueError('缺少逐页消息映射')
                        asset={k:page[k] for k in ['path','sha256','width','height','mime_type']}
                        asset['source_path']=str(file)
                        result.append(self.make_item('B',revision,['content','messages'],asset,ref+':'+str(page['page']),
                                                     'synthetic',content['source_text'][:500],indices))
                    return result
                collect(ref,convert)
        random.Random(20261106).shuffle(items)
        for index,item in enumerate(items,1):
            item['id']=entry['dataset'].lower()+str(index).zfill(3)
        scope=dict(source_id=source_id,source_title=entry['title'],dataset=entry['dataset'],annotation_level=entry['annotation_level'],
                   source_records=source_records,items=len(items),messages=sum(len(i['messages']) for i in items),excluded=errors,
                   reason=entry['reason'],shuffle_seed=20261106)
        if entry['dataset']=='B':
            versions={}
            for item in items:
                raw=item['original_json']
                text=(raw.get('source') or {}).get('text') if source_id.startswith('repo:') else (raw.get('content') or {}).get('source_text')
                version=item['source_ref'].split('#page=')[0] if source_id.startswith('repo:') else item['source_ref'].rsplit(':',1)[0]
                versions[version]=digest(text) if isinstance(text,str) and text else None
            scope.update(generated_versions=len(versions),judgment_texts=len({v for v in versions.values() if v}),
                         versions_without_source_text=sum(v is None for v in versions.values()),
                         count_basis='仅当前来源批次；判决原文按完整文本 SHA256 去重，生成版本按来源记录区分，截图按渲染页逐张计数。')
        fingerprint=digest([scope,items])
        return items,dict(**scope,fingerprint=fingerprint)

    def initialize(self,owner,panel,source_id,fingerprint,version,acknowledge_exclusions):
        items,scope=self.prepare(owner,source_id)
        if fingerprint!=scope['fingerprint']:
            raise ValueError('来源已变化，请重新核对清单')
        if scope['excluded'] and not acknowledge_exclusions:
            raise ValueError('请先核对异常清单，明确只纳入可用截图')
        for item in items:
            asset=item['asset'];file=Path(asset.pop('source_path'))
            data=file.read_bytes()
            if digest(data)!=asset['sha256']:
                raise ValueError('图片在预检后发生变化')
            atomic_write(self.store.root/asset['path'],data)
        return panel.initialize(owner,scope['dataset'],items,scope,version)
