"""
E00 · Single-shot direct answer

论文出处：
- 无单篇对应论文；本项目通用基线。

复现程度：generic_baseline。
通用单次回答基线；不对应单篇论文，不声称作者系统复现。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e00_single_shot/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

原方法/benchmark：无对应单篇论文，属于本项目单次回答基线。
原输入/输出：不适用；本项目输入冻结来源，输出 CaseAnalysisOutput。
本文件当前实际实现：通用单次回答基线；不对应单篇论文，不声称作者系统复现。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：非单篇论文复现的项目基线
尚未完成/阻塞：原项目基线，无作者复现任务
当前作者原代码状态：not_applicable_project_baseline
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""


METHOD_ID = 'E00'
METHOD_NAME = 'e00_single_shot'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'generic_baseline'
REPRODUCTION_SCOPE = '通用单次回答基线；不对应单篇论文，不声称作者系统复现。'
PAPER_REFERENCES = []






























ORIGINAL_PAPER_CONTRACTS = []
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'not_applicable_project_baseline', 'adaptability': '非单篇论文复现的项目基线', 'current_project_implementation': '通用单次回答基线；不对应单篇论文，不声称作者系统复现。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': []}

async def run(context):
    visible = context.visible
    answer = context.answer
    return await answer('answer', '直接根据材料完成有来源的分析；未知事项保持未知。', dict(input=visible))
