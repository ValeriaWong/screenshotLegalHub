"""
论文出处：Khatri et al., SCALE, EMNLP 2026.
https://aclanthology.org/2026.emnlp-main.36/
复现程度：author_components_with_domain_adaptation；原论文benchmark未复现。
作者代码：paper/upstream_sources/scale @ 1700924ca8c448af56c854e5e4c9ae693e86beb3。
原方法/创新：指南Issue–Factor层级→问题/因素匹配→¶段落检索→迭代分析。
原输入：ECHR案例、公约条文、Case-law Guides及其层级；原输出：因素/指南路径和LAW分析。
原benchmark：ECHR案例法律推理专家评估，不是KIE/DocVQA。
原任务入口：paper/author_reproductions/scale/product_adapter.py；公开案例双条文样本已运行。
产品入口：paper/author_reproductions/scale/case_adapter.py；实际加载作者阶段与检索函数。
产品输入：冻结中国法源、可选独立层级、案件来源及原文引用单元；输出CaseAnalysisOutput
及可导出的层级、段落路径、逐次分析、原/新提示词。Stage I/II只读法源，不读案件或Gold。
适配调试：法规替代ECHR指南；中文研究分析prompt替代裁判prompt；增加JSON投影。
不加载本地模型权重，模型由父进程AIPING预算接口调用。派生层级未经专家复核，
不是判例指南等价资源；保留法源草稿状态、事实争议与未知。真实产品验证结果另行记录。
作者问题/因素选择、段落检索和迭代分析；冻结中国法源及结构化输出任务适配。

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。
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

本文件当前实际实现：作者问题/因素选择、段落检索和迭代分析；冻结中国法源及结构化输出任务适配。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：作者StageProcessing(3/4)、ReasoningStage及段落函数体不变；Stage I/II原提示仅处理独立法源；中文研究提示及JSON投影差异完整保存；官方法源原文、快照及SHA256补齐；仍为unverified/unreviewed；实际AIPING产品6步完成；原生与产品共享100次账本
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证
当前作者原代码状态：author_native_and_case_product_real_validated
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""
METHOD_ID='E19'
METHOD_NAME='e19_scale'
IMPLEMENTATION_STATUS='implemented'
REPRODUCTION_LEVEL='author_components_with_domain_adaptation'
REPRODUCTION_SCOPE='作者问题/因素选择、段落检索和迭代分析；冻结中国法源及结构化输出任务适配。'
PAPER_REFERENCES = [{'paper_id': 'L09', 'reference': 'Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026:', 'sources': ['https://aclanthology.org/2026.emnlp-main.36/'], 'verification': 'paper_listing_verified_not_code_reproduced'}]





























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L09', 'method': 'SCALE', 'task': '基于 ECHR 案例和条款特定的 Case Law Guides 进行结构化先例法律推理。', 'input': '案件事实、相关公约条款及独立指南派生的 Issue–Factor Hierarchy。', 'output': '关联指南片段支持的法律分析；不是从测试答案反推的要件树。', 'benchmark': 'ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。', 'innovation': '用 Issue–Factor 层级把法律问题/事实因素映射到指南段落，驱动检索与分析。', 'repo': 'scale', 'source': 'https://aclanthology.org/2026.emnlp-main.36/', 'fit': '可适配冻结法律文本的案例证据研究。产品case_product已执行作者组件；中国法规集合替代ECHR判例指南，层级为未复核模型派生结果，不能验证原论文先例覆盖收益；不支持直接像素KIE。', 'pinned_author_source': {'repository': 'https://github.com/khatrimann/SCALE', 'commit': '1700924ca8c448af56c854e5e4c9ae693e86beb3', 'local_path': 'paper/upstream_sources/scale'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_native_and_case_product_real_validated', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '作者问题/因素选择、段落检索和迭代分析；冻结中国法源及结构化输出任务适配。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': True, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': True, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['作者StageProcessing(3/4)、ReasoningStage及段落函数体不变', 'Stage I/II原提示仅处理独立法源；中文研究提示及JSON投影差异完整保存', '官方法源原文、快照及SHA256补齐；仍为unverified/unreviewed', '实际AIPING产品6步完成；原生与产品共享100次账本'], 'blockers': [], 'native_verification': {'status': 'completed', 'checks': {'author_controller_completed': True, 'articles_processed': ['1_PROTOCOL_1', '6_CIVIL'], 'issue_factor_guide_paths_preserved': True, 'product_adaptation_completed': False, 'answer_quality': 'expert_review_deferred'}, 'original_complete_benchmark': False, 'new_supplier_requests_on_resume': 33, 'replayed_responses': 14}, 'real_product_tracks_completed': ['case_product'], 'product_verification': {'status': 'completed', 'checks': {'author_controller_completed': True, 'product_case_output_schema_valid': True, 'literal_citations_valid': True, 'guide_reference_path_preserved': True, 'independent_guide_source_only': True, 'local_model_inference': False, 'expert_legal_accuracy': None}, 'original_complete_benchmark': False}, 'local_model_inference': False, 'adaptation_limitations': ['中国法规集合替代ECHR判例指南，不验证原论文先例覆盖收益', '仅案例产品轨道；没有像素KIE接口或专家法律准确率']}

async def run(context):
    from .scale_bridge import scale_case
    return await scale_case(context)
