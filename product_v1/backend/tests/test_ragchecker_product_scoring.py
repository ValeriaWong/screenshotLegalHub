"""RAGChecker product mapping, reference honesty, binding and immutable supplement."""
import copy,json
import pytest
from screenshotlegal.research.ragchecker_scoring import product
from screenshotlegal.research.contracts import digest
from screenshotlegal.research.benchmark import Benchmark
from screenshotlegal.research.store import Store
from screenshotlegal.research import benchmark_scoring

async def forbidden(*args):raise AssertionError('No judge request is permitted here')

def task():
    pred=dict(dialog_name=None,conversation=[dict(speaker='right',content='你好',timestamp=None)])
    return dict(task_id='task',task_family='vqa.categorical',input=dict(track='vqa_predicted_text',question='对话属于哪个类别？',upstream_prediction=pred,upstream_sha256=digest(pred),upstream_attempt_id='kie'))

async def test_vqa_passes_actual_frozen_context_and_keeps_reference_separate():
    calls=[]
    async def raw(stage,messages,parameters):
        calls.append((stage,messages))
        return dict(raw='("对话", "类别", "non_legal_dialog")' if stage.startswith('extract.') else 'Entailment')
    t=task();result=await product(t,'{"answer":"non_legal_dialog"}','non_legal_dialog',raw)
    assert result['status']=='scored'
    row=result['original_scorer_input']['results'][0]
    assert row['gt_answer']=='non_legal_dialog' and row['response']=='non_legal_dialog'
    assert json.loads(row['retrieved_context'][0]['text'])==t['input']['upstream_prediction']
    assert len(row['retrieved_context'])==1 and len(calls)==6
    assert result['metrics']['overall_metrics']['f1']==100.
    assert result['expert_legal_accuracy'] is None

@pytest.mark.parametrize('kind',['missing_target','kie_missing_transcript','image_vqa','abstention'])
async def test_incompatible_or_missing_reference_never_fabricates_a_score(kind):
    t=task();target='non_legal_dialog';raw='{"answer":"non_legal_dialog"}'
    if kind=='missing_target':target=None
    if kind=='kie_missing_transcript':t['task_family']='kie.extract';target={}
    if kind=='image_vqa':t['input']['track']='vqa_image_full'
    if kind=='abstention':raw='{"answer":null}'
    result=await product(t,raw,target,forbidden)
    assert result['status']!='scored' and result['metrics'] is None and result['score'] is None

async def test_modified_frozen_kie_rejected_before_paid_call():
    t=task();t['input']['upstream_prediction']['conversation'][0]['content']='篡改'
    with pytest.raises(ValueError,match='hash differs'):await product(t,'{"answer":"non_legal_dialog"}','non_legal_dialog',forbidden)

@pytest.mark.parametrize('upstream_image',['image','other'])
async def test_benchmark_dispatch_keeps_primary_score_and_reuses_completed_supplement(tmp_path,upstream_image):
    store=Store(tmp_path);owner='owner';t=task();t['asset']=dict(sha256='image');before=dict(id='primary',attempt_id='answer',scorer_version=benchmark_scoring.VERSION,target_snapshot='non_legal_dialog',reference_status='legacy_unverified',result=dict(score=1))
    with store.tx() as db:
        store.put('benchmark.run',dict(id='run',dataset_id='dataset',tasks=[t]),owner,db)
        store.put('benchmark.attempt',dict(id='kie',status='completed',task_family='kie.extract',image_sha256=upstream_image,parsed=t['input']['upstream_prediction']),owner,db)
        store.put('benchmark.attempt',dict(id='answer',status='completed',run_id='run',task_id='task',image_sha256='image',input_hash=digest(t['input']),response=dict(raw='{"answer":"non_legal_dialog"}')),owner,db)
        store.put('benchmark.score',before,owner,db)
    async def raw(stage,messages,parameters):return dict(raw='("对话", "类别", "non_legal_dialog")' if stage.startswith('extract.') else 'Entailment')
    benchmark=Benchmark(store);p=dict(idempotency_key='once')
    if upstream_image!='image':
        with pytest.raises(ValueError,match='冻结上游KIE'):
            await benchmark.ragchecker_score(owner,'answer',p,forbidden)
        assert not store.list('benchmark.ragchecker_score',owner)
        store.close();return
    first=await benchmark.ragchecker_score(owner,'answer',p,raw)
    again=await benchmark.ragchecker_score(owner,'answer',p,forbidden)
    assert first==again and first['reference_status']=='legacy_unverified'
    assert store.get('benchmark.score','primary',owner)==before
    assert len(store.list('benchmark.ragchecker_score',owner))==1
    assert first['result']['status']=='scored'
    store.close()

async def test_kie_human_transcript_scores_text_only_with_original_overall_metrics():
    t=dict(task_id='kie-task',task_family='kie.extract',asset=dict(width=100,height=100))
    raw=json.dumps(dict(dialog_name=None,conversation=[dict(speaker='right',content='你好',timestamp=None,image=None,transfer=None,file=None,message_bbox=[1,2,20,30])]),ensure_ascii=False)
    calls=[]
    async def judge(stage,messages,parameters):
        calls.append(stage)
        return dict(raw='("right", "说", "你好")' if stage.startswith('extract.') else 'Entailment')
    result=await product(t,raw,dict(human_transcript='right说：你好'),judge)
    assert result['status']=='scored'
    assert len(calls)==4 and all(not s.startswith('check.retrieved') for s in calls)
    assert result['metrics']['overall_metrics']['f1']==100.
    assert not result['metrics']['retriever_metrics'] and not result['metrics']['generator_metrics']
    row=result['original_scorer_input']['results'][0]
    assert row['retrieved_context']==[] and 'message_bbox' not in row['response']

async def test_categorical_label_is_not_a_retrieved_fact_only_evidence_is_checked():
    t=task();t['answer_kind']='categorical';calls=[]
    async def judge(stage,messages,parameters):
        calls.append(stage)
        assert not stage.startswith('extract.gt_answer')
        return dict(raw='("right", "说", "你好")' if stage.startswith('extract.') else 'Entailment')
    result=await product(t,'{"answer":"non_legal_dialog","evidence":["你好"]}','non_legal_dialog',judge)
    assert result['status']=='scored' and result['ground_truth_used'] is False
    assert len(calls)==2 and result['metrics']['generator_metrics']['faithfulness']==100.
    assert not result['metrics']['overall_metrics'] and not result['metrics']['retriever_metrics']
    row=result['original_scorer_input']['results'][0]
    assert row['gt_answer']=='' and row['response']=='你好'
