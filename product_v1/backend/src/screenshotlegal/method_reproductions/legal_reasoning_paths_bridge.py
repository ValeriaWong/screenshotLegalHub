"""L06 product text bridge; paper graph construction, not embedding retrieval."""
import json
from .paper_bridge import execute
async def benchmark_task(messages,call,tool_trace=None):
    task=None
    for message in messages:
        if message['role']!='user':continue
        if not isinstance(message['content'],str):raise ValueError('L06 needs frozen KIE text, not pixels')
        task=json.loads(message['content'])
    if not isinstance(task,dict) or task.get('track')!='vqa_predicted_text' or not isinstance(task.get('upstream_prediction'),dict) or not task['upstream_prediction'].get('conversation'):
        raise ValueError('L06 requires a nonempty frozen KIE prediction')
    prediction=task['upstream_prediction']
    text=json.dumps(prediction,ensure_ascii=False)
    question=task['question']
    if task.get('allowed_values'):question+='\nAllowed answer options (not Gold): '+json.dumps(task['allowed_values'],ensure_ascii=False)
    request=dict(mode='product',documents=[dict(id='kie:'+task['upstream_sha256'],source_status='unverified_KIE_prediction',overview='未人工核验的聊天预测文本，不是法院已认定事实。',blocks=[dict(id='frozen-conversation',text=text)])],question=question,
                 projection=dict(instruction=messages[0]['content']+' 标签是对输入内容的分类任务，不要求来源中存在同名字段；根据图中可支持的内容回答，无法判断才返回null。',anchors=prediction))
    return await execute('legal_reasoning_paths',request,call,tool_trace)
async def case_task(context):
    if context.raw_call is None:raise ValueError('L06 needs durable raw-call transport')
    documents=[dict(id=s['id'],source_status='unverified_party_statement',overview='各方陈述材料，未经过法院事实认定；保留陈述者身份。',blocks=[dict(id='source-text',text=s['text'])]) for s in context.visible['sources']]
    request=dict(mode='product',documents=documents,question=context.visible['goal'],
        projection=dict(instruction=context.final_system+' 这是论文图构建分支的产品映射，不是裁判或法条检索。facts只能整理图中有逐字来源的陈述，并明确谁如何陈述；不能把付款/借款存在等推断写成已查明事实。图没有法规范/法适用时不得生成法律结论。',anchors=context.visible['sources']))
    observations=[]
    async def observe(action,result):observations.append(dict(action=action,result=result))
    result=await execute('legal_reasoning_paths',request,context.raw_call,observe)
    result['observations']=observations
    if context.author_record:await context.author_record('legal_reasoning_paths',result)
    return result['output']
def demo_reply(stage,messages,output):
    """Zero-supplier transport fixture only; no ability or reproduction score."""
    if stage=='product_projection':return json.dumps(output,ensure_ascii=False)
    if stage.endswith('.extract_nodes'):
        return json.dumps({'司法事実':[],'法律・省令・政令・規則・契約書の引用や参照':[],'法規範':[],'法解釈':[],'法適用':[],'裁判の結論':[]},ensure_ascii=False)
    raise ValueError('Unexpected offline L06 stage; do not fabricate legal graph')
