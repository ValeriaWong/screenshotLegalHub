import asyncio
from dataclasses import replace
import pytest
from agentic.contracts import (HarnessError, ReviewResult, Plan, TaskSpec, Limits, Status, RetryPolicy, TransientError)
from agentic.planning import validate_plan, transition
from agentic.state import SQLiteStore
from .conftest import Number, request

async def test_dependencies_and_aggregation(factory, principal):
    async def work(value, ctx):
        return {'value': value.value + sum(v['value'] for v in ctx.dependencies.values())}
    def plan(v):
        return Plan(tasks=[TaskSpec(task_id='a',stage_id=0,skill='step',input={'value':2}),
                           TaskSpec(task_id='b',stage_id=1,skill='step',input={'value':3},dependencies=['a'])])
    runtime=factory(work,plan=plan)
    run=runtime.create_run(request(),principal)
    final=await runtime.wait(run['run_id'],principal)
    assert final['status']=='COMPLETED' and final['result']=={'b':{'value':5}}
    assert all(t['review_status']=='PASS' for t in final['tasks'].values())
    events=[e async for e in runtime.stream_events(run['run_id'],principal)]
    assert [e['sequence'] for e in events]==list(range(1,len(events)+1))
    assert all(e['trace_id']==run['trace_id'] for e in events)
    assert len([e for e in events if e['type']=='stage-completed'])==2
    assert len([e async for e in runtime.stream_events(run['run_id'],principal,events[-2]['sequence'])])==1

@pytest.mark.parametrize('kind',['cycle','missing','backwards','duplicate'])
def test_invalid_dag(kind):
    a=TaskSpec(task_id='a',stage_id=0,skill='step')
    b=TaskSpec(task_id='b',stage_id=1,skill='step',dependencies=['a'])
    if kind=='cycle':
        b.stage_id=0; a.dependencies=['b']
    elif kind=='missing': a.dependencies=['missing']
    elif kind=='backwards': a.dependencies=['b']; b.dependencies=[]
    else: b.task_id='a'
    with pytest.raises(HarnessError,match='dependency|duplicate|backwards'):
        validate_plan(Plan(tasks=[a,b]))

@pytest.mark.parametrize('origin,target',[(Status.COMPLETED,Status.RUNNING),(Status.CANCELLED,Status.RUNNING),(Status.PENDING,Status.COMPLETED)])
def test_invalid_state(origin,target):
    class State: status=origin
    with pytest.raises(HarnessError): transition(State(),target)

async def test_retry_then_success(factory,principal):
    attempts=[]
    async def work(v,ctx):
        attempts.append(1)
        if len(attempts)==1: raise TransientError()
        return {'value':v.value+10}
    runtime=factory(work,plan=lambda v:Plan(tasks=[TaskSpec(task_id='first',stage_id=0,skill='step',input=v.model_dump(),
                                                        retry_policy=RetryPolicy(max_attempts=2,backoff=0))]))
    run=runtime.create_run(request(),principal)
    result=await runtime.wait(run['run_id'],principal)
    assert result['status']=='COMPLETED' and result['tasks']['first']['attempts']==2

async def test_repair_and_rereview(factory,principal):
    async def work(v,ctx): return {'value':-v.value}
    def positive(out,ctx): return ReviewResult(status='PASS' if out['value']>=0 else 'REWORK',score=0)
    async def repair(v,ctx):
        assert ctx.review.status=='REWORK'
        return {'value':abs(ctx.previous_output['value'])}
    runtime=factory(work,repair=repair,rules=(positive,))
    result=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert result['status']=='COMPLETED'
    assert [r['status'] for r in result['tasks']['first']['reviews']]==['REWORK','PASS']
    assert result['tasks']['first']['repairs']==1

async def test_schema_repair(factory,principal):
    async def bad(v,ctx): return {'unknown':3}
    async def fix(v,ctx): return {'value':v.value}
    runtime=factory(bad,repair=fix)
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['status']=='COMPLETED' and final['tasks']['first']['reviews'][0]['reviewer_type']=='schema'

async def test_repair_bound(factory,principal):
    async def work(v,ctx): return {'value':v.value}
    def reject(out,ctx): return ReviewResult(status='REWORK',score=0)
    runtime=factory(work,repair=work,rules=(reject,))
    result=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert result['status']=='FAILED' and result['error']['code']=='REVIEW_FAILED'
    assert result['tasks']['first']['repairs']==2 and result['usage']['iterations']==3

async def test_human_gate_and_stale_decision(factory,principal):
    runtime=factory(human=True)
    run=runtime.create_run(request(),principal)
    paused=await runtime.wait(run['run_id'],principal)
    assert paused['status']=='WAITING_REVIEW'
    with pytest.raises(HarnessError,match='stale'):
        runtime.resume_run(run['run_id'],principal,{'decision':'approve','gate_digest':'wrong'})
    runtime.resume_run(run['run_id'],principal,{'decision':'approve','gate_digest':paused['gate']['digest']})
    final=await runtime.wait(run['run_id'],principal)
    assert final['status']=='COMPLETED' and final['usage']['iterations']==1
    assert final['tasks']['first']['reviews'][-1]['reviewer_type']=='human'

