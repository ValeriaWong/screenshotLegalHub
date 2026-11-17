"""Independent Algorithm 1 control-flow checks; no supplier calls/local weights."""
import importlib.util,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'paper/author_reproductions/jurisma'
spec=importlib.util.spec_from_file_location('jurisma_algorithm_test',HERE/'algorithm.py')
algo=importlib.util.module_from_spec(spec);spec.loader.exec_module(algo)
GRAPH={k:[] for k in ['entities','events','user_claims','key_facts','legal_questions','relationships']}
SOURCE=dict(id='statute-a',title='Historical rule',text='exact full article',version_scope='historical')

@pytest.mark.parametrize('stop',['Pass',[]])
def test_pass_and_empty_always_run_content_check(stop):
    seen=[]
    def generate(stage,messages,params):
        seen.append(stage)
        return json.dumps(GRAPH) if stage=='element_graph' else 'draft' if stage=='initial_draft' else json.dumps(dict(actions=stop)) if stage.startswith('manager.') else json.dumps(dict(response='answer',legal_basis=[],uncertainties=[]))
    result=algo.run(dict(question='query'),generate)
    assert seen==['element_graph','initial_draft','manager.0','content_check']
    assert result['calls']==4 and not result['training_reproduced']

def test_both_actions_use_revised_draft_then_actual_source_read_in_paper_order():
    seen=[];events=[]
    def generate(stage,messages,params):
        payload=json.loads(messages[-1]['content']);seen.append((stage,payload))
        if stage=='element_graph':return json.dumps(GRAPH)
        if stage=='initial_draft':return 'initial'
        if stage=='manager.0':return json.dumps(dict(actions=['LawSearch','FormatCheck']))
        if stage=='format_suggestions.0':return 'restructure'
        if stage=='apply_suggestions.0':return 'formatted'
        if stage=='law_search.0':
            assert payload['draft']=='formatted'
            assert 'text' not in payload['catalog'][0]
            return json.dumps(dict(source_ids=['statute-a']))
        if stage=='integrate_statutes.0':
            assert payload['statutes']==[SOURCE]
            return 'grounded'
        if stage=='manager.1':
            assert payload['draft']=='grounded'
            return json.dumps(dict(actions='Pass'))
        assert stage=='content_check' and payload['revised_draft']=='grounded'
        return json.dumps(dict(response='answer',legal_basis=[dict(source_id='statute-a',article_text=SOURCE['text'])],uncertainties=[]))
    result=algo.run(dict(question='query',statutes=[SOURCE]),generate,lambda a,r:events.append((a,r)))
    assert [s for s,p in seen]==['element_graph','initial_draft','manager.0','format_suggestions.0','apply_suggestions.0','law_search.0','integrate_statutes.0','manager.1','content_check']
    assert result['retrieved_statutes']==[SOURCE]
    assert next(r for a,r in events if a=='jurisma.statute_read')['draft_received']=='formatted'

def test_five_round_limit_and_content_always_match_maximum_28_calls():
    seen=[]
    def generate(stage,messages,params):
        seen.append(stage)
        if stage=='element_graph':return json.dumps(GRAPH)
        if stage.startswith('manager.'):return json.dumps(dict(actions=['FormatCheck','LawSearch']))
        if stage.startswith('law_search.'):return json.dumps(dict(source_ids=[]))
        if stage=='content_check':return json.dumps(dict(response='done',legal_basis=[],uncertainties=['no law found']))
        return 'draft'
    result=algo.run(dict(question='query'),generate)
    assert result['calls']==28 and result['stop_reason']=='iteration_limit'
    assert len(result['iterations'])==5 and 'manager.5' not in seen and seen[-1]=='content_check'

@pytest.mark.parametrize('selection',[['missing'],['statute-a','statute-a']])
def test_fake_or_duplicate_statutes_stop_before_integration(selection):
    seen=[]
    def generate(stage,messages,params):
        seen.append(stage)
        return json.dumps(GRAPH) if stage=='element_graph' else 'draft' if stage=='initial_draft' else json.dumps(dict(actions=['LawSearch'])) if stage=='manager.0' else json.dumps(dict(source_ids=selection))
    with pytest.raises(ValueError,match='source ID'):algo.run(dict(question='q',statutes=[SOURCE]),generate)
    assert seen[-1]=='law_search.0'

