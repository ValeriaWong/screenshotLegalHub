"""B15 RAGChecker — Ru et al., NeurIPS 2024, arXiv:2408.08067.
Author amazon-science/RAGChecker @ 6091f08c00e676e87a970f2aeb4a23a484746348;
author dependency RefChecker @ 1df1b25cee792ba2b171302e31ca4f768bd67703.
Original method/innovation: claim extraction; answer<->response and retrieved->
answer/response entailment matrices; 11 original diagnosis/aggregation metrics.
Original input: query, gt_answer, generated response, retrieved_context[{doc_id,text}].
Original output: extracted triplets, four checking matrices, per-result and aggregate
metrics. Original benchmark: 4k questions across 10 domains; human meta-evaluation.
This validates both complete public examples, not the complete benchmark or its scores.
Fidelity: original RAGChecker evaluator/container/computation, LLMExtractor/LLMChecker,
base parsers, prompts and official custom_llm_api_func transport branch execute.
Adaptation: remote DeepSeek replaces original Llama judge; no local model weights.
Only eager optional imports bypassed. The default triplet extractor does not use
RCText/spaCy and RAGChecker sets max_reference_segment_length=0. Rule sentencizing,
NLI, AlignScore, localizer, subsentence branches explicitly unsupported here.
Model-generated Python tuple literals use literal_eval instead of eval; no algorithm
or scoring formula change. Product scope: rescore frozen predicted-text VQA with its
actual frozen KIE contexts and existing reference; missing KIE transcript is unscored.
These are text faithfulness/overlap diagnoses, not pixel KIE or expert legal accuracy.
"""
import ast,contextlib,importlib,inspect,json,re,sys,types,typing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import source,original_definitions,call,emit,tool


def load():
    rag,rpin=source('ragchecker');ref,fpin=source('refchecker')
    for name,path in [('ragchecker',rag/'ragchecker'),('refchecker',ref/'refchecker'),('refchecker.extractor',ref/'refchecker/extractor'),('refchecker.checker',ref/'refchecker/checker')]:
        module=types.ModuleType(name);module.__path__=[str(path)];sys.modules[name]=module
    def deferred(*args,**kwargs):raise ValueError('Local-model, segmentation or subsentence branch is deferred')
    base=types.ModuleType('refchecker.base');base.__dict__.update(List=typing.List,Union=typing.Union,English=deferred)
    sys.modules[base.__name__]=base
    original_definitions(ref/'refchecker/base.py',['RCSentence','RCText','RCClaim','ExtractionResult'],base.__dict__)
    utils=types.ModuleType('refchecker.utils');utils.__dict__.update(json=json,split_text=deferred)
    sys.modules[utils.__name__]=utils
    original_definitions(ref/'refchecker/utils.py',['get_model_batch_response'],utils.__dict__)
    extractor=importlib.import_module('refchecker.extractor.llm_extractor')
    extractor_base=sys.modules['refchecker.extractor.extractor_base'];extractor_base.eval=ast.literal_eval
    checker=importlib.import_module('refchecker.checker.llm_checker')
    sys.modules['refchecker.extractor'].LLMExtractor=extractor.LLMExtractor
    sys.modules['refchecker.checker'].__dict__.update(LLMChecker=checker.LLMChecker,NLIChecker=deferred,AlignScoreChecker=deferred)
    evaluator=importlib.import_module('ragchecker.evaluator');container=importlib.import_module('ragchecker.container')
    return evaluator,container,dict(ragchecker=rpin['commit'],refchecker=fpin['commit'])


def execute(request):
    evaluator,container,commits=load();stages=[];calls=0
    def remote(prompts):
        nonlocal calls
        frame=inspect.currentframe().f_back
        parameters={k:frame.f_locals[k] for k in ['model','temperature','max_new_tokens','n_choices']}
        scan=frame;stage='unknown'
        while scan:
            if scan.f_code.co_name=='extract_claims':stage='extract.'+scan.f_locals['extract_type'];break
            if scan.f_code.co_name=='check_claims':stage='check.'+scan.f_locals['check_type'];break
            scan=scan.f_back
        caller=frame.f_back
        expected=caller.f_locals.get('claim_nums',[])
        offset=caller.f_locals.get('i',0)
        replies=[]
        for index,prompt in enumerate(prompts):
            label=stage+'.'+str(calls);calls+=1
            messages=[dict(role='user',content=prompt)] if isinstance(prompt,str) else prompt
            replies.append(call(label,messages,parameters))
            item=dict(stage=label,prompt_sha256=__import__('hashlib').sha256(json.dumps(messages,ensure_ascii=False).encode()).hexdigest())
            if stage.startswith('check.'):
                item['original_parser_labels']=[v.title() for v in re.findall(r'\b(Entailment|Neutral|Contradiction)\b',replies[-1],re.IGNORECASE)]
                item['expected_joint_labels']=expected[offset+index]
            stages.append(item)
        return replies
    data=container.RAGResults.from_json(json.dumps(request['rag_results']))
    metrics=request.get('metrics',['all_metrics'])
    judge=evaluator.RAGChecker(extractor_name='remote-author-api-alias',checker_name='remote-author-api-alias',
        extractor_max_new_tokens=1000,batch_size_extractor=32,batch_size_checker=32,
        joint_check=True,joint_check_num=5,custom_llm_api_func=remote)
    judge.evaluate(data,metrics)
    result=json.loads(data.to_json())
    checks=dict(original_evaluator_executed=True,original_metric_formulas_executed=True,
        all_responses_have_claims=all(bool(r['response_claims']) for r in result['results']),
        all_ground_truths_have_claims=all(bool(r['gt_answer_claims']) for r in result['results']),
        cases=len(result['results']),model_requests=calls,local_model_inference=False,expert_legal_accuracy=None,
        joint_labels_all_matched=all(len(s['original_parser_labels'])==s['expected_joint_labels'] for s in stages if s['stage'].startswith('check.')),
        no_local_optional_model_modules=not any(n in sys.modules for n in ['torch','transformers','spacy']),
        all_eleven_metrics_present=all(len(r['metrics'])==11 for r in result['results']) if metrics==['all_metrics'] else None)
    tool('ragchecker.original_result',result)
    return dict(event='result',method='b15_ragchecker',output=result,checks=checks,stages=stages,source_commits=commits,
        author_entry='RAGChecker.evaluate -> RefChecker LLMExtractor/LLMChecker -> original METRIC_FUNC_MAP',
        original_complete_benchmark=False,local_model_inference=False,
        adaptations=['author custom_llm_api_func -> parent authorized DeepSeek transport','triplet/no-segmentation API branch; unused optional imports bypassed','literal_eval for tuple literals; unchanged original regex/parser/metric formulas'])

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=execute(request)
    emit(result)
