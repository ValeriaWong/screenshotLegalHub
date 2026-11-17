import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from screenshotlegal.api.main import create_app
from screenshotlegal.application.services.auth import AuthService
from screenshotlegal.domain.common.models import CaseCreate
from screenshotlegal.domain.settings.auth import CreateUserRequest
from screenshotlegal.infrastructure.db.models import MODELS
from screenshotlegal.settings import ROOT


PASSWORD = 'synthetic-import-password'


@pytest.fixture
def importer():
    spec = importlib.util.spec_from_file_location('repository_import_under_test', ROOT / 'tools/import_repository_cases.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def admin_auth(workspace):
    auth = AuthService(workspace.repo, workspace.settings)
    admin = auth.create_user(CreateUserRequest(username='admin', password=PASSWORD, display_name='Administrator'), bootstrap=True)
    return auth, admin


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / 'repository'
    (root / 'datasets').mkdir(parents=True)
    return root


@pytest.fixture
def png():
    return (ROOT / 'fixtures/demo_private_lending/chat-1.png').read_bytes()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def write_lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, ensure_ascii=False) + '\n' for value in values), encoding='utf-8')


def sample(text_value='原文公开的消息', **message_fields):
    return dict(id='q5_0001', language='zh', platform='wechat', status='reviewed',
                participants=[dict(id='p1', name='甲')], conversations=[dict(id='c1')],
                messages=[dict(id='m1', text=text_value, sender_id='p1', **message_fields)])


def rendered_sample(root, png, name='q5_0001', case=None):
    directory = root / 'datasets/v2.0.0/round_005/zh' / name
    write_json(directory / 'case.json', case or sample())
    (directory / 'chat.png').write_bytes(png)
    write_json(directory / 'render.json', dict(images=[dict(
        path='chat.png', sha256=hashlib.sha256(png).hexdigest(), page=2,
        boxes=[dict(message_id='m1', bbox_pixels=[10, 20, 100, 40])])]))
    return directory


def snapshot(workspace):
    result = {table: sorted(workspace.repo.list(table), key=lambda row: json.dumps(row, sort_keys=True)) for table in MODELS}
    with workspace.repo.engine.connect() as connection:
        result['fts'] = sorted(tuple(row) for row in connection.execute(text('SELECT * FROM search_index')))
    result['files'] = sorted((p.relative_to(workspace.storage.root).as_posix(), p.read_bytes())
                             for p in workspace.storage.root.rglob('*') if p.is_file())
    return result


def test_sync_is_idempotent_and_preserves_manual_cases_and_human_reviews(importer, workspace, admin_auth, repository, png, tmp_path):
    rendered_sample(repository, png)
    manual = workspace.create_case(CaseCreate(title='人工案件', description='人工记录'), owner_id='admin')
    workspace.upload(manual.id, 'manual.png', 'image/png', png)
    review = dict(id='human-review', case_id=manual.id, target_id='manual-target', action='edited',
                  text='律师人工意见，必须保留', reviewer='human-reviewer', reviewed_output_digest='manual-digest')
    workspace.repo.put('review_decisions', review['id'], review, case_id=manual.id, immutable=True)
    original_manual = workspace.repo.get('cases', manual.id)

    first = importer.sync(repository, workspace, 'admin', tmp_path / 'first-report.json', apply=True)
    imported_id = first['results'][0]['case_id']
    imported_review = dict(review, id='imported-human-review', case_id=imported_id)
    workspace.repo.put('review_decisions', imported_review['id'], imported_review, case_id=imported_id, immutable=True)
    before_repeat = snapshot(workspace)
    second = importer.sync(repository, workspace, 'admin', tmp_path / 'second-report.json', apply=True)

    assert first['result_counts'] == {'created': 1}
    assert second['result_counts'] == {'existing': 1}
    assert snapshot(workspace) == before_repeat
    assert workspace.repo.get('cases', manual.id) == original_manual
    assert workspace.repo.get('review_decisions', review['id']) == review
    assert workspace.repo.get('review_decisions', imported_review['id']) == imported_review
    assert second['admin_visible_cases'] == 2
    assert Path(first['backup']).is_file() and Path(second['backup']).is_file()
    assert first['backup'] != second['backup']


