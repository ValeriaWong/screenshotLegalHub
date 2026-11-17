"""SCALE case transport; algorithm execution lives in the named paper adapter."""
import json
from .author_bridge import REPO, stream_author
from .paper_bridge import environment

async def scale_case(context):
    if context.raw_call is None:raise ValueError('SCALE作者方法需要原始响应预算接口')
    python,_=environment('scale')
    request=dict(question=context.visible['goal'],sources=context.visible['sources'],
                 legal_corpus=context.visible['legal_corpus'],
                 factor_hierarchy=context.visible.get('matterpack',{}).get('factor_hierarchy'),
                 instruction=context.final_system)
    async def handle(event):
        if event['event']=='tool':return dict(ok=True)
        return await context.raw_call(event['stage'],event['messages'],event['original_parameters'])
    result=await stream_author(python,REPO/'paper/author_reproductions/scale/case_adapter.py',request,handle)
    if context.author_record:await context.author_record('scale',result)
    return result['output']
