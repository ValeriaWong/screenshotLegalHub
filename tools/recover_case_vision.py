"""Recover complementary, unchanged-original extractions after an interrupted retry.
No model requests and no transcript text changes. Refuses an actively running job.
"""
import argparse
import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub import benchmark as b
from legalhub.case_registry import CaseRegistry,retain_successful_images
from legalhub.casework import DEFAULT_CASE,atomic_json,now

def main():
    parser=argparse.ArgumentParser();parser.add_argument('case_id');args=parser.parse_args()
    if args.case_id==DEFAULT_CASE:raise ValueError('Reviewed default case is preserved')
    registry=CaseRegistry();folder=registry.folder(args.case_id)
    job=folder/'generation-job.json'
    if job.exists() and b.read(job)['status']=='running':raise ValueError('Stop the generation before recovery')
    paths=sorted((folder/'vision-runs').glob('*/corpus.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if (folder/'vision/corpus.json').exists():paths.append(folder/'vision/corpus.json')
    if not paths:raise ValueError('No recorded extraction')
    priors=[({'file':p.relative_to(b.ROOT).as_posix(),'sha256':b.sha(p)},b.read(p)) for p in paths]
    fresh=b.read(paths[0]);combined=retain_successful_images(fresh,priors[1:])
    combined['metadata'].update(recovery_time=now(),base_corpus=priors[0][0],model_requests=0)
    out=folder/'vision-recoveries'/uuid.uuid4().hex[:16]/'corpus.json'
    b.write(out,combined);atomic_json(folder/'vision-active.json',{'corpus':out.relative_to(b.ROOT).as_posix(),'created_at':now()})
    print(json.dumps({'case_id':args.case_id,'images_total':len(combined['images']),'images_ok':combined['metadata']['ok_images'],'messages':sum(r['kind']=='message' for r in combined['records']),'model_requests':0,'corpus':out.relative_to(b.ROOT).as_posix()}))
if __name__=='__main__':main()
