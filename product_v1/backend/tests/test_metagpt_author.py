"""Run author MetaGPT software SOP with a scripted API; no supplier/local-model inference."""
import ast,json
import pytest
from test_accounts_ingestion import accounts
from screenshotlegal.method_reproductions.paper_bridge import execute


def scripted(stage):
    if stage.startswith('WritePRD.'):
        value={'Original Requirements':'Write a cli snake game','Product Goals':['cli snake'],'User Stories':['Play in terminal'],
            'Competitive Analysis':['terminal snake'],'Competitive Quadrant Chart':'quadrantChart\n A: [0.5,0.5]',
            'Requirement Analysis':'One small program','Requirement Pool':[['P0','snake movement']],'UI Design draft':'text','Anything UNCLEAR':'none'}
    elif stage.startswith('WriteDesign.'):
        value={'Implementation approach':'standard library','Python package name':'snake_fixture','File list':['main.py'],
            'Data structures and interface definitions':'classDiagram\n class Snake','Program call flow':'sequenceDiagram\n Main->>Snake: step','Anything UNCLEAR':'none'}
    elif stage.startswith('WriteTasks.'):
        value={'Required Python third-party packages':[],'Required Other language third-party packages':[],'Full API spec':'none',
            'Logic Analysis':[['main.py','step']],'Task list':['main.py'],'Shared Knowledge':'position tuple','Anything UNCLEAR':'none'}
    elif stage.startswith('WriteCodeReview.'):
        return '## Code Review\n1. Keep the function.\n## Rewrite Code: main.py\n```python\ndef step(position, direction):\n    return tuple(a+b for a,b in zip(position, direction))\n```'
    elif stage.startswith('WriteCode.'):
        return '```python\ndef step(position, direction):\n    return tuple(a+b for a,b in zip(position, direction))\n```'
    else:return '0'
    return '[CONTENT]'+json.dumps(value)+'[/CONTENT]'


async def test_original_metagpt_team_runs_all_software_roles_and_review(tmp_path):
    requests=[];events=[]
    async def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        return dict(raw=scripted(stage))
    async def tool(action,result):events.append(dict(action=action,result=result))
    result=await execute('metagpt',dict(mode='native',runtime=str(tmp_path/'author-runtime'),idea='Write a cli snake game'),call,tool)
    stages=[r['stage'].split('.')[0] for r in requests]
    assert stages==['WritePRD','WriteDesign','WriteTasks','role','WriteCode','WriteCodeReview']
    assert result['calls']==6 and result['local_model_inference'] is False
    files=result['output']['files']
    assert {'snake_fixture/docs/prd.md','snake_fixture/docs/system_design.md','snake_fixture/docs/api_spec_and_tasks.md','snake_fixture/snake_fixture/main.py'}<=set(files)
    ast.parse(files['snake_fixture/snake_fixture/main.py'])
    published=[e['result'] for e in events if e['action']=='metagpt.published_message']
    assert [r['cause_by'] for r in published][:4]==['BossRequirement','WritePRD','WriteDesign','WriteTasks']
    assert 'Product Goals' in json.dumps(requests[1]['messages'])
    assert 'Data structures and interface definitions' in json.dumps(requests[2]['messages'])
    assert 'snake_fixture' in json.dumps(requests[4]['messages'])
    assert any(e['action']=='metagpt.diagram_source' for e in events)


async def test_author_destructive_output_path_is_checked_before_use(tmp_path):
    async def call(stage,messages,parameters):
        raw=scripted(stage)
        if stage.startswith('WriteDesign.'):raw=raw.replace('snake_fixture','../../outside')
        return dict(raw=raw)
    with pytest.raises(ValueError,match='delete path escapes'):
        await execute('metagpt',dict(mode='native',runtime=str(tmp_path/'author-runtime'),idea='Write a cli snake game'),call)
    assert not (tmp_path/'outside').exists()


async def test_metagpt_case_product_uses_author_subscriptions_and_literal_feedback():
    from screenshotlegal.method_reproductions import run_method
    from screenshotlegal.experiments.engine import demo_analysis,SYSTEM_POLICY,validate_output
    from screenshotlegal.experiments.inputs import citation_units
    source=dict(id='s1',text='甲说已付款，乙说未核实。',citation_units=citation_units('甲说已付款，乙说未核实。'))
    visible=dict(goal='核对陈述',sources=[source],legal_corpus=[],matterpack={})
    output=dict(elements=[],**demo_analysis(dict(sources=[source])));requests=[];artifacts=[]
    async def raw(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        value=dict(analysis=output,issues=['机械校验不是法律准确率']) if stage.startswith('ReviewEvidence.') else output
        return dict(raw='[CONTENT]'+json.dumps(value,ensure_ascii=False)+'[/CONTENT]')
    async def record(name,result):artifacts.append(result)
    async def generic(*args):raise AssertionError('MetaGPT must use author Team/Role rather than staged baseline')
    result=await run_method('E22',visible,[source],generic,generic,SYSTEM_POLICY,lambda:output,{},raw_call=raw,author_record=record)
    validate_output(result,dict(sources=[source]))
    assert [r['stage'].split('.')[0] for r in requests]==['ExtractEvidence','MapLegalElements','ReviewEvidence','FinalizeCounsel']
    assert len(artifacts)==1 and len(artifacts[0]['messages'])==5
    assert [r['watch'] for r in artifacts[0]['subscriptions']]==[['BossRequirement'],['ExtractEvidence'],['MapLegalElements'],['ReviewEvidence']]
    validation=next(t for t in artifacts[0]['tools'] if t['action']=='metagpt.validate_case_output')
    assert validation['result']['valid'] is True and validation['result']['legal_accuracy'] is None
    assert 'schema_and_literal_citations_only' in json.dumps(requests[2]['messages'])
    assert '本阶段仅遵循下列输出Schema' in requests[2]['messages'][-1]['content']
    assert '"required": ["analysis", "issues"]' in requests[2]['messages'][-1]['content']
    assert '最终输出必须符合此JSON Schema' not in requests[0]['messages'][-1]['content']
    assert artifacts[0]['original_complete_benchmark'] is False and artifacts[0]['local_model_inference'] is False


async def test_metagpt_invalid_structured_reply_does_not_retry(tmp_path):
    requests=[]
    async def invalid(stage,messages,parameters):
        requests.append(stage)
        return dict(raw='invalid json')
    with pytest.raises(ValueError):
        await execute('metagpt',dict(mode='native',runtime=str(tmp_path/'run'),idea='Write a cli snake game'),invalid)
    assert len(requests)==1


def test_metagpt_http_case_exports_author_sop(accounts):
    import time
    from test_agent_experiments import create_case,payload
    _,_,client,_=accounts
    cid,doc=create_case(client,'甲称已经付款，乙称尚待核对。')
    client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending'))
    response=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,method_ids=['E22'],allow_draft_matter=True))
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0]
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        value=client.get('/v1/evaluation/agent-runs/'+rid).json()
        if value['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert value['run']['status']=='completed',value['run'].get('error')
    assert value['run']['scoring_status']=='unscored_demo'
    assert value['reproduction_name']=='e22_metagpt'
    execution=value['author_artifacts'][0]['execution']
    assert len(execution['subscriptions'])==4 and len(execution['messages'])==5
    assert execution['local_model_inference'] is False
    assert 'GOLD_HIDDEN_NOT_INPUT' not in json.dumps(value,ensure_ascii=False)
    export=client.get('/v1/evaluation/agent-runs/'+rid+'/export')
    assert export.status_code==200 and 'e22_metagpt.' in export.headers['content-disposition']
