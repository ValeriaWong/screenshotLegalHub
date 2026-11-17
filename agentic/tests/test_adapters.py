import json
import pytest
import httpx
from agentic.adapters.generic import GenericAdapter
from agentic.adapters.responses import ResponsesAdapter
from agentic.adapters.dify import DifyAdapter
from agentic.adapters.http import create_app, TokenAuth
from agentic.contracts import HarnessError, Principal
from .conftest import request

TOKEN='test-service-token-abcdefghijklmnopqrstuvwxyz'

def call(**kwargs):
    return dict(type='function_call',call_id='call_1',name='harness_run_work',arguments='{"value":2}',**kwargs)

async def test_responses_function_contract(factory,principal):
    runtime=factory(); bridge=ResponsesAdapter(runtime,principal,scope_id='session-1')
    tools=bridge.tools(); definition=next(t for t in tools if t['name']=='harness_run_work')
    assert definition['type']=='function' and 'function' not in definition
    assert definition['parameters']['additionalProperties'] is False and definition['strict'] is False
    result=await bridge.handle_call(call(id='fc_123',status='completed'))
    assert result['type']=='function_call_output' and result['call_id']=='call_1'
    payload=json.loads(result['output']); assert payload['ok'] and payload['data']['result']=={'first':{'value':3}}
    repeated=json.loads((await bridge.handle_call(call()))['output'])
    assert repeated['data']['run_id']==payload['data']['run_id']
    conflict=dict(call(),arguments='{"value":3}')
    assert json.loads((await bridge.handle_call(conflict))['output'])['error']['code']=='IDEMPOTENCY_CONFLICT'

async def test_responses_scope_and_identity(factory,principal):
    runtime=factory()
    a=ResponsesAdapter(runtime,principal,scope_id='one'); b=ResponsesAdapter(runtime,principal,scope_id='two')
    ra=json.loads((await a.handle_call(call()))['output']); rb=json.loads((await b.handle_call(call()))['output'])
    assert ra['data']['run_id']!=rb['data']['run_id']

async def test_stream_never_executes_partial_arguments(factory,principal):
    runtime=factory(); bridge=ResponsesAdapter(runtime,principal,scope_id='s')
    for type_ in ['response.output_item.added','response.function_call_arguments.delta','response.function_call_arguments.done']:
        assert await bridge.handle_event({'type':type_,'item':call(),'delta':'{incomplete'}) is None
    assert runtime.store.db.execute('SELECT count(*) FROM runs').fetchone()[0]==0
    event={'type':'response.output_item.done','output_index':0,'item':call()}
    result=await bridge.handle_event(event)
    assert json.loads(result['output'])['data']['status']=='COMPLETED'

@pytest.mark.parametrize('arguments',['{"value":','null','[]','{"value":"2"}','{"value":2,"permissions":["all"]}','{"value":NaN}'])
async def test_invalid_responses_arguments(factory,principal,arguments):
    bridge=ResponsesAdapter(factory(),principal,scope_id='s')
    result=await bridge.handle_call(dict(call(),arguments=arguments))
    assert json.loads(result['output'])['ok'] is False

async def test_no_model_approval_tool(factory,principal):
    bridge=ResponsesAdapter(factory(),principal,scope_id='s')
    assert all('resume' not in t['name'] and 'approve' not in t['name'] for t in bridge.tools())
    result=await bridge.handle_call(dict(call(),name='harness_resume_run'))
    assert json.loads(result['output'])['error']['code']=='UNKNOWN_OPERATION'

async def test_incomplete_call_rejected(factory,principal):
    bridge=ResponsesAdapter(factory(),principal,scope_id='s')
    with pytest.raises(HarnessError): await bridge.handle_call(call(status='in_progress'))

async def test_multi_output_response(factory,principal):
    bridge=ResponsesAdapter(factory(),principal,scope_id='s')
    response={'output':[{'type':'reasoning','id':'r'},call(),dict(call(),call_id='call_2',arguments='{"value":8}')]}
    results=await bridge.handle_response(response)
    assert [r['call_id'] for r in results]==['call_1','call_2']
    assert json.loads(results[1]['output'])['data']['result']['first']['value']==9

