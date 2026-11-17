import copy
import json
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from screenshotlegal.domain.common.models import digest, RunRequest, ReviewRequest, SkillResult, Entity
from screenshotlegal.domain.evidence.models import validate_bbox
from screenshotlegal.domain.runtime.models import CasePlan
from screenshotlegal.plugins.skills.registry import CompileError
from screenshotlegal.runtime.context_projection import project
from screenshotlegal.runtime.retry import with_retry
from screenshotlegal.application.services.proof import graph,matrix
from screenshotlegal.api.main import create_app
from screenshotlegal.plugins.perception.adapters import normalize
from screenshotlegal.infrastructure.model.providers import OpenAICompatibleProvider

def test_matter_validation_digest_and_deterministic_compile(workspace):
    pack=next(iter(workspace.matters.packs.values()))
    assert pack['manifest']['status']=='draft'
    assert len(pack['digest'])==64
    assert all(a['verification_status']=='unverified' for a in pack['authorities'])
    selection={'matter_pack_id':pack['manifest']['id'],'version':'1.0.0'}
    a=workspace.compiler.compile('case',selection,workspace.profile)
    b=workspace.compiler.compile('case',selection,workspace.profile)
    assert a.plan_digest==b.plan_digest
    assert len(a.nodes)==13
    assert all(n.skill_digest for n in a.nodes)
    with pytest.raises(CompileError):
        workspace.compiler.compile('case',selection,workspace.profile,{'evidence.map':'missing'})
    assert pack['digest']==workspace.matters.get(selection['matter_pack_id'])['digest']

def test_resolver_priority_ambiguity_and_trust(workspace):
    registry=workspace.skills
    generic=registry.skills['evidence.map.generic.v1']
    jurisdiction=generic.model_copy(update={'id':'jurisdiction','applies_to':{'jurisdictions':['CN'],'matters':['*']}})
    specific=generic.model_copy(update={'id':'specific','applies_to':{'jurisdictions':['*'],'matters':['cn.civil.private_lending']}})
    registry.skills.update(jurisdiction=jurisdiction,specific=specific)
    resolve=lambda override=None:registry.resolve('evidence.map','cn.civil.private_lending','CN','civil',override)
    assert resolve().id=='specific'
    assert resolve(generic.id).id==generic.id
    registry.skills.pop('specific');assert resolve().id=='jurisdiction'
    registry.skills['duplicate']=jurisdiction.model_copy(update={'id':'duplicate'})
    with pytest.raises(CompileError):resolve()
    for trust in ['external_untrusted','trusted']:
        with pytest.raises(PermissionError):registry.authorize(generic.model_copy(update={'trust':{'level':trust}}))
    with pytest.raises(PermissionError):registry.authorize(generic.model_copy(update={'permissions':dict(generic.permissions,network=True)}))

def test_projection_isolation():
    state={'facts':[{'id':'f'}],'raw_model_response':'secret','conversation':['hidden']}
    p=project(['facts'],state);p['facts'][0]['id']='changed'
    assert state['facts'][0]['id']=='f'
    assert 'conversation' not in p
    with pytest.raises(ValueError):project(['missing'],state)

@pytest.mark.parametrize('bbox',[[0,0,101,10],[10,0,1,5],[0,0,float('nan'),5],[True,0,5,5]])
def test_bbox_rejects_invalid(bbox):
    with pytest.raises(ValueError):validate_bbox(bbox,[100,100])

