import json
from contextlib import ExitStack
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from screenshotlegal.api.main import create_app
from screenshotlegal.domain.common.models import CaseCreate, Selection, RunRequest
from screenshotlegal.settings import ROOT

PASSWORD='synthetic-password-123'
KEY='synthetic-key-not-a-real-credential'


@pytest.fixture
def accounts(workspace):
    app=create_app(workspace.settings,workspace.repo)
    with ExitStack() as stack:
        admin=stack.enter_context(TestClient(app))
        first=admin.post('/v1/auth/setup',json=dict(username='admin',password=PASSWORD,display_name='Administrator'))
        assert first.status_code==200
        clients={}
        for name in ['alice','bob']:
            assert admin.post('/v1/users',json=dict(username=name,password=PASSWORD,display_name=name)).status_code==201
            client=stack.enter_context(TestClient(app))
            assert client.post('/v1/auth/login',json=dict(username=name,password=PASSWORD)).status_code==200
            clients[name]=client
        yield workspace,admin,clients['alice'],clients['bob']


def upload_files():
    fixture=ROOT/'fixtures/demo_private_lending'
    return [('files',(f'chat-{i}.png',(fixture/f'chat-{i}.png').read_bytes(),'image/png')) for i in [1,2]]


def model(client, **changes):
    data=dict(name='Test vision',base_url='https://unit.test/v1',model_name='mock-vision',api_key=KEY,supports_vision=True,allow_external_egress=True)
    data.update(changes)
    response=client.post('/v1/settings/models',json=data)
    assert response.status_code==201,response.text
    return response.json()


def test_login_required_and_initial_admin_is_unique(workspace):
    with TestClient(create_app(workspace.settings,workspace.repo)) as client:
        assert client.get('/v1/cases').status_code==401
        assert client.get('/v1/settings/models').status_code==401
        assert client.get('/v1/auth/status').json()=={'initialized':False}
        data=dict(username='admin',password=PASSWORD,display_name='Admin')
        response=client.post('/v1/auth/setup',json=data)
        assert response.status_code==200 and response.json()['role']=='admin'
        assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
        assert client.post('/v1/auth/setup',json=data).status_code==403
        assert client.get('/v1/auth/me').json()['username']=='admin'
        assert PASSWORD not in json.dumps(workspace.repo.list('auth_users'))
        token=client.cookies.get('screenshotlegal_session')
        assert token not in json.dumps(workspace.repo.list('auth_sessions'))
        assert client.post('/v1/auth/logout').status_code==200
        assert client.get('/v1/cases').status_code==401


def test_accounts_admin_scope_and_case_sharing(accounts):
    w,admin,alice,bob=accounts
    case=alice.post('/v1/cases',json={'title':'Alice private case'}).json()
    id=case['id']
    assert case['owner_id']=='alice'
    assert bob.get('/v1/cases').json()==[]
    assert bob.get('/v1/cases/'+id).status_code==404
    assert alice.get('/v1/users').status_code==403
    assert alice.post('/v1/users',json=dict(username='other',password=PASSWORD,display_name='Other')).status_code==403
    assert admin.get('/v1/cases/'+id).status_code==200
    assert alice.put(f'/v1/cases/{id}/members',json=dict(username='bob',role='viewer')).status_code==200
    assert bob.get('/v1/cases').json()[0]['access_role']=='viewer'
    assert bob.get(f'/v1/cases/{id}/evidence').status_code==200
    assert bob.post(f'/v1/cases/{id}/evidence/batch',files=upload_files()).status_code==403
    assert bob.put(f'/v1/cases/{id}/members',json=dict(username='alice',role='remove')).status_code==403
    alice.put(f'/v1/cases/{id}/members',json=dict(username='bob',role='editor'))
    assert bob.post(f'/v1/cases/{id}/evidence/batch',files=upload_files()).status_code==200
    alice.put(f'/v1/cases/{id}/members',json=dict(username='bob',role='remove'))
    evidence=w.evidence(id)[0]
    assert bob.get(f'/v1/cases/{id}/evidence/{evidence["id"]}/file').status_code==404
    assert bob.get(f'/v1/cases/{id}/search?q=anything').status_code==404


