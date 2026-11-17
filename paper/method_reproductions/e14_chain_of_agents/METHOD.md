# e14_chain_of_agents

原论文与适配核查（2026-10-29）



复现判定：论文Algorithm 1及Table 9/10的重实现，非作者源码执行；完整原论文benchmark未复现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[A06] Chain of Agents (Zhang et al., 2024)

原有方法/任务：完整长上下文问答、摘要与代码补全；worker顺序更新累计CU，独立manager只接收最后CU。

原输入大致形态（结构示意，不是 Gold）：完整长文本x、可选问题q、task requirement；初始CU为空。原任务本轮为官方LongBench HotpotQA第0条完整54062字符上下文。

原输出大致形态：答案/摘要/代码文本及逐轮CU；不直接包含截图坐标或CaseAnalysisOutput。

原 benchmark：HotpotQA、MuSiQue、NarrativeQA、Qasper、QuALITY、QMSum、GovReport、BookSum、RepoBench-P。原QA F1、摘要ROUGE与代码相似度分轨记录；未跑完整benchmark。

论文创新点（作者方法的组成）：顺序交错阅读和跨片段CU交接，以独立manager仅基于最终累计知识作答；不是独立分块摘要后拼接或RAG。

对本工作的可适配性：按公开Algorithm 1和Table 9/10重实现；未核实到作者发布的源码入口，不用OPPO同名项目冒充。DeepSeek替换Vertex模型，cl100k_base作为显式分词代理；产品增加JSON、原文引用保留。支持冻结KIE预测文本VQA和案件文本，不直接抽取图像。

核查依据：https://arxiv.org/html/2406.02818v1

作者代码：未固定对应作者入口；不得宣称已运行作者代码



本文件当前实际实现：论文Algorithm 1与Tables 9/10重实现：完整token分块、顺序CU、last-CU-only manager；DeepSeek/分词器和产品JSON为显式适配。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

论文算法重实现已接入本文件run()：是；不是作者源码执行。

已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：按Algorithm 1及Tables 9/10实现，不执行未经核实的同名仓库；完整token文本覆盖、Unicode无损分块、逐轮CU与last-CU-only manager通过工程验证；旧字符分块计划拒绝以新代码运行；模型输出cap与温度向网关实际传递；冻结KIE文本VQA与案例JSON引用契约单独适配，无本地权重

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证

当前作者原代码状态：not_executed_no_verified_author_repository

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
