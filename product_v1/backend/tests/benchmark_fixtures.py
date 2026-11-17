import io,json
from PIL import Image
from screenshotlegal.research.benchmark_import import blob
from screenshotlegal.research.contracts import digest,now

def seed(store,owner='alice',dataset_id='benchmark.fixture'):
    out=io.BytesIO();Image.new('RGB',(200,160),'white').save(out,format='PNG');data=out.getvalue();sha=digest(data)
    from screenshotlegal.research.renderer import atomic_write
    atomic_write(store.root/('originals/'+sha+'.png'),data)
    asset=dict(id=sha,path='originals/'+sha+'.png',sha256=sha,width=200,height=160,mime_type='image/png',origin='source_image_present')
    tasks=[]
    for id,family,label,target,kind,bbox in [('vqa','vqa.categorical','evidence','is_evidence','categorical',[10,10,110,90]),('kie','kie.extract','',None,'kie',None),('open','vqa.open_text','legal_analysis','LEGACY_PRIVATE_ANSWER','open_text',[10,10,110,90])]:
        tasks.append(dict(task_id=id,dataset_id=dataset_id,migration_record_type='kie_candidate' if id=='kie' else 'vqa_candidate',image_name='fixture.png',task_family=family,source_label=label,question='Visible question '+label,answer_kind=kind,target=target,bbox_xyxy=bbox,region_id='region.fixture' if bbox else None,source_ref=dict(path='attrs.json',json_pointer='/0',sha256='sourcehash'),asset=asset,asset_status='source_image_present',reference_status='legacy_unverified',output_schema='kie-output.v1' if id=='kie' else 'vqa-answer.v1',legacy_raw=dict(answer=target)))
    bundle=blob(store,json.dumps(tasks).encode());replay=blob(store,json.dumps(dict(details=[dict(image='fixture.png',label='evidence',best_iou=0.,no_message=True,best_msg=None)],threshold=.6)).encode())
    d=dict(id=dataset_id,name='迁移测试数据',created_at=now(),status='needs_review',images={'fixture.png':asset},image_files={'fixture.png':bundle},tasks=bundle,replay=replay,counts=dict(images=1,candidate_images=0,kie=1,vqa=2,review_notes=0),formal_scoring_ready=False,split='unassigned',new_model_calls=0)
    with store.tx() as db:
        store.put('review.asset',asset,owner,db,immutable=True);store.put('benchmark.dataset',d,owner,db,immutable=True)
    return d,tasks