@pytest.mark.parametrize('language', ['zh', 'en'])
def test_source_without_screenshots_still_becomes_a_case(importer, workspace, admin_auth, repository, tmp_path, language):
    original = '判决公开全文，未公开任何聊天截图。' if language == 'zh' else 'The full judgment contains no chat screenshots.'
    source = (dict(text=original, paragraphs=[dict(id='p1', text=original)], case_no='原文案号')
              if language == 'zh' else dict(judgment_text=original, neutral_citation='[2026] Test 1', title='Source judgment'))
    write_json(repository / 'datasets/source_archive/source.json', source)
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'source-report.json', apply=True)
    assert report['inventory_counts'] == {'source': 1}
    assert report['images'] == report['messages'] == 0
    case = workspace.repo.list('cases')[0]
    assert case['owner_id'] == 'admin'
    evidence = workspace.evidence(case['id'])
    assert len(evidence) == 2 and all(item['kind'] != 'image' for item in evidence)
    original_item = next(item for item in evidence if item['filename'] == '判决原文.txt')
    assert workspace.storage.verified_path(original_item).read_text(encoding='utf-8') == original
    assert workspace.repo.list('messages', case_id=case['id']) == []
    assert workspace.repo.list('source_refs', case_id=case['id']) == []


def test_same_round_versions_stay_separate_and_frozen_aliases_survive(importer, workspace, admin_auth, repository, tmp_path):
    original = sample('最终版的公开消息')
    rel = Path('datasets/v2.0.0/round_005/zh/q5_0001/case.json')
    frozen_rel = Path('datasets/frozen/snapshot') / rel
    draft_rel = rel.with_name('draft.json')
    write_json(repository / rel, original)
    write_json(repository / frozen_rel, original)
    write_json(repository / draft_rel, sample('旧草稿的消息'))
    bundles, _ = importer.discover(repository)
    assert len(bundles) == 2 and len({bundle['id'] for bundle in bundles}) == 2
    final = next(bundle for bundle in bundles if len(bundle['aliases']) == 2)
    assert set(final['aliases']) == {rel.as_posix(), frozen_rel.as_posix()}
    draft = next(bundle for bundle in bundles if len(bundle['aliases']) == 1)
    assert draft['aliases'] == [draft_rel.as_posix()]
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'versions-report.json', apply=True)
    assert report['case_versions'] == 2 and report['aliases'] == 3
    case = workspace.repo.get('cases', final['id'])
    assert all(alias in case['description'] for alias in final['aliases'])
    metadata = next(item for item in workspace.evidence(final['id']) if item['filename'] == '来源与版本说明.txt')
    assert json.loads(workspace.storage.verified_path(metadata).read_text(encoding='utf-8'))['source_paths'] == sorted(final['aliases'])
    assert workspace.repo.get('cases', draft['id'])['id'] != final['id']


def test_v2_xywh_boxes_and_only_source_dates_are_imported(importer, workspace, admin_auth, repository, png, tmp_path):
    case = sample(timestamp='2020-04-01T12:34:00', date_basis='source_day')
    case['messages'].append(dict(id='m2', sender_id='p1', text='排版时间不是史实', timestamp='2020-04-02T08:01:00', date_basis='synthetic'))
    directory = rendered_sample(repository, png, case=case)
    render = json.loads((directory / 'render.json').read_text(encoding='utf-8'))
    render['images'][0]['boxes'].append(dict(message_id='m2', bbox_pixels=[20, 80, 110, 30]))
    write_json(directory / 'render.json', render)
    importer.sync(repository, workspace, 'admin', tmp_path / 'v2-report.json', apply=True)
    messages = {row['text']: row for row in workspace.repo.list('messages')}
    refs = {row['message_id']: row for row in workspace.repo.list('source_refs')}
    first = messages['原文公开的消息']
    assert first['speaker'] == '甲' and first['timestamp'] == '2020-04-01'
    assert refs[first['id']]['bbox'] == [10.0, 20.0, 110.0, 60.0]
    assert refs[first['id']]['evidence_page'] == 2
    assert messages['排版时间不是史实']['timestamp'] is None
    assert workspace.retriever.search(workspace.repo.list('cases')[0]['id'], '公开')