async def test_human_reject(factory,principal):
    runtime=factory(human=True)
    run=runtime.create_run(request(),principal)
    paused=await runtime.wait(run['run_id'],principal)
    result=runtime.resume_run(run['run_id'],principal,{'decision':'reject','gate_digest':paused['gate']['digest']})
    assert result['status']=='FAILED' and result['error']['code']=='REVIEW_REJECTED'

async def test_timeout(factory,principal):
    async def slow(v,ctx): await asyncio.sleep(1)
    runtime=factory(slow,plan=lambda v:Plan(tasks=[TaskSpec(task_id='first',stage_id=0,skill='step',input=v.model_dump(),timeout_seconds=.02)]))
    result=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert result['status']=='FAILED' and result['error']['code']=='STAGE_TIMEOUT'

@pytest.mark.parametrize('started',[False,True])
async def test_cancellation(factory,principal,started):
    signal=asyncio.Event()
    async def wait(v,ctx): signal.set(); await asyncio.sleep(10)
    runtime=factory(wait)
    run=runtime.create_run(request(),principal)
    if started: await signal.wait()
    final=await runtime.cancel_run(run['run_id'],principal)
    assert final['status']=='CANCELLED'
    with pytest.raises(HarnessError): runtime.resume_run(run['run_id'],principal)

async def test_restart_resume_keeps_completed_tasks(factory,principal,tmp_path):
    entered=asyncio.Event(); stop=True; counts=[]
    async def handler(v,ctx):
        counts.append(ctx.task_id)
        if ctx.task_id=='b' and stop:
            entered.set(); await asyncio.sleep(10)
        return {'value':v.value+1}
    def plan(v):
        return Plan(tasks=[TaskSpec(task_id='a',stage_id=0,skill='step',input=v.model_dump()),
                           TaskSpec(task_id='b',stage_id=1,skill='step',input=v.model_dump(),dependencies=['a'],retry_policy=RetryPolicy(max_attempts=2))])
    file=tmp_path/'checkpoint.sqlite'
    first=factory(handler,plan=plan,store=SQLiteStore(file))
    run=first.create_run(request(),principal); await entered.wait(); await first.close()
    stop=False
    second=factory(handler,plan=plan,store=SQLiteStore(file))
    assert second.get_run(run['run_id'],principal)['status']=='INTERRUPTED'
    second.resume_run(run['run_id'],principal)
    final=await second.wait(run['run_id'],principal)
    assert final['status']=='COMPLETED' and counts==['a','b','b']
    assert final['usage']['iterations']==3

async def test_version_change_blocks_resume(factory,principal):
    runtime=factory(human=True)
    run=runtime.create_run(request(),principal); paused=await runtime.wait(run['run_id'],principal)
    runtime.skills._items['step']=replace(runtime.skills.get('step'),version='changed')
    with pytest.raises(HarnessError,match='version'):
        runtime.resume_run(run['run_id'],principal,{'decision':'approve','gate_digest':paused['gate']['digest']})

async def test_idempotency(factory,principal):
    runtime=factory()
    one=runtime.create_run(request(),principal); two=runtime.create_run(request(),principal)
    assert one['run_id']==two['run_id']
    await runtime.wait(one['run_id'],principal)
    with pytest.raises(HarnessError,match='idempotency'):
        runtime.create_run(dict(request(),input={'value':3}),principal)

async def test_iteration_budget(factory,principal):
    async def work(v,ctx): return {'value':-1}
    def reject(out,ctx): return ReviewResult(status='REWORK',score=0)
    runtime=factory(work,repair=work,rules=(reject,))
    result=await runtime.wait(runtime.create_run(request(limits=Limits(max_iterations=1)),principal)['run_id'],principal)
    assert result['error']['code']=='BUDGET_EXHAUSTED'

async def test_model_budget_and_settlement(factory,principal):
    async def work(v,ctx):
        reservation=ctx.reserve_model(10,.1)
        reservation.settle(4,.03)
        return {'value':v.value}
    limits=Limits(max_model_calls=1,max_tokens=10,max_cost=.1)
    runtime=factory(work,limits=limits)
    result=await runtime.wait(runtime.create_run(request(limits=limits),principal)['run_id'],principal)
    assert result['status']=='COMPLETED'
    assert result['usage']['tokens']==4 and result['usage']['model_calls']==1
    assert result['usage']['cost']==pytest.approx(.03)

async def test_default_denies_model_usage(factory,principal):
    async def work(v,ctx): ctx.reserve_model(1,.01)
    runtime=factory(work)
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['error']['code']=='BUDGET_EXHAUSTED'

async def test_active_run_limit(factory,principal):
    runtime=factory(); runtime.max_active_runs=1
    runtime.create_run(request(),principal)
    with pytest.raises(HarnessError,match='rate limited'):
        runtime.create_run(request('second'),principal)
