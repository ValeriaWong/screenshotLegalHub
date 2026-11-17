import copy
import json
import pytest
from test_accounts_ingestion import accounts
from test_agent_experiments import create_case,payload,wait_run
from screenshotlegal.experiments.budget import BudgetTracker,BudgetExceeded
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.experiments.engine import demo_analysis,SYSTEM_POLICY
from screenshotlegal.experiments.inputs import SourceReader
from screenshotlegal.research.contracts import digest
from screenshotlegal.research.gateway import ModelFailure
from test_accounts_ingestion import model


def test_reservations_settle_against_actual_not_cumulative_estimates():
    limits=dict(max_input_tokens=1200,max_output_tokens=1000,max_model_calls=3,max_tool_calls=0,max_wall_time_s=10,max_output_per_call=100)
    tracker=BudgetTracker(limits)
    for _ in range(3):
        tracker.reserve([])
        tracker.charge(dict(usage=dict(prompt_tokens=20,completion_tokens=10)))
    assert tracker.usage['input_tokens']==60 and tracker.usage['reserved_input_tokens']==0


def test_failed_response_usage_is_charged_and_not_unknown(accounts,monkeypatch):
    _,_,client,_=accounts;cid,doc=create_case(client);m=model(client)
    async def empty(*args):
        raise ModelFailure('output_limit','empty',evidence=dict(usage=dict(prompt_tokens=12,completion_tokens=99),cost_estimate=.25))
    monkeypatch.setattr(client.app.state.research['agent_experiments'].gateway,'call',empty)
    rid=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,model_id=m['id'])).json()['run_ids'][0]
    result=wait_run(client,rid)
    assert result['run']['usage']['input_tokens']==12
    assert result['run']['usage']['output_tokens']==99
    assert result['run']['usage']['cost']==.25
    assert result['steps'][0]['status']=='failed'
    assert result['steps'][0]['messages']


def test_new_methods_execute_and_preserve_polarity(accounts):
    _,_,client,_=accounts;cid,doc=create_case(client)
    methods=['E07','E08','E09','E10','E11','E12','E14','E18','E20']
    client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending'))
    data=payload(cid,doc,goal='公开原文',method_ids=methods,allow_draft_matter=True,budget=dict(max_model_calls=20,max_tool_calls=30,max_input_tokens=1000000))
    response=client.post('/v1/evaluation/agent-runs',json=data)
    assert response.status_code==201,response.text
    results=[wait_run(client,rid) for rid in response.json()['run_ids']]
    assert all(r['run']['status']=='completed' for r in results),[(r['run']['method']['id'],r['run'].get('error')) for r in results]
    assert all(any(e['relation']=='context' for e in r['graph']['edges']) for r in results)
    assert all(r['run']['method']['reproduction_level']=='project_mechanism' for r in results)
    assert all(r['steps'][0]['messages'] for r in results)
    assert {r['run']['method']['id']:r['run']['usage']['model_calls'] for r in results}==dict(E07=8,E08=9,E09=9,E10=4,E11=3,E12=5,E14=2,E18=6,E20=7)


@pytest.mark.asyncio
async def test_debate_has_independent_initial_positions_and_synchronous_rounds():
    frozen=dict(sources=[dict(id='s',text='test',text_digest=digest('test'))],legal_corpus=[])
    seen={}
    async def call(stage,messages,demo):seen[stage]=copy.deepcopy(messages);return dict(demo,summary=stage)
    async def tool(*args):raise AssertionError('debate should not retrieve')
    await run_method('E09',dict(goal='test',sources=frozen['sources']),frozen['sources'],call,tool,SYSTEM_POLICY,lambda:demo_analysis(frozen),dict(debate_rounds=2))
    initial=json.loads(seen['position.respondent'][1]['content'])
    assert 'positions' not in initial and 'previous_round' not in initial
    left=json.loads(seen['debate.0.claimant'][1]['content'])['previous_round']
    right=json.loads(seen['debate.0.respondent'][1]['content'])['previous_round']
    assert left==right and left['claimant']['summary']=='position.claimant'
    next_round=json.loads(seen['debate.1.claimant'][1]['content'])['previous_round']
    assert next_round['respondent']['summary']=='debate.0.respondent'


def test_draft_template_and_no_template_are_explicit(accounts):
    _,_,client,_=accounts;cid,doc=create_case(client)
    assert client.post('/v1/evaluation/agent-preview',json=payload(cid,doc,method_ids=['E03'])).status_code==409
    client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending'))
    assert client.post('/v1/evaluation/agent-preview',json=payload(cid,doc,method_ids=['E03'])).status_code==409
    assert client.post('/v1/evaluation/agent-preview',json=payload(cid,doc,method_ids=['E03'],allow_draft_matter=True)).status_code==200
    assert client.post('/v1/evaluation/agent-preview',json=payload(cid,doc,method_ids=['E03'],allow_draft_matter=True,split='holdout')).status_code==409
    assert client.post('/v1/evaluation/agent-preview',json=payload(cid,doc,method_ids=['E19'],allow_draft_matter=True)).status_code==200


