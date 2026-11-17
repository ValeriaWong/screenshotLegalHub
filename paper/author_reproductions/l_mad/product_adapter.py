"""Isolated L-MAD selected-MALLM-component entry. Full source/I/O/fidelity: algorithm.py."""
import contextlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'paper/author_reproductions')]
from author_runtime import call,emit
from algorithm import run
if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=run(request,lambda stage,messages,parameters:call(stage,messages,parameters))
    emit(dict(event='result',**result))