async def test_demo_proof_graph_matrix_and_audit(demo):
    w,c=demo;repo=w.repo;rid=c['active_analysis_run_id']
    g=graph(repo,c['id']);rows=matrix(repo,c['id'])
    assert len(rows)==4
    assert any(r.supporting and r.contradicting for r in rows)
    assert any(e.kind=='contradiction' for e in g.entities)
    assert any(e.kind=='gap' for e in g.entities)
    assert any(e.kind=='strategy' and e.source_refs for e in g.entities)
    assert {'evidence','message','source_ref','event','fact','element','claim','remedy','authority'} <= {e.kind for e in g.entities}
    ids={e.id for e in g.entities}
    assert all(edge['source'] in ids and edge['target'] in ids for edge in g.edges)
    assert all(e.review_status=='unreviewed' for e in g.entities)
    assert len(repo.list('skill_runs',run_id=rid))==13
    assert len(repo.list('events',run_id=rid))>=3
    run=repo.get('analysis_runs',rid)
    assert run['status']=='COMPLETED'
    assert run['matter_pack_digest'] and run['analysis_profile_digest']
    assert run['model_config_snapshot']['provider']=='deterministic'

async def test_idempotency_and_immutable_runs(demo):
    w,c=demo;repo=w.repo;rid=c['active_analysis_run_id']
    before=repo.list('analysis_snapshots',run_id=rid)
    run=repo.get('analysis_runs',rid)
    node=CasePlan.model_validate(run['plan']).nodes[0]
    await w.runtime.stages.execute_node(run,node)
    assert repo.list('analysis_snapshots',run_id=rid)==before
    with pytest.raises(ValueError):repo.put('analysis_snapshots',before[0]['id'],{'changed':True},immutable=True)
    new=w.start_run(c['id'],RunRequest());await w.runtime.tasks[new['id']]
    assert repo.list('analysis_snapshots',run_id=rid)==before
    assert repo.get('analysis_runs',rid)==run
    assert new['id']!=rid

async def test_review_history_and_staleness(demo):
    w,c=demo;repo=w.repo
    fact=next(e for e in graph(repo,c['id']).entities if e.kind=='fact')
    request=ReviewRequest(target_id=fact.id,output_digest=fact.output_digest,action='verified')
    w.review(c['id'],request)
    assert next(e for e in graph(repo,c['id']).entities if e.id==fact.id).review_status=='verified'
    w.review(c['id'],request.model_copy(update={'action':'deferred'}))
    evidence=w.evidence(c['id'])[0]
    await w.perceive(c['id'],'manual',{evidence['id']:[dict(text='补充承认：这笔是借款，月底归还。',bbox=[30,130,690,220],speaker='李四',timestamp='2024-02-02')]})
    run=w.start_run(c['id'],RunRequest());await w.runtime.tasks[run['id']]
    updated=next(e for e in graph(repo,c['id']).entities if e.id==fact.id)
    assert updated.review_status=='stale'
    assert len(repo.list('review_decisions',case_id=c['id']))==2
    assert len(repo.list('lawyer_assessments',case_id=c['id']))==2
    with pytest.raises(ValueError):w.review(c['id'],request)

async def test_review_gates(demo):
    from screenshotlegal.runtime.review_gate import resolve_gate
    w,c=demo;w.settings.auto_approve_gates=False
    run=w.start_run(c['id'],RunRequest(critical_gate=True))
    assert run['status']=='WAITING_REVIEW'
    await w.runtime.execute(run['id'])
    assert not w.repo.list('skill_runs',run_id=run['id'])
    resolve_gate(w.repo,run['id'],'compile-review','approve')
    await w.runtime.execute(run['id'])
    assert w.repo.get('analysis_runs',run['id'])['status']=='WAITING_REVIEW'
    resolve_gate(w.repo,run['id'],'critical-finding','approve')
    await w.runtime.execute(run['id'])
    assert w.repo.get('analysis_runs',run['id'])['status']=='COMPLETED'
    assert len(w.repo.list('skill_runs',run_id=run['id']))==13

async def test_retry_policy():
    class TransientError(Exception):pass
    from screenshotlegal.domain.runtime.models import RetryPolicy
    count=0;audits=[]
    async def operation():
        nonlocal count
        count+=1
        if count==1:raise TransientError()
        return SkillResult(entities=[Entity(id='f',kind='fact',title='test')])
    async def audit(*args):audits.append(args)
    result=await with_retry(operation,RetryPolicy(backoff=0),audit)
    assert len(result.entities)==1 and len(audits)==2
    async def forbidden():raise PermissionError()
    audits.clear()
    with pytest.raises(PermissionError):await with_retry(forbidden,RetryPolicy(backoff=0),audit)
    assert len(audits)==1

