"""Run real pinned author control flow using deterministic transport, no paid calls."""
import importlib.util,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'paper/author_reproductions/legalagentbench'))
import product_adapter as adapter
import pytest

@pytest.mark.parametrize('variant',['react','plan_and_solve','plan_and_execute'])
def test_author_native_exact_observation_control_flow(variant):
    fixture=json.loads((adapter.HERE/'native_inputs/author_log_first_task.json').read_text(encoding='utf-8'))
    seen=[];events=[];actions=0
    def generate(stage,messages,parameters):
        nonlocal actions
        seen.append((stage,messages));text=messages[-1]['content']
        if '.tables.' in stage:return '{"名称":["CompanyInfo"]}'
        if '.filter_answer.' in stage:return '688106，金向华，陈莹'
        if '.summarize_process.' in stage:return '检索公司信息后得到688106、金向华、陈莹'
        if '请根据情况更新计划' in text or '请不要实际执行计划' in text:
            return '计划:第1步: 查询公司信息 第2步: 根据上述步骤, 请回答用户的原始问题 计划结束'
        if variant=='react' and text.rstrip().endswith('思考 '+str(actions+1)+':'):return '核对工具所需字段。'
        actions+=1
        value=dict(action='get_company_info',action_input=fixture['observations'][0]['input']) if actions==1 else dict(action='Final Answer',action_input='688106，金向华，陈莹')
        return '```json'+json.dumps(value,ensure_ascii=False)+'```'
    result=adapter.run(dict(mode='native_replay',variant=variant,question=fixture['question'],max_calls=26),generate,lambda *a:events.append(a))
    assert result['controller_finished'] and result['author_controller_executed']
    assert result['observations'][0]['response']==fixture['observations'][0]['response']
    assert result['tool_mode']=='author_log_exact_replay' and not result['original_live_corpora_available']
    assert len(result['observations'])==1 and len(events)==1
    assert result['output']=='688106，金向华，陈莹'
    assert '688106' not in json.dumps(seen[0],ensure_ascii=False)


def test_unknown_tool_request_is_not_filled_from_ground_truth():
    fixture=json.loads((adapter.HERE/'native_inputs/author_log_first_task.json').read_text(encoding='utf-8'))
    calls=[]
    def generate(stage,messages,parameters):
        calls.append(stage)
        if '.tables.' in stage:return '{"名称":["CompanyInfo"]}'
        if '.filter_answer.' in stage or '.summarize_process.' in stage:return '未知'
        if len(calls)==2:return '检查原工具。'
        if len(calls)==3:return '```json{"action":"get_company_info","action_input":{"identifier":"不存在的公司","columns":["公司代码"]}}```'
        if len(calls)==4:return '工具不可用，保留未知。'
        return '```json{"action":"Final Answer","action_input":"未知"}```'
    result=adapter.run(dict(mode='native_replay',variant='react',question=fixture['question']),generate,lambda *a:None)
    assert result['observations'][0]['mode']=='unavailable_exact_request'
    assert result['output']=='未知' and '688106' not in result['scratchpad']


def test_eval_fallback_never_executes_model_python(tmp_path):
    ns,_=adapter.originals();marker=tmp_path/'should_not_exist'
    payload="x```pythonopen("+repr(str(marker))+",'w').write('bad')```"
    assert ns['parse_action'](payload)==('','') and not marker.exists()


def test_original_parameter_bug_is_exposed_and_transport_can_supply_name():
    ns,_=adapter.originals()
    with pytest.raises(TypeError):ns['format_input']({'identifier':'x'})
    assert ns['format_input']('get_sum',[1,2])=={'identifier':[1,2]}


def test_product_tool_uses_only_frozen_text_and_structured_final_answer():
    calls=0;events=[]
    def generate(stage,messages,parameters):
        nonlocal calls
        calls+=1
        if calls%2:return '核对冻结证据。'
        if calls==2:value=dict(action='read_evidence',action_input=dict(identifier='s1'))
        else:value=dict(action='Final Answer',action_input=dict(answer='private_chat',evidence=['s1']))
        return '```json'+json.dumps(value)+'```'
    result=adapter.run(dict(mode='product',variant='react',question='请用answer/evidence返回JSON',documents=[dict(id='s1',text='只有两人对话')]),generate,lambda *a:events.append(a))
    assert result['output']['answer']=='private_chat'
    assert events[0][1]['response']==dict(id='s1',text='只有两人对话')
    assert result['tool_mode']=='frozen_product_text'


