"""SOLAR Stage I (Sadowski & Chudziak, CIKM 2025; arXiv:2509.00710).
Author albsadowski/solar @ 067f8f78b128dc7647c8a54b2560a612fae91a87.
Original method: parallel concept/rule extraction -> TBox integration/validation
-> human review -> interpreter generation -> training feedback -> Stage II.
Original input: complete SARA tax statute text; output: TBox and executable interpreter.
Original benchmark: SARA numeric and Housing Statute; no full benchmark claim here.
Innovation: explicit ontological knowledge and executable symbolic application.
Fidelity: original Stage I graph/nodes/prompts/validator execute until original input()
asks for human review. No automatic approval; code generation/training are NOT run.
Adaptation: structured model transport uses authorized remote API; concurrent graph
requests serialized over parent JSON protocol. No local weights or trained evaluator.
The historical SARA TBox is NOT a Chinese civil-law screenshot KIE/VQA rule pack.
Product adaptation remains incomplete until an appropriate reviewed rule domain exists.
"""
import contextlib,io,json,sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import source,call,emit

class ReviewRequired(Exception):
    """Original human input is needed; never turn a missing answer into approval."""

def execute(request):
    folder,provenance=source('solar');sys.path.insert(0,str(folder))
    from solar import knowledge_acquisition as original
    lock=threading.Lock();stages=[];updates=[];review={};human_text=io.StringIO()
    class Broker:
        def with_structured_output(self,schema):
            class Structured:
                def invoke(self,prompt):
                    with lock:
                        stage=schema.__name__+'.'+str(len(stages))
                        raw=call(stage,[dict(role='system',content='Return only a JSON object matching this schema.\n'+json.dumps(schema.model_json_schema(),ensure_ascii=False)),dict(role='user',content=prompt)],
                            dict(original_interface='with_structured_output',schema=schema.__name__,max_tokens=12000))
                        parsed=schema.model_validate_json(raw)
                        stages.append(dict(stage=stage,output=parsed.model_dump(mode='json')))
                        return parsed
            return Structured()
        def invoke(self,prompt):
            raise AssertionError('Interpreter generation must not run before original human approval')
    original_human=original.human_review_node
    def stop_at_input(prompt):
        review['input_prompt']=prompt
        raise ReviewRequired('Original SOLAR human review input required')
    def capture_human(state):
        review['state']=state.model_dump(mode='json')
        with contextlib.redirect_stdout(human_text):
            return original_human(state)
    original.input=stop_at_input;original.human_review_node=capture_human
    graph=original.graph(Broker(),False)
    try:
        for update in graph.stream(original.State(raw_statute_text=request['statute']),stream_mode='updates'):
            updates.append({node:{k:(v.model_dump(mode='json') if hasattr(v,'model_dump') else [i.model_dump(mode='json') if hasattr(i,'model_dump') else i for i in v] if isinstance(v,list) else v) for k,v in values.items()} for node,values in update.items()})
    except ReviewRequired:
        if 'state' not in review:raise
    else:raise AssertionError('Original graph passed human review without explicit input')
    tbox=original.TBox.model_validate(review['state']['tbox'])
    issues=original.validate_tbox(tbox)
    return dict(event='result',method='solar',state='awaiting_human_review',output=dict(tbox=tbox.model_dump(mode='json'),review_state=review['state'],human_review_text=human_text.getvalue(),validation_issues=issues,graph_updates=updates,stages=stages),
        checks=dict(original_pre_review_graph_executed=True,original_human_review_body_executed=True,original_input_intercepted=True,tbox_validator_issues=issues,interpreter_generated=False,training_evaluated=False,product_adaptation_completed=False,local_model_inference=False,original_complete_benchmark=False),
        source_commit=provenance['commit'],author_entry='knowledge_acquisition.graph -> original human_review_node -> input boundary',
        original_complete_benchmark=False,local_model_inference=False)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=execute(request)
    emit(result)
