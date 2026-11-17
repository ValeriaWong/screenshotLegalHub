"""Sync a recorded local trial into the operation console; never calls a model."""
import argparse,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from screenshotlegal.settings import Settings
from screenshotlegal.research.store import Store
from screenshotlegal.research.operations import Operations
from screenshotlegal.research import audit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--owner',default='admin');parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args();s=Settings()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=s.data_dir/'backups'/('operations-'+stamp);backup.mkdir(parents=True)
    for name,source in [('cases',s.data_dir/'screenshotlegal.sqlite3'),('research',s.data_dir/'research/research.sqlite3')]:
        if source.exists():
            a=sqlite3.connect(source);b=sqlite3.connect(backup/(name+'.sqlite3'));a.backup(b);a.close();b.close()
    token=audit.context.set(dict(actor_id='codex',actor_type='agent',product='evaluation',correlation_id='deepseek-initial-20261024',request_id='historical-flow-sync:'+stamp))
    try:
        row=Operations(Store(s.data_dir)).import_trial(args.owner,args.directory)
        print(json.dumps(dict(id=row['id'],historical_sync=True,artifacts=len(row['artifacts']),backup=str(backup),external_calls=0),ensure_ascii=False))
    finally:audit.context.reset(token)
if __name__=='__main__':main()
