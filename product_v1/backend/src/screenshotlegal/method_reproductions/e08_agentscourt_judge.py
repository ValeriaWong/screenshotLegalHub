"""
E08 · Adversarial with judge aggregation

论文出处：
- L01: He et al. (2024), *AgentsCourt: Building Judicial Decision-Making Agents with Court Debate Simulation and Legal Knowledge Augmentation*. EMNLP Findings.
  https://arxiv.org/abs/2403.02959
- L10: Nguyen et al. (2026), *L-MAD: A Systematic Evaluation of Multi-Agent Debate Structures in Legal Reasoning*.
  https://arxiv.org/abs/2607.09099

复现程度：project_mechanism。
复现双方交换后增加中立汇总者；未复现作者训练、原始角色与评价基准。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e08_agentscourt_judge/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L01] AgentsCourt
原有方法/任务：从给定案情模拟法庭辩论、检索法律知识并生成裁判分析。
原输入大致形态（结构示意，不是 Gold）：SimuCourt 中的案情与案件类型/审级等任务信息，通常是已整理的案件叙述。
原输出大致形态：案件分析、适用法条、裁判结果；刑事任务涉及罪名、刑期和罚金。
原 benchmark：SimuCourt，420 份中文裁判文书，涉及民事、行政、刑事及审级设置；配套 Legal-KB。
论文创新点（作者方法的组成）：法庭辩论模拟、法律资源增强与裁判迭代结合；不等于增加两个对立角色。
对本工作的可适配性：仅条件适配辩论机制。聊天中的主张/否认必须保留认识状态，不能先改成法院已认定事实；裁判标签也不能直接充当证据链 Gold。
核查依据：https://aclanthology.org/2024.findings-emnlp.549/
作者代码：https://github.com/Zhitao-He/AgentsCourt @ 7c14d6960abfdfdd7366250905da8dbcb416d6d6；本地 paper/upstream_sources/agentscourt

[L10] L-MAD (Nguyen et al., 2026)
原有方法/任务：法条premise与法律hypothesis之间的二分类蕴含判断；比较三persona的混合共识与固定轮次排名投票。
原输入大致形态（结构示意，不是 Gold）：原COLIEE每题Relevant article、Query、Answer。只把法条与问题送给模型；原答案仅评分。本轮原任务为论文2.1节Article9官方英文翻译示例，不是R05/R06/R07年度数据集。
原输出大致形态：正文固定Answer:Y/N与简短公开说明；附录日文提示却要求判断:Y/N，二者分别解析。协议还产生AGREE/DISAGREE、排名与收敛/平局/未知轨迹。
原 benchmark：COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。
论文创新点（作者方法的组成）：在两轮滑动记忆下比较共识与排名投票，保持分歧和最多一轮平局补充讨论，研究协议/规模对法律判断的影响。
对本工作的可适配性：论文协议调度＋实际所引MALLM提示/共识/排名组件；未核实L-MAD作者仓库。混合参数按论文配置，不能直接用不同的MALLM默认值。DeepSeek替换原本地模型、固定附录persona、原示例英文语言差异均披露。二分类KIE文本VQA双向验候选，N不自动推出相反标签；案件先核验最多2项有原文锚点的陈述，再修订，不能由共识推定法律正确。
核查依据：https://arxiv.org/html/2607.09099v1
作者代码：未固定对应作者入口；不得宣称已运行作者代码

本文件当前实际实现：复现双方交换后增加中立汇总者；未复现作者训练、原始角色与评价基准。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：L-MAD (Nguyen et al., 2026)：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代；作者 Legal-KB、原检索组件及 SimuCourt 原协议尚未端到端运行
当前作者原代码状态：original_benchmark_not_reproduced
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""

import copy

METHOD_ID = 'E08'
METHOD_NAME = 'e08_agentscourt_judge'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'project_mechanism'
REPRODUCTION_SCOPE = '复现双方交换后增加中立汇总者；未复现作者训练、原始角色与评价基准。'
PAPER_REFERENCES = [{'paper_id': 'L01', 'reference': 'He et al. (2024), *AgentsCourt: Building Judicial Decision-Making Agents with Court Debate Simulation and Legal Knowledge Augmentation*. EMNLP Findings.', 'sources': ['https://arxiv.org/abs/2403.02959'], 'verification': 'paper_listing_verified_not_code_reproduced'}, {'paper_id': 'L10', 'reference': 'Nguyen et al. (2026), *L-MAD: A Systematic Evaluation of Multi-Agent Debate Structures in Legal Reasoning*.', 'sources': ['https://arxiv.org/abs/2607.09099'], 'verification': 'paper_listing_verified_not_code_reproduced'}]






























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L01', 'method': 'AgentsCourt', 'task': '从给定案情模拟法庭辩论、检索法律知识并生成裁判分析。', 'input': 'SimuCourt 中的案情与案件类型/审级等任务信息，通常是已整理的案件叙述。', 'output': '案件分析、适用法条、裁判结果；刑事任务涉及罪名、刑期和罚金。', 'benchmark': 'SimuCourt，420 份中文裁判文书，涉及民事、行政、刑事及审级设置；配套 Legal-KB。', 'innovation': '法庭辩论模拟、法律资源增强与裁判迭代结合；不等于增加两个对立角色。', 'repo': 'agentscourt', 'source': 'https://aclanthology.org/2024.findings-emnlp.549/', 'fit': '仅条件适配辩论机制。聊天中的主张/否认必须保留认识状态，不能先改成法院已认定事实；裁判标签也不能直接充当证据链 Gold。', 'pinned_author_source': {'repository': 'https://github.com/Zhitao-He/AgentsCourt', 'commit': '7c14d6960abfdfdd7366250905da8dbcb416d6d6', 'local_path': 'paper/upstream_sources/agentscourt'}}, {'paper_id': 'L10', 'method': 'L-MAD (Nguyen et al., 2026)', 'task': '法条premise与法律hypothesis之间的二分类蕴含判断；比较三persona的混合共识与固定轮次排名投票。', 'input': '原COLIEE每题Relevant article、Query、Answer。只把法条与问题送给模型；原答案仅评分。本轮原任务为论文2.1节Article9官方英文翻译示例，不是R05/R06/R07年度数据集。', 'output': '正文固定Answer:Y/N与简短公开说明；附录日文提示却要求判断:Y/N，二者分别解析。协议还产生AGREE/DISAGREE、排名与收敛/平局/未知轨迹。', 'benchmark': 'COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。', 'innovation': '在两轮滑动记忆下比较共识与排名投票，保持分歧和最多一轮平局补充讨论，研究协议/规模对法律判断的影响。', 'repo': None, 'cited_framework_repo': 'mallm', 'source': 'https://arxiv.org/html/2607.09099v1', 'fit': '论文协议调度＋实际所引MALLM提示/共识/排名组件；未核实L-MAD作者仓库。混合参数按论文配置，不能直接用不同的MALLM默认值。DeepSeek替换原本地模型、固定附录persona、原示例英文语言差异均披露。二分类KIE文本VQA双向验候选，N不自动推出相反标签；案件先核验最多2项有原文锚点的陈述，再修订，不能由共识推定法律正确。', 'pinned_author_source': None}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'original_benchmark_not_reproduced', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '复现双方交换后增加中立汇总者；未复现作者训练、原始角色与评价基准。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': ['L-MAD (Nguyen et al., 2026)：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代', '作者 Legal-KB、原检索组件及 SimuCourt 原协议尚未端到端运行'], 'native_component_verification': 'SimuCourt首例庭辩组件真实执行完成；完整Legal-KB检索和判决未完成；产品入口仍为原型'}

async def run(context):
    visible = context.visible
    answer = context.answer
    staged = context.staged
    output = await staged(visible)
    rounds = 1
    positions = {}
    roles = {'claimant': '从主张方角度检验支持路径，也要明确不利事实与不能成立的前提。', 'respondent': '从相对方角度检验反证、抗辩及替代解释；不能虚构材料。'}
    for name, task in roles.items():
        positions[name] = await answer('position.' + name, task, dict(input=visible, draft=output))
    for round_no in range(rounds):
        previous = copy.deepcopy(positions)
        for name, task in roles.items():
            positions[name] = await answer('debate.' + str(round_no) + '.' + name, task + ' 只根据冻结原文和上一轮双方意见修订，保留无法消解的分歧。', dict(input=visible, previous_round=previous))
    output = await answer('reconcile', '作为原始起草者整合双方论点，明确接受/拒绝依据和未解决分歧。', dict(input=visible, draft=output, positions=positions))
    output = await answer('judge', '作为独立中立汇总者核对原文及双方观点，形成有条件的结论。不得多数投票代替事实，不宣称真实裁判。', dict(input=visible, positions=positions, reconciled=output))
    return output