def test_document_profiles_and_snapshot_continuation(accounts):
    _,_,client,_=accounts;cid,doc=create_case(client,'甲😀乙'*1000)
    other=client.post('/v1/cases/'+cid+'/documents/'+doc['id']+'/parse-runs',json=dict(text_chunk_chars=500))
    assert other.status_code==201,other.text
    second=other.json();assert second['id']!=doc['id']
    assert client.post('/v1/cases/'+cid+'/documents/'+second['id']+'/parse-next',json=dict(pages=3)).status_code==200
    store=client.app.state.documents.store
    snap=store.freeze(cid,doc['id']);new=store.freeze(cid,second['id'])
    assert snap['id']!=new['id'] and snap['source_sha256']==new['source_sha256']
    assert len(snap['blocks'])!=len(new['blocks'])
    block=snap['blocks'][0];url='/v1/cases/'+cid+'/document-snapshots/'+snap['id']+'/read'
    args=dict(block_id=block['id'],start=0,max_chars=7);parts=[]
    while True:
        r=client.post(url,json=args);assert r.status_code==200,r.text
        value=r.json();parts.append(value['text'])
        if not value['next_request']:break
        args=value['next_request']
    assert ''.join(parts)==block['text']


def test_document_only_main_flow_has_sources_without_fake_messages(accounts):
    w,_,client,_=accounts;cid,doc=create_case(client)
    response=client.post('/v1/cases/'+cid+'/analysis/runs',json=dict(document_ids=[doc['id']]))
    assert response.status_code==200,response.text
    assert not w.active_messages(cid)
    refs=client.get('/v1/cases/'+cid+'/source-refs')
    assert refs.status_code==200,refs.text
    assert any(r.get('source_kind')=='document' and r['original_url'].endswith('/file') for r in refs.json())
    import time
    rid=response.json()['id']
    for _ in range(100):
        run=w.repo.get('analysis_runs',rid)
        if run['status'] in {'COMPLETED','FAILED'}:break
        time.sleep(.03)
    assert run['status']=='COMPLETED',run
    from screenshotlegal.application.services.proof import graph
    facts=[e for e in graph(w.repo,cid,rid).entities if e.kind=='fact']
    assert facts and all(e.source_refs for e in facts)
    assert not any(e.kind=='claim' for e in graph(w.repo,cid,rid).entities)



@pytest.mark.asyncio
async def test_corrective_retrieval_discards_rejected_passages():
    source=dict(id='s',text='原文',text_digest=digest('原文'));prompts={}
    async def call(stage,messages,demo):
        prompts[stage]=messages
        if stage=='retrieval_gate':return dict(confidence='incorrect',keep_source_ids=[],revised_query='修正查询')
        return demo
    async def tool(stage,name,args):
        sid='good' if stage.startswith('corrective') else 'bad'
        if name=='case_search':return [dict(source_ref_id=sid)]
        return dict(source_ref_id=sid,text='片段',start=0,end=2,next_request=None)
    await run_method('E12',dict(goal='原查询',sources=[source]),[source],call,tool,SYSTEM_POLICY,lambda:demo_analysis(dict(sources=[source])),dict(retrieval_top_k=1))
    final=json.loads(prompts['synthesize'][1]['content'])
    assert [r['id'] for r in final['input']['sources']]==['good']


def test_comparison_rejects_declared_model_revision_mismatch(accounts):
    _,_,client,_=accounts;cid,doc=create_case(client);ids=[]
    for revision in ['revision-a','revision-b']:
        rid=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,model_revision=revision,idempotency_key=revision)).json()['run_ids'][0]
        wait_run(client,rid);ids.append(rid)
    result=client.get('/v1/evaluation/agent-comparison',params={'ids':','.join(ids)}).json()
    assert 'model_revision_declared' in result['mismatches']
    assert not result['fixed_factors_match']


