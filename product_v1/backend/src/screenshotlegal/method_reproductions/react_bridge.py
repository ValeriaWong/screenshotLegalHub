"""ReAct Notebook controller with frozen image catalog / real pixel crop tools."""
import base64
import copy
import io
import json
import os
from PIL import Image
from screenshotlegal.research import benchmark_scoring
from .author_bridge import REPO,stream_author

def environment():
    python=REPO/'paper/.author_envs/react'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    driver=REPO/'paper/author_reproductions/react/product_adapter.py'
    if not python.is_file() or not driver.is_file():raise ValueError('ReAct作者独立环境未配置')
    return python,driver

async def react(messages,call,tool_trace=None,native=False,native_index=0):
    python,driver=environment()
    images=[];context=[]
    for m in messages:
        if m['role']=='system':continue
        if isinstance(m['content'],list):
            images.extend(copy.deepcopy(p) for p in m['content'] if p.get('type')=='image_url')
            context.extend(p['text'] for p in m['content'] if p.get('type')=='text')
        else:context.append(m['content'])
    import hashlib
    image_bytes=[base64.b64decode(p["image_url"]["url"].split(",",1)[1]) for p in images]
    catalog=[]
    for i,data in enumerate(image_bytes):
        with Image.open(io.BytesIO(data)) as im:catalog.append(dict(image_index=i,width=im.width,height=im.height,sha256=hashlib.sha256(data).hexdigest()))
    crops=[];normalizations=[]
    async def handle(event):
        if event['event']=='tool':
            action=event['action']
            if action.startswith('search[') and action.endswith(']'):
                result=dict(images=catalog,note='Lookup uses original pixel coordinates on image 0')
            elif action.startswith('lookup[') and action.endswith(']') and images:
                values=action[len('lookup['):-1]
                coordinates=json.loads(values if values.strip().startswith('[') else '['+values+']')
                raw=image_bytes[0]
                with Image.open(io.BytesIO(raw)) as im:
                    box=benchmark_scoring.box(coordinates,*im.size)
                    pixels=[int(box[0]),int(box[1]),int(box[2]+.999999),int(box[3]+.999999)]
                    out=io.BytesIO();im.crop(pixels).convert('RGB').save(out,format='PNG')
                attachment=dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()))
                crops.append(attachment)
                result=dict(crop_index=len(crops),source_image_index=0,source_sha256=catalog[0]['sha256'],crop_sha256=hashlib.sha256(out.getvalue()).hexdigest(),source_bbox_xyxy=pixels,note='The new crop is appended after the unchanged original image')
            else:raise ValueError('ReAct适配工具只允许Search[image]和Lookup[原图像素坐标]')
            if tool_trace is not None:await tool_trace(action,result)
            return result
        policy='Thought只用一句公开行动标签，不输出隐含推理过程；按当前编号输出Action N:，最终Finish[JSON]。' if not native else 'Thought只用一句公开行动标签，不输出隐含推理过程；保留原Action编号和原任务答案格式。'
        import re
        slot=re.search(r'(Thought|Action) (\d+):\s*$',event['prompt'])
        if slot:
            kind,number=slot.groups()
            policy+=' The prompt already contains '+kind+' '+number+':. '
            policy+=('Return only the bare tool call Search[...] / Lookup[...] / Finish[...], without any Action prefix.' if kind=='Action' else
                     'Continue with a short public action label, then a newline and exactly Action '+number+': <one tool call>. Do not restart at Action 1; do not generate an Observation.')
        forwarded=[dict(role='system',content=messages[0]['content']+' '+policy),dict(role='user',content=[dict(type='text',text=event['prompt']),*copy.deepcopy(images),*copy.deepcopy(crops)] if images else event['prompt'])]
        response=await call(event['stage'],forwarded,event['original_parameters'])
        # Chat models sometimes echo the prefilled Completion slot. Preserve
        # the supplier raw response in the parent; map only its exact slot prefix.
        raw=response['raw'];normalized=raw.strip()
        if slot:
            kind,number=slot.groups();prefix='Action '+number+':'
            if kind=='Action' and normalized.startswith(prefix):normalized=normalized[len(prefix):].strip()
            elif kind=='Thought' and normalized.startswith(prefix):normalized='执行所选动作\n'+normalized
            elif kind=='Thought' and normalized.startswith(('Search[','Lookup[','Finish[')):normalized='执行所选动作\n'+prefix+' '+normalized
        if normalized!=raw:
            normalizations.append(dict(stage=event['stage'],source='exact Chat/Completion slot prefix',canonicalized_response=normalized))
        return dict(response,raw=normalized)
    result=await stream_author(python,driver,dict(context=context,instruction=messages[0]['content'],native_task=native,native_index=native_index),handle)
    result['transport_normalizations']=normalizations
    result['adaptations']=['original Notebook webthink function and action parser','DeepSeek/chat transport substitutes original Completion model','public action labels instead of hidden reasoning','screenshot variant replaces Wikipedia tools with frozen image catalog and bounded pixel crops'] if not native else ['original WikiEnv/HotPotQAWrapper and original examples','DeepSeek/chat transport substitutes original Completion model','public action labels requested; bounded Wikipedia network timeout']
    return result
