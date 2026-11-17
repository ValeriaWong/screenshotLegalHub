"""
E10 · Factor aware legal retrieval

论文出处：
- L09: Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026:
  https://aclanthology.org/2026.emnlp-main.36/
- L14: Li et al. (2026), *Legal-DC: Benchmarking Retrieval-Augmented Generation for Legal Documents* (LegRAG).
  https://arxiv.org/abs/2603.11772

复现程度：project_mechanism。
复现按要件提问后闭域检索与阶段分析；当前词项检索，不含向量训练、重排或完整 SCALE 指南层级。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e10_factor_guided_retrieval/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L09] SCALE
原有方法/任务：基于 ECHR 案例和条款特定的 Case Law Guides 进行结构化先例法律推理。
原输入大致形态（结构示意，不是 Gold）：案件事实、相关公约条款及独立指南派生的 Issue–Factor Hierarchy。
原输出大致形态：关联指南片段支持的法律分析；不是从测试答案反推的要件树。
原 benchmark：ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。
论文创新点（作者方法的组成）：用 Issue–Factor 层级把法律问题/事实因素映射到指南段落，驱动检索与分析。
对本工作的可适配性：可适配冻结法律文本的案例证据研究。产品case_product已执行作者组件；中国法规集合替代ECHR判例指南，层级为未复核模型派生结果，不能验证原论文先例覆盖收益；不支持直接像素KIE。
核查依据：https://aclanthology.org/2026.emnlp-main.36/
作者代码：https://github.com/khatrimann/SCALE @ 1700924ca8c448af56c854e5e4c9ae693e86beb3；本地 paper/upstream_sources/scale

[L14] Legal-DC / LegRAG
原有方法/任务：中文法律文档咨询与检索器/生成器联合评测。
原输入大致形态（结构示意，不是 Gold）：法律文档集合与 question；标注带条款级引用。
原输出大致形态：检索条款及依据文档的咨询答案。
原 benchmark：Legal-DC：480 份法律文档、2,475 个问答，条款级标注；不是聊天真实性或举证责任测试集。
论文创新点（作者方法的组成）：条款完整性的索引与双路径自反思检验，配套检索/回答联合评测。
对本工作的可适配性：适合法源/文档检索层的条件适配；E10 当前词项查询没有实现 LegRAG 的原索引/双路径反思。
核查依据：https://arxiv.org/html/2603.11772v1
作者代码：https://github.com/legal-dc/Legal-DC @ 1f4422e4a9de4ce7bb311ebf926f61c1b077d50a；本地 paper/upstream_sources/legal_dc

本文件当前实际实现：复现按要件提问后闭域检索与阶段分析；当前词项检索，不含向量训练、重排或完整 SCALE 指南层级。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：原项目基线，无作者复现任务
当前作者原代码状态：original_benchmark_not_reproduced
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""


METHOD_ID = 'E10'
METHOD_NAME = 'e10_factor_guided_retrieval'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'project_mechanism'
REPRODUCTION_SCOPE = '复现按要件提问后闭域检索与阶段分析；当前词项检索，不含向量训练、重排或完整 SCALE 指南层级。'
PAPER_REFERENCES = [{'paper_id': 'L09', 'reference': 'Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026:', 'sources': ['https://aclanthology.org/2026.emnlp-main.36/'], 'verification': 'paper_listing_verified_not_code_reproduced'}, {'paper_id': 'L14', 'reference': 'Li et al. (2026), *Legal-DC: Benchmarking Retrieval-Augmented Generation for Legal Documents* (LegRAG).', 'sources': ['https://arxiv.org/abs/2603.11772'], 'verification': 'paper_listing_verified_not_code_reproduced'}]





























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L09', 'method': 'SCALE', 'task': '基于 ECHR 案例和条款特定的 Case Law Guides 进行结构化先例法律推理。', 'input': '案件事实、相关公约条款及独立指南派生的 Issue–Factor Hierarchy。', 'output': '关联指南片段支持的法律分析；不是从测试答案反推的要件树。', 'benchmark': 'ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。', 'innovation': '用 Issue–Factor 层级把法律问题/事实因素映射到指南段落，驱动检索与分析。', 'repo': 'scale', 'source': 'https://aclanthology.org/2026.emnlp-main.36/', 'fit': '可适配冻结法律文本的案例证据研究。产品case_product已执行作者组件；中国法规集合替代ECHR判例指南，层级为未复核模型派生结果，不能验证原论文先例覆盖收益；不支持直接像素KIE。', 'pinned_author_source': {'repository': 'https://github.com/khatrimann/SCALE', 'commit': '1700924ca8c448af56c854e5e4c9ae693e86beb3', 'local_path': 'paper/upstream_sources/scale'}}, {'paper_id': 'L14', 'method': 'Legal-DC / LegRAG', 'task': '中文法律文档咨询与检索器/生成器联合评测。', 'input': '法律文档集合与 question；标注带条款级引用。', 'output': '检索条款及依据文档的咨询答案。', 'benchmark': 'Legal-DC：480 份法律文档、2,475 个问答，条款级标注；不是聊天真实性或举证责任测试集。', 'innovation': '条款完整性的索引与双路径自反思检验，配套检索/回答联合评测。', 'repo': 'legal_dc', 'source': 'https://arxiv.org/html/2603.11772v1', 'fit': '适合法源/文档检索层的条件适配；E10 当前词项查询没有实现 LegRAG 的原索引/双路径反思。', 'pinned_author_source': {'repository': 'https://github.com/legal-dc/Legal-DC', 'commit': '1f4422e4a9de4ce7bb311ebf926f61c1b077d50a', 'local_path': 'paper/upstream_sources/legal_dc'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'original_benchmark_not_reproduced', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '复现按要件提问后闭域检索与阶段分析；当前词项检索，不含向量训练、重排或完整 SCALE 指南层级。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': []}

async def run(context):
    visible = context.visible
    options = context.options
    answer = context.answer
    staged = context.staged
    retrieve = context.retrieve
    hierarchy = visible.get('matterpack', {}).get('factor_hierarchy')
    query = await answer('factor_query', '按争点与法律要件提出一个检索查询，返回 {"query":字符串,"factor_ids":[字符串]}。只用给定规则结构，不预判案件事实。', dict(goal=visible['goal'], matterpack=visible.get('matterpack'), factor_hierarchy=hierarchy), dict(query=visible['goal'][:200], factor_ids=[hierarchy[0]['factors'][0]['id']] if hierarchy else []))
    chosen = await retrieve(query['query'], 'factor', options['retrieval_top_k'])
    material = dict(visible, sources=chosen, retrieval_scope='selected_frozen_passages', factor_selection=query)
    return await staged(material)
