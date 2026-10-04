"""Multi-case registry. Original sources and model runs remain independently preserved."""
import base64
import collections
import copy
import hashlib
import io
import json
import re
import threading
import uuid
from pathlib import Path
from legalhub import benchmark as b
from legalhub.casework import CaseWorkspace, DEFAULT_CASE, HOME, atomic_json, digest, now
from legalhub.retrieval import Retriever, validate_corpus

CASES_HOME=b.ROOT/'blocks/evidence/artifacts/cases'

def source_order(image):
    match=re.search(r'_image_(\d+)',image['image_id'])
    return (int(match[1]) if match else image.get('evidence_page') or 99999,image['image_id'])

def select_transcripts(rows):
    """Select a recorded version per image; do not splice conflicting versions."""
    groups=collections.defaultdict(lambda:collections.defaultdict(list))
    for row in rows:
        version=(row.get('extraction_origin',{}).get('run_id') or
                 str(row.get('source_artifact',''))+':'+str(row.get('source_index','')))
        groups[row['image_id']][version].append(row)
    selected=[];alternatives=0;corrupted=0
    for versions in groups.values():
        def quality(rs):
            readable=sum(len(r['text']) for r in rs if '\ufffd' not in r['text'])
            return (any(r.get('origin_type')=='fresh_model_extraction' for r in rs),readable,len(rs))
        chosen=max(versions.values(),key=quality);alternatives+=len(versions)-1
        for row in sorted(chosen,key=lambda r:r.get('order',0)):
            if '\ufffd' in row['text']:corrupted+=1;continue
            selected.append(copy.deepcopy(row))
    return selected,{'alternative_versions_preserved':alternatives,'corrupted_messages_excluded':corrupted}

def retain_successful_images(fresh, priors):
    """Keep one extraction version per unchanged original, preferring the latest attempt."""
    combined=copy.deepcopy(fresh)
    expected={x['image_id']:x['sha256'] for x in fresh['images']}
    covered={r['image_id'] for r in fresh['records'] if r['kind']=='message'}
    retained=[]
    for provenance,prior in priors:
        if {x['image_id']:x['sha256'] for x in prior['images']}!=expected:
            raise ValueError('Prior vision originals changed')
        old_ids={r['image_id'] for r in prior['records'] if r['kind']=='message'}-covered
        if not old_ids:continue
        combined['records'].extend(copy.deepcopy(r) for r in prior['records'] if r.get('image_id') in old_ids or any(ref.get('image_id') in old_ids for ref in r.get('source_refs',[])))
        covered.update(old_ids);retained.append({'corpus':provenance,'images':sorted(old_ids)})
    combined['metadata'].update(latest_attempt_ok_images=fresh['metadata'].get('ok_images',0),ok_images=len(covered),retained_prior_sources=retained)
    validate_corpus(combined)
    return combined

