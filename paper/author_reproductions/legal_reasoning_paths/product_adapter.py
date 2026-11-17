"""L06 isolated stdlib-only transport; algorithm and fidelity: algorithm.py."""
import json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent.parent))
from author_runtime import call,emit
from algorithm import run
if __name__=='__main__':
 try:
  request=json.loads(sys.stdin.readline());result=run(request,call);emit(dict(event='result',**result))
 except Exception as error:
  traceback.print_exc(file=sys.stderr);emit(dict(event='error',error=str(error)));raise
