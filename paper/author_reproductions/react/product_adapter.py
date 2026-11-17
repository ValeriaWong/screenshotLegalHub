"""Pinned ReAct HotpotQA controller, native task or screenshot task adaptation.

Paper: Yao et al., ReAct, https://arxiv.org/abs/2210.03629
Author: ysymyth/ReAct @ 6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9.
Original input/output: HotpotQA question + Wikipedia Search/Lookup -> Finish[answer].
Original benchmark: HotpotQA, FEVER, ALFWorld, WebShop; only HotpotQA entry here.
Adaptation: same Notebook webthink function body and action parser; replace WikiEnv
with frozen-image Search catalog / Lookup crop tools, return Finish[JSON] for KIE/VQA.
Model transport, token cap and public action-label instruction differ from original.
No claim of original benchmark reproduction; no targets enter adapted task context.
"""
import ast
from contextlib import redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3]
UPSTREAM=REPO/'paper/upstream_sources/react'
PROTOCOL_OUT=sys.stdout

def emit(value):
    PROTOCOL_OUT.write(json.dumps(value,ensure_ascii=False)+'\n');PROTOCOL_OUT.flush()

def main():
    request=json.loads(sys.stdin.readline())
    lock=json.loads((REPO/'paper/author_reproductions/sources.lock.json').read_text(encoding='utf-8'))
    pinned=next(s for s in lock if s['name']=='react')
    native=request.get('native_task',False)
    names=['hotpotqa.ipynb']+(['wikienv.py','wrappers.py','prompts/prompts_naive.json','data/hotpot_dev_v1_simplified.json'] if native else [])
    for name in names:
        if hashlib.sha256((UPSTREAM/name).read_bytes()).hexdigest()!=pinned['files'][name]:raise ValueError('Pinned author source changed: '+name)
    notebook=json.loads((UPSTREAM/'hotpotqa.ipynb').read_text(encoding='utf-8'))
    cells=[''.join(c.get('source',[])) for c in notebook['cells'] if c['cell_type']=='code']
    functions=[]
    for code in cells:
        functions.extend(n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef) and n.name in ['webthink','step'])
    controller=next(n for n in functions if n.name=='webthink')
    source_hash=hashlib.sha256(ast.dump(controller,include_attributes=False).encode()).hexdigest()
    calls=0
    def llm(prompt,stop=None):
        nonlocal calls
        stage='llm.'+str(calls);calls+=1
        emit(dict(event='request',stage=stage,prompt=prompt,original_parameters=dict(model='text-davinci-002',temperature=0,max_tokens=100,stop=stop)))
        response=json.loads(sys.stdin.readline())
        if 'error' in response:raise RuntimeError(response['error'])
        return response['raw']
    class ImageEnv:
        def reset(self,idx=None):
            self.answer=None;self.steps=0
            return 'Question: '+json.dumps(request['context'],ensure_ascii=False)
        def step(self,action):
            self.steps+=1
            if action.startswith('finish[') and action.endswith(']'):
                self.answer=action[len('finish['):-1]
                return 'Finished',0,True,dict(answer=self.answer,steps=self.steps)
            emit(dict(event='tool',action=action))
            response=json.loads(sys.stdin.readline())
            if 'error' in response:raise ValueError(response['error'])
            return json.dumps(response,ensure_ascii=False),0,False,dict(answer=None,steps=self.steps)
    if native:
        sys.path.insert(0,str(UPSTREAM));os.chdir(UPSTREAM)
        import wikienv,wrappers,requests
        # Source network reads need a bounded timeout. This does not change
        # the author's question, action semantics, reward or model control loop.
        original_get=requests.get
        def research_get(url,**kwargs):
            kwargs.setdefault('timeout',(5,15))
            headers=dict(kwargs.pop('headers',{}))
            headers.setdefault('User-Agent','ScreenshotLegalResearch/0.1 (academic ReAct reproduction; https://github.com/ysymyth/ReAct)')
            return original_get(url,headers=headers,**kwargs)
        requests.get=research_get
        env=wrappers.HotPotQAWrapper(wikienv.WikiEnv(),split='dev')
        examples=json.loads((UPSTREAM/'prompts/prompts_naive.json').read_text())['webthink_simple6']
        instruction=next(c for c in cells if 'webthink_examples =' in c)
        # Load only the literal original instruction; exclude Notebook's batch run.
        tree=ast.parse(instruction)
        text=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='instruction' for t in n.targets))
        prompt=text+examples
        namespace=dict(env=env,llm=llm,webthink_prompt=prompt,requests=requests)
        step_function=next(n for n in functions if n.name=='step')
        exec(compile(ast.fix_missing_locations(ast.Module(body=[step_function],type_ignores=[])),str(UPSTREAM/'hotpotqa.ipynb'),'exec'),namespace)
    else:
        env=ImageEnv()
        prompt=(request['instruction']+'\n使用Thought、Action、Observation协议；Thought只能是一句公开行动标签，不得输出推理过程。'
                'Search[image]列出冻结原图；Lookup[x1,y1,x2,y2]按原图像素读取局部，不能越界。'
                '最终用Finish[完整JSON对象]作答。每轮只输出一句行动标签和换行Action N: 工具动作，N与当前Thought编号一致。\n')
        namespace=dict(env=env,llm=llm,webthink_prompt=prompt,step=lambda e,a:e.step(a))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[controller],type_ignores=[])),str(UPSTREAM/'hotpotqa.ipynb'),'exec'),namespace)
    with redirect_stdout(sys.stderr):reward,info=namespace['webthink'](idx=request.get('native_index',0) if native else None,to_print=False)
    output=info if native else json.loads(info['answer'])
    if not isinstance(output,dict):raise ValueError('Final answer is not a JSON object')
    emit(dict(event='result',output=output,model_calls=calls,author_commit=pinned['commit'],controller_source='hotpotqa.ipynb:webthink',controller_body_sha256=source_hash,native_task=native,reward=reward if native else None,original_benchmark_reproduced=False))

if __name__=='__main__':main()