def test_per_unit_cap_stops_before_next_generation():
    fixture=json.loads((adapter.HERE/'native_inputs/author_log_first_task.json').read_text(encoding='utf-8'));calls=[]
    def generate(*args):calls.append(args);return '{"名称":["CompanyInfo"]}'
    with pytest.raises(adapter.UnitBudgetExceeded):
        adapter.run(dict(mode='native_replay',variant='react',question=fixture['question'],max_calls=1),generate,lambda *a:None)
    assert len(calls)==1

def test_original_metric_retains_literal_substring_semantics():
    from original_score import score
    result=score('688106','688106/金向华',dict(key=['688106','金向华','陈莹'],key_middle=['查询公司']))
    assert result['metrics']['key_answer']['score']==1/3
    assert result['metrics']['key_middle']['score']==.5

async def test_isolated_process_final_event_envelope_is_consumable():
    from screenshotlegal.method_reproductions.paper_bridge import execute
    count=0
    async def transport(stage,messages,parameters):
        nonlocal count
        count+=1
        if count%2:return dict(raw='核对来源。')
        if count==2:value=dict(action='read_evidence',action_input=dict(identifier='s1'))
        else:value=dict(action='Final Answer',action_input=dict(answer='private_chat',evidence=['s1']))
        return dict(raw='```json'+json.dumps(value)+'```')
    result=await execute('legalagentbench',dict(mode='product',variant='react',question='返回answer/evidence',documents=[dict(id='s1',text='两人对话')]),transport)
    assert result['controller_finished'] and result['output']['answer']=='private_chat'
    assert count==4


@pytest.mark.parametrize('variant',['react','plan_and_solve','plan_and_execute'])
async def test_product_contract_reaches_every_original_solve_step(variant):
    from screenshotlegal.method_reproductions.legalagentbench_bridge import benchmark_task
    actions=0;seen=[]
    async def transport(stage,messages,parameters):
        nonlocal actions
        seen.append(messages)
        assert '恰含answer和evidence两个键' in messages[0]['content']
        text=messages[-1]['content']
        if '请不要实际执行计划' in text or '请根据情况更新计划' in text:
            return dict(raw='第1步: 列出证据 第2步: 读取证据 第3步: 根据上述步骤, 请回答用户的原始问题 计划结束')
        if re.search(r'思考 \d+:\s*$',text):return dict(raw='核对公开来源。')
        actions+=1
        if actions==1:value=dict(action='list_evidence',action_input={})
        elif actions==2:value=dict(action='read_evidence',action_input=dict(identifier='kie:fixed'))
        else:value=dict(action='Final Answer',action_input=dict(answer=None,evidence=['kie:fixed']))
        return dict(raw='```json'+json.dumps(value)+'```')
    task=dict(track='vqa_predicted_text',upstream_prediction=dict(conversation=[dict(content='未提供聊天类型')]),upstream_sha256='fixed',question='群聊还是私聊',allowed_values=['group_chat','private_chat'])
    result=await benchmark_task([dict(role='user',content=json.dumps(task))],transport,variant=variant)
    assert result['output']==dict(answer=None,evidence=['kie:fixed'])
    assert [o['action'] for o in result['observations']]==['list_evidence','read_evidence']
    assert len(seen)>=4