def test_disabled_account_and_last_admin(accounts):
    w,admin,alice,bob=accounts
    assert admin.put('/v1/users/admin',json=dict(role='member',enabled=True)).status_code==409
    assert admin.put('/v1/users/alice',json=dict(role='member',enabled=False)).status_code==200
    assert alice.get('/v1/cases').status_code==401
    assert alice.post('/v1/auth/login',json=dict(username='alice',password=PASSWORD)).status_code==401
    admin.put('/v1/users/alice',json=dict(role='member',enabled=True))
    assert alice.post('/v1/auth/login',json=dict(username='alice',password=PASSWORD)).status_code==200


def test_password_change_revokes_all_sessions(accounts):
    w,admin,alice,bob=accounts
    assert alice.post('/v1/auth/password',json=dict(current_password='incorrect',new_password='new-synthetic-password')).status_code==403
    assert alice.post('/v1/auth/password',json=dict(current_password=PASSWORD,new_password='new-synthetic-password')).status_code==200
    assert alice.get('/v1/cases').status_code==401
    assert alice.post('/v1/auth/login',json=dict(username='alice',password=PASSWORD)).status_code==401
    assert alice.post('/v1/auth/login',json=dict(username='alice',password='new-synthetic-password')).status_code==200


def test_login_rate_limit(accounts):
    w,admin,alice,bob=accounts
    for _ in range(5):
        assert bob.post('/v1/auth/login',json=dict(username='missing',password=PASSWORD)).status_code==401
    assert bob.post('/v1/auth/login',json=dict(username='missing',password=PASSWORD)).status_code==429


def test_expired_session_is_rejected(accounts):
    from sqlalchemy import select
    from screenshotlegal.infrastructure.db.models import MODELS
    w,admin,alice,bob=accounts
    with w.repo.session.begin() as session:
        for row in session.scalars(select(MODELS['auth_sessions'])):
            if row.body['user_id']=='alice':
                row.body=dict(row.body,expires_at='2000-01-01T00:00:00+00:00')
    assert alice.get('/v1/cases').status_code==401
    assert bob.get('/v1/cases').status_code==200


def test_unclaimed_cases_bind_to_initial_admin(workspace):
    case=workspace.create_case(CaseCreate(title='Legacy case'))
    with TestClient(create_app(workspace.settings,workspace.repo)) as client:
        client.post('/v1/auth/setup',json=dict(username='first',password=PASSWORD,display_name='First'))
        assert client.get('/v1/cases/'+case.id).json()['owner_id']=='first'


def test_foreign_origin_and_validation_do_not_leak_credentials(accounts):
    w,admin,alice,bob=accounts
    assert alice.post('/v1/cases',json={'title':'bad origin'},headers={'Origin':'https://other.test'}).status_code==403
    response=alice.post('/v1/settings/models',json=dict(name='',base_url='https://unit.test/v1',model_name='x',api_key=KEY))
    assert response.status_code==422 and KEY not in response.text


def test_batch_upload_partial_failure_duplicates_and_retry(accounts):
    w,admin,alice,bob=accounts
    id=alice.post('/v1/cases',json={'title':'Chat screenshots'}).json()['id']
    files=upload_files()+[('files',('corrupt.png',b'not-an-image','image/png')),('files',('copy.png',upload_files()[0][1][1],'image/png'))]
    response=alice.post(f'/v1/cases/{id}/evidence/batch',files=files)
    assert response.status_code==200
    result=response.json()
    assert (result['uploaded'],result['duplicates'],result['failed'])==(2,1,1)
    assert [r['status'] for r in result['results']]==['uploaded','uploaded','failed','duplicate']
    assert len(w.evidence(id))==2
    again=alice.post(f'/v1/cases/{id}/evidence/batch',files=upload_files()).json()
    assert again['duplicates']==2 and again['failed']==0
    for evidence in w.evidence(id):
        assert evidence['width'] and evidence['height']
        assert alice.get(f'/v1/cases/{id}/evidence/{evidence["id"]}/file').status_code==200


