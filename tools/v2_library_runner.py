"""Persistent, bounded-concurrency coordinator for the local judgment campaign.

Run ``start`` to detach, ``status`` to inspect, or create the campaign STOP file
to drain existing jobs without starting another. No external API keys are used.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import v2_library_authoring as author
from tools.v2_worker_retry import recover_dead_authors
from tools.v2_library_expansion import OUT, read, save, sha, rel, quota_target, review_enabled

STATE=OUT/'runner.status.json'
EVENTS=OUT/'runner.events.jsonl'
CODE=['tools/v2_library_runner.py','tools/v2_library_authoring.py','tools/v2_library_expansion.py',
      'tools/v2_claim_support.py','tools/v2_peer_round.py','tools/v2_full_queue.py','tools/v2_cause_batch.py','tools/render_v2_round2.py','legalhub/synthesis.py','legalhub/providers.py','tools/v2_fact_constrained.py','tools/v2_worker_retry.py']


def now():return datetime.now(timezone.utc).isoformat()


def emit(phase,**extra):
    value={'time_utc':now(),'pid':os.getpid(),'phase':phase,'overall_goal_complete':False,'minimum_distinct_judgments_per_cause':quota_target(),'concurrency_limit':author.worker_limit(),**extra}
    save(STATE,value)
    with EVENTS.open('a',encoding='utf-8') as out:out.write(json.dumps(value,ensure_ascii=False)+'\n')
    return value


def jobs(include_reviews=True):
    return sorted([*(OUT/'jobs').glob('*/assignment.json'),*((OUT/'peer_jobs').glob('*/assignment.json') if include_reviews else [])])


def unassigned():
    used={r['document_id'] for p in (OUT/'jobs').glob('*/assignment.json') for r in read(p)['records']}
    q=read(OUT/'queue.json')
    return sum(r['document_id'] not in used for key in ['chinese','english'] for r in q[key])


def check_dead_jobs(active,include_reviews=True):
    for p in jobs(include_reviews):
        d=p.parent
        if (d/'runtime.json').exists() and not author.job_finished(d) and d not in active:
            raise RuntimeError(f'Worker exited without completion marker: {rel(d)}. Inspect logs; never relaunch blindly.')

def coordinate_generation(size,fact_pending):
    """Generate new source candidates without waiting for or scheduling independent reviews."""
    active=[p for p in author.active_jobs() if p.is_relative_to(OUT/'jobs')]
    check_dead_jobs(active,include_reviews=False)
    assignments=jobs(include_reviews=False)
    pending=[p for p in assignments if not (p.parent/'runtime.json').exists()]
    if active or pending:
        author.launch()
        emit('generation_only_running',active_jobs=[p.name for p in author.active_jobs()],remaining_unassigned=unassigned(),independent_review_enabled=False)
        return True
    progress=read(OUT/'generation.automation.json') if (OUT/'generation.automation.json').exists() else {}
    finished=[p.parent.name for p in assignments if author.job_finished(p.parent)]
    if set(finished)!=set(progress.get('author_jobs_ingested',[])):
        author.collect();state=read(OUT/'authoring_status.json');assert not state['errors'],state['errors']
        expected={r['document_id'] for p in assignments for r in read(p)['records']}
        assert {r['id'] for r in state['records']}==expected,'Author completion omitted assigned sources'
        author.render();author.verify();assert read(OUT/'verification.json')['passed'],'Generated screenshot validation failed'
        author.report();author.bundle()
        save(OUT/'generation.automation.json',{'author_jobs_ingested':finished,'updated_utc':now(),'independent_review_enabled':False})
    if unassigned():
        author.assign(size);author.launch()
        emit('generation_only_next_batch',active_jobs=[p.name for p in author.active_jobs()],remaining_unassigned=unassigned(),independent_review_enabled=False)
        return True
    save(OUT/'source_generation.exhausted.json',{'time_utc':now(),'independent_review_deferred':True,'overall_goal_complete':False})
    emit('source_generation_exhausted',active_jobs=[p.name for p in author.active_jobs()],remaining_unassigned=0,independent_review_enabled=False,review_backlog_retained=True)
    return fact_pending


def coordinate(size):
    active=author.active_jobs()
    if (OUT/'STOP').exists():
        emit('draining_stop_request' if active else 'stopped',active_jobs=[p.name for p in active],remaining_unassigned=unassigned())
        return bool(active)
    from tools import v2_fact_constrained as facts
    retries=recover_dead_authors([OUT,facts.OUT],active,author.job_finished)
    if retries['queued'] or retries['waiting']:
        emit('transport_retry',**retries,active_jobs=[p.name for p in active],remaining_unassigned=unassigned())
    if retries['waiting']:
        return True
    fact_pending=facts.advance()
    if not review_enabled():return coordinate_generation(size,fact_pending)
    active_all=author.active_jobs()
    active=[p for p in active_all if p.is_relative_to(OUT)]
    check_dead_jobs(active)
    pending_source_jobs=[p for p in jobs() if not (p.parent/'runtime.json').exists()]
    if (OUT/'local_queue.exhausted.json').exists() and not unassigned() and not active and not pending_source_jobs and not author.pending_recovery_ids() and not author.pending_review_records():
        emit('source_queue_exhausted_fact_track_active' if fact_pending else 'local_queues_exhausted',active_jobs=[p.name for p in active_all],remaining_unassigned=0,minimum_targets_complete=read(OUT/'expansion_summary.json').get('all_cause_targets_met',False))
        return fact_pending
    if active:
        if len(active)<author.worker_limit():
            author.peer_launch()
            author.launch()
            active=author.active_jobs()
        emit('running_workers',active_jobs=[p.name for p in active],remaining_unassigned=unassigned())
        return True
    # Refill only existing assignments before selecting more judgments.
    pending=[p for p in jobs() if not (p.parent/'runtime.json').exists()]
    if pending:
        author.peer_launch()
        author.launch()
        emit('launched_pending_jobs',active_jobs=[p.name for p in author.active_jobs()],remaining_unassigned=unassigned())
        return True
    author.status()
    progress=read(OUT/'progress.json')
    incomplete=[r['worker'] for r in progress['workers'] if r['completed']!=r['assigned']]
    assert not incomplete,('Finished author job left incomplete sources',incomplete)
    author.collect()
    assert not read(OUT/'authoring_status.json')['errors'],'Author validation failed; inspect authoring_status.json'
    author.render()
    author.verify()
    assert read(OUT/'verification.json')['passed'],'Screenshot validation failed; inspect verification.json'
    author.report()
    author.bundle()
    # Both communication candidates and documented gaps get another full reading.
    unreviewed=author.pending_review_records()
    if unreviewed:
        author.peer_assign()
        author.peer_launch()
        emit('independent_review',new_review_assignments=len(unreviewed),active_jobs=[p.name for p in author.active_jobs()],remaining_unassigned=unassigned())
        return True
    author.peer_apply()
    assert not read(OUT/'peer_application.json')['errors'],'Peer acceptance failed; inspect peer_application.json'
    author.render()
    author.verify()
    assert read(OUT/'verification.json')['passed'],'Post-revision validation failed'
    author.report()
    author.bundle()
    recovery_reviews=author.pending_review_records()
    if recovery_reviews:
        author.peer_assign();author.peer_launch()
        emit('recovery_visual_review',new_review_assignments=len(recovery_reviews),
             active_jobs=[p.name for p in author.active_jobs()],remaining_unassigned=unassigned())
        return True
    if unassigned():
        author.assign(size)
        author.launch()
        emit('next_authoring_batch',active_jobs=[p.name for p in author.active_jobs()],remaining_unassigned=unassigned(),recovery_candidates_pending=len(read(OUT/'peer_application.json')['recoveries_pending']))
        return True
    # Exhausting local sources does not satisfy quotas or certify benchmark quality.
    save(OUT/'local_queue.exhausted.json',{'time_utc':now(),'minimum_distinct_judgments_per_cause':quota_target(),'minimum_targets_complete':read(OUT/'expansion_summary.json').get('all_cause_targets_met',False)})
    emit('local_queue_exhausted',remaining_unassigned=0,quota_review='See cause_progress.json',recovery_candidates_pending=len(read(OUT/'peer_application.json')['recoveries_pending']),minimum_targets_complete=read(OUT/'expansion_summary.json').get('all_cause_targets_met',False))
    return fact_pending


def run(size,once=False):
    assert size>0,'Batch size must be positive'
    OUT.mkdir(parents=True,exist_ok=True)
    hashes={name:sha(ROOT/name) for name in CODE}
    save(OUT/'runner.code.json',{'started_utc':now(),'python':sys.version,'code_sha256':hashes,'concurrency_limit':author.worker_limit(),'batch_per_chinese_author':size})
    emit('starting',active_jobs=[],remaining_unassigned=unassigned())
    try:
        while True:
            for name,digest in hashes.items():
                assert sha(ROOT/name)==digest,('Coordinator code changed during a run; restart after review',name)
            again=coordinate(size)
            if once or not again:return
            time.sleep(20)
    except Exception as error:
        emit('needs_attention',error=str(error),traceback=traceback.format_exc(),remaining_unassigned=unassigned())
        raise


def start(size):
    assert size>0,'Batch size must be positive'
    if STATE.exists():
        old=read(STATE)
        pid=old.get('pid')
        if pid:
            check=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/NH','/FO','CSV'],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if f'"{pid}"' in check.stdout:
                raise RuntimeError(f'Coordinator already running with PID {pid}')
    assert not (OUT/'STOP').exists(),'STOP marker exists; remove it only when resuming is intended'
    args=[sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'run','--size',str(size)]
    with (OUT/'runner.stdout.log').open('ab') as stdout,(OUT/'runner.stderr.log').open('ab') as stderr:
        process=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    save(OUT/'runner.launch.json',{'pid':process.pid,'argv':args,'started_utc':now()})
    print(json.dumps({'pid':process.pid,'status_file':rel(STATE)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['start','run','once','status'])
    parser.add_argument('--size',type=int,default=10)
    args=parser.parse_args()
    if args.command=='start':start(args.size)
    elif args.command=='status':print(json.dumps(read(STATE) if STATE.exists() else {'phase':'not_started'},ensure_ascii=False,indent=2))
    else:run(args.size,once=args.command=='once')
