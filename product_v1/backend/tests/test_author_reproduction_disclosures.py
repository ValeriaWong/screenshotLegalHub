import pytest
from screenshotlegal.method_reproductions import METHOD_MODULES,method_module
from screenshotlegal.method_reproductions.catalog import method_metadata
from screenshotlegal.experiments.registry import CandidateRegistry

@pytest.mark.parametrize('method',list(METHOD_MODULES),ids=list(METHOD_MODULES.values()))
def test_original_task_and_adaptation_are_disclosed_without_claiming_paper_reproduction(method):
    module=method_module(method);meta=method_metadata(method);text=module.__doc__
    assert meta['original_paper_reproduced'] is False
    assert meta['author_code_status']==module.ADAPTATION_AUDIT['author_code_execution']
    assert '原论文与适配核查' in text
    assert '原 benchmark' in text or '原方法/benchmark' in text
    assert '如何适配' in text and '能否直接适配' in text and '尚未完成/阻塞' in text
    assert {p['paper_id'] for p in module.ORIGINAL_PAPER_CONTRACTS}=={p['paper_id'] for p in module.PAPER_REFERENCES}
    for contract in module.ORIGINAL_PAPER_CONTRACTS:
        assert all(contract[k] for k in ['task','input','output','benchmark','innovation','fit','source'])
        assert contract['source'].startswith('https://')
        assert contract['input'] in text and contract['output'] in text
    public=next(c for c in CandidateRegistry().public()['candidates'] if c['id']==method)
    assert public['original_paper_reproduced'] is False
    assert '原论文benchmark尚未复现' in public['paper_claim'] or '非单篇论文复现' in public['paper_claim']
