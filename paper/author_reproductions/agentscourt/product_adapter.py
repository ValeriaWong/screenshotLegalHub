"""AgentsCourt — He et al., EMNLP Findings 2024, https://arxiv.org/abs/2403.02959.
Author https://github.com/Zhitao-He/AgentsCourt @ 7c14d6960abfdfdd7366250905da8dbcb416d6d6.
复现程度：直接执行原 court_interact、RolePlaying、ChatAgent 的庭审模拟分支。
这是整篇 AgentsCourt 的一个原组件；Legal-KB 检索、类案精炼及最终裁判尚未闭环，
不能将本入口称为完整 AgentsCourt 复现。真实任务记录与脚本化传输测试分开保存。
原输入：SimuCourt 的案件名、类别、原被告、指控/诉请及基本案情。
原输出：[原告控诉]/[原告发言] 与 [被告辩解] 庭审记录列表。
原 benchmark：作者 SimuCourt；创新包括庭审辩论与外部法律知识/类案增强。
本项目适配：将冻结证据和各方陈述置入基本案情，并保留“陈述/否认/未知”；
不得自动补造原被告、认定事实或法律指南。不直接产生消息 KIE；可作为案件或
冻结KIE文本全局VQA的立场讨论组件，最终产品输出须另做schema适配。
工程改动仅为提示模板绝对路径转为固定源码路径、SDK调用交回父进程、选择原函数
避免导入仓库中不存在且 court_interact 并未使用的 Self_Feedback 模块。
"""
import contextlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import source,original_definitions,exchange,emit


def execute(request):
    folder,provenance=source('agentscourt')
    role=folder/'AgentsCourt/role'
    sys.path.insert(0,str(role))
    import openai
    import generators
    import role_playing
    count=0
    def create(**parameters):
        nonlocal count
        stage='court.'+str(count);count+=1
        result=exchange(dict(event='request',stage=stage,messages=parameters['messages'],
                             original_parameters={k:v for k,v in parameters.items() if k!='messages'}))
        return dict(id=result.get('request_id','parent-transport'),usage=result.get('usage'),
                    choices=[dict(message=dict(role='assistant',content=result['raw']),finish_reason='stop')])
    openai.ChatCompletion.create=create
    def prompt(role_name):
        file='plaintiff_message.txt' if role_name=='plaintiff' else 'defendant_message.txt'
        return (folder/'AgentsCourt/system_prompt'/file).read_text(encoding='utf-8')
    generators.get_system_prompt=prompt
    # Generator calls with keyword role, kept in this path-only shim.
    generators.get_system_prompt=lambda role:prompt(role)
    namespace=dict(RolePlaying=role_playing.RolePlaying)
    original_definitions(role/'main_court.py',['court_interact'],namespace)
    result=namespace['court_interact'](request['case'],request.get('turns',4))
    if not result:raise ValueError('Original court interaction returned no recognized utterance')
    return dict(event='result',method='agentscourt',output=result,calls=count,
                source_commit=provenance['commit'],author_entry='main_court.court_interact -> RolePlaying/ChatAgent',
                original_complete_benchmark=False,full_legal_kb_judgment_pipeline_completed=False)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=execute(request)
    emit(result)
