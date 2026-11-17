"""Execute pinned author code with scripted transports; zero inference-provider calls.

These are engineering controls, never paper/native answer quality results.
"""
import json
from pathlib import Path
import pytest
from screenshotlegal.method_reproductions.paper_bridge import execute,benchmark_task
from screenshotlegal.method_reproductions.author_bridge import REPO


async def test_reflexion_original_failure_memory_and_second_trial():
    requests=[]
    async def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        raw='Check the source comparison.' if stage.startswith('reflection.') else 'compare sources' if stage.startswith('label.') else 'Finish[wrong]' if len(requests)==2 else 'Finish[SOURCE_ONLY_ANSWER_4791]'
        return dict(raw=raw)
    result=await execute('reflexion',dict(mode='native',question='Compare the two named sources.',context='Two source descriptions.',answer_key='SOURCE_ONLY_ANSWER_4791',attempts=2),call)
    assert result['output']=='SOURCE_ONLY_ANSWER_4791' and len(requests)==5
    assert result['trials'][0]['feedback'] is False and result['trials'][1]['feedback'] is True
    assert result['trials'][1]['reflection_memory']==['Check the source comparison.']
    assert 'Check the source comparison.' in requests[-1]['messages'][-1]['content']
    assert all('SOURCE_ONLY_ANSWER_4791' not in json.dumps(r['messages']) for r in requests)


async def test_reflexion_product_schema_feedback_has_no_answer_gold():
    requests=[];tools=[]
    messages=[dict(role='system',content='Return JSON with schema {"answer": null, "evidence": []}.'),dict(role='user',content=json.dumps(dict(track='vqa_predicted_text',task_type='vqa.closed',question='What is visible?',upstream_prediction=dict(conversation=[dict(content='hello')]))))]
    async def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        raw='Fix JSON schema.' if stage.startswith('reflection.') else 'check schema' if stage.startswith('label.') else 'Finish[invalid]' if len(requests)==2 else 'Finish[{"answer":null,"evidence":[]}]'
        return dict(raw=raw)
    async def tool(action,result):tools.append(dict(action=action,result=result))
    result=await benchmark_task('reflexion',messages,call,2,tool)
    assert result['output']==dict(answer=None,evidence=[]) and len(requests)==5
    assert tools[0]['result']['validation']['valid'] is False and tools[-1]['result']['validation']['valid'] is True
    assert all(t['result']['validation']['factual_accuracy'] is None for t in tools)


async def test_solar_runs_original_stategraph_with_scripted_extraction():
    requests=[]
    abox=dict(individuals=[dict(object=dict(name='Alice',class_name='Taxpayer'),confidence=1,explanation='Named in input')],
      assertions=[dict(object=dict(property_name=p,arguments=a),confidence=1,explanation='Fixture from SARA tax_case_33') for p,a in [
          ('isEmployer',['Alice']),('hasTotalWagesPaid',['Alice','453009']),('hasTaxableIncomeAmount',['Alice','0'])]])
    async def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        return dict(raw=json.dumps(dict(abox=abox) if stage=='extract_abox' else dict(query=dict(taxpayer_id='Alice',year=2015))))
    result=await execute('solar',dict(mode='native',description='Alice paid each of her 87 employees $5207 for work done in 2015. Alice had no income.',question='How much tax does Alice have to pay in 2015?'),call)
    assert result['output']['answer']==pytest.approx(27180.54)
    assert [r['stage'] for r in requests]==['extract_abox','identify_taxpayer']
    assert result['stage_i_generated_here'] is False


async def test_agentscourt_uses_original_roleplaying_loop_and_original_case_fields():
    requests=[]
    case=json.loads((REPO/'paper/upstream_sources/agentscourt/data/SimuCourt(1).json').read_text(encoding='utf-8'))[0]
    async def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        raw='[原告控诉]：按原材料陈述。' if len(requests)%2==0 else '[被告辩解]：保留争议。'
        return dict(raw=raw,usage=None)
    result=await execute('agentscourt',dict(case=case,turns=2),call)
    assert len(requests)==5 and len(result['output'])==4
    assert result['output'][0].startswith('[原告控诉]')
    assert case['基本案情'] in json.dumps(requests,ensure_ascii=False)
    assert result['full_legal_kb_judgment_pipeline_completed'] is False


async def test_lightrag_executes_original_graph_extraction_and_hybrid_query():
    requests=[];tools=[]
    async def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        raw=(json.dumps(dict(high_level_keywords=['materials'],low_level_keywords=['FROZEN SOURCE'])) if stage.startswith('keywords.') else
             '("entity"<|>"FROZEN SOURCE"<|>"CONCEPT"<|>"Offline transport source")##("entity"<|>"MATERIAL"<|>"CONCEPT"<|>"Offline input")##("relationship"<|>"FROZEN SOURCE"<|>"MATERIAL"<|>"Offline transport link"<|>"materials"<|>1)<|COMPLETE|>' if stage.startswith('index.') else '{"answer":null,"evidence":[]}')
        return dict(raw=raw)
    async def tool(action,result):tools.append(dict(action=action,result=result))
    result=await execute('lightrag',dict(mode='product',documents=[dict(id='frozen:a',text='The frozen source contains materials.')],question='What materials?',instruction='Return JSON with answer and evidence.'),call,tool)
    assert result['output']==dict(answer=None,evidence=[]) and len(requests)==4
    assert len(result['graph']['nodes'])==2 and len(result['graph']['edges'])==1
    assert list(result['graph']['chunk_source_ids'].values())==[['frozen:a']]
    assert any(r['stage'].startswith('keywords.') for r in requests)


async def test_raptor_runs_original_leaf_retrieval_with_frozen_source_ids():
    requests=[];tools=[]
    async def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        return dict(raw='{"answer":"visible","evidence":["frozen:a"]}')
    async def tool(action,result):tools.append(result)
    result=await execute('raptor',dict(mode='product',documents=[dict(id='frozen:a',text='A visible material is present.')],question='What is visible?',instruction='Return JSON.'),call,tool)
    assert result['output']['answer']=='visible' and len(requests)==1
    assert result['tree']['layers']=={'0':1}
    assert result['tree']['original_leaf_evidence'][0]['source_id']=='frozen:a'
    assert result['tree']['selected'][0]['layer_number']==0
    # A one-leaf case doesn't exercise recursive clustering; the real Cinderella run does.