def test_batch_file_count_and_byte_limits(accounts):
    w,admin,alice,bob=accounts
    id=alice.post('/v1/cases',json={'title':'Limits'}).json()['id']
    w.settings.max_batch_files=1
    assert alice.post(f'/v1/cases/{id}/evidence/batch',files=upload_files()).status_code==413
    w.settings.max_batch_files=50;w.settings.max_batch_bytes=5
    response=alice.post(f'/v1/cases/{id}/evidence/batch',files=[('files',('a.txt',b'1234','text/plain')),('files',('b.txt',b'56','text/plain')),('files',('c.txt',b'7','text/plain'))]).json()
    assert response['uploaded']==1 and response['failed']==2
    w.settings.max_batch_bytes=100;w.settings.max_upload_bytes=3
    assert alice.post(f'/v1/cases/{id}/evidence/batch',files=[('files',('large.txt',b'1234','text/plain'))]).json()['failed']==1


def test_format_registry_pdf_text_unknown_and_mime_fallback(accounts):
    w,admin,alice,bob=accounts
    id=alice.post('/v1/cases',json={'title':'Formats'}).json()['id']
    files=[('files',('chat.PNG',upload_files()[0][1][1],'application/octet-stream')),('files',('document.pdf',b'%PDF-1.7\nsynthetic','application/pdf')),('files',('notes.txt',b'UTF-8 notes','text/plain')),('files',('archive.zip',b'PK\x03\x04','application/zip'))]
    result=alice.post(f'/v1/cases/{id}/evidence/batch',files=files).json()
    assert result['uploaded']==3 and result['failed']==1
    assert [r['evidence']['kind'] for r in result['results'][:3]]==['image','pdf','txt']
    assert 'application/zip' not in [f['mime_type'] for f in alice.get('/v1/evidence/formats').json()['formats']]


def test_models_user_isolation_encryption_edit_and_delete(accounts):
    w,admin,alice,bob=accounts
    m=model(alice)
    assert m['has_api_key'] and m['is_default'] and KEY not in json.dumps(m)
    assert KEY not in json.dumps(w.repo.list('model_configs'))
    assert w.preferences('alice').provider_settings().model_api_key==KEY
    assert bob.get('/v1/settings/models').json()==[]
    for method,path,payload in [('put',f'/v1/settings/models/{m["id"]}',dict(name='x',base_url='https://unit.test/v1',model_name='x')),('post',f'/v1/settings/models/{m["id"]}/test',{}),('put','/v1/settings/default-model',{'model_id':m['id']})]:
        assert getattr(bob,method)(path,json=payload).status_code==404
    assert bob.delete(f'/v1/settings/models/{m["id"]}').status_code==404
    changed=alice.put(f'/v1/settings/models/{m["id"]}',json=dict(name='Renamed',base_url='https://unit.test/v1',model_name='changed',api_key=None,allow_external_egress=True)).json()
    assert changed['has_api_key'] and w.preferences('alice').provider_settings().model_api_key==KEY
    second=model(alice,name='Second',api_key='replacement-test-key')
    assert alice.put('/v1/settings/default-model',json={'model_id':second['id']}).status_code==200
    assert alice.delete(f'/v1/settings/models/{second["id"]}').status_code==200
    assert w.preferences('alice').selected() is None
    assert alice.put('/v1/user',json=dict(display_name='Alice updated',organization='Test organization')).status_code==200
    assert alice.get('/v1/auth/me').json()['display_name']=='Alice updated'


@pytest.mark.parametrize('url',['http://remote.test/v1','https://key:secret@unit.test/v1','https://unit.test/v1?api_key=secret'])
def test_model_endpoint_rejects_unsafe_config(accounts,url):
    w,admin,alice,bob=accounts
    response=alice.post('/v1/settings/models',json=dict(name='x',base_url=url,model_name='x',api_key=KEY))
    assert response.status_code==409 and KEY not in response.text