def test_v3_unknown_page_and_synthetic_timestamp_remain_unknown(importer, workspace, admin_auth, repository, png, tmp_path):
    collection = repository / 'datasets/v3.0.0'
    directory = collection / 'renders/scenario_1/unknownpage'
    write_json(collection / 'case_scope.json', [dict(case_id='scenario_1', title='合成校准')])
    write_lines(directory / 'messages.jsonl', [dict(id='v3m1', sender_id='unknown', text='合成消息', timestamp='2021-01-01T09:12:00')])
    (directory / 'page.png').write_bytes(png)
    write_json(directory / 'render_manifest.json', dict(pages=[dict(file='page.png', image_id='img1', sha256=hashlib.sha256(png).hexdigest())]))
    write_lines(collection / 'source_refs.jsonl', [dict(conversation_id='scenario_1', variant='unknownpage', image_id='img1', message_id='v3m1', bbox=[10, 20, 110, 60])])
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'v3-report.json', apply=True)
    assert report['inventory_counts'] == {'v3': 1}
    message, = workspace.repo.list('messages')
    ref, = workspace.repo.list('source_refs')
    assert message['timestamp'] is None and message['speaker'] == 'unknown'
    assert ref['evidence_page'] is None
    assert ref['bbox'] == [10.0, 20.0, 110.0, 60.0]
    assert 'unknownpage' in workspace.repo.list('cases')[0]['description']


@pytest.mark.parametrize('fault', ['invalid_json', 'missing_image', 'wrong_digest', 'outside_bbox', 'unresolved_message'])
def test_preflight_errors_write_no_cases_or_files(importer, workspace, admin_auth, repository, png, tmp_path, fault):
    rendered_sample(repository, png, 'a_valid')
    bad = rendered_sample(repository, png, 'z_invalid', case=sample('应当拒绝的素材'))
    path = bad / 'render.json'
    render = json.loads(path.read_text(encoding='utf-8'))
    if fault == 'invalid_json':
        path.write_text('{invalid', encoding='utf-8')
    elif fault == 'missing_image':
        (bad / 'chat.png').unlink()
    elif fault == 'wrong_digest':
        render['images'][0]['sha256'] = '0' * 64
        write_json(path, render)
    elif fault == 'outside_bbox':
        render['images'][0]['boxes'][0]['bbox_pixels'] = [10, 20, 99999, 40]
        write_json(path, render)
    else:
        render['images'][0]['boxes'][0]['message_id'] = 'missing'
        write_json(path, render)
    before = snapshot(workspace)
    with pytest.raises((ValueError, FileNotFoundError)):
        importer.sync(repository, workspace, 'admin', tmp_path / 'failed-report.json', apply=True)
    assert snapshot(workspace) == before
    assert not (workspace.settings.data_dir / 'backups').exists()


def test_read_only_preflight_does_not_write_live_data(importer, workspace, admin_auth, repository, png, tmp_path):
    rendered_sample(repository, png)
    before = snapshot(workspace)
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'preflight.json')
    assert report['result_counts'] == {'validated': 1}
    assert report['backup'] is None and snapshot(workspace) == before


