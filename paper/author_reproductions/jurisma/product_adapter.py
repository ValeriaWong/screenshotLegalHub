"""JurisMA paper-inference entry; fidelity/original I/O: algorithm.py.
Only shared transport is reused; original trained author system is not claimed.
"""
import contextlib,json,sys
from pathlib import Path
HERE=Path(__file__).parent
sys.path[:0]=[str(HERE),str(HERE.parent)]
from author_runtime import call,emit,tool
from algorithm import run,parse_json

def main(request):
    result=run(request,call,tool)
    if request.get('projection'):
        projection=request['projection']
        messages=[dict(role='system',content=projection['instruction']),dict(role='user',content=json.dumps(dict(native_inference_output=result['output'],element_graph=result['element_graph'],frozen_source_anchors=projection['anchors'],task=projection.get('task')),ensure_ascii=False))]
        raw=call('product_projection',messages,dict(temperature=0,max_tokens=4096))
        output=parse_json(raw)
        if not isinstance(output,dict):raise ValueError('Product projection must return an object')
        result.update(native_output=result['output'],output=output,projection_raw=raw,projection_is_product_adaptation=True,total_calls=result['calls']+1)
    return dict(event='result',**result)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=main(request)
    emit(result)
