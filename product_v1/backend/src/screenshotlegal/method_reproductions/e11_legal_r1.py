"""
E11 · Agentic legal retrieval

论文出处：
- L11: Pang et al. (2026-10), *Legal-R1: Agentic Retrieval for Evidence-Based Legal Reasoning*.
  https://arxiv.org/abs/2610.18611

复现程度：project_mechanism。
复现 Lawyer 检索规划、冻结工具执行与 Judge 读取轨迹；未执行 masked SFT、GRPO、MMR/PSI 或作者检查点。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e11_legal_r1/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L11] Legal-R1
原有方法/任务：法律问题上的主动法源选择、检索充分性判断和证据轨迹回答。
原输入大致形态（结构示意，不是 Gold）：作者 infer_pipeline.py 默认读训练/RL JSON；实际取 row['Open-ended Verifiable Question']。同一行还含 Ground-True Answer、Complex_CoT，仅可保留作评测/参考，不能混入用户问题。规范库/类案库另行加载。
原输出大致形态：原 rollout 保存 original_question、turns、final_answer 及参考标签字段；最终回答从轨迹生成。它不是原图解析或带字符坐标的 ProofGraph。
原 benchmark：LawBench、LexEval；法条检索另有 provision-oriented 查询。原规范库与 LeCaRDv2 类案库须版本匹配。
论文创新点（作者方法的组成）：训练 Lawyer 检索策略（masked SFT、轨迹强化学习），结合 authority/diversity-aware Assistant 和 Judge。
对本工作的可适配性：可条件迁移法源检索，但案内证据必须另轨读取。未载入作者训练模型/检索库就不能算原 Legal-R1；当前 E11 是项目路由原型。 原入口的默认训练数据路径并非 LawBench/LexEval 的完整评测入口；需要另行配置原 benchmark 与评分器。
核查依据：https://arxiv.org/html/2610.18611v1
作者代码：https://github.com/killerqueen-wonder/Legal-R1 @ a2bf5054841a108b5f1a3be10fe1cd8a336ed806；本地 paper/upstream_sources/legal_r1

本文件当前实际实现：复现 Lawyer 检索规划、冻结工具执行与 Judge 读取轨迹；未执行 masked SFT、GRPO、MMR/PSI 或作者检查点。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：原训练模型/过程验证器/记忆机制或原任务资源未部署；同一底座 prompt 不能替代原训练
当前作者原代码状态：original_benchmark_not_reproduced
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""

from screenshotlegal.research.gateway import ModelFailure
from .context import TOOL_PROTOCOL

METHOD_ID = 'E11'
METHOD_NAME = 'e11_legal_r1'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'project_mechanism'
REPRODUCTION_SCOPE = '复现 Lawyer 检索规划、冻结工具执行与 Judge 读取轨迹；未执行 masked SFT、GRPO、MMR/PSI 或作者检查点。'
PAPER_REFERENCES = [{'paper_id': 'L11', 'reference': 'Pang et al. (2026-10), *Legal-R1: Agentic Retrieval for Evidence-Based Legal Reasoning*.', 'sources': ['https://arxiv.org/abs/2610.18611'], 'verification': 'paper_listing_verified_not_code_reproduced'}]





























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L11', 'method': 'Legal-R1', 'task': '法律问题上的主动法源选择、检索充分性判断和证据轨迹回答。', 'input': "作者 infer_pipeline.py 默认读训练/RL JSON；实际取 row['Open-ended Verifiable Question']。同一行还含 Ground-True Answer、Complex_CoT，仅可保留作评测/参考，不能混入用户问题。规范库/类案库另行加载。", 'output': '原 rollout 保存 original_question、turns、final_answer 及参考标签字段；最终回答从轨迹生成。它不是原图解析或带字符坐标的 ProofGraph。', 'benchmark': 'LawBench、LexEval；法条检索另有 provision-oriented 查询。原规范库与 LeCaRDv2 类案库须版本匹配。', 'innovation': '训练 Lawyer 检索策略（masked SFT、轨迹强化学习），结合 authority/diversity-aware Assistant 和 Judge。', 'repo': 'legal_r1', 'source': 'https://arxiv.org/html/2610.18611v1', 'fit': '可条件迁移法源检索，但案内证据必须另轨读取。未载入作者训练模型/检索库就不能算原 Legal-R1；当前 E11 是项目路由原型。 原入口的默认训练数据路径并非 LawBench/LexEval 的完整评测入口；需要另行配置原 benchmark 与评分器。', 'pinned_author_source': {'repository': 'https://github.com/killerqueen-wonder/Legal-R1', 'commit': 'a2bf5054841a108b5f1a3be10fe1cd8a336ed806', 'local_path': 'paper/upstream_sources/legal_r1'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'original_benchmark_not_reproduced', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '复现 Lawyer 检索规划、冻结工具执行与 Judge 读取轨迹；未执行 masked SFT、GRPO、MMR/PSI 或作者检查点。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': ['原训练模型/过程验证器/记忆机制或原任务资源未部署；同一底座 prompt 不能替代原训练']}

async def run(context):
    visible = context.visible
    tool = context.tool
    options = context.options
    answer = context.answer
    catalog = context.catalog
    observations = []
    material = {k: v for k, v in visible.items() if k not in {'sources', 'legal_corpus'}}
    material['source_catalog'] = catalog
    for turn in range(options['retrieval_rounds']):
        decision = await answer('lawyer.' + str(turn), TOOL_PROTOCOL + ' 当前仅是检索规划者，不是最终报告撰写者。选择案内证据或法律法源，针对缺口检索；证据不足也可结束，后续由独立judge说明未知。结束时只返回 {"tool":"finish","args":{}}，不要生成output、facts、summary或next_action字段。', dict(input=material, trajectory=observations), dict(tool='case_search', args=dict(query=visible['goal'][:200], limit=options['retrieval_top_k'])) if turn == 0 else dict(tool='finish', args={}))
        if decision.get('tool') == 'finish':
            break
        if decision.get('tool') not in {'case_search', 'source_read', 'authority_search'} or not isinstance(decision.get('args'), dict):
            raise ModelFailure('tool_protocol', '检索规划者未返回支持的工具动作；未执行工具')
        observation = await tool('legal_search.' + str(turn), decision.get('tool'), decision.get('args', {}))
        observations.append(dict(action=decision, observation=observation))
    return await answer('retrieval_judge', '根据完整检索轨迹生成结果；没有获得原文的来源不得编造引用。明确证据是否充分。', dict(input=material, trajectory=observations))
