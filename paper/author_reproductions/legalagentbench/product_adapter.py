"""B01 LegalAgentBench (Li et al., ACL 2025), DOI 10.18653/v1/2025.acl-long.116.
Author source: https://github.com/CSHaitao/LegalAgentBench @
ec14d8ab1fc439bfd99cbefba08d8e27dafca534. Actual original ReactAgent, PSAgent,
PEAgent, prompts, examples, table selector and parsers execute from pinned AST.
Original input: legal/business question + 17 corpora / 37 external tools.
Original output: final answer, scratchpad, filtered answer, summarized process.
Benchmark: 300 tasks, 1-5 hop and writing; key_answer success and key_middle
progress substring scoring, optional remote BERTScore. Innovation: domain-specific
tool/corpus benchmark and intermediate progress; these are baseline controllers,
not a newly proposed legal reasoning model. All three are distinct variants.
Reproduction degree: original controller execution with bounded model transport;
LIVE TOOL SERVICE NOT REPRODUCED. Its published endpoint refused connection.
Native validation replays only author-published tool observations for exact
requests; it never substitutes answer labels or feeds original model thoughts.
Adaptations: DeepSeek API replaces original providers; 2000 output-token budget;
minimal str.format PromptTemplate shim instead of full LangChain imports; Pydantic
1.10 schema preserved. Original post_request calls format_input without its name
argument; our transport invokes original format_input(name,input) correctly.
Original parser's eval fallback is unreachable: only fenced JSON enters it.
Product-only valid whole action JSON can receive lossless fences first; native
strict parsing remains unchanged. Raw replies and each wrapper normalization stay recorded.
Native table selector's three attempts remain recorded; global/unit caps prevent
additional supplier calls, no transport retries/reset. Optional FAISS/BERTScore
and remote corpora are NOT executed, installed or presented as working.
Product output policy is repeated in every product model message because the
original PS solve prompt does not retain the original question/schema. Native
prompts do not receive this product contract.
Product mapping: frozen KIE text is read by explicit local list/read tools, then
original controllers return answer/evidence JSON. It is not screenshot parsing,
original 17-corpus retrieval, expert legal accuracy or the full paper benchmark.
"""
import ast
import contextlib
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from pydantic import BaseModel
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'paper/author_reproductions'))
from author_runtime import source,original_definitions,call,tool,emit
HERE=Path(__file__).parent

class PromptTemplate:
    """Only original format interface is used; no LangChain orchestration claimed."""
    def __init__(self,*,input_variables,template):self.input_variables=input_variables;self.template=template
    def format(self,**values):return self.template.format(**values)

class UnitBudgetExceeded(BaseException):pass

def originals(allow_bare_json=False):
    folder,pin=source('legalagentbench')
    module=ModuleType('_legalagentbench_originals');module.__file__=str(folder/'agents.py')
    sys.modules[module.__name__]=module
    ns=module.__dict__;ns.update(re=re,json=json,Enum=Enum,BaseModel=BaseModel,PromptTemplate=PromptTemplate,
        print_colored=lambda *a,**k:None)
    for relative in ['fewshots.py','prompts.py','src/generated_tools.py','src/schema.py','src/prompt.py']:
        path=folder/relative;tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),ns)
    original_definitions(folder/'src/utils.py',['prase_json_from_response','filter_table_and_tool'],ns)
    original_definitions(folder/'agents.py',['ReactAgent','PSAgent','PEAgent','parse_plan','parse_action','format_step','format_input'],ns)
    unsafe_fallback_parser=ns['parse_action'];ns['_transport_normalizations']=[]
    def fenced_json_only(value):
        if re.search(r'```json(.*?)```',value,re.DOTALL) is None:
            if not allow_bare_json:return '',''
            try:decoded=json.loads(value)
            except json.JSONDecodeError:return '',''
            if not isinstance(decoded,dict) or set(decoded)!={'action','action_input'}:return '',''
            ns['_transport_normalizations'].append(dict(kind='product_bare_json_action_wrapper',formatted_action_sha256=hashlib.sha256(value.encode()).hexdigest(),semantic_content_changed=False))
            value='```json'+value+'```'
        return unsafe_fallback_parser(value)
    ns['parse_action']=fenced_json_only
    return ns,pin