@pytest.mark.parametrize('stage', ['storage', 'database', 'search'])
def test_late_failure_rolls_back_entire_case_and_allows_retry(importer, workspace, admin_auth, repository, png, monkeypatch, stage):
    rendered_sample(repository, png)
    bundles, _ = importer.discover(repository)
    prepared = importer.prepare(workspace, bundles[0], 'admin')
    before = snapshot(workspace)
    target, name = {'storage': (workspace.storage, 'save'), 'database': (workspace.repo, 'batch'), 'search': (workspace.retriever, 'index')}[stage]
    original = getattr(target, name)
    calls = 0

    def fail_after_write(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if stage != 'storage' or calls == 2:
            raise RuntimeError('injected late failure')
        return result

    monkeypatch.setattr(target, name, fail_after_write)
    with pytest.raises(RuntimeError, match='injected late failure'):
        importer.apply_one(workspace, prepared)
    assert snapshot(workspace) == before
    assert not workspace.storage.path(prepared[0].id).exists()
    monkeypatch.setattr(target, name, original)
    assert importer.apply_one(workspace, prepared) == 'created'
    assert workspace.retriever.search(prepared[0].id, '公开')
    assert all(workspace.storage.verified_path(item).is_file() for item in workspace.evidence(prepared[0].id))


def test_imports_are_admin_owned_and_hidden_from_ordinary_users(importer, workspace, admin_auth, repository, png, tmp_path):
    auth, _ = admin_auth
    auth.create_user(CreateUserRequest(username='alice', password=PASSWORD, display_name='Alice'))
    rendered_sample(repository, png)
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'ownership-report.json', apply=True)
    case_id = report['results'][0]['case_id']
    assert workspace.repo.get('cases', case_id)['owner_id'] == 'admin'
    app = create_app(workspace.settings, workspace.repo)
    with TestClient(app) as admin, TestClient(app) as alice:
        for client, username in [(admin, 'admin'), (alice, 'alice')]:
            assert client.post('/v1/auth/login', json=dict(username=username, password=PASSWORD)).status_code == 200
        assert {case['id'] for case in admin.get('/v1/cases').json()} == {case_id}
        assert admin.get('/v1/cases/' + case_id).status_code == 200
        assert alice.get('/v1/cases').json() == []
        assert alice.get('/v1/cases/' + case_id).status_code == 404
        assert alice.get('/v1/cases/' + case_id + '/evidence').status_code == 404
        assert alice.get('/v1/cases/' + case_id + '/search?q=公开').status_code == 404


@pytest.mark.parametrize('owner', ['alice', 'disabled-admin'])
def test_sync_rejects_non_admin_or_disabled_owner(importer, workspace, admin_auth, repository, png, tmp_path, owner):
    auth, _ = admin_auth
    user = auth.create_user(CreateUserRequest(username=owner, password=PASSWORD, display_name=owner,
                                            role='admin' if owner == 'disabled-admin' else 'member'))
    if owner == 'disabled-admin':
        row = workspace.repo.get('auth_users', user.id)
        workspace.repo.put('auth_users', user.id, dict(row, enabled=False))
    rendered_sample(repository, png)
    before = snapshot(workspace)
    with pytest.raises(ValueError, match='enabled admin'):
        importer.sync(repository, workspace, owner, tmp_path / 'forbidden-report.json', apply=True)
    assert snapshot(workspace) == before


def test_empty_message_defer_version_is_visible_without_fabricated_messages(importer, workspace, admin_auth, repository, tmp_path):
    deferred = dict(id='q5_gap', status='defer', participants=[], conversations=[], messages=[],
                    limitations=['原文未公开聊天内容，不得补造对话'])
    alias = Path('datasets/v2.0.0/round_005/zh/q5_gap/case.json')
    write_json(repository / alias, deferred)
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'defer-report.json', apply=True)
    assert report['inventory_counts'] == {'sample': 1}
    assert report['messages'] == report['images'] == 0
    case_id = report['results'][0]['case_id']
    assert 'defer' in workspace.repo.get('cases', case_id)['description']
    assert workspace.repo.list('messages', case_id=case_id) == []
    assert workspace.repo.list('source_refs', case_id=case_id) == []
    assert workspace.repo.list('events', case_id=case_id) == []
    assert workspace.retriever.search(case_id, '聊天') == []
    evidence = workspace.evidence(case_id)
    assert len(evidence) == 2 and all(item['kind'] != 'image' for item in evidence)
    authored = next(item for item in evidence if item['filename'] == '作者对话稿（非原始聊天证据）.txt')
    assert json.loads(workspace.storage.verified_path(authored).read_text(encoding='utf-8'))['messages'] == []
    with TestClient(create_app(workspace.settings, workspace.repo)) as admin:
        assert admin.post('/v1/auth/login', json=dict(username='admin', password=PASSWORD)).status_code == 200
        assert {case['id'] for case in admin.get('/v1/cases').json()} == {case_id}
        assert admin.get('/v1/cases/' + case_id).status_code == 200


