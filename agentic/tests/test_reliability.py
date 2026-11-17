import asyncio
from dataclasses import replace
import sqlite3
import pytest
import hashlib
import json
from agentic.contracts import digest, HarnessError, Plan, TaskSpec, RetryPolicy, Limits
from agentic.state import SQLiteStore
from agentic.tools import Tool, ToolRegistry
from .conftest import Number, request


def test_canonical_digest_is_stable():
    value = {"b": 2, "a": "中文"}
    assert digest(value) == hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

async def test_completed_tool_replayed_after_interruption(factory,principal,tmp_path):
    calls=[]; entered=asyncio.Event(); stop=True
    async def atomic(v,ctx,key): calls.append(key); return {'value':v.value*2}
    tools=ToolRegistry(); tools.register(Tool('double','1',Number,Number,atomic))
    async def skill(v,ctx):
        result=(await ctx.call_tool('double',v.model_dump())).data
        if stop: entered.set(); await asyncio.sleep(10)
        return result
    file=tmp_path/'harness.sqlite'
    first=factory(skill,tools=tools,store=SQLiteStore(file))
    run=first.create_run(request(),principal); await entered.wait(); await first.close()
    stop=False
    second=factory(skill,tools=tools,store=SQLiteStore(file)); second.resume_run(run['run_id'],principal)
    final=await second.wait(run['run_id'],principal)
    assert final['status']=='COMPLETED' and len(calls)==1 and final['usage']['tool_calls']==1
    assert any(e.type=='tool-replayed' for e in second.store.events(run['run_id']))

async def test_cancelled_tool_is_audited(factory,principal):
    entered=asyncio.Event()
    async def atomic(v,ctx,key): entered.set(); await asyncio.sleep(10)
    tools=ToolRegistry(); tools.register(Tool('slow','1',Number,Number,atomic))
    async def skill(v,ctx): return (await ctx.call_tool('slow',v.model_dump())).data
    runtime=factory(skill,tools=tools); run=runtime.create_run(request(),principal)
    await entered.wait(); await runtime.cancel_run(run['run_id'],principal)
    assert any(e.type=='tool-cancelled' for e in runtime.store.events(run['run_id']))

async def test_failure_skips_downstream(factory,principal):
    async def fail(v,ctx): raise RuntimeError('provider raw body')
    runtime=factory(fail,plan=lambda v:Plan(tasks=[TaskSpec(task_id='a',stage_id=0,skill='step',input=v.model_dump()),
        TaskSpec(task_id='b',stage_id=1,skill='step',input=v.model_dump(),dependencies=['a'])]))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['tasks']['a']['status']=='FAILED' and final['tasks']['b']['status']=='SKIPPED'
    assert final['usage']['iterations']==1

async def test_shared_stage_timeout(factory,principal):
    async def slow(v,ctx): await asyncio.sleep(.02); return {'value':v.value}
    runtime=factory(slow,plan=lambda v:Plan(stage_timeout_seconds=.03,tasks=[
        TaskSpec(task_id='a',stage_id=0,skill='step',input=v.model_dump()),
        TaskSpec(task_id='b',stage_id=0,skill='step',input=v.model_dump(),dependencies=['a'])]))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['status']=='FAILED' and final['error']['code']=='STAGE_TIMEOUT'

async def test_context_projection_isolated(factory,principal):
    async def skill(v,ctx):
        if ctx.task_id=='b': ctx.dependencies['a']['value']=999
        return {'value':v.value}
    runtime=factory(skill,plan=lambda v:Plan(tasks=[TaskSpec(task_id='a',stage_id=0,skill='step',input=v.model_dump()),
        TaskSpec(task_id='b',stage_id=1,skill='step',input=v.model_dump(),dependencies=['a'])]))
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert runtime.store.get(final['run_id']).tasks['a'].output=={'value':2}

async def test_secret_error_code_cannot_leak(factory,principal):
    async def skill(v,ctx): raise HarnessError('sk-secret12345678901234567890')
    runtime=factory(skill)
    final=await runtime.wait(runtime.create_run(request(),principal)['run_id'],principal)
    assert final['error']['code']=='EXECUTION_FAILED'

async def test_schema_artifacts_match_export(factory):
    from pathlib import Path
    import json
    from agentic.builtin.workflow import components
    from agentic.adapters.responses import ResponsesAdapter
    from agentic.core import Runtime
    from agentic.contracts import Principal
    runtime=Runtime(*components(None),SQLiteStore())
    try:
        generated=ResponsesAdapter(runtime,Principal(subject='schema'),scope_id='s').tools()
        checked=json.loads((Path(__file__).parents[1]/'examples/responses-tools.json').read_text(encoding='utf-8'))
        assert generated==checked
        from agentic.adapters.dify import DifyAdapter
        from agentic.adapters.http import create_app, TokenAuth
        from agentic.model import stage_prompt
        package=Path(__file__).parents[1]
        assert DifyAdapter(runtime).openapi('http://127.0.0.1:18440')==json.loads((package/'examples/dify-openapi.json').read_text(encoding='utf-8'))
        principal=Principal(subject='schema-export',permissions=frozenset({'run:read'}))
        assert create_app(runtime,TokenAuth({'schema-export-placeholder-not-a-live-token':principal})).openapi()==json.loads((package/'docs/http-openapi.json').read_text(encoding='utf-8'))
        manifest=json.loads((package/'examples/harness-manifest.json').read_text(encoding='utf-8'))
        assert manifest['skills']==runtime.skills.describe() and manifest['tools']==runtime.tools.describe()
        for stage in manifest['stages']:
            assert manifest['prompts'][stage]['content']==stage_prompt(stage)
    finally: await runtime.close()


def test_unknown_checkpoint_version_fails(tmp_path):
    file=tmp_path/'unsupported.sqlite'
    with sqlite3.connect(file) as db: db.execute('PRAGMA user_version=999')
    with pytest.raises(HarnessError): SQLiteStore(file)

async def test_nested_input_cannot_mutate_checkpoint(principal):
    from agentic.primitives import StrictModel
    from agentic.skills import SkillRegistry, Skill
    from agentic.planning import Workflow
    from agentic.core import Runtime
    class Nested(StrictModel):
        payload: dict
    async def mutate(value,ctx):
        value.payload['nested']['value']=999
        return {'value':1}
    skills=SkillRegistry(); skills.register(Skill('step','1',Nested,Number,mutate))
    workflow=Workflow('nested','1',Nested,lambda v:Plan(tasks=[TaskSpec(task_id='first',stage_id=0,skill='step',input=v.model_dump())]))
    runtime=Runtime(ToolRegistry(),skills,[workflow],SQLiteStore())
    try:
        run=runtime.create_run(dict(workflow='nested',input={'payload':{'nested':{'value':2}}},idempotency_key='copy-test'),principal)
        final=await runtime.wait(run['run_id'],principal)
        assert final['status']=='COMPLETED'
        assert runtime.store.get(run['run_id']).tasks['first'].input['payload']['nested']['value']==2
    finally: await runtime.close()

async def test_invalid_done_event_is_controlled(factory,principal):
    from agentic.adapters.responses import ResponsesAdapter
    bridge=ResponsesAdapter(factory(),principal,scope_id='s')
    with pytest.raises(HarnessError,match='invalid event'):
        await bridge.handle_event({'type':'response.output_item.done','item':None})
