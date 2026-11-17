"""论文出处：Hong et al., MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework.
https://arxiv.org/abs/2308.00352 ; author https://github.com/FoundationAgents/MetaGPT
固定作者v0.3.0 / 820fee5df6697b4e85e90c787940de111c3ed05b。
复现程度：作者startup、Team/Environment/Role/Memory、软件动作、原提示/解析器真实执行；
替换远程LLM传输，禁用付费自动重试，隔离输出路径；非原论文benchmark分数复现。
原方法/创新：SOP约束角色，结构化中间产物与消息订阅，软件需求→PRD→设计→任务→代码/审查。
原输入示例：Write a cli snake game。原输出：PRD、系统/API设计、任务依赖及项目代码。
原benchmark：HumanEval、MBPP和软件开发任务（包括SoftwareDev）；原评测模型/样本条件
须与本文单个公开README任务区别。原模型替换为用户AIPING DeepSeek，实际身份在父记录。
原任务与产品适配必须分别验证。本文件首先保留作者软件原任务入口；不把E02三段提示
基线算作MetaGPT，不把游戏代码生成直接当作法律能力。产品法律SOP另行明确改角色与任务。
无本地模型权重推理/训练。默认关闭的长期向量记忆保持关闭；图形渲染暂缓，Mermaid文本保存。
可选资源保护和路径/重试差异见loader.py及每次运行返回adaptations。
"""
import asyncio,contextlib,json,locale,sys,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import emit,original_definitions,tool
from loader import load

async def execute(request):
    runtime=load(request['runtime'])
    roles=runtime['roles'];Team=runtime['Team']
    if request.get('mode')=='probe':
        team=Team();team.hire([roles.ProductManager(),roles.Architect(),roles.ProjectManager(),roles.Engineer(use_code_review=True)])
        return dict(event='result',method='metagpt',status='environment_probe_passed',roles=list(team.environment.roles),
            local_model_inference=False,calls=runtime['calls'](),source_commit=runtime['provenance']['commit'])
    if request.get('mode')!='native':raise ValueError('Product SOP must be explicitly implemented and validated separately')
    captured=[];original_run=Team.run
    async def observed(self,*args,**kwargs):
        captured.append(self)
        return await original_run(self,*args,**kwargs)
    Team.run=observed
    class DeferredQa:
        def __init__(self):raise ValueError('Native QA execution requires a separate reviewed generated-code test step')
    namespace=dict(Team=Team,ProductManager=roles.ProductManager,Architect=roles.Architect,
        ProjectManager=roles.ProjectManager,Engineer=roles.Engineer,QaEngineer=DeferredQa)
    original_definitions(runtime['folder']/'startup.py',['startup'],namespace)
    await namespace['startup'](request['idea'],investment=3.0,n_round=5,code_review=True,run_tests=False,implement=True)
    company=captured[0]
    messages=[dict(role=m.role,content=m.content,cause_by=getattr(m.cause_by,'__name__',str(m.cause_by)),
              structured=m.instruct_content.dict() if m.instruct_content else None) for m in company.environment.memory.get()]
    files={p.relative_to(Path(request['runtime'])/'workspace').as_posix():p.read_text(encoding='utf-8')
           for p in (Path(request['runtime'])/'workspace').rglob('*') if p.is_file()}
    tool('metagpt.native_software_outputs',dict(messages=messages,files=files))
    return dict(event='result',method='metagpt',output=dict(messages=messages,files=files),calls=runtime['calls'](),
        source_commit=runtime['provenance']['commit'],author_entry='startup.startup -> Team.run -> Environment.run -> Role.run -> software actions',
        original_complete_benchmark=False,local_model_inference=False,adaptations=runtime['adaptations'],
        native_functional_tests='pending generated-code review and smoke checks',product_adaptation_completed=False)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=asyncio.run(execute(request))
    emit(result)