def test_identical_v3_material_in_two_collections_remains_two_versions(importer, workspace, admin_auth, repository, png, tmp_path):
    for version in ['v3.0.0', 'v3.0.1']:
        collection = repository / 'datasets' / version
        directory = collection / 'renders/scenario_1/unknownpage'
        write_json(collection / 'case_scope.json', [dict(case_id='scenario_1', title='同一校准素材')])
        write_lines(directory / 'messages.jsonl', [dict(id='same-message', sender_id='unknown', text='两集合相同消息')])
        (directory / 'page.png').write_bytes(png)
        write_json(directory / 'render_manifest.json', dict(pages=[dict(file='page.png', image_id='same-image', sha256=hashlib.sha256(png).hexdigest())]))
        write_lines(collection / 'source_refs.jsonl', [dict(conversation_id='scenario_1', variant='unknownpage', image_id='same-image', message_id='same-message', bbox=[10, 20, 110, 60])])
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'v3-collections-report.json', apply=True)
    assert report['inventory_counts'] == {'v3': 2} and report['case_versions'] == 2
    assert report['messages'] == report['images'] == 2
    cases = workspace.repo.list('cases')
    assert len({case['id'] for case in cases}) == 2
    assert {case['title'].split(']')[0] for case in cases} == {'[v3.0.0', '[v3.0.1'}
    image_paths = []
    image_hashes = []
    for case in cases:
        messages = workspace.repo.list('messages', case_id=case['id'])
        assert len(messages) == 1 and messages[0]['text'] == '两集合相同消息'
        image, = [item for item in workspace.evidence(case['id']) if item['kind'] == 'image']
        image_paths.append(image['storage_path'])
        image_hashes.append(image['sha256'])
        metadata = next(item for item in workspace.evidence(case['id']) if item['filename'] == '来源与版本说明.txt')
        details = json.loads(workspace.storage.verified_path(metadata).read_text(encoding='utf-8'))
        assert len(details['source_paths']) == 1
        assert '/' + details['collection'] + '/' in details['source_paths'][0]
    assert len(set(image_paths)) == 2 and len(set(image_hashes)) == 1


def test_orphan_render_archive_keeps_all_images_and_manifest_without_transcription(importer, workspace, admin_auth, repository, png, tmp_path):
    rendered_sample(repository, png)
    directory = repository / 'datasets/v2.0.0/round_004/zh/q5_0001/render.versions/archive_1'
    directory.mkdir(parents=True)
    second_png = (ROOT / 'fixtures/demo_private_lending/chat-2.png').read_bytes()
    originals = {'old-1.png': png, 'old-2.png': second_png}
    manifest = dict(images=[dict(path=name, sha256=hashlib.sha256(content).hexdigest(),
                                 boxes=[dict(message_id='unmatched-old-revision', bbox_pixels=[10, 20, 100, 40])])
                            for name, content in originals.items()])
    for name, content in originals.items():
        (directory / name).write_bytes(content)
    write_json(directory / 'render.json', manifest)
    assert not (directory / 'case.json').exists()
    report = importer.sync(repository, workspace, 'admin', tmp_path / 'orphan-report.json', apply=True)
    assert report['inventory_counts'] == {'render': 1, 'sample': 1}
    orphan_id = next(row['case_id'] for row in report['results'] if row['kind'] == 'render')
    items = workspace.evidence(orphan_id)
    images = [item for item in items if item['kind'] == 'image']
    assert len(images) == 2
    assert {workspace.storage.verified_path(item).read_bytes() for item in images} == set(originals.values())
    archived = next(item for item in items if item['filename'] == '历史渲染清单（非当前转录）.txt')
    assert json.loads(workspace.storage.verified_path(archived).read_text(encoding='utf-8')) == manifest
    assert workspace.repo.list('messages', case_id=orphan_id) == []
    assert workspace.repo.list('source_refs', case_id=orphan_id) == []
    with workspace.repo.engine.connect() as connection:
        assert connection.execute(text('SELECT COUNT(*) FROM search_index WHERE case_id=:case_id'), dict(case_id=orphan_id)).scalar_one() == 0


