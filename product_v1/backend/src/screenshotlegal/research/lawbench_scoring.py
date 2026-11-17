"""LawBench official scorer integration; see paper/author_reproductions/lawbench/adapter.py.
The author benchmark has 20 legal text tasks. This product uses its unmodified
2-5 reading-comprehension character F1 only as a supplemental lexical measure.
KIE geometry is matched by our existing IoU scorer before comparing text fields;
this does not reproduce LawBench criminal NER or score screenshot localization.
Closed global VQA labels map in frozen order to original 1-2 MCQ A-D options.
No model request, no local weights, no expert legal quality inference.
"""
import os
from pathlib import Path
from . import benchmark_scoring as scoring
from screenshotlegal.method_reproductions.author_bridge import stream_author

ROOT=Path(__file__).resolve().parents[5]
VERSION='lawbench-text-supplement.v1'

async def official(tasks):
    python=ROOT/'paper/.author_envs/lawbench'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    driver=ROOT/'paper/author_reproductions/lawbench/adapter.py'
    if not python.is_file():raise ValueError('LawBench 独立环境未配置：paper/author_reproductions/lawbench/README.md')
    async def no_model(event):raise ValueError('LawBench scoring cannot request model inference')
    return await stream_author(python,driver,dict(tasks=tasks),no_model)

async def product(task,raw,target,*,threshold=.6):
    base=dict(method='b02_lawbench',paper_id='B02',scorer_version=VERSION,model_requests=0,
        local_model_inference=False,legal_accuracy=None,original_complete_benchmark=False,
        metric='official_2-5_rc_f1',scope='supplemental_lexical_overlap',score=None)
    if target is None:return dict(base,status='unscored_missing_reference')
    rows=[];bindings=[];author_task='2-5'
    try:
        if task['task_family']=='kie.extract':
            width,height=task['asset']['width'],task['asset']['height']
            reference=scoring.kie(target,width,height)
            prediction=scoring.kie(raw,width,height)
            matching=scoring.match(reference['conversation'],prediction['conversation'],threshold)
            for pair in matching['matches']:
                a=reference['conversation'][pair['gold']];b=prediction['conversation'][pair['prediction']]
                for field in ('timestamp','speaker','content','image','transfer','file'):
                    if not isinstance(a[field],str):continue
                    rows.append(dict(origin_prompt='截图中已匹配消息的原文字段：'+field,prediction=b[field] or '',refr='回答:'+a[field]))
                    bindings.append(dict(field=field,gold_message=pair['gold'],predicted_message=pair['prediction'],iou=pair['iou']))
            base.update(geometry_match=matching,aggregation='macro over non-null reference text fields of geometry-matched messages only',
                caveat='Unmatched messages remain in the existing detection score; lexical similarity does not validate identity, currency, geometry, or evidence truth.')
        else:
            if task.get('region_id') or not isinstance(target,str):
                return dict(base,status='unsupported_task',reason='Whole-image VQA with a frozen string reference is required.')
            value=scoring.parse(raw).get('answer')
            if value is not None and not isinstance(value,str):raise ValueError('VQA answer must be text or null')
            question=(task.get('input') or {}).get('question','')
            if task.get('answer_kind')=='categorical':
                labels=task.get('allowed_values') or []
                if not 2<=len(labels)<=4 or not all(isinstance(v,str) for v in labels) or len(set(labels))!=len(labels) or target not in labels:
                    return dict(base,status='unsupported_task',reason='Choice adaptation needs 2-4 distinct frozen allowed labels containing the reference.')
                mapping=dict(zip(labels,'ABCD'))
                author_task='1-2'
                rows.append(dict(origin_prompt=question+'\n'+'\n'.join(mapping[label]+'. '+label for label in labels),
                    prediction=mapping.get(value,'未返回有效选项'),refr='正确答案：'+mapping[target]+'。'))
                bindings.append(dict(field='answer',task_id=task.get('task_id'),label_to_option=mapping,raw_predicted_label=value))
                base.update(metric='official_1-2_choice_accuracy',scope='frozen_label_to_option_domain_adaptation',
                    caveat='Two-to-four screenshot labels map to author A-D options; task content differs from legal knowledge MCQ. Invalid labels are abstentions; this is not legal accuracy.')
            elif task.get('answer_kind') in ('text','filename'):
                rows.append(dict(origin_prompt=question,prediction=value or '',refr='回答:'+target))
                bindings.append(dict(field='answer',task_id=task.get('task_id')))
            else:return dict(base,status='unsupported_task',reason='Open legal analysis, identity, amount and set targets are not compatible with these author metrics.')
    except (ValueError,TypeError,KeyError,OverflowError) as error:
        return dict(base,status='format_failure',reason=str(error))
    if not rows:return dict(base,status='unscored_no_comparable_fields')
    # Keep per-field scores inspectable while using the exact original task scorer
    # and CLI for every field. One bounded child process, zero model requests.
    execution=await official({author_task:rows})
    return dict(base,status='scored',score=execution['raw_scores'][author_task]['score'],
        original_scorer_input={author_task:rows},bindings=bindings,author_execution=execution)