async def test_retrieval_no_model_and_evidence_hashing(demo):
    w,c=demo
    results=w.retriever.search(c['id'],'借款')
    assert results and results[0]['source_refs']
    assert not w.retriever.search('nonexistent','借款')
    assert not w.repo.list('egress_audit')
    evidence=w.evidence(c['id'])[0]
    path=w.storage.verified_path(evidence)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==evidence['sha256']
    with pytest.raises(ValueError):w.storage.path('../outside')
    with pytest.raises(ValueError):w.storage.save(c['id'],'../../bad.exe','image/png',b'not png')
    raw=path.read_bytes();path.write_bytes(b'tampered')
    with pytest.raises(ValueError):w.storage.verified_path(evidence)
    path.write_bytes(raw)
    normalized=normalize(evidence,[dict(text='one',bbox=[0,0,500,500],coordinate_space='normalized_1000')])
    assert normalized.source_refs[0].bbox==(0,0,evidence['width']/2,evidence['height']/2)

async def test_external_egress_off(demo):
    w,c=demo
    with pytest.raises(PermissionError):await OpenAICompatibleProvider(w.settings,w.repo).complete('run',[],[])
    assert not w.repo.list('egress_audit')

async def test_sse_reconstructs_snapshot_and_api(demo):
    w,c=demo
    w.repo.put('parties','old-shape',dict(id='old-party',name='Synthetic party',status='unreviewed'),c['id'])
    with TestClient(create_app(w.settings,w.repo)) as client:
        assert client.post('/v1/auth/setup',json=dict(username='admin',password='test-password-123',display_name='Test administrator')).status_code==200
        assert client.get('/health').status_code==200
        assert client.get('/openapi.json').status_code==200
        response=client.get('/v1/runs/'+c['active_analysis_run_id']+'/events')
        assert 'event: state-snapshot' in response.text
        payload=json.loads(response.text.split('data: ',1)[1].split('\n\n',1)[0])
        assert payload['run']['status']=='COMPLETED'
        assert len(payload['skill_runs'])==13
        assert len(client.get('/v1/cases/'+c['id']+'/proof-matrix').json())==4
        parties=client.get('/v1/cases/'+c['id']+'/parties')
        assert parties.status_code==200 and parties.json()[-1]['identity_status']=='unreviewed'
        assert client.get('/v1/cases/missing/evidence').status_code==404
        assert client.post('/v1/cases/'+c['id']+'/reviews',json={'target_id':'foreign','action':'verified','output_digest':'x'}).status_code==404

def test_matter_schema_rejects_invalid():
    from screenshotlegal.domain.legal.models import MatterManifest,SkillManifest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):MatterManifest.model_validate({'id':'bad'})
    with pytest.raises(ValidationError):SkillManifest.model_validate({'id':'bad'})

async def test_mocked_openai_vision_contract(demo,monkeypatch):
    import httpx
    from screenshotlegal.plugins.perception.adapters import OpenAICompatibleVisionAdapter
    w,c=demo;evidence=w.evidence(c['id'])[0]
    w.settings.enable_real_model=True;w.settings.allow_external_egress=True
    w.settings.model_api_key='unit-test-placeholder';w.settings.model_name='mock-vision';w.settings.model_base_url='https://unit.test/v1'
    calls=[]
    async def respond(request):
        calls.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'messages':[{'text':'visible text','bbox':[30,130,690,220],'coordinate_space':'pixels'}]})}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(respond)))
    result=await OpenAICompatibleVisionAdapter(OpenAICompatibleProvider(w.settings,w.repo),w.storage).perceive(evidence,'mocked-run')
    assert result.messages[0].text=='visible text'
    assert str(calls[0].url)=='https://unit.test/v1/chat/completions'
    audits=w.repo.list('egress_audit')
    assert len(audits)==1 and 'unit-test-placeholder' not in json.dumps(audits)