def test_new_source_alias_appends_provenance_without_overwriting_human_work(importer, workspace, admin_auth, repository, png, tmp_path):
    import asyncio

    original = '相同正文只形成一个来源案件。'
    source = dict(text=original, paragraphs=[dict(id='p1', text=original)], case_no='同文案号')
    first_alias = Path('datasets/v2.0.0/round_005/source_archive/a_source.json')
    second_alias = Path('datasets/v2.0.0/round_006/source_archive/z_alias.json')
    write_json(repository / first_alias, source)
    first = importer.sync(repository, workspace, 'admin', tmp_path / 'alias-initial.json', apply=True)
    source_id = first['results'][0]['case_id']
    item = workspace.upload(source_id, 'human-evidence.png', 'image/png', png)
    asyncio.run(workspace.perceive(source_id, adapter='manual', fixtures={item.id: [dict(text='人工保留的消息', speaker='人工确认的说话者', bbox=[10, 20, 110, 60])]}))
    case = dict(workspace.repo.get('cases', source_id), title='人工改过的标题', description='人工说明必须完整保留')
    workspace.repo.put('cases', source_id, case, case_id=source_id)
    review = dict(id='alias-human-review', case_id=source_id, target_id='manual-target', action='edited',
                  text='人工复核必须保留', reviewer='human-reviewer', reviewed_output_digest='human-digest')
    workspace.repo.put('review_decisions', review['id'], review, case_id=source_id, immutable=True)
    before = snapshot(workspace)
    old_evidence = workspace.evidence(source_id)
    old_metadata = next(row for row in old_evidence if row['filename'] == '来源与版本说明.txt')
    old_provenance = workspace.storage.verified_path(old_metadata).read_bytes()

    write_json(repository / second_alias, source)
    updated = importer.sync(repository, workspace, 'admin', tmp_path / 'alias-updated.json', apply=True)
    assert updated['case_versions'] == 1 and updated['result_counts'] == {'updated_provenance': 1}
    assert workspace.repo.get('cases', source_id) == case
    assert workspace.storage.verified_path(old_metadata).read_bytes() == old_provenance
    after = snapshot(workspace)
    for table in MODELS:
        if table != 'evidence_items':
            assert after[table] == before[table], table
    assert after['fts'] == before['fts']
    assert len(after['files']) == len(before['files']) + 1
    assert all(row in workspace.evidence(source_id) for row in old_evidence)
    provenance = [row for row in workspace.evidence(source_id) if row['filename'] == '来源与版本说明.txt']
    assert len(provenance) == 2
    new_metadata = next(row for row in provenance if row['id'] != old_metadata['id'])
    assert json.loads(workspace.storage.verified_path(new_metadata).read_text(encoding='utf-8'))['source_paths'] == [first_alias.as_posix(), second_alias.as_posix()]
    assert workspace.retriever.search(source_id, '人工')
    repeated = importer.sync(repository, workspace, 'admin', tmp_path / 'alias-repeated.json', apply=True)
    assert repeated['result_counts'] == {'existing': 1}
    assert snapshot(workspace) == after


@pytest.mark.parametrize('mutation', ['new_dataset_file', 'legacy_export', 'legacy_image'])
def test_preflight_rejects_file_set_and_legacy_changes(importer, workspace, admin_auth, repository, png, tmp_path, monkeypatch, mutation):
    rendered_sample(repository, png)
    legacy_image = repository / 'legacy-assets/chat.png'
    legacy_image.parent.mkdir(parents=True)
    legacy_image.write_bytes(png)
    legacy_export = repository / 'reports/admin_case_inventory_20261024/legacy-corpora.json'
    write_json(legacy_export, dict(validation_errors=[], cases={'legacy-1': dict(metadata={}, records=[], images=[dict(
        file=legacy_image.relative_to(repository).as_posix(), image_id='legacy-img', sha256=hashlib.sha256(png).hexdigest())])}))
    original_prepare = importer.prepare
    mutated = False

    def prepare_then_mutate(*args, **kwargs):
        nonlocal mutated
        prepared = original_prepare(*args, **kwargs)
        if not mutated:
            mutated = True
            if mutation == 'new_dataset_file':
                write_json(repository / 'datasets/new_during_preflight.json', dict(new=True))
            elif mutation == 'legacy_export':
                legacy_export.write_text(legacy_export.read_text(encoding='utf-8') + '\n ', encoding='utf-8')
            else:
                legacy_image.write_bytes(png + b'changed-during-preflight')
        return prepared

    monkeypatch.setattr(importer, 'prepare', prepare_then_mutate)
    before = snapshot(workspace)
    with pytest.raises(ValueError, match='changed during preflight'):
        importer.sync(repository, workspace, 'admin', tmp_path / 'mutation-report.json', apply=True)
    assert mutated
    assert snapshot(workspace) == before
    assert not (workspace.settings.data_dir / 'backups').exists()