@pytest.mark.parametrize('status,body,success',[(200,{'choices':[{'message':{'content':'OK'}}]},True),(401,{'secret':KEY},False),(200,{},False)])
def test_connectivity_request_redaction_and_failures(accounts,monkeypatch,status,body,success):
    w,admin,alice,bob=accounts
    m=model(alice)
    requests=[]
    async def respond(request):
        requests.append(request)
        return httpx.Response(status,json=body)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(respond)))
    response=alice.post(f'/v1/settings/models/{m["id"]}/test',json={})
    assert response.status_code==200 and response.json()['success'] is success
    assert KEY not in response.text and KEY not in json.dumps(w.repo.list('egress_audit'))
    payload=json.loads(requests[0].content)
    assert payload['model']=='mock-vision' and 'max_tokens' not in payload and 'response_format' not in payload
    assert requests[0].headers['authorization']=='Bearer '+KEY
    assert w.repo.list('egress_audit')[0]['evidence_ids']==[]
    assert w.repo.list('egress_audit')[0]['user_id']=='alice'


def test_connectivity_permission_and_timeout(accounts,monkeypatch):
    w,admin,alice,bob=accounts
    m=model(alice,allow_external_egress=False)
    assert not alice.post(f'/v1/settings/models/{m["id"]}/test',json={}).json()['success']
    assert not w.repo.list('egress_audit')
    m=model(alice,base_url='http://127.0.0.1:9000/v1')
    async def respond(request):
        raise httpx.ReadTimeout('private provider body '+KEY,request=request)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(respond)))
    response=alice.post(f'/v1/settings/models/{m["id"]}/test',json={})
    assert not response.json()['success'] and KEY not in response.text


def test_saved_model_processes_all_images_skips_pdf_and_blocks_foreign_model(accounts,monkeypatch):
    w,admin,alice,bob=accounts
    id=alice.post('/v1/cases',json={'title':'Vision batch'}).json()['id']
    alice.post(f'/v1/cases/{id}/evidence/batch',files=upload_files()+[('files',('a.pdf',b'%PDF-1.7\nsynthetic','application/pdf'))])
    m=model(alice)
    foreign=model(bob)
    assert alice.post(f'/v1/cases/{id}/perception/runs',json=dict(adapter='openai-compatible',model_id=foreign['id'])).status_code==404
    calls=[]
    async def respond(request):
        calls.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'messages':[{'text':'visible text','bbox':[30,130,690,220]}]})}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(respond)))
    response=alice.post(f'/v1/cases/{id}/perception/runs',json=dict(adapter='openai-compatible',model_id=m['id']))
    assert response.status_code==200 and response.json()['messages']==2 and len(calls)==2
    assert all(r.headers['authorization']=='Bearer '+KEY for r in calls)


async def test_perception_replacement_and_unrelated_material_preserve_runs(workspace):
    w=workspace
    c=w.create_case(CaseCreate(title='Corrected transcript'))
    e=w.upload(c.id,'chat.png','image/png',upload_files()[0][1][1])
    await w.perceive(c.id,'manual',{e.id:[dict(text='不是借款',bbox=[30,130,690,220])]})
    w.select_matter(c.id,Selection());w.compile(c.id)
    old=w.start_run(c.id,RunRequest());await w.runtime.tasks[old['id']]
    await w.perceive(c.id,'manual',{e.id:[dict(text='Good morning',bbox=[40,140,680,230])]})
    new=w.start_run(c.id,RunRequest());await w.runtime.tasks[new['id']]
    assert w.repo.get('analysis_runs',new['id'])['status']=='COMPLETED'
    assert [m['text'] for m in w.repo.get('analysis_runs',new['id'])['input_snapshot']['messages']]==['Good morning']
    assert [m['text'] for m in w.repo.get('analysis_runs',old['id'])['input_snapshot']['messages']]==['不是借款']
    await w.perceive(c.id,'manual',{e.id:[dict(text='Good morning',bbox=[50,150,680,230])]})
    assert len(w.active_messages(c.id))==1
    assert not w.retriever.search(c.id,'借款')


