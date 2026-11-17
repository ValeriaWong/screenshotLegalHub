"""
E01 · Single agent with controlled tools

论文出处：
- A01: Yao et al. (2022/23), *ReAct: Synergizing Reasoning and Acting in Language Models*.
  https://arxiv.org/abs/2210.03629

复现程度：project_mechanism。
案件run仍为项目受控工具原型；KIE/全图VQA的run_task执行作者Notebook webthink控制器，工具适配为冻结原图目录与像素局部读取；原benchmark未复现。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e01_react/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[A01] ReAct
原有方法/任务：知识问答、事实核验及交互环境决策。
原输入大致形态（结构示意，不是 Gold）：问答为 question；交互任务为目标与环境 observation。结构示意：question='某人的出生地是什么？'。
原输出大致形态：工具 action/observation 轨迹与最终答案或任务完成状态；不是带 SourceRef 的案件证明图。
原 benchmark：HotpotQA、FEVER、ALFWorld、WebShop；原任务分别采用回答/核验或环境成功率指标。
论文创新点（作者方法的组成）：交替进行任务分析与工具行动，利用真实环境观察更新后续行动。
对本工作的可适配性：条件可适配工具决策层；须把案内证据读取与法源检索分开，并保留观察到的陈述而非默认其为真。
核查依据：https://arxiv.org/html/2210.03629
作者代码：https://github.com/ysymyth/ReAct @ 6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9；本地 paper/upstream_sources/react

本文件当前实际实现：案件run仍为项目受控工具原型；KIE/全图VQA的run_task执行作者Notebook webthink控制器，工具适配为冻结原图目录与像素局部读取；原benchmark未复现。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
已接入run_task的输入轨道：kie_image、vqa_image_full；每步输入输出可追溯。
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩；独立gym/numpy环境；原WikiEnv与HotPotQAWrapper成功载入7405道dev题；原Notebook webthink函数体原样载入；截图变体用冻结原图目录和真实像素局部读取替换Wikipedia工具；KIE/全图VQA入口已接run_task；原图和局部图的哈希、坐标、逐步请求/响应保留，边界错误会停止；真实调用及失败记录：results/2026-10-29-per-paper/README.md；各论文100次持久上限共享原生/产品轨道
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：案件run(context)仍为项目原型；KIE/全图VQA为作者控制器
当前作者原代码状态：author_controller_native_and_product_real_validated
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""

import json
from screenshotlegal.experiments.contracts import CaseAnalysisOutput
from screenshotlegal.experiments.budget import BudgetExceeded
from .context import TOOL_PROTOCOL

METHOD_ID = 'E01'
METHOD_NAME = 'e01_react'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'project_mechanism'
REPRODUCTION_SCOPE = '案件run仍为项目受控工具原型；KIE/全图VQA的run_task执行作者Notebook webthink控制器，工具适配为冻结原图目录与像素局部读取；原benchmark未复现。'
PAPER_REFERENCES = [{'paper_id': 'A01', 'reference': 'Yao et al. (2022/23), *ReAct: Synergizing Reasoning and Acting in Language Models*.', 'sources': ['https://arxiv.org/abs/2210.03629'], 'verification': 'paper_listing_verified_not_code_reproduced'}]






























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'A01', 'method': 'ReAct', 'task': '知识问答、事实核验及交互环境决策。', 'input': "问答为 question；交互任务为目标与环境 observation。结构示意：question='某人的出生地是什么？'。", 'output': '工具 action/observation 轨迹与最终答案或任务完成状态；不是带 SourceRef 的案件证明图。', 'benchmark': 'HotpotQA、FEVER、ALFWorld、WebShop；原任务分别采用回答/核验或环境成功率指标。', 'innovation': '交替进行任务分析与工具行动，利用真实环境观察更新后续行动。', 'repo': 'react', 'source': 'https://arxiv.org/html/2210.03629', 'fit': '条件可适配工具决策层；须把案内证据读取与法源检索分开，并保留观察到的陈述而非默认其为真。', 'pinned_author_source': {'repository': 'https://github.com/ysymyth/ReAct', 'commit': '6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9', 'local_path': 'paper/upstream_sources/react'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_controller_native_and_product_real_validated', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '案件run仍为项目受控工具原型；KIE/全图VQA的run_task执行作者Notebook webthink控制器，工具适配为冻结原图目录与像素局部读取；原benchmark未复现。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': ['kie_image', 'vqa_image_full'], 'native_author_controller_real_run_passed': True, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩', '独立gym/numpy环境；原WikiEnv与HotPotQAWrapper成功载入7405道dev题', '原Notebook webthink函数体原样载入；截图变体用冻结原图目录和真实像素局部读取替换Wikipedia工具', 'KIE/全图VQA入口已接run_task；原图和局部图的哈希、坐标、逐步请求/响应保留，边界错误会停止', '真实调用及失败记录：results/2026-10-29-per-paper/README.md；各论文100次持久上限共享原生/产品轨道'], 'blockers': ['案件run(context)仍为项目原型；KIE/全图VQA为作者控制器'], 'native_verification': {'checks': {'author_controller_completed': True, 'answer_exact_match': True}, 'status': 'completed', 'original_complete_benchmark': False, 'scope': 'Native task/adapter execution; expert legal metrics deferred'}, 'real_product_tracks_completed': ['kie_image', 'vqa_image_full']}

async def run(context):
    visible = context.visible
    sources = context.sources
    tool = context.tool
    demo_output = context.demo_output
    options = context.options
    answer = context.answer
    catalog = context.catalog
    observations = []
    material = {k: v for k, v in visible.items() if k != 'sources'}
    material['source_catalog'] = catalog
    for turn in range(options['max_model_calls']):
        demo = dict(tool='source_read', args=dict(source_ref_id=sources[0]['id'], start=0, max_chars=3000)) if turn == 0 else dict(tool='finish', output=demo_output())
        decision = await answer('tool_' + str(turn), TOOL_PROTOCOL + ' finish.output需符合：' + json.dumps(CaseAnalysisOutput.model_json_schema(), ensure_ascii=False), dict(input=material, observations=observations), demo)
        if decision.get('tool') == 'finish':
            return decision.get('output')
        observation = await tool('react.' + str(turn), decision.get('tool'), decision.get('args', {}))
        observations.append(dict(tool=decision['tool'], observation=observation))
    raise BudgetExceeded('受控工具循环已到上限，未产生最终输出')


async def run_task(messages,call,attempts=2,tool_trace=None):
    """KIE/full-image VQA: original Notebook webthink + frozen image tools."""
    from .react_bridge import react
    return await react(messages,call,tool_trace)
