"""B04 LegalBench — Guha et al. (2023), arXiv:2308.11462.
Paper https://arxiv.org/abs/2308.11462; author HazyResearch/legalbench
@ b46bf4ffae90524b2b72aaa30e7745fe9db64481; original HF data
nguha/legalbench @ daec8237410aa23e3faf4bc41ad8b3a7e1696826.
Original method/innovation: 162 collaboratively curated legal tasks with few-shot
prompts, reasoning categories and task-specific metrics. Original input is task
text/question and supplied demonstrations; output is labels, extracted terms,
citations, numeric amounts or free-text answers. The benchmark is not an agent.
Fidelity: original utils.generate_prompts and the complete original evaluation.py
execute unchanged. The author notebook demonstrates random predictions, not an LLM
controller; our explicit remote API runner supplies actual model generations.
Native scope: representatives of original metadata groups plus original application
prompt and every distinct evaluator family/manual status; not all test examples.
Product: original normalized exact-match balanced accuracy as a supplemental metric
for frozen global VQA labels / geometry-matched KIE text fields, not legal accuracy.
No local weights, training, corpus/tokenizer downloads or GPU. Rule-QA stays manual.
Known original issues (successor dispatch shadowing, numeric punctuation parsing and
SSLA FP accounting) are preserved and disclosed, not silently corrected as scores.
"""
import contextlib,importlib.util,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import source,call,emit,tool