async def test_foreign_run_and_sse_are_protected(demo):
    w,c=demo
    app=create_app(w.settings,w.repo)
    with TestClient(app) as admin,TestClient(app) as member:
        admin.post('/v1/auth/setup',json=dict(username='admin',password=PASSWORD,display_name='Admin'))
        admin.post('/v1/users',json=dict(username='other',password=PASSWORD,display_name='Other'))
        member.post('/v1/auth/login',json=dict(username='other',password=PASSWORD))
        id=c['active_analysis_run_id']
        for path in [f'/v1/runs/{id}',f'/v1/runs/{id}/events']:
            assert member.get(path).status_code==404
        assert member.post(f'/v1/runs/{id}/review-gates/compile-review',json={'action':'approve'}).status_code==404


def test_connectivity_repeated_reasoning_only_responses_are_successful(accounts, monkeypatch):
    w, admin, alice, bob = accounts
    saved = model(alice)
    before = w.repo.get("model_configs", saved["id"])
    bodies = iter([
        {"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": None, "reasoning_content": "Thinking"}, "finish_reason": "length"}]},
        {"choices": [{"message": {"content": "", "reasoning": "Thinking"}, "finish_reason": "length"}]},
    ])
    async def respond(request):
        return httpx.Response(200, json=next(bodies))
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)))
    for _ in range(3):
        response = alice.post(f"/v1/settings/models/{saved['id']}/test", json={})
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert KEY not in response.text and "Thinking" not in response.text
    assert w.repo.get("model_configs", saved["id"]) == before
    assert len(w.repo.list("egress_audit")) == 3


@pytest.mark.parametrize("body", [
    {"choices": []},
    {"choices": [{"message": {"content": None, "reasoning_content": ""}}]},
    {"choices": [{"message": {"content": "", "reasoning_content": ["invalid"]}}]},
])
def test_connectivity_rejects_empty_or_malformed_responses(accounts, monkeypatch, body):
    w, admin, alice, bob = accounts
    saved = model(alice)
    async def respond(request):
        return httpx.Response(200, json=body)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)))
    response = alice.post(f"/v1/settings/models/{saved['id']}/test", json={})
    assert response.status_code == 200 and response.json()["success"] is False
    assert KEY not in response.text


async def test_analysis_still_requires_final_content(accounts, monkeypatch):
    from screenshotlegal.infrastructure.model.providers import OpenAICompatibleProvider
    w, admin, alice, bob = accounts
    saved = model(alice)
    async def respond(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "reasoning_content": "Thinking"}}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)))
    provider = OpenAICompatibleProvider(w.preferences("alice").provider_settings(saved["id"]), w.repo, "alice")
    with pytest.raises(ValueError, match="Invalid model response"):
        await provider.complete("unit-analysis", [], [{"role": "user", "content": "Analyze"}])


def test_image_connectivity_sends_authorized_case_image_and_audits_it(accounts, monkeypatch):
    import base64
    w, admin, alice, bob = accounts
    case = alice.post("/v1/cases", json={"title": "Image probe case"}).json()
    uploaded = alice.post(f"/v1/cases/{case['id']}/evidence/batch", files=upload_files()).json()
    evidence = uploaded["results"][0]["evidence"]
    sample = alice.get("/v1/settings/test-image").json()
    assert sample["case_id"] == case["id"] and sample["evidence_id"] == evidence["id"]
    assert sample["filename"] == evidence["filename"]
    saved = model(alice)
    requests = []
    async def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "A chat screenshot."}}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)))
    for _ in range(2):
        response = alice.post(f"/v1/settings/models/{saved['id']}/test", json={"mode": "image", "case_id": sample["case_id"], "evidence_id": sample["evidence_id"]})
        assert response.status_code == 200 and response.json()["success"]
        assert response.json()["mode"] == "image" and response.json()["evidence_id"] == evidence["id"]
        assert KEY not in response.text
    payload = json.loads(requests[0].content)
    assert "max_tokens" not in payload and "response_format" not in payload
    content = payload["messages"][0]["content"]
    assert [part["type"] for part in content] == ["text", "image_url"]
    encoded = content[1]["image_url"]["url"]
    assert encoded.startswith("data:image/png;base64,")
    assert base64.b64decode(encoded.split(",", 1)[1]) == upload_files()[0][1][1]
    audits = w.repo.list("egress_audit")
    assert len(audits) == 2 and all(a["evidence_ids"] == [evidence["id"]] and a["user_id"] == "alice" for a in audits)
    assert encoded not in json.dumps(audits)
    assert not w.repo.list("analysis_runs") and not w.repo.list("messages", case_id=case["id"])


