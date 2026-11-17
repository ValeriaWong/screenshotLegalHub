"""Original RAGChecker + RefChecker formula/control-flow verification; no paid calls."""
import json
import pytest
from screenshotlegal.method_reproductions.b15_ragchecker import evaluate

@pytest.mark.parametrize('label',['Entailment','Neutral'])
async def test_original_extraction_checking_and_metric_formulas(label):
    calls=[];tools=[]
    async def raw(stage,messages,parameters):
        calls.append(dict(stage=stage,messages=messages,parameters=parameters))
        return dict(raw='("Alice", "is in", "Paris")' if stage.startswith('extract.') else label)
    async def record(action,result):tools.append(dict(action=action,result=result))
    request=dict(results=[dict(query_id='fixture',query='Where is Alice?',gt_answer='Alice is in Paris.',response='Alice is in Paris.',retrieved_context=[dict(doc_id='d',text='Alice is in Paris.')])])
    result=await evaluate(request,raw,record)
    assert len(calls)==6
    assert {c['stage'].rsplit('.',1)[0] for c in calls}=={'extract.response','extract.gt_answer','check.answer2response','check.response2answer','check.retrieved2answer','check.retrieved2response'}
    row=result['output']['results'][0]
    assert row['response_claims']==[['Alice','is in','Paris']]
    assert row['gt_answer_claims']==[['Alice','is in','Paris']]
    assert row['retrieved2response']==[[label]]
    expected=1. if label=='Entailment' else 0.
    assert row['metrics']['precision']==expected and row['metrics']['recall']==expected
    assert row['metrics']['f1']==expected and row['metrics']['faithfulness']==expected
    assert row['metrics']['claim_recall']==expected and row['metrics']['context_precision']==expected
    assert row['metrics']['hallucination']==1.-expected
    assert len(row['metrics'])==11
    assert result['checks']['local_model_inference'] is False
    assert result['source_commits']['ragchecker']=='6091f08c00e676e87a970f2aeb4a23a484746348'
    assert any(t['action']=='ragchecker.original_result' for t in tools)
    assert 'Extract' in calls[0]['messages'][0]['content'] or any(c['stage'].startswith('extract.') for c in calls)

async def test_failure_is_one_request_no_implicit_retry():
    calls=[]
    async def fail(stage,messages,parameters):calls.append(stage);raise RuntimeError('controlled provider failure')
    request=dict(results=[dict(query_id='fixture',query='Where?',gt_answer='Paris.',response='Paris.',retrieved_context=[dict(doc_id='d',text='Paris.')])])
    with pytest.raises(RuntimeError,match='controlled provider failure'):await evaluate(request,fail)
    assert len(calls)==1
