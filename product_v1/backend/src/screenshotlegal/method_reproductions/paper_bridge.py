"""Transport for per-paper author algorithms; no algorithm is implemented here."""
import base64
import copy
import io
import json
import os
from PIL import Image
from .author_bridge import REPO,stream_author


def environment(name):
    python=REPO/'paper/.author_envs'/name/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    driver=REPO/'paper/author_reproductions'/name/'product_adapter.py'
    if not python.is_file() or not driver.is_file():
        raise ValueError('作者独立环境未配置：'+name+'；参见 paper/author_reproductions/'+name+'/README.md')
    return python,driver


async def execute(name,request,call,tool_trace=None,images=None,validator=None):
    python,driver=environment(name)
    async def handle(event):
        if event['event']=='tool':
            result=event['result']
            if event['action']=='reflexion.validate_output':
                result=validator(event['result']['answer'])
                if tool_trace:await tool_trace(event['action'],dict(input=event['result'],validation=result))
                return result
            if tool_trace:await tool_trace(event['action'],result)
            return dict(ok=True)
        forwarded=copy.deepcopy(event['messages'])
        if images:
            final=forwarded[-1]
            final['content']=[dict(type='text',text=final['content']),*copy.deepcopy(images)]
        return await call(event['stage'],forwarded,event['original_parameters'])
    return await stream_author(python,driver,request,handle)


async def benchmark_task(name,messages,call,attempts=2,tool_trace=None):
    task=None;images=[]
    for message in messages:
        if message['role']!='user':continue
        content=message['content']
        if isinstance(content,list):
            images.extend(p for p in content if p.get('type')=='image_url')
            for part in content:
                if part.get('type')=='text':task=json.loads(part['text'])
        else:task=json.loads(content)
    if not isinstance(task,dict):raise ValueError('Missing frozen task input')
    request=dict(mode='product',question=task['question'],instruction=messages[0]['content'],attempts=attempts)
    validator=None
    if name=='reflexion':
        from screenshotlegal.research import benchmark_scoring as scoring
        dimensions=None
        if images:
            with Image.open(io.BytesIO(base64.b64decode(images[0]['image_url']['url'].split(',',1)[1]))) as image:
                dimensions=image.size
        def validate(raw):
            try:
                if task['task_type']=='kie.extract':
                    if dimensions is None:raise ValueError('KIE requires image dimensions')
                    scoring.kie(raw,*dimensions)
                else:
                    value=scoring.parse(raw)
                    if 'answer' not in value or not isinstance(value.get('evidence'),list):raise ValueError('answer/evidence schema invalid')
                return dict(valid=True,scope='schema_and_coordinates_only',factual_accuracy=None,legal_accuracy=None)
            except (ValueError,TypeError,KeyError) as error:
                return dict(valid=False,scope='schema_and_coordinates_only',validation_error=str(error),factual_accuracy=None,legal_accuracy=None)
        validator=validate
        request['context']=json.dumps(task,ensure_ascii=False)
    else:
        if images or task.get('track')!='vqa_predicted_text':
            raise ValueError(name+' requires frozen KIE predictions; it does not directly extract image pixels')
        prediction=task['upstream_prediction']
        conversation=prediction.get('conversation',[])
        if not conversation:raise ValueError('Frozen KIE prediction contains no messages for retrieval')
        request['documents']=([dict(id='kie:'+task['upstream_sha256'],text=json.dumps(prediction,ensure_ascii=False))] if name=='lightrag' else
                              [dict(id='kie:'+task['upstream_sha256']+':'+str(i),text=json.dumps(message,ensure_ascii=False)) for i,message in enumerate(conversation)])
        request.update(language='Chinese',num_layers=attempts)
    return await execute(name,request,call,tool_trace,images=images,validator=validator)


async def case_task(name,context):
    if context.raw_call is None:raise ValueError('作者方法需要保留原始响应的预算调用接口')
    request=dict(mode='product',question=context.visible.get('goal') or '分析给定证据支持的请求、事实与不确定性',
                 instruction=context.final_system,documents=[dict(id=s['id'],text=s['text']) for s in context.sources],
                 num_layers=context.options.get('refinement_rounds',2),language='Chinese')
    validator=None
    if name=='reflexion':
        from screenshotlegal.experiments.engine import validate_output
        request.update(context=json.dumps(dict(input=context.visible,sources=context.sources),ensure_ascii=False),attempts=context.options.get('refinement_rounds',2))
        def validate(raw):
            try:
                validate_output(json.loads(raw),dict(sources=context.sources))
                return dict(valid=True,scope='schema_and_literal_citations_only')
            except (ValueError,TypeError,KeyError) as error:
                return dict(valid=False,scope='schema_and_literal_citations_only',validation_error=str(error))
        validator=validate
    result=await execute(name,request,context.raw_call,validator=validator)
    if context.author_record:await context.author_record(name,result)
    return result['output']
