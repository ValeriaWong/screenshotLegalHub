"""
E20 · VERDICT style iterative correction

论文出处：
- L08: Liao et al. (2026), *VERDICT: Verifiable Evolving Reasoning with Directive-Informed Collegial Teams for Legal Judgment Prediction*.
  https://arxiv.org/abs/2603.19306

复现程度：project_mechanism。
复现 clerk/assistant/judge/collegial/presiding 角色链与退回修订；无专家对齐模型、HJM 标准/微指令记忆演化。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e20_verdict/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L08] VERDICT
原有方法/任务：基于刑事案情预测适用法条、罪名和刑期，使用合议反馈与演化记忆。
原输入大致形态（结构示意，不是 Gold）：作者 CAIL 环境接收 configs['task'] 案情文本和 configs['expected'] 评分标签；模型任务文本只由 task 构造。训练监督与测试模式须分别配置。
原输出大致形态：原格式为 Finish[JSON]，字段 relevant_articles、accusation、term_of_imprisonment；刑期子字段 death_penalty、life_imprisonment、imprisonment。
原 benchmark：CAIL2018（CAIL-Small）、未来时间划分 CJO2025；当前作者 CLI 仅暴露 cail2018。
论文创新点（作者方法的组成）：五角色监督式 Pass/Reject 修订与 Hybrid Jurisprudential Memory / Micro-Directives 演化；不是普通多轮改写。
对本工作的可适配性：不能直接把刑事预测指标用于民事证据链。需重写任务环境/标签/规范检索，并隔离训练记忆与留出案件；E20 未复现 HJM/专家对齐模型。 源码训练验证分支可读取 expected；适配留出评测必须 mode=test 且关闭 training_mode_verification，并另审计 expected/正确性反馈是否经记忆回流。该边界尚未端到端验证。
核查依据：https://github.com/luckyhui235/VERDICT
作者代码：https://github.com/luckyhui235/VERDICT @ 1b6c9d6ecfbe95900076cbfd2eedf94aecaaf952；本地 paper/upstream_sources/verdict

本文件当前实际实现：复现 clerk/assistant/judge/collegial/presiding 角色链与退回修订；无专家对齐模型、HJM 标准/微指令记忆演化。
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


METHOD_ID = 'E20'
METHOD_NAME = 'e20_verdict'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'project_mechanism'
REPRODUCTION_SCOPE = '复现 clerk/assistant/judge/collegial/presiding 角色链与退回修订；无专家对齐模型、HJM 标准/微指令记忆演化。'
PAPER_REFERENCES = [{'paper_id': 'L08', 'reference': 'Liao et al. (2026), *VERDICT: Verifiable Evolving Reasoning with Directive-Informed Collegial Teams for Legal Judgment Prediction*.', 'sources': ['https://arxiv.org/abs/2603.19306'], 'verification': 'paper_listing_verified_not_code_reproduced'}]





























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L08', 'method': 'VERDICT', 'task': '基于刑事案情预测适用法条、罪名和刑期，使用合议反馈与演化记忆。', 'input': "作者 CAIL 环境接收 configs['task'] 案情文本和 configs['expected'] 评分标签；模型任务文本只由 task 构造。训练监督与测试模式须分别配置。", 'output': '原格式为 Finish[JSON]，字段 relevant_articles、accusation、term_of_imprisonment；刑期子字段 death_penalty、life_imprisonment、imprisonment。', 'benchmark': 'CAIL2018（CAIL-Small）、未来时间划分 CJO2025；当前作者 CLI 仅暴露 cail2018。', 'innovation': '五角色监督式 Pass/Reject 修订与 Hybrid Jurisprudential Memory / Micro-Directives 演化；不是普通多轮改写。', 'repo': 'verdict', 'source': 'https://github.com/luckyhui235/VERDICT', 'fit': '不能直接把刑事预测指标用于民事证据链。需重写任务环境/标签/规范检索，并隔离训练记忆与留出案件；E20 未复现 HJM/专家对齐模型。 源码训练验证分支可读取 expected；适配留出评测必须 mode=test 且关闭 training_mode_verification，并另审计 expected/正确性反馈是否经记忆回流。该边界尚未端到端验证。', 'pinned_author_source': {'repository': 'https://github.com/luckyhui235/VERDICT', 'commit': '1b6c9d6ecfbe95900076cbfd2eedf94aecaaf952', 'local_path': 'paper/upstream_sources/verdict'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'original_benchmark_not_reproduced', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '复现 clerk/assistant/judge/collegial/presiding 角色链与退回修订；无专家对齐模型、HJM 标准/微指令记忆演化。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': ['原训练模型/过程验证器/记忆机制或原任务资源未部署；同一底座 prompt 不能替代原训练']}

async def run(context):
    visible = context.visible
    tool = context.tool
    demo_output = context.demo_output
    options = context.options
    answer = context.answer
    notes = await answer('court_clerk', '提取争点、行为、主观意图是否可知及后果。返回 {"issues":[...],"facts":[...],"query":字符串}，事实须有原文引用；对意图只列可见证据和不确定项。', dict(input=visible), dict(issues=[], facts=demo_output()['facts'], query=visible['goal'][:200]))
    statutes = await tool('judicial_assistant', 'authority_search', dict(query=notes['query'], limit=options['retrieval_top_k']))
    material = dict(visible, legal_corpus=statutes)
    output = await answer('case_judge', '根据书记员记录和检索法源起草分析；法源未审核、事实不明时明确保留。', dict(input=material, clerk_notes=notes))
    history = []
    for i in range(options['refinement_rounds']):
        review = await answer('collegial_review.' + str(i), '逐项审查事实、规范适用与结论一致性。返回 {"pass":bool,"directives":[字符串]}；每条修改指令指出对象、依据和可执行动作，不得补造证据。', dict(input=material, draft=output, review_history=history), {'pass': False, 'directives': ['核对原文与未决项']})
        if type(review.get('pass')) is not bool or not isinstance(review.get('directives'), list) or any((not isinstance(d, str) for d in review['directives'])):
            raise ValueError('合议审查输出无效')
        history.append(review)
        if review['pass']:
            break
        output = await answer('redraft.' + str(i), '逐项执行合议修改指令，保持原文引用与明确的不确定项。', dict(input=material, draft=output, review_history=history))
    return await answer('presiding_judge', '汇总草稿和完整审查记录，核对原文后给出最终分析，不将未决争议写成定论。', dict(input=material, draft=output, review_history=history))
