"""
E03 · Fixed workflow with Matter Pack

论文出处：
- L07: Lu et al. (2026), *From Query to Counsel: Structured Reasoning with a Multi-Agent Framework and Dataset for Legal Consultation* (JurisMA).
  https://arxiv.org/abs/2604.10470
- L09: Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026:
  https://aclanthology.org/2026.emnlp-main.36/

复现程度：project_baseline。
本项目三阶段工作流加领域模板；参考 JurisMA/SCALE 的结构化知识，不等于两篇作者系统。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e03_staged_with_matterpack/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L07] JurisMA
原有方法/任务：中文法律咨询问答；查询转法律要素图，再动态协作与内容修订。
原输入大致形态（结构示意，不是 Gold）：用户法律咨询问题，可能长、非正式且存在多个争点；不要求先输入截图或 ProofGraph。
原输出大致形态：面向用户的咨询答复和法律依据；要素图是中间结构。
原 benchmark：修订版 LawBench；JurisCQAD 用于训练/DPO。另有 LegalBench-RuleQA 小样本迁移实验。
论文创新点（作者方法的组成）：实体/事件/意图/争点结构、动态任务路由、法条 grounding 与内容修订，并构建咨询偏好数据。
对本工作的可适配性：可将论文§3.2–3.4/Algorithm 1推理算法适配为远程API咨询、冻结预测KIE文本VQA和案件结构映射；DPO与本地检查点暂缓，非作者代码/完整论文复现。
核查依据：https://arxiv.org/html/2604.10470v1
作者代码：未固定对应作者入口；不得宣称已运行作者代码

[L09] SCALE
原有方法/任务：基于 ECHR 案例和条款特定的 Case Law Guides 进行结构化先例法律推理。
原输入大致形态（结构示意，不是 Gold）：案件事实、相关公约条款及独立指南派生的 Issue–Factor Hierarchy。
原输出大致形态：关联指南片段支持的法律分析；不是从测试答案反推的要件树。
原 benchmark：ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。
论文创新点（作者方法的组成）：用 Issue–Factor 层级把法律问题/事实因素映射到指南段落，驱动检索与分析。
对本工作的可适配性：可适配冻结法律文本的案例证据研究。产品case_product已执行作者组件；中国法规集合替代ECHR判例指南，层级为未复核模型派生结果，不能验证原论文先例覆盖收益；不支持直接像素KIE。
核查依据：https://aclanthology.org/2026.emnlp-main.36/
作者代码：https://github.com/khatrimann/SCALE @ 1700924ca8c448af56c854e5e4c9ae693e86beb3；本地 paper/upstream_sources/scale

本文件当前实际实现：本项目三阶段工作流加领域模板；参考 JurisMA/SCALE 的结构化知识，不等于两篇作者系统。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：非单篇论文复现的项目基线
尚未完成/阻塞：JurisMA：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代
当前作者原代码状态：not_applicable_project_baseline
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""


METHOD_ID = 'E03'
METHOD_NAME = 'e03_staged_with_matterpack'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'project_baseline'
REPRODUCTION_SCOPE = '本项目三阶段工作流加领域模板；参考 JurisMA/SCALE 的结构化知识，不等于两篇作者系统。'
PAPER_REFERENCES = [{'paper_id': 'L07', 'reference': 'Lu et al. (2026), *From Query to Counsel: Structured Reasoning with a Multi-Agent Framework and Dataset for Legal Consultation* (JurisMA).', 'sources': ['https://arxiv.org/abs/2604.10470'], 'verification': 'paper_listing_verified_not_code_reproduced'}, {'paper_id': 'L09', 'reference': 'Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026:', 'sources': ['https://aclanthology.org/2026.emnlp-main.36/'], 'verification': 'paper_listing_verified_not_code_reproduced'}]






























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L07', 'method': 'JurisMA', 'task': '中文法律咨询问答；查询转法律要素图，再动态协作与内容修订。', 'input': '用户法律咨询问题，可能长、非正式且存在多个争点；不要求先输入截图或 ProofGraph。', 'output': '面向用户的咨询答复和法律依据；要素图是中间结构。', 'benchmark': '修订版 LawBench；JurisCQAD 用于训练/DPO。另有 LegalBench-RuleQA 小样本迁移实验。', 'innovation': '实体/事件/意图/争点结构、动态任务路由、法条 grounding 与内容修订，并构建咨询偏好数据。', 'repo': None, 'source': 'https://arxiv.org/html/2604.10470v1', 'fit': '可将论文§3.2–3.4/Algorithm 1推理算法适配为远程API咨询、冻结预测KIE文本VQA和案件结构映射；DPO与本地检查点暂缓，非作者代码/完整论文复现。', 'pinned_author_source': None}, {'paper_id': 'L09', 'method': 'SCALE', 'task': '基于 ECHR 案例和条款特定的 Case Law Guides 进行结构化先例法律推理。', 'input': '案件事实、相关公约条款及独立指南派生的 Issue–Factor Hierarchy。', 'output': '关联指南片段支持的法律分析；不是从测试答案反推的要件树。', 'benchmark': 'ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。', 'innovation': '用 Issue–Factor 层级把法律问题/事实因素映射到指南段落，驱动检索与分析。', 'repo': 'scale', 'source': 'https://aclanthology.org/2026.emnlp-main.36/', 'fit': '可适配冻结法律文本的案例证据研究。产品case_product已执行作者组件；中国法规集合替代ECHR判例指南，层级为未复核模型派生结果，不能验证原论文先例覆盖收益；不支持直接像素KIE。', 'pinned_author_source': {'repository': 'https://github.com/khatrimann/SCALE', 'commit': '1700924ca8c448af56c854e5e4c9ae693e86beb3', 'local_path': 'paper/upstream_sources/scale'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'not_applicable_project_baseline', 'adaptability': '非单篇论文复现的项目基线', 'current_project_implementation': '本项目三阶段工作流加领域模板；参考 JurisMA/SCALE 的结构化知识，不等于两篇作者系统。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': ['JurisMA：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代']}

async def run(context):
    visible = context.visible
    staged = context.staged
    output = await staged(visible)
    return output
