import httpx
from screenshotlegal.application.services.operation_events import operation, record
from test_accounts_ingestion import accounts, model, KEY


def emit(workspace, owner, model_id, mode, success, fingerprint=None):
    changes = dict(mode=mode, success=success, latency_ms=12)
    if fingerprint is not None:
        changes['config_fingerprint'] = fingerprint
    event = operation(owner, 'settings', 'model.tested', 'model', model_id, changes)
    workspace.repo.batch([record(event)])


def test_connection_history_is_latest_per_mode_and_owner_scoped(accounts):
    workspace, admin, alice, bob = accounts
    saved = model(alice)
    foreign = model(bob)
    emit(workspace, 'alice', saved['id'], 'text', False)
    emit(workspace, 'alice', saved['id'], 'text', True)
    emit(workspace, 'alice', saved['id'], 'image', False)
    emit(workspace, 'bob', saved['id'], 'text', False)
    emit(workspace, 'bob', foreign['id'], 'text', True)
    checks = alice.get('/v1/settings/models').json()[0]['connectivity']
    assert checks['text']['success'] is True
    assert checks['image']['success'] is False
    assert checks['text']['checked_at']
    assert bob.get('/v1/settings/models').json()[0]['id'] == foreign['id']


def test_connection_changes_invalidate_history_but_name_and_price_changes_do_not(accounts):
    workspace, admin, alice, bob = accounts
    saved = model(alice)
    emit(workspace, 'alice', saved['id'], 'text', True)
    payload = dict(name='Renamed', base_url=saved['base_url'], model_name=saved['model_name'],
                   supports_vision=True, allow_external_egress=True, api_key=None)
    # Defaults match the saved configuration; changing a label/price does not alter the connection.
    payload['input_token_price'] = 1
    assert alice.put('/v1/settings/models/' + saved['id'], json=payload).status_code == 200
    assert alice.get('/v1/settings/models').json()[0]['connectivity']['text']['success'] is True
    payload['model_name'] = 'different-model'
    assert alice.put('/v1/settings/models/' + saved['id'], json=payload).status_code == 200
    assert alice.get('/v1/settings/models').json()[0]['connectivity'] == {}


def test_late_result_for_an_old_configuration_is_not_promoted(accounts):
    workspace, admin, alice, bob = accounts
    saved = model(alice)
    pref = workspace.preferences('alice')
    fingerprint = pref.connection_fingerprint(pref.owned(saved['id']))
    payload = dict(name=saved['name'], base_url=saved['base_url'], model_name='new-model',
                   supports_vision=True, allow_external_egress=True, api_key=None)
    assert alice.put('/v1/settings/models/' + saved['id'], json=payload).status_code == 200
    emit(workspace, 'alice', saved['id'], 'text', True, fingerprint)
    assert alice.get('/v1/settings/models').json()[0]['connectivity'] == {}


def test_test_endpoint_persists_public_status_without_modifying_credentials(accounts, monkeypatch):
    workspace, admin, alice, bob = accounts
    saved = model(alice)
    before = workspace.repo.get('model_configs', saved['id'])
    async def respond(request):
        return httpx.Response(200, json={'choices':[{'message':{'content':'OK'}}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)))
    assert alice.post('/v1/settings/models/' + saved['id'] + '/test', json={}).json()['success'] is True
    response = alice.get('/v1/settings/models')
    assert response.json()[0]['connectivity']['text']['success'] is True
    assert workspace.preferences('alice').models()[0].connectivity['text'].success is True
    assert workspace.repo.get('model_configs', saved['id']) == before
    assert KEY not in response.text and 'encrypted_api_key' not in response.text
    assert 'config_fingerprint' not in response.text
