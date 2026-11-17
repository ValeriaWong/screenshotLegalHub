"""RAGChecker author evaluator adaptation for frozen product attempts.
Source/innovation/original I/O and fidelity: ../method_reproductions/b15_ragchecker.py.
Text VQA uses ONLY its actual frozen predicted-KIE input as retrieved context.
KIE needs a frozen human transcript and uses original overall metrics only; it cannot
score geometry or invent a transcript from another model. Primary scores stay intact.
Remote judge calls must come from the caller's durable per-paper budgeted raw_call.
"""
import json
from screenshotlegal.method_reproductions.b15_ragchecker import evaluate
from . import benchmark_scoring as scoring
from .contracts import digest
VERSION='ragchecker.author-api.v2'

async def product(task,raw,target,raw_call,author_record=None):
    base=dict(method='b15_ragchecker',paper_id='B15',scorer_version=VERSION,score=None,metrics=None,
        original_complete_benchmark=False,local_model_inference=False,expert_legal_accuracy=None)
    if target is None:return dict(base,status='unscored_missing_reference',reason='No frozen reference; no model call was made.')
    if task['task_family']=='kie.extract':
        if not isinstance(target,dict) or 'human_transcript' not in target:
            return dict(base,status='unscored_missing_transcript',reason='KIE needs a frozen human_transcript; no surrogate OCR/model transcript is fabricated.')
        prediction=scoring.kie(raw,task['asset']['width'],task['asset']['height'])
        fields=('timestamp','speaker','content','image','transfer','file')
        response=json.dumps([{k:m.get(k) for k in fields} for m in prediction['conversation']],ensure_ascii=False)
        reference=target['human_transcript']
        if not isinstance(reference,str):reference=json.dumps(reference,ensure_ascii=False)
        query='复述截图中的消息原文、说话人和时间；仅比较转录文本，不评测坐标或事实真伪。'
        contexts=[];metrics=['overall_metrics'];mapping='human transcript vs extracted text fields only; no geometry and no retrieved-context metrics'
    else:
        inp=task['input']
        if task.get('region_id') or inp.get('track')!='vqa_predicted_text':
            return dict(base,status='unsupported_task',reason='Only global VQA with its original frozen predicted-KIE context is supported; pixels are not fabricated as retrieved text.')
        if not isinstance(target,str):return dict(base,status='unsupported_reference',reason='VQA requires an existing frozen string reference.')
        predicted=inp['upstream_prediction']
        if digest(predicted)!=inp['upstream_sha256']:raise ValueError('Frozen KIE prediction hash differs')
        answer=scoring.parse(raw).get('answer')
        if answer is None:return dict(base,status='unscored_abstention',reason='Null answer is retained; no factual answer is invented.')
        if not isinstance(answer,str):return dict(base,status='unsupported_answer',reason='This adaptation requires a textual/categorical answer.')
        response=answer;reference=target;query=inp['question'];metrics=['all_metrics']
        mapping='original answer field / frozen reference text; full original frozen KIE input context'
        if task.get('answer_kind')=='categorical':
            evidence=scoring.parse(raw).get('evidence')
            if not isinstance(evidence,(str,list)) or not evidence or isinstance(evidence,list) and not all(isinstance(v,str) for v in evidence):
                return dict(base,status='unscored_no_evidence_text',reason='A classification label is not a source fact; its actual evidence text is required for faithfulness.')
            response=evidence if isinstance(evidence,str) else '\n'.join(evidence)
            reference='';metrics=['faithfulness']
            query='仅核对回答附带的证据文字是否受实际输入支持，不判断分类标签。原问题：'+query
            mapping='categorical answer is not a factual claim; evaluate original evidence text against frozen KIE only; no ground-truth-dependent metrics'
        contexts=[dict(doc_id='kie:'+inp['upstream_sha256'],text=json.dumps(predicted,ensure_ascii=False,sort_keys=True))]

    request=dict(results=[dict(query_id=task['task_id'],query=query,gt_answer=reference,response=response,retrieved_context=contexts)])
    execution=await evaluate(request,raw_call,author_record,metrics)
    return dict(base,status='scored',metrics=execution['output']['metrics'],original_scorer_input=request,
        adaptation_mapping=mapping,ground_truth_used=metrics!=['faithfulness'],author_execution=execution,
        caveat='LLM-judged text entailment relative to predicted contexts/reference; not OCR/pixel accuracy, human/legal correctness or original paper scores.')
