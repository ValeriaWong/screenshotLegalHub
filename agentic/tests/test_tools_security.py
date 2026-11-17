import asyncio
import json
from dataclasses import replace
import pytest
from agentic.contracts import HarnessError, Principal, Limits, RetryPolicy, TransientError, Status
from agentic.tools import ToolRegistry, Tool
from agentic.skills import SkillRegistry, Skill
from agentic.state import SQLiteStore
from .conftest import Number, request

def registry(handler, **kwargs):
    tools=ToolRegistry()
    tools.register(Tool('double','1',Number,Number,handler,permissions=frozenset({'compute'}),**kwargs))
    return tools

async def use(value,ctx):
    return (await ctx.call_tool('double',value.model_dump())).data

async def test_real_sync_tool(factory,principal):
    def double(v,ctx,key): return {'value':v.value*2}
    runtime=factory(use,tools=registry(double))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['result']=={'first':{'value':4}} and final['usage']['tool_calls']==1
    events=runtime.store.events(final['run_id'])
    audit=next(e for e in events if e.type=='tool-completed')
    assert audit.task_id=='first' and audit.data['latency_seconds']>=0 and audit.data['operation_key']

async def test_tool_retry_reuses_operation_key(factory,principal):
    keys=[]
    async def work(v,ctx,key):
        keys.append(key)
        if len(keys)==1: raise TransientError()
        return {'value':v.value*2}
    runtime=factory(use,tools=registry(work,retry_policy=RetryPolicy(max_attempts=2,backoff=0)))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['status']=='COMPLETED' and final['usage']['tool_calls']==2 and keys[0]==keys[1]

async def test_no_retry_for_bad_input(factory,principal):
    calls=[]
    async def work(v,ctx,key): calls.append(key); return {'value':v.value}
    async def illegal(v,ctx): return await ctx.call_tool('double',{'value':'2'})
    runtime=factory(illegal,tools=registry(work))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['error']['code']=='INVALID_TOOL_INPUT' and calls==[]

async def test_wrong_output_fails(factory,principal):
    async def work(v,ctx,key): return {'value':'wrong'}
    runtime=factory(use,tools=registry(work))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['error']['code']=='INVALID_TOOL_OUTPUT'

async def test_tool_timeout(factory,principal):
    async def work(v,ctx,key): await asyncio.sleep(1)
    runtime=factory(use,tools=registry(work,timeout_seconds=.01))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['error']['code']=='TOOL_TIMEOUT'

async def test_tool_budget(factory,principal):
    async def work(v,ctx,key): return {'value':v.value}
    runtime=factory(use,tools=registry(work))
    final=await runtime.wait(runtime.create_run(request(limits=Limits(max_tool_calls=0)),principal)['run_id'],principal)
    assert final['error']['code']=='BUDGET_EXHAUSTED' and final['usage']['tool_calls']==0

async def test_permission_denied_before_execution(factory,principal):
    async def work(v,ctx,key): return {'value':v.value}
    runtime=factory(use,tools=registry(work))
    unauthorized=principal.model_copy(update={'permissions':principal.permissions-{'compute'}})
    with pytest.raises(HarnessError,match='permission'):
        runtime.create_run(request(),unauthorized)

async def test_undeclared_tool_denied(factory,principal):
    async def work(v,ctx,key): return {'value':v.value}
    runtime=factory(use,tools=registry(work))
    runtime.skills._items['step']=replace(runtime.skills.get('step'),tools=())
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['error']['code']=='PERMISSION_DENIED'

async def test_effect_gate_and_replay(factory,principal):
    effects={}
    async def write(v,ctx,key):
        effects.setdefault(key,{'value':v.value*2})
        return effects[key]
    runtime=factory(use,tools=registry(write,side_effect=True,idempotent=True))
    run=runtime.create_run(request(),principal)
    paused=await runtime.wait(run['run_id'],principal)
    assert paused['status']=='WAITING_REVIEW' and effects=={}
    runtime.resume_run(run['run_id'],principal,{'decision':'approve','gate_digest':paused['gate']['digest']})
    final=await runtime.wait(run['run_id'],principal)
    assert final['status']=='COMPLETED' and len(effects)==1
    assert runtime.create_run(request(),principal)['run_id']==run['run_id'] and len(effects)==1

async def test_effect_timeout_is_uncertain(factory,principal):
    async def write(v,ctx,key): await asyncio.sleep(1)
    runtime=factory(use,tools=registry(write,side_effect=True,idempotent=True,timeout_seconds=.01))
    run=runtime.create_run(request(),principal); paused=await runtime.wait(run['run_id'],principal)
    runtime.resume_run(run['run_id'],principal,{'decision':'approve','gate_digest':paused['gate']['digest']})
    final=await runtime.wait(run['run_id'],principal)
    assert final['status']=='FAILED' and final['error']['code']=='EFFECT_UNCERTAIN'

@pytest.mark.parametrize('async_handler,idempotent',[(False,True),(True,False)])
def test_unsafe_tool_registration(async_handler,idempotent):
    def sync(v,c,k): return {'value':1}
    async def async_(v,c,k): return {'value':1}
    with pytest.raises(HarnessError,match='write tools'):
        registry(async_ if async_handler else sync,side_effect=True,idempotent=idempotent)

