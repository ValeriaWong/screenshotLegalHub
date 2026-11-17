"""Run the original WriteCodeReview action on a measured native software failure.
This is an explicitly harness-triggered follow-up, not the original autonomous QA
controller. Original native outputs and their failure are preserved separately.
"""
import asyncio,contextlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import emit
from loader import load
async def execute(request):
    rt=load(request['runtime'])
    from metagpt.actions import WriteCodeReview
    code=await WriteCodeReview().run(context=request['context'],code=request['code'],filename=request['filename'])
    return dict(event='result',method='metagpt',output=code,calls=rt['calls'](),source_commit=rt['provenance']['commit'],
        author_entry='original WriteCodeReview.run/write_code/CodeParser',harness_triggered_feedback=True,
        original_autonomous_qa_pipeline=False,original_complete_benchmark=False,local_model_inference=False)
if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=asyncio.run(execute(request))
    emit(result)
