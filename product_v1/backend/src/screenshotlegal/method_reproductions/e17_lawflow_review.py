"""
E17 · Human review gates

论文出处：
- L03: Das et al. (2025), *LawFlow: Collecting and Simulating Lawyers�� Thought Processes*. Microsoft Research:
  https://www.microsoft.com/en-us/research/publication/lawflow-collecting-and-simulating-lawyers-thought-processes/

复现程度：not_implemented。
尚未实现受控人工反馈评测协议；不把现有审核页面视作 LawFlow 复现。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e17_lawflow_review/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L03] LawFlow
原有方法/任务：采集并模拟真实商业实体设立场景中的完整律师工作流。
原输入大致形态（结构示意，不是 Gold）：客户业务/实体设立情景及后续约束、信息需求。
原输出大致形态：动态、模块化、会回退修订的法律工作流记录；不是单一判断标签。
原 benchmark：LawFlow 工作流数据及人类与 LLM 工作流比较；不是现有截图案件的法律准确率 benchmark。
论文创新点（作者方法的组成）：记录端到端律师流程与分支/修订行为，比较人类和模型工作流结构。
对本工作的可适配性：可借鉴人工介入和回退评测，但 E17 目前没有实现该数据/协议；现有审核 UI 不等于 LawFlow 复现。
核查依据：https://www.microsoft.com/en-us/research/publication/lawflow-collecting-and-simulating-lawyers-thought-processes/
作者代码：https://github.com/minnesotanlp/LawFlow @ 0a3f0327c7d44f0c38d27b1f6d5e0362b72f1d64；本地 paper/upstream_sources/lawflow

本文件当前实际实现：尚未实现受控人工反馈评测协议；不把现有审核页面视作 LawFlow 复现。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链；当前模块未实现
尚未完成/阻塞：当前只有明确拒绝执行的登记文件，没有对应算法实现
当前作者原代码状态：original_benchmark_not_reproduced
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""


METHOD_ID = 'E17'
METHOD_NAME = 'e17_lawflow_review'
IMPLEMENTATION_STATUS = 'planned'
REPRODUCTION_LEVEL = 'not_implemented'
REPRODUCTION_SCOPE = '尚未实现受控人工反馈评测协议；不把现有审核页面视作 LawFlow 复现。'
PAPER_REFERENCES = [{'paper_id': 'L03', 'reference': 'Das et al. (2025), *LawFlow: Collecting and Simulating Lawyers�� Thought Processes*. Microsoft Research:', 'sources': ['https://www.microsoft.com/en-us/research/publication/lawflow-collecting-and-simulating-lawyers-thought-processes/'], 'verification': 'paper_listing_verified_not_code_reproduced'}]





























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L03', 'method': 'LawFlow', 'task': '采集并模拟真实商业实体设立场景中的完整律师工作流。', 'input': '客户业务/实体设立情景及后续约束、信息需求。', 'output': '动态、模块化、会回退修订的法律工作流记录；不是单一判断标签。', 'benchmark': 'LawFlow 工作流数据及人类与 LLM 工作流比较；不是现有截图案件的法律准确率 benchmark。', 'innovation': '记录端到端律师流程与分支/修订行为，比较人类和模型工作流结构。', 'repo': 'lawflow', 'source': 'https://www.microsoft.com/en-us/research/publication/lawflow-collecting-and-simulating-lawyers-thought-processes/', 'fit': '可借鉴人工介入和回退评测，但 E17 目前没有实现该数据/协议；现有审核 UI 不等于 LawFlow 复现。', 'pinned_author_source': {'repository': 'https://github.com/minnesotanlp/LawFlow', 'commit': '0a3f0327c7d44f0c38d27b1f6d5e0362b72f1d64', 'local_path': 'paper/upstream_sources/lawflow'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'original_benchmark_not_reproduced', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链；当前模块未实现', 'current_project_implementation': '尚未实现受控人工反馈评测协议；不把现有审核页面视作 LawFlow 复现。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': ['当前只有明确拒绝执行的登记文件，没有对应算法实现']}

async def run(context):
    raise ValueError('方法仅已登记，尚未实现，不可创建运行：e17_lawflow_review')
