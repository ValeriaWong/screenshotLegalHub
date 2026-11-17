# e19_scale

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