def test_image_connectivity_requires_access_and_an_available_image(accounts, monkeypatch):
    w, admin, alice, bob = accounts
    saved = model(alice)
    assert alice.get("/v1/settings/test-image").json() is None
    response = alice.post(f"/v1/settings/models/{saved['id']}/test", json={"mode": "image"})
    assert response.status_code == 200 and not response.json()["success"] and response.json()["mode"] == "image"
    case = bob.post("/v1/cases", json={"title": "Private image"}).json()
    evidence = bob.post(f"/v1/cases/{case['id']}/evidence/batch", files=upload_files()).json()["results"][0]["evidence"]
    assert alice.get("/v1/settings/test-image").json() is None
    response = alice.post(f"/v1/settings/models/{saved['id']}/test", json={"mode": "image", "case_id": case["id"], "evidence_id": evidence["id"]})
    assert response.status_code == 404 and not w.repo.list("egress_audit")
    assert admin.get("/v1/settings/test-image").json()["case_id"] == case["id"]
    bob.put(f"/v1/cases/{case['id']}/members", json={"username": "alice", "role": "viewer"})
    assert alice.get("/v1/settings/test-image").json()["case_id"] == case["id"]
    bob.put(f"/v1/cases/{case['id']}/members", json={"username": "alice", "role": "remove"})
    assert alice.get("/v1/settings/test-image").json() is None


def test_image_connectivity_blocks_nonvision_models_and_tampered_files(accounts):
    w, admin, alice, bob = accounts
    case = alice.post("/v1/cases", json={"title": "Probe integrity"}).json()
    evidence = alice.post(f"/v1/cases/{case['id']}/evidence/batch", files=upload_files()).json()["results"][0]["evidence"]
    saved = model(alice, supports_vision=False)
    payload = {"mode": "image", "case_id": case["id"], "evidence_id": evidence["id"]}
    response = alice.post(f"/v1/settings/models/{saved['id']}/test", json=payload)
    assert response.status_code == 200 and not response.json()["success"]
    assert not w.repo.list("egress_audit")
    w.storage.verified_path(evidence).write_bytes(b"tampered")
    response = alice.post(f"/v1/settings/models/{saved['id']}/test", json=payload)
    assert response.status_code == 409 and not w.repo.list("egress_audit")


def test_image_connectivity_disabled_egress_and_invalid_selection(accounts):
    w, admin, alice, bob = accounts
    case = alice.post("/v1/cases", json={"title": "Probe consent"}).json()
    evidence = alice.post(f"/v1/cases/{case['id']}/evidence/batch", files=upload_files()).json()["results"][0]["evidence"]
    saved = model(alice, allow_external_egress=False)
    endpoint = f"/v1/settings/models/{saved['id']}/test"
    response = alice.post(endpoint, json={"mode": "image"})
    assert response.status_code == 200 and not response.json()["success"] and not w.repo.list("egress_audit")
    assert alice.post(endpoint, json={"mode": "image", "case_id": case["id"]}).status_code == 409
    assert alice.post(endpoint, json={"mode": "image", "case_id": case["id"], "evidence_id": "missing"}).status_code == 404
    assert alice.post(endpoint, json={"mode": "invalid"}).status_code == 422
