"""Protocol/fault tests; this server is not represented as a real model evaluation."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import httpx
import pytest
from agentic.model import ModelConfig, ResponsesReasoner, strict_schema, stage_prompt
from agentic.builtin.contracts import Reasoning
from agentic.examples.report import create_runtime, demo_case
from agentic.contracts import HarnessError

SECRET = 'test-credential-never-persist-12345'

def config(**overrides):
    return ModelConfig(url='http://127.0.0.1:9999/v1/responses',model='contract-test-model',api_key=SECRET,
                       allow_egress=True,input_price_per_million=1,output_price_per_million=2,**overrides)

def answer(body):
    payload=json.loads(body['input'][0]['content'][0]['text'])['data']
    source=payload['case']['sources'][0]
    return {'focus':['alternatives'],'findings':[{'text':'需结合完整语境验证该文本所述内容。','kind':'inference',
        'citations':[{'source_id':source['source_id'],'quote':source['text']}], 'uncertainty':'引用可追溯并不代表现实事实已核验。'}],
        'questions':['材料是否完整？'],'gap_proposals':[]}

def envelope(reasoning):
    return {'id':'resp_contract','status':'completed','usage':{'input_tokens':41,'output_tokens':19},
            'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps(reasoning)}]}]}

async def execute(tmp_path, handler, *, cfg=None, budget=None):
    model=ResponsesReasoner(cfg or config(),transport=httpx.MockTransport(handler))
    runtime,principal=create_runtime(tmp_path,model)
    limits=runtime.limits.model_dump()
    if budget: limits.update(budget)
    run=runtime.create_run(dict(workflow='evidence_analysis',input=demo_case(),idempotency_key='model',limits=limits),principal)
    result=await runtime.wait(run['run_id'],principal)
    events=[e.model_dump(mode='json') for e in runtime.store.events(run['run_id'])]
    persisted=runtime.store.get(run['run_id']).model_dump(mode='json')
    await runtime.close()
    return result,events,persisted

async def test_each_stage_uses_own_prompt_and_counts_actual_usage(tmp_path):
    bodies=[]
    def handler(request):
        assert request.headers['Authorization']=='Bearer '+SECRET
        body=json.loads(request.content); bodies.append(body)
        return httpx.Response(200,json=envelope(answer(body)))
    final,events,persisted=await execute(tmp_path,handler)
    assert final['status']=='COMPLETED'
    assert final['usage']['model_calls']==5 and final['usage']['tokens']==300
    assert final['usage']['unsettled_model_calls']==0
    assert final['usage']['cost']==pytest.approx(0.000395)
    assert final['usage']['tool_calls']==10
    stages=['planning','facts','assessment','gaps','synthesis']
    for stage,body in zip(stages,bodies):
        assert body['instructions']==stage_prompt(stage)
        assert body['store'] is False and body['text']['format']['strict'] is True
    assert all(s['mode']=='model' for s in final['result']['synthesis']['stages'])
    assert SECRET not in json.dumps([persisted,events])
    assert len([e for e in events if e['type']=='model-completed'])==5

async def test_invalid_citation_repaired_with_feedback(tmp_path):
    bodies=[]
    def handler(request):
        body=json.loads(request.content); bodies.append(body); reasoning=answer(body)
        if len(bodies)==1: reasoning['findings'][0]['citations'][0]['source_id']='foreign'
        return httpx.Response(200,json=envelope(reasoning))
    final,_,_=await execute(tmp_path,handler)
    assert final['status']=='COMPLETED' and final['tasks']['planning']['repairs']==1
    assert json.loads(bodies[1]['input'][0]['content'][0]['text'])['repair_findings']
    assert final['usage']['model_calls']==6

async def test_persistent_fabricated_quote_stops_after_bound(tmp_path):
    def handler(request):
        reasoning=answer(json.loads(request.content)); reasoning['findings'][0]['citations'][0]['quote']='nonexistent quote'
        return httpx.Response(200,json=envelope(reasoning))
    final,_,_=await execute(tmp_path,handler)
    assert final['status']=='FAILED' and final['error']['code']=='REVIEW_FAILED'
    assert final['usage']['model_calls']==3 and final['tasks']['facts']['status']=='SKIPPED'

async def test_semantic_summary_must_remain_inference(tmp_path):
    def handler(request):
        reasoning=answer(json.loads(request.content)); reasoning['findings'][0]['kind']='observation'
        return httpx.Response(200,json=envelope(reasoning))
    final,_,_=await execute(tmp_path,handler)
    assert final['status']=='FAILED' and final['error']['code']=='REVIEW_FAILED'

@pytest.mark.parametrize('fault,code',[
    ('refusal','MODEL_REFUSED'),('incomplete','MODEL_INCOMPLETE'),('malformed','INVALID_MODEL_RESPONSE'),
    ('missing_usage','INVALID_MODEL_RESPONSE'),('bad_usage','INVALID_MODEL_USAGE'),('http','MODEL_HTTP_ERROR'),
    ('function_call','INVALID_MODEL_RESPONSE'),('too_large','MODEL_RESPONSE_TOO_LARGE'),('timeout','MODEL_TIMEOUT')])
async def test_provider_failures_are_explicit(tmp_path,fault,code):
    def handler(request):
        raw=envelope(answer(json.loads(request.content)))
        if fault=='refusal': raw['output'][0]['content']=[{'type':'refusal','refusal':'private provider detail'}]
        if fault=='incomplete': raw['status']='incomplete'
        if fault=='malformed': raw['output'][0]['content'][0]['text']='not json'
        if fault=='missing_usage': raw.pop('usage')
        if fault=='bad_usage': raw['usage']['input_tokens']=-1
        if fault=='http': return httpx.Response(401,text='secret='+SECRET)
        if fault=='function_call': raw['output']=[{'type':'function_call','name':'untrusted_tool'}]
        if fault=='too_large': return httpx.Response(200,content=b'x'*1000001)
        if fault=='timeout': raise httpx.ReadTimeout('secret='+SECRET)
        return httpx.Response(200,json=raw)
    final,events,persisted=await execute(tmp_path,handler)
    assert final['status']=='FAILED' and final['error']['code']==code
    assert final['usage']['model_calls']==1
    assert SECRET not in json.dumps([persisted,events])

async def test_transient_retry_is_bounded_and_charged_conservatively(tmp_path):
    final,_,_=await execute(tmp_path,lambda request:httpx.Response(429,text=SECRET))
    assert final['status']=='FAILED' and final['usage']['model_calls']==2
    assert final['usage']['tokens']>0 and final['usage']['unsettled_model_calls']==2

async def test_no_silent_fallback_after_budget_exhausted(tmp_path):
    final,_,_=await execute(tmp_path,lambda r:httpx.Response(200,json=envelope(answer(json.loads(r.content)))),budget={'max_model_calls':1})
    assert final['status']=='FAILED' and final['error']['code']=='BUDGET_EXHAUSTED'
    assert final['usage']['model_calls']==1

async def test_json_object_capability_is_explicit(tmp_path):
    bodies=[]
    def handler(request):
        body=json.loads(request.content); bodies.append(body)
        return httpx.Response(200,json=envelope(answer(body)))
    final,_,_=await execute(tmp_path,handler,cfg=config(format='json_object'))
    assert final['status']=='COMPLETED'
    assert bodies[0]['text']['format']=={'type':'json_object'}
    assert 'schema:' in bodies[0]['instructions']

async def test_model_cannot_close_external_gaps(tmp_path):
    def handler(request):
        reasoning=answer(json.loads(request.content))
        reasoning['gap_proposals']=[{'title':'身份已由模型推断','action':'请核实','method':'code','citations':reasoning['findings'][0]['citations']}]
        return httpx.Response(200,json=envelope(reasoning))
    final,_,_=await execute(tmp_path,handler)
    gaps={g['gap_id']:g for g in final['result']['synthesis']['gaps']['items']}
    assert gaps['authenticity']['status']=='needs_evidence'
    assert all(g['status']=='candidate' for k,g in gaps.items() if k.startswith('suggested_'))

async def test_cancel_inflight_model_call(tmp_path):
    entered=asyncio.Event()
    async def handler(request):
        entered.set(); await asyncio.sleep(10)
    runtime,principal=create_runtime(tmp_path,ResponsesReasoner(config(),transport=httpx.MockTransport(handler)))
    try:
        created=runtime.create_run(dict(workflow='evidence_analysis',input=demo_case(),idempotency_key='cancel-model',limits=runtime.limits.model_dump()),principal)
        await asyncio.wait_for(entered.wait(),2)
        final=await runtime.cancel_run(created['run_id'],principal)
        assert final['status']=='CANCELLED' and final['usage']['model_calls']==1
        assert final['usage']['tokens']>0
    finally: await runtime.close()

@pytest.mark.parametrize('url',['http://remote.example/v1/responses','https://user:password@example.org/v1/responses',
    'https://example.org/v1/chat/completions','https://example.org/v1/responses?credential=abc'])
def test_unsafe_endpoint_rejected(url):
    values=config().model_dump(); values['api_key']=SECRET; values['url']=url
    with pytest.raises(ValueError): ModelConfig(**values)

def test_configuration_does_not_autodiscover_old_secrets(monkeypatch):
    for name in ['HARNESS_MODEL','HARNESS_RESPONSES_URL','HARNESS_MODEL_API_KEY',
                 'HARNESS_INPUT_PRICE_PER_MILLION','HARNESS_OUTPUT_PRICE_PER_MILLION']:
        monkeypatch.delenv(name,raising=False)
    with pytest.raises(HarnessError,match='model not configured'): ModelConfig.from_env()

def test_strict_schema_requires_every_property():
    def walk(value):
        if isinstance(value,dict):
            if value.get('type')=='object':
                assert value['additionalProperties'] is False
                assert set(value['required'])==set(value['properties'])
            for item in value.values(): walk(item)
        if isinstance(value,list):
            for item in value: walk(item)
    walk(strict_schema(Reasoning))

async def test_actual_loopback_http_responses_transport(tmp_path):
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append((self.path,body))
            payload=json.dumps(envelope(answer(body))).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    values=config().model_dump(); values.update(api_key=SECRET,url='http://127.0.0.1:'+str(server.server_port)+'/v1/responses')
    runtime,principal=create_runtime(tmp_path,ResponsesReasoner(ModelConfig(**values)))
    try:
        created=runtime.create_run(dict(workflow='evidence_analysis',input=demo_case(),idempotency_key='socket-model',limits=runtime.limits.model_dump()),principal)
        final=await runtime.wait(created['run_id'],principal)
        assert final['status']=='COMPLETED' and len(received)==5
        assert all(p=='/v1/responses' for p,_ in received)
    finally:
        await runtime.close(); await asyncio.to_thread(server.shutdown); server.server_close(); thread.join(timeout=2)

async def test_model_planning_focus_drives_later_code_checks(tmp_path):
    def handler(request):
        body=json.loads(request.content)
        return httpx.Response(200,json=envelope(answer(body)))
    model=ResponsesReasoner(config(),transport=httpx.MockTransport(handler))
    runtime,principal=create_runtime(tmp_path,model)
    case=demo_case();case['question']='整理记录';case['sources']=[dict(case['sources'][0],text='普通会议信息。')]
    try:
        created=runtime.create_run(dict(workflow='evidence_analysis',input=case,idempotency_key='focus',limits=runtime.limits.model_dump()),principal)
        final=await runtime.wait(created['run_id'],principal)
        report=final['result']['synthesis']
        assert 'alternatives' in report['plan']['focus']
        assert 'alternatives' in {c['check_id'] for c in report['assessment']['checks']}
    finally: await runtime.close()
