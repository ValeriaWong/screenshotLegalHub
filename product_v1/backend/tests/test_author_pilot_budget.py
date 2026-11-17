import importlib.util
from pathlib import Path
import pytest
from types import SimpleNamespace
from screenshotlegal.research.store import Store
from screenshotlegal.research.contracts import digest
from screenshotlegal.research.gateway import ModelFailure

REPO=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('author_kie_pilot',REPO/'paper/author_reproductions/run_kie_vqa_pilot.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)

@pytest.fixture
def gateway(tmp_path):
    store=Store(tmp_path)
    configuration=SimpleNamespace(get=lambda *a:dict(enabled=True,allow_external_egress=True))
    instance=pilot.BoundedGateway(store,SimpleNamespace(),configuration,'owner',1)
    yield instance
    store.close()

async def test_durable_cap_counts_failed_requests_before_network(gateway):
    with gateway.store.tx() as db:gateway.store.put('evaluation.request',dict(id='previous',status='failed'),'owner',db)
    with pytest.raises(ModelFailure,match='上限'):await gateway.call('owner',{},[],'test','new')
    assert len(gateway.store.list('evaluation.request','owner'))==1

async def test_saved_response_reuse_never_calls_provider(gateway):
    messages=[dict(role='user',content='same input')]
    response=dict(raw='original response',usage=dict(prompt_tokens=1,completion_tokens=1))
    with gateway.store.tx() as db:gateway.store.put('evaluation.request',dict(id='same',input_hash=digest(messages),status='completed',response=response),'owner',db)
    assert await gateway.call('owner',{},messages,'test','same')==response
    assert len(gateway.store.list('evaluation.request','owner'))==1

@pytest.mark.parametrize('status',['failed','unknown','calling_model'])
async def test_unresolved_native_requests_are_not_automatically_reissued(gateway,status):
    with gateway.store.tx() as db:gateway.store.put('evaluation.request',dict(id='same',input_hash=digest([]),status=status),'owner',db)
    with pytest.raises(ModelFailure,match='不自动重发'):await gateway.call('owner',{},[],'test','same')
    assert len(gateway.store.list('evaluation.request','owner'))==1


async def test_native_failure_keeps_exact_input_before_gateway_call(tmp_path):
    import json
    calls=[]
    async def fail(owner,model,messages,purpose,request_id):
        trace=json.loads((tmp_path/'e05_self_refine.native_trace.json').read_text(encoding='utf-8'))
        assert trace[0]['status']=='calling_model' and trace[0]['effective_messages']==messages
        assert trace[0]['native_request']['messages']
        calls.append(request_id)
        raise ModelFailure('network','fixed failure fixture; no supplier request',unknown=True)
    result=await pilot.native_acronym(SimpleNamespace(call=fail),'owner',dict(parameters={}),tmp_path,'fixed-fixture')
    assert result['status']=='failed' and len(calls)==1
    trace=json.loads((tmp_path/'e05_self_refine.native_trace.json').read_text(encoding='utf-8'))
    assert trace[0]['status']=='failed' and trace[0]['error']['category']=='network'
    assert trace[0]['effective_messages'] and trace[0]['native_request']
