"""LegalBench author prompt/evaluation protocol checks; fixtures are not model scores."""
import pytest
from screenshotlegal.method_reproductions.author_bridge import REPO,stream_author
from screenshotlegal.method_reproductions.b04_legalbench import score
DRIVER=REPO/'paper/author_reproductions/legalbench/product_adapter.py'
PYTHON=REPO/'paper/.author_envs/legalbench/Scripts/python.exe'

async def forbidden(event):raise AssertionError('No model call during preparation/scoring')

async def test_original_balanced_accuracy_is_not_plain_accuracy_and_normalizes_punctuation():
    result=await score([dict(id='imbalanced',predictions=['a','a','a','a'],references=['a','a','a','b']),dict(id='normalization',predictions=[' YES. ','No!'],references=['yes','no'])])
    assert result['output'][0]['score']==.5
    assert result['output'][1]['score']==1.
    assert result['model_requests']==0 and result['local_model_inference'] is False

async def test_all_original_template_declarations_and_native_protocols_execute_with_oracle_fixture():
    prepared=await stream_author(PYTHON,DRIVER,dict(mode='prepare'),forbidden,python_utf8=True)
    assert len(prepared['template_checks'])==162
    assert all(r['base_template_exists'] and r['evaluation_declared'] for r in prepared['template_checks'])
    lookup={prompt:target for g in prepared['groups'] for prompt,target in zip(g['prompts'],g['targets'])}
    calls=[];tools=[]
    async def oracle(event):
        if event['event']=='tool':tools.append(event);return dict(ok=True)
        calls.append(event)
        return dict(raw=lookup[event['messages'][0]['content']])
    request=dict(mode='native',frozen_groups=prepared['groups'])
    result=await stream_author(PYTHON,DRIVER,request,oracle,python_utf8=True)
    checks=result['checks']
    assert checks['groups']==12 and checks['distinct_tasks']==11
    assert checks['scored_groups']==11 and checks['manual_groups']==1
    assert len(calls)==checks['model_requests']==sum(len(g['prompts']) for g in prepared['groups'])
    assert checks['no_neural_model_modules'] and checks['no_test_answer_placeholder']
    assert len(tools)==12
    manual=next(r for r in result['output']['task_results'] if r['task']=='rule_qa')
    assert manual['score'] is None and manual['status']=='unscored_original_manual_task'
    shadow=next(r for r in result['output']['task_results'] if r['task']=='successor_liability')
    assert shadow['original_dispatch_shadowed'] is True
    assert result['original_complete_benchmark'] is False

async def test_frozen_native_source_inputs_cannot_be_replaced_before_model_call():
    with pytest.raises(ValueError,match='frozen selected tasks'):
        await stream_author(PYTHON,DRIVER,dict(mode='native',frozen_groups=[]),forbidden,python_utf8=True)
