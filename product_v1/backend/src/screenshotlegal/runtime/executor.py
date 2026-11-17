import asyncio
from screenshotlegal.domain.runtime.models import CasePlan
from screenshotlegal.domain.common.models import now
from screenshotlegal.runtime.events import emit
from screenshotlegal.runtime.review_gate import create_gate
from screenshotlegal.runtime.stage_executor import StageExecutor

class Runtime:
    def __init__(self,repo,skills,settings):
        self.repo,self.settings=repo,settings
        self.stages=StageExecutor(repo,skills)
        self.tasks={}

    def schedule(self,run_id):
        existing=self.tasks.get(run_id)
        if existing and not existing.done():
            return
        self.tasks[run_id]=asyncio.create_task(self.execute(run_id))

    async def execute(self,run_id):
        repo=self.repo;run=repo.get('analysis_runs',run_id)
        if run['status'] in ['COMPLETED','FAILED','INTERRUPTED']:
            return
        gates=repo.list('review_gates',run_id=run_id)
        if any(g['status']=='REJECTED' for g in gates):
            run.update(status='FAILED',completed_at=now(),error='Review gate rejected')
            repo.put('analysis_runs',run_id,run,run['case_id']);emit(repo,run_id,'run-failed',{'error':run['error']});return
        if any(g['status']=='WAITING_REVIEW' for g in gates):
            return
        run['status']='RUNNING';repo.put('analysis_runs',run_id,run,run['case_id'])
        emit(repo,run_id,'run-started')
        plan=CasePlan.model_validate(run['plan'])
        try:
            for stage in sorted({n.stage for n in plan.nodes}):
                pending={n.node_id:n for n in plan.nodes if n.stage==stage}
                done={s['node_id'] for s in repo.list('analysis_snapshots',run_id=run_id)}
                emit(repo,run_id,'stage-started',dict(stage=stage))
                while pending:
                    for id in list(pending):
                        if id in done:
                            pending.pop(id)
                    if not pending:
                        break
                    ready=[n for n in pending.values() if set(n.depends_on)<=done]
                    if not ready:
                        raise ValueError('Unsatisfied node dependencies')
                    results=await asyncio.gather(*(self.stages.execute_node(run,n) for n in ready),return_exceptions=True)
                    errors=[r for r in results if isinstance(r,BaseException)]
                    if errors:
                        raise errors[0]
                    done.update(n.node_id for n in ready)
                    for n in ready:
                        pending.pop(n.node_id)
                emit(repo,run_id,'stage-completed',dict(stage=stage))
                requires=any(s.get('requires_review') for s in repo.list('analysis_snapshots',run_id=run_id))
                if stage==6 and (run['critical_gate'] or requires):
                    gate=repo.optional('review_gates',run_id+':critical-finding')
                    if not gate:
                        gate=create_gate(repo,run,'critical-finding',self.settings.auto_approve_gates)
                    if gate['status']=='WAITING_REVIEW':
                        run['status']='WAITING_REVIEW';repo.put('analysis_runs',run_id,run,run['case_id']);return
            run.update(status='COMPLETED',completed_at=now())
            case=repo.get('cases',run['case_id']);case['active_analysis_run_id']=run_id
            repo.batch([('analysis_runs',run_id,run,run['case_id'],run_id,False),('cases',case['id'],case,case['id'],'',False)])
            emit(repo,run_id,'run-completed')
        except asyncio.CancelledError:
            run.update(status='INTERRUPTED',completed_at=now());repo.put('analysis_runs',run_id,run,run['case_id']);raise
        except Exception as error:
            run.update(status='FAILED',error=type(error).__name__+': '+str(error),completed_at=now())
            repo.put('analysis_runs',run_id,run,run['case_id']);emit(repo,run_id,'run-failed',{'error':run['error']})

    async def close(self):
        tasks=[t for t in self.tasks.values() if not t.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