async def test_output_secret_never_persisted(factory,principal,tmp_path,caplog):
    secret='sk-privateSECRETvalue123456789'
    async def work(v,ctx): return {'value':1,'api_key':secret}
    file=tmp_path/'private.sqlite'
    runtime=factory(work,store=SQLiteStore(file))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['error']['code']=='SENSITIVE_CONTEXT'
    assert secret not in json.dumps(final) and secret not in caplog.text
    assert secret not in runtime.store.db.execute('SELECT body FROM runs').fetchone()[0]

@pytest.mark.parametrize('raised',[RuntimeError,HarnessError])
async def test_exception_messages_not_exposed(factory,principal,raised):
    secret='Bearer secret-that-must-never-leak'
    async def work(v,ctx):
        if raised is HarnessError: raise HarnessError('TOOL_FAILED',secret)
        raise RuntimeError(secret)
    runtime=factory(work)
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert secret not in json.dumps(final)
    assert secret not in runtime.store.get(final['run_id']).model_dump_json()

async def test_foreign_run_is_hidden(factory,principal):
    runtime=factory(); run=runtime.create_run(request(),principal)
    other=principal.model_copy(update={'subject':'bob'})
    with pytest.raises(HarnessError,match='not found'): runtime.get_run(run['run_id'],other)
    with pytest.raises(HarnessError,match='not found'): await runtime.cancel_run(run['run_id'],other)
    with pytest.raises(HarnessError,match='not found'): runtime.resume_run(run['run_id'],other)

async def test_human_permission_required(factory,principal):
    runtime=factory(human=True); run=runtime.create_run(request(),principal)
    paused=await runtime.wait(run['run_id'],principal)
    no_review=principal.model_copy(update={'permissions':principal.permissions-{'run:review'}})
    with pytest.raises(HarnessError) as error:
        runtime.resume_run(run['run_id'],no_review,{'decision':'approve','gate_digest':paused['gate']['digest']})

async def test_no_read_cannot_start(factory,principal):
    runtime=factory()
    no_read=principal.model_copy(update={'permissions':principal.permissions-{'run:read'}})
    with pytest.raises(HarnessError): runtime.create_run(request(),no_read)
    assert runtime.store.db.execute('SELECT count(*) FROM runs').fetchone()[0]==0

async def test_input_limit(factory,principal):
    runtime=factory()
    with pytest.raises(HarnessError): runtime.create_run(dict(request(),input={'value':2,'prompt':'x'*1000001}),principal)

async def test_parameter_permissions_cannot_be_injected(factory,principal):
    runtime=factory()
    from pydantic import ValidationError
    with pytest.raises(ValidationError): runtime.create_run(dict(request(),permissions=['all']),principal)

async def test_checkpoint_cas_and_exclusive_lock(factory,principal,tmp_path):
    file=tmp_path/'state.sqlite'; store=SQLiteStore(file)
    runtime=factory(store=store); run=runtime.create_run(request(),principal)
    await runtime.wait(run['run_id'],principal)
    a=store.get(run['run_id']); b=store.get(run['run_id'])
    store.save(a,'test-checkpoint')
    before=len(store.events(a.run_id))
    with pytest.raises(HarnessError,match='checkpoint conflict'): store.save(b,'stale')
    assert len(store.events(a.run_id))==before
    with pytest.raises(HarnessError,match='one runtime'): SQLiteStore(file)

async def test_crash_recovery_reserves_budgets(factory,principal,tmp_path):
    store=SQLiteStore(tmp_path/'state.sqlite'); runtime=factory(store=store)
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    run=store.get(final['run_id']); run.status=Status.RUNNING; run.tasks['first'].status=Status.RUNNING
    run.active_seconds=run.request.limits.timeout_seconds; run.usage.iterations=1
    store.save(run,'crash-fixture'); await runtime.close()
    fresh=factory(store=SQLiteStore(tmp_path/'state.sqlite'))
    assert fresh.get_run(run.run_id,principal)['status']=='INTERRUPTED'
    fresh.resume_run(run.run_id,principal)
    failed=await fresh.wait(run.run_id,principal)
    assert failed['status']=='FAILED'
    assert failed['error']['code'] in {'STAGE_TIMEOUT','RETRY_EXHAUSTED'}

async def test_effect_approval_binds_actual_validated_arguments(factory,principal):
    effects=[]; changing=2
    async def write(v,ctx,key): effects.append(v.value); return {'value':v.value}
    async def skill(v,ctx): return (await ctx.call_tool('double',{'value':changing})).data
    runtime=factory(skill,tools=registry(write,side_effect=True,idempotent=True))
    run=runtime.create_run(request(),principal); first=await runtime.wait(run['run_id'],principal)
    assert first['gate']['tool']=='double' and first['gate']['input']=={'value':2}
    changing=7
    runtime.resume_run(run['run_id'],principal,{'decision':'approve','gate_digest':first['gate']['digest']})
    second=await runtime.wait(run['run_id'],principal)
    assert second['status']=='WAITING_REVIEW' and effects==[]
    assert second['gate']['input']=={'value':7} and second['gate']['digest']!=first['gate']['digest']
    runtime.resume_run(run['run_id'],principal,{'decision':'approve','gate_digest':second['gate']['digest']})
    final=await runtime.wait(run['run_id'],principal)
    assert final['status']=='COMPLETED' and effects==[7]