async def test_dify_openapi_and_dispatch(factory,principal):
    runtime=factory(); adapter=DifyAdapter(runtime)
    schema=adapter.openapi('https://harness.example.test')
    op=schema['paths']['/adapters/dify/harness_run_work']['post']
    assert op['operationId']=='harness_run_work'
    assert op['requestBody']['content']['application/json']['schema']['properties']['value']['type']=='integer'
    assert op['security']==[{'HarnessBearer':[]}]
    result=await adapter.invoke('harness_run_work',{'value':5},principal,idempotency_key='dify-request-1')
    assert result['status']=='COMPLETED' and result['result']['first']['value']==6

@pytest.mark.parametrize('url',['http://remote.example','https://user:pass@example.com','https://example.com/?token=s','file:///tmp/run'])
async def test_dify_server_url_boundary(factory,url):
    with pytest.raises(HarnessError): DifyAdapter(factory()).openapi(url)

async def test_http_auth_contract_sse_and_validation(factory,principal):
    runtime=factory(); auth=TokenAuth({TOKEN:principal})
    app=create_app(runtime,auth)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/tools')).status_code==401
        headers={'Authorization':'Bearer '+TOKEN}
        created=await client.post('/runs',json=request(),headers=headers)
        assert created.status_code==202
        run_id=created.json()['run_id']; await runtime.wait(run_id,principal)
        final=await client.get('/runs/'+run_id,headers=headers)
        assert final.json()['status']=='COMPLETED'
        events=await client.get('/runs/'+run_id+'/events',headers=headers)
        assert events.status_code==200 and 'event: run-completed' in events.text and 'id: 1' in events.text
        last=runtime.store.events(run_id)[-1].sequence
        resumed=await client.get('/runs/'+run_id+'/events',headers=dict(headers,**{'Last-Event-ID':str(last-1)}))
        assert resumed.text.count('data: ')==1
        secret='Bearer should-never-appear'
        bad=await client.post('/runs',json=dict(request(),password=secret),headers=headers)
        assert bad.status_code==422 and secret not in bad.text and 'password' not in bad.text
        assert (await client.get('/runs/'+run_id+'/events',headers=dict(headers,**{'Last-Event-ID':'invalid'}))).status_code==422
        assert (await client.get('/adapters/responses/tools',headers=headers)).json()[0]['type']=='function'
        output=await client.post('/adapters/responses/calls',json=call(),headers=dict(headers,**{'X-Harness-Scope':'http-session'}))
        assert output.status_code==200 and output.json()['type']=='function_call_output'
        dify=await client.post('/adapters/dify/harness_run_work',json={'value':6},headers=dict(headers,**{'Idempotency-Key':'dify-http'}))
        assert dify.status_code==200 and dify.json()['result']['first']['value']==7

async def test_http_foreign_identity_and_limits(factory,principal):
    runtime=factory(); other=principal.model_copy(update={'subject':'other'})
    other_token='other-service-token-abcdefghijklmnopqrstuvwxyz'
    app=create_app(runtime,TokenAuth({TOKEN:principal,other_token:other}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        headers={'Authorization':'Bearer '+TOKEN}
        run=(await client.post('/runs',json=request(),headers=headers)).json()
        forbidden=await client.get('/runs/'+run['run_id'],headers={'Authorization':'Bearer '+other_token})
        assert forbidden.status_code==404
        large=await client.post('/runs',content=b'x'*1000001,headers=headers)
        assert large.status_code==413

async def test_http_rate_limit(factory,principal):
    app=create_app(factory(),TokenAuth({TOKEN:principal}),requests_per_minute=1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+TOKEN}) as client:
        assert (await client.get('/tools')).status_code==200
        assert (await client.get('/tools')).status_code==429

async def test_http_human_resume(factory,principal):
    runtime=factory(human=True); run=runtime.create_run(request(),principal)
    paused=await runtime.wait(run['run_id'],principal)
    app=create_app(runtime,TokenAuth({TOKEN:principal}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+TOKEN}) as client:
        response=await client.post('/runs/'+run['run_id']+'/resume',json={'decision':'approve','gate_digest':paused['gate']['digest']})
        assert response.status_code==200
        assert (await runtime.wait(run['run_id'],principal))['status']=='COMPLETED'