async def test_legacy_import_is_standalone(workspace):
    import importlib.util
    from screenshotlegal.settings import ROOT
    spec=importlib.util.spec_from_file_location('import_legacy_case',ROOT/'tools/import_legacy_case.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    folder=ROOT/'fixtures/demo_private_lending';content=(folder/'chat-1.png').read_bytes()
    ref=dict(image_id='old-image',message_id='old-message',bbox=[30,130,690,220],quote='borrow',evidence_page=1)
    corpus=dict(images=[dict(image_id='old-image',file='chat-1.png',sha256=hashlib.sha256(content).hexdigest())],records=[dict(id='old-message',kind='message',text='borrow',source_refs=[ref]),dict(id='old-event',kind='event',text='agreement',source_refs=[ref])])
    case=await module.import_case(workspace,corpus,folder,'Synthetic legacy import')
    assert len(workspace.evidence(case.id))==1
    assert len(workspace.repo.list('messages',case_id=case.id))==1
    assert len(workspace.repo.list('source_refs',case_id=case.id))==1
    assert len(workspace.repo.list('events',case_id=case.id))==1

def test_matter_digest_changes_with_content(tmp_path):
    import shutil
    from screenshotlegal.settings import ROOT
    from screenshotlegal.plugins.matterpacks.registry import MatterRegistry
    target=tmp_path/'pack'
    shutil.copytree(ROOT/'matterpacks/cn/civil/private_lending/1.0.0',target)
    original=next(iter(MatterRegistry(tmp_path).packs.values()))['digest']
    file=target/'patterns.yaml';file.write_text(file.read_text(encoding='utf-8')+'\n# changed bytes\n',encoding='utf-8')
    assert next(iter(MatterRegistry(tmp_path).packs.values()))['digest']!=original

async def test_retry_audit_and_rejected_output_are_atomic(demo):
    from screenshotlegal.plugins.skills.deterministic import DeterministicSkill
    w,c=demo
    class TransientError(Exception):pass
    class FailOnce(DeterministicSkill):
        calls=0
        async def run(self,context,input):
            if self.manifest.capability=='evidence.perceive' and FailOnce.calls==0:
                FailOnce.calls+=1
                raise TransientError()
            return await super().run(context,input)
    w.runtime.stages.factory=FailOnce
    run=w.start_run(c['id'],RunRequest());await w.runtime.tasks[run['id']]
    assert w.repo.get('analysis_runs',run['id'])['status']=='COMPLETED'
    assert len(w.repo.list('analysis_snapshots',run_id=run['id']))==13
    assert len(w.repo.list('skill_runs',run_id=run['id']))==14
    class Invalid(DeterministicSkill):
        async def run(self,context,input):
            return SkillResult(entities=[Entity(id='bad',kind='unknown',title='bad')])
    w.runtime.stages.factory=Invalid
    failed=w.start_run(c['id'],RunRequest());await w.runtime.tasks[failed['id']]
    assert w.repo.get('analysis_runs',failed['id'])['status']=='FAILED'
    assert not w.repo.list('analysis_snapshots',run_id=failed['id'])
    audits=w.repo.list('skill_runs',run_id=failed['id'])
    assert len(audits)==1 and audits[0]['status']=='FAILED'
    assert w.repo.get('cases',c['id'])['active_analysis_run_id']==run['id']

async def test_source_reconciliation_validates_case(demo):
    from screenshotlegal.domain.evidence.assessments import Reconciliation
    w,c=demo
    refs=w.repo.list('source_refs',case_id=c['id'])
    request=Reconciliation(id='r1',case_id=c['id'],source_ref_ids=[r['id'] for r in refs[:2]],relation='different',rationale='Synthetic comparison')
    w.reconcile(c['id'],request)
    assert len(w.repo.list('reconciliations',case_id=c['id']))==1
    with pytest.raises(ValueError):w.reconcile(c['id'],request.model_copy(update={'id':'r2','source_ref_ids':['foreign','unknown']}))