def test_final_cannot_invent_unretrieved_statutory_text():
    def generate(stage,messages,params):
        if stage=='element_graph':return json.dumps(GRAPH)
        if stage=='initial_draft':return 'draft'
        if stage=='manager.0':return json.dumps(dict(actions='Pass'))
        return json.dumps(dict(response='answer',legal_basis=[dict(source_id='statute-a',article_text=SOURCE['text'])],uncertainties=[]))
    with pytest.raises(ValueError,match='actually retrieved'):algo.run(dict(question='q',statutes=[SOURCE]),generate)

def test_code_fence_json_and_call_cap():
    fence=chr(96)*3
    assert algo.parse_json(fence+'json\n{"actions":[]}\n'+fence)==dict(actions=[])
    def generate(stage,messages,params):return json.dumps(GRAPH)
    with pytest.raises(ValueError,match='budget'):algo.run(dict(question='q',max_calls=1),generate)

@pytest.mark.asyncio
async def test_e18_case_dispatch_uses_real_independent_algorithm_and_projection():
    from screenshotlegal.method_reproductions import run_method
    from screenshotlegal.method_reproductions.jurisma_bridge import demo_reply
    from screenshotlegal.experiments.engine import SYSTEM_POLICY,validate_output
    source=dict(id='s',text='甲：我否认收款。')
    frozen=dict(goal='区分陈述和未知',case_title='test',sources=[source],legal_corpus=[],matterpack={})
    from screenshotlegal.experiments.engine import visible_input
    output=dict(summary='仅记录否认',facts=[dict(id='f',statement='甲否认收款',citations=[dict(source_ref_id='s',quote=source['text'],start=0,end=len(source['text']))])])
    seen=[];artifacts=[]
    async def raw(stage,messages,params):
        seen.append(stage);return dict(raw=demo_reply(stage,output),demo=True)
    async def forbidden(*a):raise AssertionError('old generic path must not execute')
    async def record(name,result):artifacts.append(result)
    result=await run_method('E18',visible_input(frozen,'E18'),[source],forbidden,forbidden,SYSTEM_POLICY,lambda:{},dict(max_model_calls=29),raw_call=raw,author_record=record)
    assert validate_output(result,frozen)['facts'][0]['statement']=='甲否认收款'
    assert seen==['element_graph','initial_draft','manager.0','content_check','product_projection']
    assert artifacts[0]['native_output']['legal_basis']==[]
    assert artifacts[0]['projection_is_product_adaptation'] and not artifacts[0]['training_reproduced']

@pytest.mark.asyncio
async def test_pixel_input_rejected_before_supplier_call():
    from screenshotlegal.method_reproductions.e18_jurisma import run_task
    async def forbidden(*a):raise AssertionError('no paid calls')
    with pytest.raises(ValueError,match='text-only'):
        await run_task([dict(role='user',content=[dict(type='image_url')])],forbidden)

def test_e18_benchmark_plan_discloses_inference_only():
    from screenshotlegal.research.benchmark_methods import specification
    result=specification('E18')
    assert result['calls_per_task']==29 and not result['author_code_executed'] and not result['native_full_method_completed']

@pytest.mark.parametrize('budget,expected',[(29,29),(40,29),(10,10)])
def test_case_ceiling_and_public_label_follow_new_controller(budget,expected):
    from screenshotlegal.experiments.registry import CandidateRegistry,call_ceiling
    assert call_ceiling('E18',dict(max_model_calls=budget),dict(retrieval_rounds=0),[])==expected
    method=next(m for m in CandidateRegistry().public()['candidates'] if m['id']=='E18')
    assert method['reproduction']=='paper_algorithm_inference_adaptation'
    assert 'DPO' in method['paper_claim'] and method['implementation_status']=='implemented'