@pytest.mark.parametrize('variant',['react','plan_and_solve','plan_and_execute'])
async def test_benchmark_variant_freeze_reaches_author_controller_and_records_tools(lab,variant):
    from test_benchmark_pipeline import setup
    from test_benchmark_migration import prompt
    from test_research_products import drain
    from screenshotlegal.method_reproductions.legalagentbench_bridge import demo_reply
    pipeline,p,_,benchmark=setup(lab);row=pipeline.create('alice',p);await drain(lab)
    upstream=next(a for a in lab.store.list('benchmark.attempt','alice') if a.get('pipeline_id')==row['id'] and a['task_family']=='kie.extract')
    frozen=benchmark.freeze_task('alice',p['dataset_id'],'global','vqa_predicted_text',upstream_id=upstream['id'])
    sid='kie:'+frozen['input']['upstream_sha256'];observed=[]
    async def transport(owner,model,messages,purpose,request_id):
        observed.append(dict(model=model,messages=messages))
        raw=demo_reply(request_id.rsplit(':',1)[1],dict(answer='is_evidence',evidence=[sid]),sid)
        return dict(raw=raw,usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),latency_ms=1,cost_estimate=0,cost_currency='CNY',demo=False)
    lab.gateway._call=transport
    vp=prompt(benchmark,'vqa');payload=dict(dataset_id=p['dataset_id'],name='LAB '+variant,task_ids=['global'],track='vqa_predicted_text',mode='development_reference',release_id=None,model_id='local-fixture',prompt_id=vp['id'],method_id='E23',method_variant=variant,method_attempts=2,method_max_output_tokens=6144,max_calls=26,iou_threshold=.6,upstream_attempt_id=upstream['id'],idempotency_key='lab-'+variant)
    run=benchmark.create_run('alice',payload);await drain(lab);result=benchmark.results('alice',run['id'])
    assert result['run']['status']=='completed',result['attempts']
    assert result['run']['method']['variant']==variant
    assert result['attempts'][0]['parsed']['answer']=='is_evidence'
    assert len(result['method_tools'])==2
    assert all(r['model']['parameters']['temperature']==0 and r['model']['parameters']['max_tokens']==2000 for r in observed)
    execution=result['attempts'][0]['response']['author_execution']
    assert execution['variant']==variant and execution['author_controller_executed']
    assert 'LEGACY_PRIVATE_ANSWER' not in json.dumps(observed)

@pytest.mark.parametrize('variant',['react','plan_and_solve','plan_and_execute'])
def test_case_http_dispatch_exports_original_controller_and_counts_tools(accounts,variant):
    import time
    from test_agent_experiments import create_case,payload
    _,_,client,_=accounts;cid,doc=create_case(client,'甲称已付款，乙称待核对。')
    p=payload(cid,doc,method_ids=['E23']);p['method_options']=dict(legalagentbench_variant=variant)
    response=client.post('/v1/evaluation/agent-runs',json=p)
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0];deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        result=client.get('/v1/evaluation/agent-runs/'+rid).json()
        if result['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert result['run']['status']=='completed',result['run'].get('error')
    assert result['run']['usage']['tool_calls']==2 and len(result['tools'])==2
    assert result['author_artifacts'][0]['execution']['variant']==variant
    assert client.get('/v1/evaluation/agent-runs/'+rid+'/export').status_code==200

from test_accounts_ingestion import accounts
from test_research_products import lab


def test_product_valid_bare_action_json_is_losslessly_wrapped():
    count=0
    def generate(stage,messages,parameters):
        nonlocal count
        count+=1
        if count%2:return '核对证据。'
        value=dict(action='read_evidence',action_input=dict(identifier='s1')) if count==2 else dict(action='Final Answer',action_input=dict(answer=None,evidence=['s1']))
        return json.dumps(value,ensure_ascii=False)
    result=adapter.run(dict(mode='product',variant='react',question='核对',documents=[dict(id='s1',text='甲称已付款')]),generate,lambda *a:None)
    assert result['output']==dict(answer=None,evidence=['s1'])
    assert len(result['transport_normalizations'])==2
    assert all(not n['semantic_content_changed'] for n in result['transport_normalizations'])


def test_case_tool_budget_blocks_author_observation_before_next_model_step(accounts):
    import time
    from test_agent_experiments import create_case,payload
    _,_,client,_=accounts;cid,doc=create_case(client,'甲称已付款。')
    p=payload(cid,doc,method_ids=['E23']);p['budget']=dict(max_tool_calls=0)
    response=client.post('/v1/evaluation/agent-runs',json=p)
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0];deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        result=client.get('/v1/evaluation/agent-runs/'+rid).json()
        if result['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert result['run']['status']=='failed'
    assert result['run']['usage']['model_calls']==2
    assert result['tools']==[] and result['author_artifacts']==[]
