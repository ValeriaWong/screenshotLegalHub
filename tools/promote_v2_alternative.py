"""Create a separate candidate folder after full reading finds a useful alternative."""
import sys,argparse,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save,status

def promote(parent,index,author):
    manifest=read(OUT/'manifest.json');primary=next(i for i in manifest['representatives'] if i['id']==parent)
    assert index in primary['alternatives'] and index!=primary['source_index']
    primary_dir=OUT/'zh'/parent;assert read(primary_dir/'status.json')['phase']=='deferred'
    reviewed=[]
    for name in ['alternatives.review.json','root.alternatives.review.json']:
        if (primary_dir/name).exists():
            document=read(primary_dir/name);assert document.get('full_judgment_read')
            reviewed.extend(document.get('alternatives',[]))
    assert any(r['source_index']==index and r['decision'] in ['usable','candidate'] for r in reviewed),'Alternative must have a usable full-reading record before promotion'
    original=OUT/'zh'/parent/'alternatives'/f'{index:04d}'
    source=read(original/'source.json');ident=f'zh_alt_{index:04d}';d=OUT/'zh'/ident
    source=copy.deepcopy(source);source.update(id=ident,status='synthetic_candidate_requires_review',
        cause_label_status='historical_source_label_not_current_national_catalog',
        alternative_archive=f'zh/{parent}/alternatives/{index:04d}/source.json')
    if (d/'source.json').exists():assert read(d/'source.json')==source
    else:
        from tools.build_v2_judgment_review import verify_archive
        save(d/'source.json',source);save(d/'source.verification.json',verify_archive(source))
        (d/'judgment.txt').write_bytes(source['text'].encode('utf-8'));status(d,'source_prepared',author=author,parent_case_id=parent)
    item={'id':ident,'parent_case_id':parent,'source_index':index,'cause':source['cause'],
        'atomic_causes':primary['atomic_causes'],'case_no':source['case_no'],'alternatives':[],
        'judgment_text_sha256':source['judgment_text_sha256'],'selection_method':'full alternative judgment read after primary deferral'}
    entries=manifest.setdefault('supplemental_representatives',[])
    if not any(i['id']==ident for i in entries):entries.append(item);save(OUT/'manifest.json',manifest)
    print(ident)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parent');p.add_argument('index',type=int);p.add_argument('--author',required=True);a=p.parse_args();promote(a.parent,a.index,a.author)
