"""MetaGPT product transport; author framework and explicit task adaptation run in their environment."""
from uuid import uuid4
from .author_bridge import REPO,stream_author
from .paper_bridge import environment

async def metagpt_case(context):
    if context.raw_call is None:raise ValueError('MetaGPT作者方法需要原始响应预算接口')
    python,_=environment('metagpt')
    runtime=REPO/'paper/.cache/metagpt/case'/uuid4().hex
    from screenshotlegal.experiments.contracts import CaseAnalysisOutput
    request=dict(policy=context.system,output_schema=CaseAnalysisOutput.model_json_schema(),runtime=str(runtime),question=context.visible['goal'],sources=context.visible['sources'],
                 legal_corpus=context.visible['legal_corpus'],matterpack=context.visible.get('matterpack'),instruction=context.final_system)
    events=[]
    async def handle(event):
        if event['event']=='tool':
            result=dict(ok=True)
            if event['action']=='metagpt.validate_case_output':
                from screenshotlegal.experiments.engine import validate_output
                try:
                    validate_output(event['result']['answer'],dict(sources=context.sources))
                    result=dict(valid=True,scope='schema_and_literal_citations_only',factual_accuracy=None,legal_accuracy=None)
                except (ValueError,KeyError,TypeError) as error:
                    result=dict(valid=False,error=str(error),scope='schema_and_literal_citations_only',factual_accuracy=None,legal_accuracy=None)
            events.append(dict(action=event['action'],input=event['result'],result=result))
            return result
        return await context.raw_call(event['stage'],event['messages'],event['original_parameters'])
    result=await stream_author(python,REPO/'paper/author_reproductions/metagpt/case_adapter.py',request,handle)
    result['tools']=events
    if context.author_record:await context.author_record('metagpt',result)
    return result['output']
