"""User resource-boundary regression: batch setup must not load local weights."""
import importlib.util,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('resource_setup_test',ROOT/'paper/author_reproductions/setup_environment.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

def test_all_only_checks_lightweight_environments(tmp_path,monkeypatch):
    root=tmp_path;here=root/'paper/author_reproductions';here.mkdir(parents=True)
    (here/'sources.lock.json').write_text('[]',encoding='utf-8')
    config=dict(light=dict(folder='paper/.author_envs/light',sources=[]),embedding=dict(folder='paper/.author_envs/embedding',sources=[],models=True),ocr=dict(folder='paper/.author_envs/ocr',sources=[],model_lock='missing.json'))
    env=root/'paper/.author_envs/light/Scripts';env.mkdir(parents=True);(env/'python.exe').touch()
    (here/'light').mkdir();(here/'light/requirements.lock.txt').write_text('# no extra dependencies',encoding='utf-8')
    calls=[]
    def check(args,**kwargs):calls.append(args);return json.dumps(dict(python='3.12.15',packages_checked=0,mismatches={}))
    monkeypatch.setattr(setup,'REPO',root);monkeypatch.setattr(setup,'CONFIG',config)
    # sources.lock lookup is relative to __file__, so point the audit module at our fixture.
    monkeypatch.setattr(setup,'__file__',str(here/'setup_environment.py'))
    monkeypatch.setattr(setup.subprocess,'check_output',check)
    monkeypatch.setattr(sys,'argv',['setup_environment.py','all','--check'])
    setup.main()
    assert len(calls)==1 and 'light' in calls[0][0]
    assert not (here/'embedding/environment_state.json').exists()
    assert not (here/'ocr/environment_state.json').exists()

@pytest.mark.parametrize('name',['raptor','lightrag','paddleocr_vl'])
def test_explicit_local_install_is_deferred_before_subprocess(name,monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('no install/download should start')
    monkeypatch.setattr(setup.subprocess,'run',forbidden)
    monkeypatch.setattr(sys,'argv',['setup_environment.py',name])
    with pytest.raises(SystemExit) as error:setup.main()
    assert error.value.code==2

@pytest.mark.parametrize('tampered',[False,True])
def test_fixed_git_blob_downloads_are_hash_checked_without_git_checkout(tmp_path,monkeypatch,tampered):
    import hashlib
    here=tmp_path/'paper/author_reproductions';here.mkdir(parents=True)
    folder=tmp_path/'paper/upstream_sources/original';folder.mkdir(parents=True)
    expected=b'original source bytes';(folder/'core.py').write_bytes(b'changed' if tampered else expected)
    entry=dict(name='original',repository='https://github.com/example/original',commit='fixed-commit',local_path='paper/upstream_sources/original',retrieval='verified_fixed_commit_download',files={'core.py':hashlib.sha256(expected).hexdigest()})
    (here/'sources.lock.json').write_text(json.dumps([entry]),encoding='utf-8')
    env=tmp_path/'paper/.author_envs/original/Scripts';env.mkdir(parents=True);(env/'python.exe').touch()
    (here/'original').mkdir();(here/'original/requirements.lock.txt').write_text('# no dependencies',encoding='utf-8')
    monkeypatch.setattr(setup,'REPO',tmp_path);monkeypatch.setattr(setup,'__file__',str(here/'setup_environment.py'))
    monkeypatch.setattr(setup,'CONFIG',dict(original=dict(folder='paper/.author_envs/original',sources=['original'])))
    def check(args,**kwargs):
        assert args[0]!='git'
        return json.dumps(dict(python='3.11.0',packages_checked=0,mismatches={}))
    monkeypatch.setattr(setup.subprocess,'check_output',check)
    monkeypatch.setattr(sys,'argv',['setup_environment.py','original','--check'])
    if tampered:
        with pytest.raises(ValueError,match='Pinned source missing/changed'):setup.main()
    else:
        setup.main()
        report=json.loads((here/'original/environment_state.json').read_text(encoding='utf-8'))
        assert report['sources'][0]['retrieval']=='verified_fixed_commit_download'
