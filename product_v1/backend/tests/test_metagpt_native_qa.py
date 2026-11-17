"""Original QaEngineer generated-test execution/repair, using zero paid calls."""
import json
from uuid import uuid4
from pathlib import Path
import pytest
from screenshotlegal.method_reproductions.author_bridge import REPO,stream_author

@pytest.mark.parametrize('case',['pass','model_false_pass','repair_test','unexecuted_rewrite'])
async def test_original_native_qa_runs_python_and_separates_reported_from_actual(tmp_path,case):
    runtime=REPO/'reports/author_expansion_20261029/native_qa_tests'/(tmp_path.name+'-'+uuid4().hex)/case
    request=dict(runtime=str(runtime),mode='native_qa_resume',rounds=3 if case=='unexecuted_rewrite' else 8,
        files={'snake_game/snake_game/calc.py':'def double(value):\n    return value * 2\n'},
        design_message=dict(role='Architect',content='Python package name snake_game',structured={'Python package name':'snake_game'}))
    wrong=case in ['model_false_pass','repair_test']
    def script(bad):
        return "import unittest\nfrom calc import double\nclass TestDouble(unittest.TestCase):\n    def test_double(self):\n        self.assertEqual(double(2), "+('999' if bad else '4')+")\nif __name__ == '__main__':\n    unittest.main()\n"
    calls=[];tools=[];run_calls=0
    async def handle(event):
        nonlocal run_calls
        if event['event']=='tool':tools.append(event);return dict(ok=True)
        calls.append(event)
        if event['stage'].startswith('WriteTest.'):
            return dict(raw='## test_calc.py\n```python\n'+script(wrong)+'```')
        if event['stage'].startswith('RunCode.'):
            run_calls+=1
            if case in ['repair_test','unexecuted_rewrite'] and run_calls==1:
                return dict(raw='## instruction:\nThe test expects 999 instead of double(2)=4. Fix test assertion.\n## File To Rewrite:\ntest_calc.py\n## Status:\nFAIL\n## Send To:\nQaEngineer')
            return dict(raw='## instruction:\nReviewed test process output.\n## File To Rewrite:\ntest_calc.py\n## Status:\nPASS\n## Send To:\nNoOne')
        if event['stage'].startswith('DebugError.'):
            return dict(raw='## test_calc.py\n```python\n'+script(case=='unexecuted_rewrite')+'```')
        raise AssertionError(event['stage'])
    result=await stream_author(REPO/'paper/.author_envs/metagpt/Scripts/python.exe',REPO/'paper/author_reproductions/metagpt/native_qa_adapter.py',request,handle,python_utf8=True)
    (runtime/'probe_result.json').write_text(json.dumps(dict(result=result,tools=tools,calls=calls),ensure_ascii=False,indent=2),encoding='utf-8')
    checks=result['checks'];assert checks['original_qa_role_scheduled'] and checks['development_source_unchanged']
    assert result['source_commit']=='820fee5df6697b4e85e90c787940de111c3ed05b'
    assert checks['all_generated_tests_passed']==(case not in ['model_false_pass','unexecuted_rewrite'])
    executions=[t['result'] for t in tools if t['action']=='metagpt.qa_execution']
    assert all(e['tests_ran']==1 for e in executions)
    assert any(t['action']=='metagpt.published_message' and t['result']['send_to']=='QaEngineer' for t in tools)
    if case=='repair_test':
        assert [e['returncode'] for e in executions]==[1,0]
        assert any(c['stage'].startswith('DebugError.') for c in calls)
    elif case=='unexecuted_rewrite':
        assert executions[0]['returncode']==0
        assert checks['final_version_executed']['tests/test_calc.py'] is False
        assert len(executions)==1
    elif case=='model_false_pass':assert executions[0]['returncode']==1
    else:assert executions[0]['returncode']==0
    assert result['full_autonomous_development_repair_supported'] is False
