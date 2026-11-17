"""
E13 · GraphReader long case

论文出处：
- A07: Li et al. (2024), *GraphReader: Building Graph-based Agent to Enhance Long-Context Abilities*.
  https://arxiv.org/abs/2406.14550

复现程度：not_implemented。
尚未实现 GraphReader 图构建与图导航；文件仅登记出处，不能运行。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e13_graphreader/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[A07] GraphReader
原有方法/任务：把长文构造成 key elements/atomic facts 图，由 agent 按计划探索后回答。
原输入大致形态（结构示意，不是 Gold）：长文档与 question。
原输出大致形态：图探索/笔记及问答结果。
原 benchmark：LongBench 的 HotpotQA、2WikiMultihopQA、MuSiQue、NarrativeQA；LV-Eval HotpotWikiQA-mixup。
论文创新点（作者方法的组成）：图构建、原子事实、邻居/原块读取、反思与笔记支撑粗到细探索。
对本工作的可适配性：可用于长证据检索层，但图中压缩事实不是已证明事实，须回溯原文。E13 未实现该图与探索 agent。
核查依据：https://arxiv.org/html/2406.14550
作者代码：未固定对应作者入口；不得宣称已运行作者代码

本文件当前实际实现：尚未实现 GraphReader 图构建与图导航；文件仅登记出处，不能运行。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链；当前模块未实现
尚未完成/阻塞：GraphReader：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代；当前只有明确拒绝执行的登记文件，没有对应算法实现
当前作者原代码状态：original_benchmark_not_reproduced
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""


METHOD_ID = 'E13'
METHOD_NAME = 'e13_graphreader'
IMPLEMENTATION_STATUS = 'planned'
REPRODUCTION_LEVEL = 'not_implemented'
REPRODUCTION_SCOPE = '尚未实现 GraphReader 图构建与图导航；文件仅登记出处，不能运行。'
PAPER_REFERENCES = [{'paper_id': 'A07', 'reference': 'Li et al. (2024), *GraphReader: Building Graph-based Agent to Enhance Long-Context Abilities*.', 'sources': ['https://arxiv.org/abs/2406.14550'], 'verification': 'paper_listing_verified_not_code_reproduced'}]





























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'A07', 'method': 'GraphReader', 'task': '把长文构造成 key elements/atomic facts 图，由 agent 按计划探索后回答。', 'input': '长文档与 question。', 'output': '图探索/笔记及问答结果。', 'benchmark': 'LongBench 的 HotpotQA、2WikiMultihopQA、MuSiQue、NarrativeQA；LV-Eval HotpotWikiQA-mixup。', 'innovation': '图构建、原子事实、邻居/原块读取、反思与笔记支撑粗到细探索。', 'repo': None, 'source': 'https://arxiv.org/html/2406.14550', 'fit': '可用于长证据检索层，但图中压缩事实不是已证明事实，须回溯原文。E13 未实现该图与探索 agent。', 'resource_dependency': '第3.2节所引InsTag归一化包含语义嵌入、DBSCAN和关联聚合；当前本地权重分支按用户指令暂缓，远程嵌入配置未核实。', 'pinned_author_source': None}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'original_benchmark_not_reproduced', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链；当前模块未实现', 'current_project_implementation': '尚未实现 GraphReader 图构建与图导航；文件仅登记出处，不能运行。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': ['GraphReader：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代', '当前只有明确拒绝执行的登记文件，没有对应算法实现']}

async def run(context):
    raise ValueError('方法仅已登记，尚未实现，不可创建运行：e13_graphreader')