def test_legacy_document_migration_is_atomic_and_keeps_original_rows(tmp_path,monkeypatch):
    import sqlite3
    from screenshotlegal.documents.store import DocumentStore
    folder=tmp_path/'documents';folder.mkdir();dbfile=folder/'documents.sqlite3'
    old=dict(id='legacy',case_id='c',sha256='hash',filename='old.txt')
    with sqlite3.connect(dbfile) as db:
        db.execute('CREATE TABLE documents(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,sha TEXT NOT NULL,body TEXT NOT NULL,UNIQUE(case_id,sha))')
        db.execute('INSERT INTO documents VALUES (?,?,?,?)',('legacy','c','hash',json.dumps(old)))
    connect=sqlite3.connect
    class FailedMigration(sqlite3.Connection):
        def execute(self,sql,*args,**kwargs):
            if sql.startswith('INSERT INTO documents SELECT'):raise sqlite3.OperationalError('forced migration interruption')
            return super().execute(sql,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3,'connect',lambda *args,**kwargs:connect(*args,**kwargs,factory=FailedMigration))
        with pytest.raises(sqlite3.OperationalError,match='forced'):DocumentStore(tmp_path)
    with connect(dbfile) as db:
        assert [r[1] for r in db.execute('PRAGMA table_info(documents)')]==['id','case_id','sha','body']
        assert json.loads(db.execute('SELECT body FROM documents').fetchone()[0])==old
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='documents_legacy_v1'").fetchall()
    store=DocumentStore(tmp_path)
    assert store.get('c','legacy')==old
    assert DocumentStore(tmp_path).get('c','legacy')==old


def test_explicit_thinking_control_is_frozen_and_changes_comparison_digest(accounts,monkeypatch):
    _,_,client,_=accounts;cid,doc=create_case(client);m=model(client,base_url='https://www.aiping.cn/api/v1')
    seen=[]
    async def gateway(owner,snapshot,messages,purpose,request_id):
        seen.append(snapshot['parameters'].copy())
        return dict(raw=json.dumps(dict(summary='test only',facts=[])),usage=dict(prompt_tokens=1,completion_tokens=1),response_model=snapshot['model'],demo=False)
    service=client.app.state.research['agent_experiments'];monkeypatch.setattr(service.gateway,'call',gateway)
    results=[]
    for thinking in [False,True]:
        response=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,model_id=m['id'],inference_options=dict(enable_thinking=thinking),idempotency_key='thinking-'+str(thinking)))
        assert response.status_code==201,response.text
        result=wait_run(client,response.json()['run_ids'][0]);results.append(result)
        assert result['run']['model']['parameters']['enable_thinking'] is thinking
        assert result['steps'][0]['model_parameters']['enable_thinking'] is thinking
    assert results[0]['run']['model_digest']!=results[1]['run']['model_digest']
    assert [r['enable_thinking'] for r in seen]==[False,True]
    other=model(client,base_url='https://unit.test/v1')
    response=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,model_id=other['id'],inference_options=dict(enable_thinking=False),idempotency_key='unsupported-thinking'))
    assert response.status_code==409
    assert len(seen)==2

def test_citation_hints_preserve_unicode_offsets_and_do_not_relax_grounding():
    from screenshotlegal.experiments.inputs import citation_units
    from screenshotlegal.experiments.engine import visible_input,validate_output
    text='甲😀：收到520元。乙：下周归还。\n'+'长'*170
    source=dict(id='s',text=text,text_digest=digest(text))
    frozen=dict(case_title='test',goal='test',sources=[source],legal_corpus=[])
    units=visible_input(frozen,'E00')['sources'][0]['citation_units']
    assert ''.join(u['quote'] for u in units)==text
    assert all(text[u['start']:u['end']]==u['quote'] for u in units)
    reader=SourceReader(frozen)
    chunk=reader.execute('source_read',dict(source_ref_id='s',start=3,max_chars=18))
    assert ''.join(u['quote'] for u in chunk['citation_units'])==text[3:21]
    assert all(text[u['start']:u['end']]==u['quote'] for u in chunk['citation_units'])
    assert citation_units('')==[]
    good=dict(summary='test',facts=[dict(id='f',statement='test',citations=[dict(source_ref_id='s',**units[0])])])
    assert validate_output(good,frozen)['facts']
    bad=copy.deepcopy(good);bad['facts'][0]['citations'][0]['end']-=1
    with pytest.raises(ValueError):validate_output(bad,frozen)
    bad=copy.deepcopy(good);bad['facts'][0]['citations']=[]
    with pytest.raises(ValueError):validate_output(bad,frozen)

@pytest.mark.asyncio
async def test_legal_r1_rejects_report_as_tool_action_without_calling_tool():
    calls=[];source=dict(id='s',text='原文')
    async def call(stage,messages,demo):
        calls.append(stage);return dict(type='json_object',output=dict(next_action='finish'))
    async def tool(*args):raise AssertionError('Invalid action must not execute a tool')
    with pytest.raises(ModelFailure) as failure:
        await run_method('E11',dict(goal='test',sources=[source]),[source],call,tool,SYSTEM_POLICY,lambda:demo_analysis(dict(sources=[source])),dict(retrieval_rounds=3,retrieval_top_k=1))
    assert failure.value.category=='tool_protocol' and calls==['lawyer.0']
