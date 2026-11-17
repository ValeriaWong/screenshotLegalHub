import copy
import hashlib
import inspect
import json
from pathlib import Path
import sys
import pytest
from screenshotlegal.experiments.registry import CandidateRegistry,IMPLEMENTED
from screenshotlegal.method_reproductions import METHOD_MODULES,method_module,run_method
from test_accounts_ingestion import accounts
from test_agent_experiments import create_case,payload,wait_run

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'paper/experiments'))
from method_artifacts import organize_existing,read_record,record_file,save_record
from report import summarize

@pytest.mark.parametrize('method',list(METHOD_MODULES),ids=list(METHOD_MODULES.values()))
def test_named_method_file_discloses_original_sources_and_extent(method):
    registry=CandidateRegistry();module=method_module(method)
    candidate=next(c for c in registry.methods if c['id']==method)
    assert Path(module.__file__).stem==METHOD_MODULES[method]
    assert module.run.__module__==module.__name__
    assert module.METHOD_ID==method
    assert '论文出处' in module.__doc__ and '复现程度' in module.__doc__
    assert module.REPRODUCTION_SCOPE in module.__doc__
    assert {p['paper_id'] for p in module.PAPER_REFERENCES}==set(candidate['references'])
    assert all(url in module.__doc__ for p in module.PAPER_REFERENCES for url in p['sources'])
    assert 'experiments.methods' not in inspect.getsource(module)
    assert (module.IMPLEMENTATION_STATUS=='implemented')==(method in IMPLEMENTED)
    public=next(c for c in registry.public()['candidates'] if c['id']==method)
    assert public['implementation_version']==(registry.method(method)['implementation_version'] if method in IMPLEMENTED else None)

@pytest.mark.asyncio
@pytest.mark.parametrize('method',list(METHOD_MODULES),ids=list(METHOD_MODULES.values()))
async def test_dispatch_calls_the_named_module_or_rejects_planned(method,monkeypatch):
    module=method_module(method);seen=[]
    async def named(context):
        seen.append(context.visible)
        return dict(reproduction_name=module.METHOD_NAME)
    monkeypatch.setattr(module,'run',named)
    arguments=(dict(goal='test'),[],None,None,'policy',lambda:{},{})
    if method in IMPLEMENTED:
        assert await run_method(method,*arguments)==dict(reproduction_name=METHOD_MODULES[method])
        assert seen==[dict(goal='test')]
    else:
        with pytest.raises(ValueError,match='尚未实现'):await run_method(method,*arguments)
        assert seen==[]

def test_protocol_digest_covers_new_method_source_files(monkeypatch):
    before=CandidateRegistry().code_digest
    original=Path.read_text
    def changed(file,*args,**kwargs):
        value=original(file,*args,**kwargs)
        return value+'\n# changed method body\n' if file.name=='e11_legal_r1.py' else value
    monkeypatch.setattr(Path,'read_text',changed)
    assert CandidateRegistry().code_digest!=before

def test_http_result_and_download_use_reproduction_name(accounts):
    _,_,client,_=accounts;cid,doc=create_case(client)
    client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending'))
    response=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,method_ids=['E11'],allow_draft_matter=True))
    assert response.status_code==201,response.text
    run_id=response.json()['run_ids'][0];result=wait_run(client,run_id)
    assert result['run']['status']=='completed'
    assert result['reproduction_name']=='e11_legal_r1'
    assert result['run']['method']['implementation_module'].endswith('.e11_legal_r1')
    assert all(s['reproduction_name']=='e11_legal_r1' for s in result['steps'])
    assert all(t['reproduction_name']=='e11_legal_r1' for t in result['tools'])
    export=client.get('/v1/evaluation/agent-runs/'+run_id+'/export')
    assert export.status_code==200 and 'e11_legal_r1.' in export.headers['content-disposition']

def fixture_record():
    task=dict(task_id='test123',method_id='E11',case_group_id='counterevidence',case_id='c',repeat=0)
    record=dict(task,status='failed',run_id='r',result=dict(
        run=dict(method=dict(id='E11',implementation_digest='historic-source'),status='failed',demo=False,
                 model=dict(billing=dict(currency='CNY')),usage=dict(model_calls=1,tool_calls=0,input_tokens=10,output_tokens=2,cost=.1,cost_recorded=1),
                 error=dict(category='schema')),
        steps=[dict(stage='lawyer.0',status='completed',messages=[dict(role='user',content='original prompt')],response=dict(raw='{"tool":"finish"}'))],
        tools=[],sources=[dict(id='s',text='original evidence')]))
    return task,record

def test_new_records_and_summaries_are_saved_under_reproduction_name(tmp_path):
    task,record=fixture_record()
    save_record(tmp_path,task,record)
    assert read_record(tmp_path,task)==record
    directory=record_file(tmp_path,task).parent
    assert directory.parent.parent.name=='e11_legal_r1'
    assert not (tmp_path/'attempts').exists()
    for suffix in ['record','prompts','model_responses','output','tools','sources','test_results','provenance']:
        assert (directory/('e11_legal_r1.'+suffix+'.json')).exists()
    assert json.loads((directory/'e11_legal_r1.output.json').read_text())['output'] is None
    (tmp_path/'planned_tasks.json').write_text(json.dumps([task]),encoding='utf-8')
    report=summarize(tmp_path)
    assert report['planned']==1 and report['statuses']==dict(failed=1)
    method_folder=tmp_path/'methods/e11_legal_r1'
    assert (method_folder/'e11_legal_r1.test_results.json').exists()
    assert json.loads((method_folder/'e11_legal_r1.test_results.json').read_text())['real_model_calls']==1

def test_legacy_organization_preserves_originals_failures_and_code_snapshot(tmp_path):
    task,record=fixture_record()
    (tmp_path/'attempts').mkdir();legacy=tmp_path/'attempts/test123.json'
    original=json.dumps(record,ensure_ascii=False,indent=2).encode()
    legacy.write_bytes(original)
    (tmp_path/'planned_tasks.json').write_text(json.dumps([task]),encoding='utf-8')
    report=tmp_path/'report.json';report.write_bytes(b'{"methods":[],"historical":true}')
    archive=tmp_path/'implementation';archive.mkdir();code=archive/'old.py';code.write_bytes(b'# original code\n')
    assert read_record(tmp_path,task)==record
    result=organize_existing(tmp_path)
    assert result['tasks']==1 and result['statuses']==dict(failed=1) and result['model_requests_created']==0
    assert legacy.read_bytes()==record_file(tmp_path,task).read_bytes()==original
    assert report.read_bytes()==b'{"methods":[],"historical":true}'
    assert code.read_bytes()==b'# original code\n'
    provenance=json.loads((record_file(tmp_path,task).parent/'e11_legal_r1.provenance.json').read_text())
    assert provenance['original_record_sha256']==hashlib.sha256(original).hexdigest()
    assert provenance['executed_method']['implementation_digest']=='historic-source'
    organize_existing(tmp_path)
    assert record_file(tmp_path,task).read_bytes()==original

def test_artifact_path_rejects_traversal_in_task_id(tmp_path):
    task,record=fixture_record();task['task_id']='../../elsewhere'
    with pytest.raises(ValueError,match='task ID'):save_record(tmp_path,task,record)
