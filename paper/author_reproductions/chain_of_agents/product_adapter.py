"""Isolated CoA paper-algorithm entry. Source/fidelity/original I/O: algorithm.py.
Transport only is shared. Author code execution is explicitly false; Algorithm 1
and paper templates run as our implementation. No local neural model is used.
"""
import contextlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'paper/author_reproductions'))
sys.path.insert(0,str(Path(__file__).parent))
from author_runtime import call,emit
from algorithm import run

def main(request):
    if request.get('mode')=='plan':
        result=run(request,lambda stage,messages,parameters:'PLANNING_ONLY')
        return dict(event='result',status='planned',inference_executed=False,chunks=result['chunks'],maximum_requests=result['calls'],window_tokens=result['window_tokens'],tokenizer_proxy=result['tokenizer_proxy'])
    result=run(request,lambda stage,messages,parameters:call(stage,messages,parameters))
    if request.get('parse_json_output'):
        text=result['output'].strip()
        if text.startswith(chr(96)*3):text='\n'.join(text.splitlines()[1:-1])
        result['raw_final_output']=result['output'];result['output']=json.loads(text)
        if not isinstance(result['output'],dict):raise ValueError('Product output must be a JSON object')
    return dict(event='result',**result)
if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=main(request)
    emit(result)
