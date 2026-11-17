"""LegalBench official normalized balanced exact-match supplement.
Source/fidelity: method_reproductions/b04_legalbench.py. Original input: legal
labels/task answers; product adaptation uses frozen categorical VQA labels and
text values of existing geometry-matched KIE messages. This is a lexical metric,
not original legal-task accuracy or a geometry/identity/OCR score. No model calls.
"""
from screenshotlegal.method_reproductions.b04_legalbench import score as official
from . import benchmark_scoring as scoring
VERSION='legalbench.balanced-exact-match.v1'

async def product(task,raw,target,*,threshold=.6):
    base=dict(method='b04_legalbench',paper_id='B04',scorer_version=VERSION,metric='original_normalized_exact_match_balanced_accuracy',
        score=None,model_requests=0,local_model_inference=False,original_complete_benchmark=False,expert_legal_accuracy=None)
    if target is None:return dict(base,status='unscored_missing_reference')
    predictions=[];references=[];bindings=[]
    if task['task_family']=='kie.extract':
        width,height=task['asset']['width'],task['asset']['height']
        gold=scoring.kie(target,width,height);prediction=scoring.kie(raw,width,height)
        matching=scoring.match(gold['conversation'],prediction['conversation'],threshold)
        for pair in matching['matches']:
            a=gold['conversation'][pair['gold']];b=prediction['conversation'][pair['prediction']]
            for field in ('timestamp','speaker','content','image','transfer','file'):
                if not isinstance(a[field],str):continue
                references.append(a[field]);predictions.append(b[field] or '')
                bindings.append(dict(field=field,gold_message=pair['gold'],predicted_message=pair['prediction'],iou=pair['iou']))
        base.update(scope='lexical values in geometry-matched messages only',geometry_match=matching,
            caveat='Macro recall over distinct reference text values; not message accuracy, speaker identity, missing-message recall or pixel localization.')
    else:
        if task.get('region_id') or task.get('answer_kind')!='categorical' or not isinstance(target,str):
            return dict(base,status='unsupported_task',reason='Only whole-image/text global VQA categorical labels are adapted here.')
        labels=task.get('allowed_values') or []
        if target not in labels:return dict(base,status='unsupported_reference',reason='Reference must belong to the frozen allowed label set.')
        value=scoring.parse(raw).get('answer')
        if value is not None and not isinstance(value,str):return dict(base,status='format_failure',reason='Categorical answer must be text or null.')
        predictions=[value or ''];references=[target];bindings=[dict(field='answer',task_id=task['task_id'])]
        base.update(scope='frozen categorical label supplement',expected_labels=labels,
            caveat='Balanced accuracy averages only reference classes present in this scored set; one example cannot estimate all-class or legal accuracy.')
    if not references:return dict(base,status='unscored_no_comparable_fields')
    groups=[dict(id=task['task_id'],predictions=predictions,references=references)]
    execution=await official(groups);entry=execution['output'][0]
    return dict(base,status='scored',score=entry['score'],examples=entry['examples'],reference_classes_present=entry['reference_classes'],
        original_scorer_input=groups,bindings=bindings,author_execution=execution)
