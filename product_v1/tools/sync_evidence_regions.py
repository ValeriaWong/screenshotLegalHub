"""Recover geometric source regions from byte-matched repository manifests/LabelU.

No OCR/model calls, no synthetic transcription or claim changes. Default preflight;
--apply appends SourceRefs after a SQLite backup. Reference catalog is reviewer-only.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.application.services.workspace import Workspace
from screenshotlegal.domain.evidence.models import SourceRef, validate_bbox
from screenshotlegal.domain.common.models import digest, now


def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(data): return hashlib.sha256(data).hexdigest()
def safe(root,path):
    value=(root/path).resolve(strict=True)
    if not value.is_relative_to(root.resolve()): raise ValueError('Source escapes repository')
    return value


def collect(root, import_report, annotation_file):
    geometries=defaultdict(dict); invalid=[]; file_hashes={}
    def metadata(path):
        relative=path.relative_to(root).as_posix()
        if relative not in file_hashes: file_hashes[relative]=sha(path.read_bytes())
        return relative,file_hashes[relative]
    def add(content_hash,size,bbox,scope,category,origin,path,pointer):
        relative,source_hash=metadata(path)
        try: validate_bbox(bbox,size)
        except ValueError as exc:
            invalid.append(dict(path=relative,pointer=pointer,error=str(exc))); return
        key=digest([bbox,scope,category])
        item=geometries[content_hash].setdefault(key,dict(image_sha256=content_hash,image_size=size,bbox=list(bbox),
            bbox_format='xyxy_pixels',bbox_scope=scope,region_type=category,origin_type=origin,
            review_status='unreviewed',source_locators=[]))
        locator=dict(path=relative,sha256=source_hash,pointer=pointer)
        if locator not in item['source_locators']: item['source_locators'].append(locator)
    manifests=set()
    for row in load(import_report)['results']:
        for alias in row['aliases']:
            path=alias.split('#',1)[0]
            if not path.startswith('datasets/'): continue
            source=safe(root,path)
            if source.name in {'render.json','render_manifest.json'}: manifests.add(source)
            elif source.name in {'case.json','final.json'} and (source.parent/'render.json').is_file(): manifests.add(source.parent/'render.json')
    for manifest in sorted(manifests):
        value=load(manifest)
        if manifest.name=='render_manifest.json':
            collection=next(p for p in manifest.parents if (p/'source_refs.jsonl').is_file())
            refs_file=collection/'source_refs.jsonl'
            rows=[json.loads(s) for s in refs_file.read_text(encoding='utf-8').splitlines() if s.strip()]
            pages={p['image_id']:p for p in value['pages']}
            for i,ref in enumerate(rows):
                if ref['image_id'] not in pages: continue
                page=pages[ref['image_id']]; image=safe(root,manifest.parent.relative_to(root)/page['file'])
                actual=sha(image.read_bytes())
                if actual!=page['sha256'] or actual!=ref['image_sha256']: raise ValueError('V3 image hash differs')
                add(actual,[page['width'],page['height']],ref['bbox'],'message_row','message_row','render_geometry',refs_file,'/line/'+str(i+1))
        else:
            for i,page in enumerate(value.get('images',[])):
                image=safe(root,manifest.parent.relative_to(root)/(page.get('path') or page.get('file')))
                content=image.read_bytes(); actual=sha(content)
                if page.get('sha256') and actual!=page['sha256']: raise ValueError('Render image hash differs')
                from PIL import Image
                from io import BytesIO
                with Image.open(BytesIO(content)) as im: size=list(im.size)
                box_key='boxes' if 'boxes' in page else 'messages'
                for j,box in enumerate(page.get(box_key,[])):
                    bbox=box.get('bbox_pixels',box.get('bbox'))
                    if 'bbox_pixels' in box:
                        x,y,w,h=bbox; bbox=[x,y,x+w,y+h]
                    category='message_bubble' if box_key=='messages' else 'message_row'
                    scope='message_row_fragment' if page.get('scroll_fragment') or box.get('same_message_scroll_crop') else category
                    add(actual,size,bbox,scope,category,'render_geometry',manifest,'/images/'+str(i)+'/'+box_key+'/'+str(j))
    if annotation_file and annotation_file.is_file():
        for i,row in enumerate(load(annotation_file)):
            value=row['result']
            for _ in range(4):
                if not isinstance(value,str): break
                value=json.loads(value)
            if not isinstance(value,dict): raise ValueError('Invalid LabelU result')
            image=safe(root,Path('projects/quiz-collector/images')/Path(row['fileName'].replace('\\','/')).name)
            actual=sha(image.read_bytes()); size=[value['width'],value['height']]
            from PIL import Image
            with Image.open(image) as decoded:
                if list(decoded.size)!=size or value.get('rotate',0):
                    invalid.append(dict(path=annotation_file.relative_to(root).as_posix(),pointer='/'+str(i),error='Annotation canvas/rotation differs from original image'));continue
            for j,tool in enumerate(value.get('annotations',[])):
                if tool.get('toolName')!='rectTool': continue
                for k,box in enumerate(tool.get('result',[])):
                    x,y,w,h=box['x'],box['y'],box['width'],box['height']
                    add(actual,size,[x,y,x+w,y+h],'annotated_element',str(box.get('label','unknown')),
                        'historical_annotation',annotation_file,'/'+str(i)+'/result/annotations/'+str(j)+'/result/'+str(k))
    return geometries,invalid,file_hashes


def build_plan(workspace, geometries):
    evidence=workspace.repo.list('evidence_items')
    by_case=defaultdict(list)
    # source_ref bodies do not carry case_id; use evidence membership to resolve them.
    from sqlalchemy import select
    from screenshotlegal.infrastructure.db.models import MODELS
    with workspace.repo.session() as session:
        for row in session.scalars(select(MODELS['source_refs'])): by_case[row.case_id].append(row.body)
    catalog=[]; additions=[]; before=Counter(); after=Counter(); unlocated=[]
    for item in evidence:
        if item['kind']!='image': continue
        workspace.storage.verified_path(item)
        refs=sorted([r for r in by_case[item['case_id']] if r['evidence_id']==item['id'] and r.get('bbox') is not None],key=lambda r:r['id'])
        covered={tuple(r['bbox']):r for r in refs}
        before['images']+=1;before['with_any_bbox']+=bool(covered)
        for region in geometries.get(item['sha256'],{}).values():
            if region['image_size']!=[item['width'],item['height']]: raise ValueError('Geometry image size differs')
            key=tuple(region['bbox'])
            if key not in covered:
                ident='region.'+('render' if region['origin_type']=='render_geometry' else 'annotation')+'.'+region['region_type'].replace(' ','_')+'.'+digest([item['case_id'],item['id'],region['bbox']])[:24]
                ref=SourceRef(id=ident,evidence_id=item['id'],image_id=item['id'],message_id=None,evidence_page=None,
                    bbox=region['bbox'],raw_bbox=region['bbox'],raw_coordinate_space='pixels',quote='').model_dump()
                covered[key]=ref
                additions.append(('source_refs',item['case_id']+':'+ident,ref,item['case_id'],'',True))
            catalog.append(dict(region,case_id=item['case_id'],evidence_id=item['id'],source_ref_id=covered[key]['id']))
        after['images']+=1;after['with_any_bbox']+=bool(covered)
        if not covered: unlocated.append(dict(case_id=item['case_id'],evidence_id=item['id'],filename=item['filename'],sha256=item['sha256']))
    catalog.sort(key=lambda r:(r['case_id'],r['evidence_id'],r['bbox'],r['bbox_scope'],r['region_type']))
    return additions,catalog,dict(before),dict(after),unlocated


def run(root,workspace,import_report,annotation_file,output,apply=False):
    geometries,invalid,hashes=collect(root,import_report,annotation_file)
    additions,catalog,before,after,unlocated=build_plan(workspace,geometries)
    report=dict(schema='code.coordinate.sync.v1',created_at=now(),apply=apply,model_calls=0,before=before,after_planned=after,
        new_region_refs=len(additions),catalog_regions=len(catalog),geometric_scopes=dict(Counter(r['bbox_scope'] for r in catalog)),
        invalid_annotations=invalid,unlocated_images=unlocated,source_hashes=hashes,backup=None,
        limits=['Any-box coverage includes avatar/time/file rectangles, not complete message detection or OCR coverage.',
                'Historical labels remain unreviewed; geometric render references are not semantic/legal gold.',
                'No transcripts/events/claims/reviews/active perception/search index are replaced.'])
    for relative,expected in hashes.items():
        if sha(safe(root,relative).read_bytes())!=expected: raise ValueError('Source changed during preflight')
    if apply:
        backup=workspace.settings.data_dir/'backups'/('before-coordinate-sync-'+uuid4().hex+'.sqlite3')
        backup.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(workspace.settings.data_dir/'screenshotlegal.sqlite3') as src:
            with sqlite3.connect(backup) as dst: src.backup(dst)
        report['backup']=str(backup)
        workspace.repo.batch(additions)
    output.mkdir(parents=True,exist_ok=True)
    (output/'regions.reviewer_only.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in catalog),encoding='utf-8')
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--import-report',type=Path,default=Path('reports/admin_case_inventory_20261024/import-result.json'))
    parser.add_argument('--annotations',type=Path,default=Path('projects/ScreenshotLegalBench_v2/process_local_evaluator/screenshot_legal_annotations (1).json'))
    parser.add_argument('--output',type=Path,default=Path('reports/coordinate_audit_20261024'))
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    root=args.repo_root.resolve(); settings=Settings(**({'data_dir':args.data_dir.resolve()} if args.data_dir else {}))
    workspace=Workspace(settings,Repository(settings.database_url))
    try:
        result=run(root,workspace,safe(root,args.import_report),safe(root,args.annotations),root/args.output,args.apply)
        print(json.dumps({k:v for k,v in result.items() if k not in {'source_hashes','invalid_annotations','unlocated_images'}},ensure_ascii=False,indent=2))
        print('Invalid annotation rectangles:',len(result['invalid_annotations']))
    finally: workspace.repo.engine.dispose()


if __name__=='__main__': main()