def load():
    folder,pin=source('legalbench');data,dpin=source('legalbench_data')
    modules={}
    for name in ['utils','evaluation','tasks']:
        spec=importlib.util.spec_from_file_location('legalbench_author_'+name,folder/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules[name]=module
    return folder,data,modules,dict(code=pin['commit'],data=dpin['commit'])


def prepare(folder,data,modules):
    import pandas as pd
    specs=[('issue_spotting','learned_hands_consumer','base_prompt.txt','classes'),
        ('rule_recall','citation_prediction_classification','base_prompt.txt','classes'),
        ('rule_conclusion','abercrombie','base_prompt.txt','classes'),
        ('rule_application','abercrombie','application_prompt.txt','classes'),
        ('interpretation','contract_nli_confidentiality_of_agreement','base_prompt.txt','classes'),
        ('rhetoric','definition_classification','base_prompt.txt','classes'),
        ('open_citation','citation_prediction_open','base_prompt.txt','first_two'),
        ('extraction','definition_extraction','base_prompt.txt','first_two'),
        ('numeric','sara_numeric','base_prompt.txt','first_two'),
        ('set_f1','ssla_company_defendants','base_prompt.txt','first_two'),
        ('shadowed_set_dispatch','successor_liability','base_prompt.txt','first_two'),
        ('original_manual','rule_qa','base_prompt.txt','first_one')]
    groups=[]
    for group,task,template_name,selection in specs:
        frame=pd.read_csv(data/'data'/task/'test.tsv',sep='\t',dtype=str,keep_default_na=False)
        subset=frame.drop_duplicates(subset=['answer'],keep='first') if selection=='classes' else frame.head(1 if selection=='first_one' else 2)
        template=(folder/'tasks'/task/template_name).read_text(encoding='utf-8')
        if '{{answer}}' in template:raise ValueError('Target column must not enter a model prompt')
        prompts=modules['utils'].generate_prompts(template,subset)
        groups.append(dict(group=group,task=task,template=template_name,selection=selection,
            test_rows=len(frame),selected_rows=subset.to_dict(orient='records'),prompts=prompts,
            targets=subset['answer'].tolist(),model_max_tokens=1536 if template_name=='application_prompt.txt' else 2048 if task=='rule_qa' else 512))
    template_checks=[dict(task=t,base_template_exists=(folder/'tasks'/t/'base_prompt.txt').is_file(),
        evaluation_declared=t in modules['evaluation'].EXACT_MATCH_BALANCED_ACC_TASKS or t in ['sara_numeric','successor_liability','citation_prediction_open','definition_extraction','rule_qa'] or t.startswith('ssla')) for t in modules['tasks'].TASKS]
    return groups,template_checks


def execute(request):
    folder,data,modules,commits=load();evaluation=modules['evaluation']
    if request['mode']=='score':
        results=[]
        for row in request['groups']:
            if len(row['predictions'])!=len(row['references']) or not row['references']:raise ValueError('Nonempty paired scoring inputs required')
            score=evaluation.evaluate_exact_match_balanced_accuracy(row['predictions'],row['references'])
            results.append(dict(id=row['id'],score=float(score),examples=len(row['references']),reference_classes=len(set(evaluation.normalize(a,False) for a in row['references'])),
                normalized_predictions=[evaluation.normalize(a,False) for a in row['predictions']],normalized_references=[evaluation.normalize(a,False) for a in row['references']]))
        return dict(event='result',method='b04_legalbench',output=results,source_commits=commits,model_requests=0,
            author_entry='evaluation.evaluate_exact_match_balanced_accuracy',local_model_inference=False,original_complete_benchmark=False)
    groups,templates=prepare(folder,data,modules)
    if request['mode']=='prepare':
        return dict(event='result',method='b04_legalbench',groups=groups,template_checks=templates,
            model_requests=0,source_commits=commits,local_model_inference=False)
    if request['mode']!='native':raise ValueError('Unknown LegalBench mode')
    if request.get('frozen_groups')!=groups:raise ValueError('Original source inputs differ from frozen selected tasks')
    results=[];calls=0
    for group in groups:
        predictions=[]
        for index,prompt in enumerate(group['prompts']):
            stage=group['group']+'.'+str(index);calls+=1
            predictions.append(call(stage,[dict(role='user',content=prompt)],dict(model_max_tokens=group['model_max_tokens'],temperature=0,original_generation_controller='not supplied; API transport added here')))
        task=group['task'];entry=dict(**group,predictions=predictions)
        try:score=evaluation.evaluate(task,predictions,group['targets'])
        except Exception as error:
            if task not in evaluation.MANUAL_EVAL_TASKS:raise
            entry.update(score=None,status='unscored_original_manual_task',reason=str(error))
        else:entry.update(score=float(score),status='scored')
        if task=='successor_liability':
            entry.update(original_dispatch_shadowed=task in evaluation.EXACT_MATCH_BALANCED_ACC_TASKS,
                original_direct_set_f1=float(evaluation.evaluate_successor_liability(predictions,group['targets'])),
                warning='Original evaluate() routes this task to balanced accuracy before the specialized F1 branch; both preserved.')
        results.append(entry);tool('legalbench.original_task_result',entry)
    checks=dict(author_prompt_generator_executed=True,author_evaluator_executed=True,groups=len(groups),
        distinct_tasks=len({g['task'] for g in groups}),model_requests=calls,original_task_count=len(templates),
        all_162_templates_present=all(t['base_template_exists'] for t in templates),all_162_evaluations_declared=all(t['evaluation_declared'] for t in templates),
        scored_groups=sum(r['status']=='scored' for r in results),manual_groups=sum(r['status']=='unscored_original_manual_task' for r in results),
        no_test_answer_placeholder=True,all_rows_received_actual_reply=all(len(r['predictions'])==len(r['targets']) for r in results),
        no_neural_model_modules=not any(n in sys.modules for n in ['torch','transformers','spacy']),local_model_inference=False,expert_legal_accuracy=None)
    return dict(event='result',method='b04_legalbench',output=dict(task_results=results,template_checks=templates),checks=checks,
        source_commits=commits,author_entry='utils.generate_prompts -> added remote API -> evaluation.evaluate (unchanged)',
        original_complete_benchmark=False,local_model_inference=False)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=execute(request)
    emit(result)
