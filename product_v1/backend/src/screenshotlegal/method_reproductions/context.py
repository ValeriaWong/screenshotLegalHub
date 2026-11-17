"""Shared I/O primitives only. Method control flow lives in each named module."""
import json
from screenshotlegal.experiments.contracts import CaseAnalysisOutput
from screenshotlegal.experiments.inputs import citation_units

STAGES={
 'identify':'识别争点、候选请求与未知前提；不要把模板中的问题当作已发生事实。',
 'map_evidence':'把逐项事实和要件连接到原文，分别列支持、反证与背景，保留缺证。',
 'synthesize':'整合前阶段，核对每个结论的证据及保留条件，给出完整结构化结果。',
}
TOOL_PROTOCOL='工具请求格式为 {"tool":"case_search|source_read|authority_search|finish","args":{...}}。case_search/authority_search用query字符串（最多200字符）和limit整数(1至10)；source_read用source_ref_id,start(从0开始),max_chars(1至5000)。每次仅返回一个工具动作，JSON顶层必须含tool字段，不能返回type=json_object包装。工具只能访问冻结输入，不得使用外部网络。'

class MethodContext:
    def __init__(self,visible,sources,call,tool,system,demo_output,options,raw_call=None,author_record=None):
        self.raw_call=raw_call
        self.author_record=author_record
        self.visible,self.sources,self.call,self.tool=visible,sources,call,tool
        self.system,self.demo_output,self.options=system,demo_output,options
        self.final_system=system+' 最终输出必须符合此JSON Schema：'+json.dumps(CaseAnalysisOutput.model_json_schema(),ensure_ascii=False)
        self.catalog=[dict(id=r['id'],page_no=r.get('page_no'),length=len(r['text'])) for r in sources]

    async def answer(self,stage,task,payload,demo=None):
        instruction=self.final_system if demo is None else self.system+' 本阶段仅执行如下协议，不输出其他对象或完整分析：'+task
        return await self.call(stage,[dict(role='system',content=instruction),dict(role='user',content=json.dumps(dict(task=task,**payload),ensure_ascii=False))],demo if demo is not None else self.demo_output())

    async def staged(self,material,prefix=''):
        output=None
        for stage,task in STAGES.items():
            output=await self.answer(prefix+stage,task,dict(input=material,previous_stage=output))
        return output

    async def retrieve(self,query,prefix,limit):
        hits=await self.tool(prefix+'.search','case_search',dict(query=query,limit=limit))
        selected=[]
        for i,hit in enumerate(hits):
            chunk=await self.tool(prefix+'.read.'+str(i),'source_read',dict(source_ref_id=hit['source_ref_id'],start=0,max_chars=5000))
            selected.append(dict(id=chunk['source_ref_id'],text=chunk['text'],read_range=[chunk['start'],chunk['end']],next_request=chunk['next_request'],citation_units=chunk.get('citation_units',citation_units(chunk['text'],chunk['start']))))
        return selected
