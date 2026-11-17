"""The user-authorized 100 supplier requests are scoped per paper across tracks."""
import copy
from types import SimpleNamespace
import pytest
from test_research_products import lab
from test_accounts_ingestion import accounts
from screenshotlegal.research.gateway import ModelFailure
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('per_paper_runner',Path(__file__).resolve().parents[3]/'paper/author_reproductions/run_per_paper_validation.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class Configuration:
    def get(self,*args):return dict(enabled=True,allow_external_egress=True)

@pytest.mark.parametrize('failure',[False,True])
async def test_100_includes_history_failures_and_cannot_reset_at_new_request(lab,tmp_path,monkeypatch,failure):
    monkeypatch.setattr(runner,'OUT',tmp_path)
    gateway=runner.PaperGateway(lab.store,SimpleNamespace(),Configuration(),'alice',100,{'A02':99})
    gateway.paper='A02';calls=[]
    async def transport(*args):
        calls.append(args)
        if failure:raise ModelFailure('network','fixture network error')
        return dict(raw='ok',usage=dict(prompt_tokens=1,completion_tokens=1),cost_estimate=0)
    gateway._call=transport
    model=dict(config_id='scripted',parameters={})
    if failure:
        with pytest.raises(ModelFailure,match='fixture'):await gateway.call('alice',model,[],'fixture','one')
    else:await gateway.call('alice',model,[],'fixture','one')
    assert gateway.count('A02')==100 and len(calls)==1
    with pytest.raises(ModelFailure,match='100-request'):await gateway.call('alice',model,[],'fixture','two')
    assert len(calls)==1 and len(lab.store.list('author.paper_request','alice'))==1
    if not failure:
        await gateway.call('alice',model,[],'fixture','one')
        assert len(calls)==1
    else:
        with pytest.raises(ModelFailure,match='Previous'):await gateway.call('alice',model,[],'fixture','one')
    # The next paper has its own allowance; starting a new track doesn't reset A02.
    gateway.paper='A01'
    if failure:
        with pytest.raises(ModelFailure):await gateway.call('alice',model,[],'fixture','three')
    else:await gateway.call('alice',model,[],'fixture','three')
    assert gateway.count('A01')==1 and gateway.count('A02')==100
    assert len(calls)==2

async def test_native_resume_keeps_paper_namespace_and_reuses_exact_completed_request(lab,tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'OUT',tmp_path)
    gateway=runner.PaperGateway(lab.store,SimpleNamespace(),Configuration(),'alice',100,{'L09':8})
    gateway.paper='L09';calls=[]
    async def transport(*args):
        calls.append(args);return dict(raw='saved',usage=dict(prompt_tokens=1,completion_tokens=1),cost_estimate=0)
    gateway._call=transport;model=dict(config_id='scripted',parameters={});messages=[dict(role='user',content='frozen SCALE issue prompt')]
    original=runner.native_request_id('frozen-plan','L09','issues.1_PROTOCOL_1.0')
    assert original=='frozen-plan.L09.native.issues.1_PROTOCOL_1.0'
    await gateway.call('alice',model,messages,'native_author_L09',original)
    resumed=runner.native_request_id('frozen-plan','L09','issues.1_PROTOCOL_1.0')
    assert (await gateway.call('alice',model,messages,'native_author_L09',resumed))['raw']=='saved'
    assert len(calls)==1 and gateway.count('L09')==9
    assert lab.store.list('author.paper_request','alice')[0]['paper_id']=='L09'
    with pytest.raises(ValueError,match='input differs'):
        await gateway.call('alice',model,[dict(role='user',content='changed prompt')],'native_author_L09',resumed)
    assert len(calls)==1
