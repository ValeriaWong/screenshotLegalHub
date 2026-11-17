"""R04 GraphRAG original API entry. Source/degree/original I-O: algorithm.py.
Transport belongs to the parent; no credentials or model weights in this process.
"""
import asyncio,contextlib,json,sys
from pathlib import Path
HERE=Path(__file__).parent
sys.path[:0]=[str(HERE),str(HERE.parent)]
from author_runtime import call,emit,tool
from algorithm import run
if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=asyncio.run(run(request,call,tool))
    emit(dict(event='result',**result))
