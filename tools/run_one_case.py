from pathlib import Path
import argparse
import json
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub.casework import CaseWorkspace,now

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    work=CaseWorkspace()
    if not args.execute:
        print(json.dumps({'dry_run':True,'case_id':work.material['metadata']['case_id'],'images':len(work.material['images']),'messages':len(work.material['records'])}))
    else:
        run_id=uuid.uuid4().hex[:16];work.job={'id':run_id,'status':'running','stage':'准备整案理解','started_at':now()}
        result=work.run(run_id)
        print(json.dumps({'job':work.job,'request_proof':result.get('request_proof') if result else None},ensure_ascii=True))
        if result is None:sys.exit(1)