class CaseRegistry:
    def __init__(self, retriever=None, home=CASES_HOME):
        self.retriever=retriever or Retriever();self.home=Path(home);self.home.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.workspaces={};self.jobs={}
        self.refresh()
    def refresh(self):
        with self.retriever.connect() as c:
            images=[json.loads(x[0]) for x in c.execute('SELECT body FROM images')]
            messages=[json.loads(x[0]) for x in c.execute("SELECT body FROM records WHERE kind='message'")]
        self.images=collections.defaultdict(list);self.rows=collections.defaultdict(list);self.metadata={}
        for image in images:self.images[image['case_id']].append(image)
        for row in messages:self.rows[row['case_id']].append(row)
        for folder in self.home.iterdir():
            path=folder/'case.json'
            if path.exists():
                meta=b.read(path);id=meta['case_id'];self.metadata[id]=meta
                if (folder/'upload-manifest.json').exists():self.images[id]=b.read(folder/'upload-manifest.json')['images']
        for id in self.images:
            path=self.folder(id)/'generation-job.json'
            if path.exists():
                job=b.read(path)
                if job['status']=='running':job.update(status='error',stage='上次生成已中断，可重新生成',error='服务重启后任务未继续')
                self.jobs[id]=job
        self.selected={id:select_transcripts(self.rows[id]) for id in self.images}
    def folder(self,id):
        if id not in self.images:raise KeyError('Unknown case')
        return self.home/hashlib.sha256(id.encode()).hexdigest()[:24]
    def material(self,id):
        folder=self.folder(id);meta=self.metadata.get(id,{})
        corpus_path=self.vision_corpus(id)
        if corpus_path:
            corpus=b.read(corpus_path);images=copy.deepcopy(corpus['images'])
            records=[copy.deepcopy(r) for r in corpus['records'] if r['kind']=='message']
            corpus_sha=b.sha(corpus_path);quality={'fresh_extraction':all(r.get('origin_type')=='fresh_model_extraction' for r in records),'rejected_messages':len(corpus['metadata'].get('rejected_messages',[])),'images_ok':corpus['metadata'].get('ok_images',0),'images_total':len(images)}
        else:
            images=copy.deepcopy(self.images[id]);records,quality=self.selected[id];records=copy.deepcopy(records)
            corpus_sha=digest({'images':images,'records':records})
        images.sort(key=source_order)
        rank={}
        for page,image in enumerate(images,1):
            image['display_page']=page;rank[image['image_id']]=page
            # Visible header is a provisional display group, never an authenticated identity.
            titles={r.get('title','') for r in records if r['image_id']==image['image_id'] and r.get('origin_type')=='fresh_model_extraction'}
            titles={x for x in titles if x and x!='unknown' and not re.search(r'\d+[:：]\d+',x)}
            if len(titles)==1:
                title=next(iter(titles));image['conversation_name']=title
                image['conversation_id']='display-header:'+digest({'case':id,'title':title})[:16]
                image['conversation_group_basis']='vision_visible_header_unreviewed'
        records.sort(key=lambda r:(rank[r['image_id']],r.get('order',0)))
        for row in records:
            if row.get('speaker_local_id') not in ('left','right','system','unknown'):
                box=row['source_refs'][0].get('bbox');width=next(i['size'][0] for i in images if i['image_id']==row['image_id'])
                row['speaker_local_id']='right' if box and (box[0]+box[2])/2>width/2 else 'left' if box else 'unknown'
                row['speaker_side_basis']='bbox_horizontal_location_not_identity'
        return {'images':images,'records':records,'metadata':{'case_id':id,'case_name':meta.get('name') or '案件 '+id[:12],
            'source_corpus_sha256':corpus_sha,'source_order':'文件顺序仅作阅读顺序；未核实日期，不补造缺失材料',
            'user_context':meta.get('context',''),'transcription_status':'现有转录；原图仍需核对','quality':quality}}
    def get(self,id=DEFAULT_CASE):
        with self.lock:
            if id not in self.workspaces:
                self.workspaces[id]=CaseWorkspace() if id==DEFAULT_CASE else CaseWorkspace(home=self.folder(id),material=self.material(id))
            return self.workspaces[id]
    def list(self,case_id=None,analyzed_only=False):
        result=[]
        for id,images in self.images.items():
            if case_id is not None and id!=case_id:continue
            folder=self.folder(id);active=HOME/'active.json' if id==DEFAULT_CASE else folder/'active.json'
            has_analysis=active.exists();job=self.jobs.get(id)
            if analyzed_only and (not has_analysis or (job and job['status'] in ('running','error'))):continue
            vision=self.vision_corpus(id);count=len(self.selected[id][0]);quality=self.selected[id][1]
            if vision:count=sum(r['kind']=='message' for r in b.read(vision)['records'])
            status='analyzed' if has_analysis else 'transcribed' if count else 'originals'
            if job and job['status']=='running':status='processing'
            elif job and job['status']=='error':status='error'
            meta=self.metadata.get(id,{})
            result.append({'case_id':id,'name':'服装选购与转款沟通' if id==DEFAULT_CASE else meta.get('name') or '案件 '+id[:12],
                'images':len(images),'messages':count,'status':status,'quality':quality,'thumbnail':images[0]['image_id'],
                'context':meta.get('context',''),'created_at':meta.get('created_at'),'uploaded':id in self.metadata,'job':job})
        return sorted(result,key=lambda x:(x['case_id']!=DEFAULT_CASE,not x['uploaded'],x['case_id']))
    def review_cases(self,case_id=None):
        """Skip unrelated vision artifacts during source-bound human review."""
        return self.list(case_id=case_id,analyzed_only=case_id is None)
    def vision_corpus(self,id):
        from legalhub.retrieval import workspace_file
        folder=self.folder(id);pointer=folder/'vision-active.json'
        if pointer.exists():
            path=workspace_file(b.read(pointer)['corpus'])
            if not path.is_relative_to(folder.resolve()):raise ValueError('Vision artifact outside case')
            return path if path.exists() else None
        path=folder/'vision/corpus.json'
        return path if path.exists() else None
    def state(self,id):
        value=self.get(id).state();value['job']=self.jobs.get(id) or value['job']
        value['user_context']=self.metadata.get(id,{}).get('context','')
        value['quality']=dict(self.get(id).material['metadata'].get('quality',{}),origin_counts=dict(collections.Counter(r.get('origin_type','unknown') for r in self.get(id).material['records'])))
        return value
    def create(self,files,name='',context=''):
        if not isinstance(files,list) or not 1<=len(files)<=30:raise ValueError('请选择1至30张图片')
        if not isinstance(name,str) or not isinstance(context,str) or len(name)>120 or len(context)>12000:raise ValueError('案情或名称超过限制')
        from PIL import Image
        validated=[];seen=set()
        for item in files:
            blob=base64.b64decode(item['base64'],validate=True)
            if len(blob)>15*1024*1024:raise ValueError('单张图片超过15MB')
            with Image.open(io.BytesIO(blob)) as im:
                size=list(im.size);format=im.format
                if format not in ('JPEG','PNG','WEBP') or size[0]*size[1]>40_000_000:raise ValueError('图片格式或尺寸不支持')
                im.verify()
            sha=hashlib.sha256(blob).hexdigest()
            if sha in seen:continue
            seen.add(sha);validated.append((item,blob,sha,size,format))
        id='case-'+uuid.uuid4().hex[:16];folder=self.home/hashlib.sha256(id.encode()).hexdigest()[:24]
        dest=folder/'originals';dest.mkdir(parents=True)
        images=[]
        for page,(item,blob,sha,size,format) in enumerate(validated,1):
            path=dest/(str(page)+{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[format]);path.write_bytes(blob)
            image_id=id+'_image_'+str(page-1)+path.suffix
            images.append({'image_id':image_id,'case_id':id,'file':path.relative_to(b.ROOT).as_posix(),'sha256':sha,'size':size,
                'evidence_page':page,'conversation_id':'unconfirmed:'+image_id,'original_filename':str(item.get('name',''))[:200],
                'page_basis':'user_selected_upload_order','submitted_by':'user'})
        meta={'case_id':id,'name':name.strip() or '新案件 '+id[-6:],'context':context.strip(),'created_at':now()}
        atomic_json(folder/'case.json',meta);b.write(folder/'upload-manifest.json',{'images':images})
        with self.lock:
            self.images[id]=images;self.rows[id]=[];self.selected[id]=([],{});self.metadata[id]=meta
        self.start(id,force_vision=True)
        return {'case_id':id,'images':len(images),'duplicates_removed':len(files)-len(images),'job':self.jobs[id]}
    def start(self,id,force_vision=False):
        self.folder(id)
        with self.lock:
            if self.jobs.get(id,{}).get('status')=='running':return self.jobs[id]
            if sum(j['status']=='running' for j in self.jobs.values())>=2:raise ValueError('已有两个生成任务运行，请稍后重试')
            job={'id':uuid.uuid4().hex[:16],'case_id':id,'status':'running','stage':'准备案件材料','started_at':now(),'completed_images':0,'planned_images':len(self.images[id])}
            self.jobs[id]=job
            atomic_json(self.folder(id)/'generation-job.json',job)
        threading.Thread(target=self.process,args=(id,force_vision),daemon=True).start()
        return job
    def process(self,id,force_vision=False):
        folder=self.folder(id)
        try:
            material=self.get(id).material
            covered={m['image_id'] for m in material['records']}
            if force_vision or len(covered)<len(material['images']):
                from legalhub.evidence import extract
                job=self.jobs[id];job['stage']='视觉模型读取原图'
                prior_path=self.vision_corpus(id)
                history=[prior_path] if prior_path else []
                history.extend(sorted((folder/'vision-runs').glob('*/corpus.json'),key=lambda p:p.stat().st_mtime,reverse=True))
                if (folder/'vision/corpus.json').exists():history.append(folder/'vision/corpus.json')
                history=list(dict.fromkeys(history))
                priors=[({'file':p.relative_to(b.ROOT).as_posix(),'sha256':b.sha(p)},b.read(p)) for p in history]
                if material['records']:
                    priors.append(({'source_corpus_sha256':material['metadata']['source_corpus_sha256'],'basis':'previously_selected_recorded_transcripts'},
                                   {'images':material['images'],'records':material['records'],'metadata':material['metadata']}))
                manifest=folder/'generation-manifest.json';b.write(manifest,{'images':material['images']})
                def progress(row):
                    with self.lock:job.update(completed_images=row['completed'],planned_images=row['planned'],stage='正在识别截图 '+str(row['completed'])+'/'+str(row['planned']))
                out=folder/'vision-runs'/job['id']
                result=extract(manifest,'sf_qwen3vl_instruct',out,True,progress,coordinate_space='normalized_1000',transport_png=True)
                fresh=b.read(out/'corpus.json');combined=retain_successful_images(fresh,priors)
                if combined['metadata']['retained_prior_sources']:
                    b.write(out/'attempt-corpus.json',fresh);b.write(out/'corpus.json',combined)
                result['ok_images']=combined['metadata']['ok_images']
                if not result['ok_images']:raise RuntimeError('图片识别未成功，请检查模型额度或运行记录')
                atomic_json(folder/'vision-active.json',{'corpus':(out/'corpus.json').relative_to(b.ROOT).as_posix(),'created_at':now()})
                with self.lock:self.workspaces.pop(id,None)
                if id==DEFAULT_CASE:raise ValueError('示例案件原始转录保持独立，不覆盖')
                work=self.get(id)
                self.jobs[id].update(vision_complete=result['ok_images']==result['planned_images'],rejected_messages=len(result['rejected_messages']))
            else:
                work=self.get(id)
                self.jobs[id].update(completed_images=len(material['images']),vision_complete=True)
            with work.lock:work.job=self.jobs[id]
            work.run(self.jobs[id]['id'])
            if work.current and self.jobs[id]['status']=='completed':
                # Partial extraction is explicit and cannot be presented as complete evidence coverage.
                if self.jobs[id].get('vision_complete') is False:self.jobs[id].update(status='needs_review',stage='已生成，部分截图未成功识别，请核对')
                atomic_json(folder/'generation-job.json',self.jobs[id])
            atomic_json(folder/'generation-job.json',self.jobs[id])
        except Exception as error:
            message=str(error) if isinstance(error,(ValueError,RuntimeError)) else type(error).__name__
            self.jobs[id].update(status='error',stage='生成未完成；原图与已有结果保留',error=message,completed_at=now())
            atomic_json(folder/'generation-job.json',self.jobs[id])