def run(request,generate=call,observe=tool):
    ns,pin=originals(allow_bare_json=request['mode']=='product');variant=request['variant']
    classes={'react':'ReactAgent','plan_and_solve':'PSAgent','plan_and_execute':'PEAgent'}
    if variant not in classes:raise ValueError('Unknown author controller variant')
    native=request['mode']=='native_replay'
    if not native and request['mode']!='product':raise ValueError('Unsupported explicit tool mode')
    unit_cap=request.get('max_calls',26);count=0;phase='tables';requests=[];observations=[]
    def llm(query,model_name):
        nonlocal count
        if count>=unit_cap:raise UnitBudgetExceeded('Bounded paper unit exhausted before supplier call')
        stage=variant+'.'+phase+'.'+str(count).zfill(3);count+=1
        messages=[dict(role='system',content='You are a helpful assistant. Provide brief public observations and decisions, without hidden chain-of-thought.'+(' '+request.get('output_policy','') if not native else '')),dict(role='user',content=query)]
        requests.append(dict(stage=stage,phase=phase))
        return generate(stage,messages,dict(temperature=0,max_tokens=2000))
    ns['LLM']=llm
    if native:
        fixture=json.loads((HERE/'native_inputs/author_log_first_task.json').read_text(encoding='utf-8'))
        if request['question']!=fixture['question']:raise ValueError('Only exact author-log native task is available; live corpus not reachable')
        used_tools,table_prompt=ns['filter_table_and_tool'](request['question'],'configured-deepseek')
        used_tools += [ns[n] for n in ['get_sum_tool','get_rank_tool','legal_article_retriever_tool','legal_case_retriever_tool','legal_knowledge_retriever_tool']]
        records=fixture['observations']
        def dispatch(name,value):
            normalized=ns['format_input'](name,value)
            matches=[r for r in records if r['action']==name and r['input']==normalized]
            if not matches:
                result='Replay fixture has no response for this exact tool request; live service unavailable.'
                state='unavailable_exact_request'
            else:result=matches[0]['response'];state='author_log_replay'
            item=dict(action=name,input=normalized,response=result,mode=state,fixture='native_inputs/author_log_first_task.json')
            observations.append(item);observe('legalagentbench.tool',item)
            return result
    else:
        documents=request['documents']
        if not documents or len({d['id'] for d in documents})!=len(documents):raise ValueError('Unique frozen text documents required')
        tools=[('list_evidence','输入{}；返回冻结证据id列表。'),('read_evidence','输入JSON字典identifier为list_evidence返回的id；返回其冻结全文。')]
        used_tools=[ns['Tool'](name,description) for name,description in tools]
        table_prompt='本项目冻结KIE预测/证据文本，不是原17个外部法律数据库。先list_evidence再read_evidence，不生成截图外信息。'
        def dispatch(name,value):
            if name=='list_evidence':result=[dict(id=d['id'],characters=len(d['text'])) for d in documents]
            elif name=='read_evidence':
                identifier=value.get('identifier') if isinstance(value,dict) else value
                match=next((d for d in documents if d['id']==identifier),None)
                result=match if match else dict(error='Frozen source ID does not exist')
            else:result=dict(error='Unsupported product tool; no external lookup performed')
            item=dict(action=name,input=value,response=result,mode='frozen_product_text')
            observations.append(item);observe('legalagentbench.tool',item)
            return result
    ns['post_request']=dispatch
    phase='controller'
    kwargs=dict(model_name='configured-deepseek',question=request['question'],tools='\n\n'.join(t.name+': '+t.description for t in used_tools),
        tool_names=' '.join(t.name for t in used_tools),table_used_prompt=table_prompt,max_steps=10)
    agent=ns[classes[variant]](**kwargs)
    if not native:
        # Author worked examples reference external tables; remove them explicitly
        # for product tool substitution, rather than advertising nonexistent tools.
        if variant=='react':agent.react_examples=''
        else:
            ns['PLAN_SOLVE_plan_EXAMPLE']='';ns['PLAN_SOLVE_solve_EXAMPLE']='';ns['PLAN_SOLVE_replan_EXAMPLE']=''
    agent.run()
    filtered=None;summary=None
    if native:
        phase='filter_answer';filtered=llm(ns['FILTER_PROMPT'].format(query=request['question'],info=agent.scratchpad),'configured-deepseek')
        phase='summarize_process';summary=llm(ns['SUMMARY_PROMPT'].format(query=request['question'],info=agent.scratchpad),'configured-deepseek')
        filtered=re.sub(r'(?<=\d),(?=\d)','',filtered);summary=re.sub(r'(?<=\d),(?=\d)','',summary)
        output=filtered
    else:
        if not agent.finished:raise ValueError('Author controller did not reach Final Answer')
        output=json.loads(agent.answer) if isinstance(agent.answer,str) else agent.answer
    return dict(output=output,variant=variant,controller=classes[variant],controller_finished=agent.finished,
        agent_answer=agent.answer,filtered_answer=filtered,summary=summary,scratchpad=agent.scratchpad,
        observations=observations,requests=requests,model_calls=count,source=pin,transport_normalizations=ns['_transport_normalizations'],
        author_controller_executed=True,tool_mode='author_log_exact_replay' if native else 'frozen_product_text',
        original_live_corpora_available=False,original_complete_benchmark=False,local_model_inference=False)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=run(request)
    emit(dict(event='result',**result))
