# 逐篇实施队列

**2026-10-30用户调整：先略过本地模型权重推理/训练和较重计算分支，优先API方法。详见[当前资源优先级](RESOURCE_PRIORITY_2026-10-30.md)。以下本地资源任务保留待办，不作为当前执行顺序。**

目标保持全部51条目中的方法、工具和基准适配。当前6篇作者源码方法完成开发轨道：ReAct、Self-Refine、Reflexion、RAPTOR、LightRAG、SCALE；CoA论文算法重实现另完成原任务/文本VQA/案件产品执行，原QA参考未命中（F1=1/3），不计为作者源码执行。L-MAD另以论文协议＋所引MALLM原组件完成原示例两协议和文本VQA执行，非L-MAD作者源码；两个VQA均弃答，案件空事实输出只通过结构验证。完整原论文benchmark与专家法律评测另行记录，不作为本轮环境/适配门槛。

1. LegalAgentBench：作者三原控制器已完成原首任务的精确工具回放；三种产品冻结KIE文本VQA均弃答0，E23网页/API及variant冻结已接入，真实案件ReAct返回3项陈述事实/3引用。原工具端点拒绝连接，仍需恢复原服务和独立浏览器验收；不阻塞后续论文API分支推进。未计整篇完成；详见[原代码与I/O](legalagentbench/README.md)。
2. SCALE原ECHR案例与中国法源case_product开发样本均已完成；详见scale/README.md，累计66/100次，保留法规替代判例指南的适配边界。MetaGPT的原默认软件流程与案件产品已真实执行，原QaEngineer续跑19次已执行，仍有2个失败测试文件及最终未执行修订，累计45/100，保持部分完成；下一步继续可通过API运行的法律方法、其余基准的官方数据/评分器，并保留该QA待办。LawBench已完成19类×两种提示的38个原任务样本和产品补充评分接口；2-1本地LTP暂缓，不能将该条目计为完整方法完成。
3. 完成PaddleOCR-VL原权重识别、原布局与页面流水线，再接消息KIE/全局VQA；元素识别单独成功不计完整方法成功。
4. 补齐AgentsCourt原Legal-KB检索与最终判决链；庭辩组件成功不计全文方法成功。
5. SOLAR Stage I审核前原图已真实4次执行，24类/71属性/21规则通过原结构校验，累计6/100；保留[原人工审核门槛](solar/STAGE_I_REVIEW_2026-10-30.md)。新解释器/训练反馈及中国规则域仍待完成。
6. LawFlow原工作流计划、执行与监控训练分支逐一验证；作者源码已固定。
7. LegalReasoner、JurisMA、Legal-R1、VERDICT、CRAG、Legal-DC、CoA后续原基准扩大验证、GraphReader、L-MAD后续数据扩大验证及其余条目，逐篇处理作者资源/检查点/原任务与适配。来源不明的同名项目不替代作者代码。

每篇至多100次AIPING供应商请求，共享原生和产品轨道。每次发送前落持久预留；缓存只回放相同请求ID和相同输入的已完成响应，失败/未知请求保留。恢复曾因请求命名空间错误重复5次SCALE请求，已计入预算并修正，详见本批报告。

[全部51条目](PAPER_COVERAGE.md) · [25配置状态](IMPLEMENTATION_STATUS.json) · [实际输入输出](results/2026-10-29-per-paper/README.md) · [本批报告](../../reports/author_expansion_20261029/REPORT.md)

2026-10-30新增：B15 [RAGChecker](ragchecker/README.md)完成独立无权重环境、两个原公开样例/原11指标、全局VQA原证据文字faithfulness开发适配，累计56/100。KIE无转录未评分；分类标签直接评RAG忠实度的首版试跑保留并修正为仅评原证据文字。作者评测器单列于[EVALUATOR_IMPLEMENTATION_STATUS.json](EVALUATOR_IMPLEMENTATION_STATUS.json)，不伪装生成E24。当前9个开发执行闭环仍不是完整原论文benchmark复现。

2026-10-30新增：B04 [LegalBench](legalbench/README.md)的原提示/原评分函数、29个原代表样本与真实整图分类补充评分开发轨道已完成执行，累计32/100；3条原截断经单独提高输出预算恢复，26回复精确复用。Rule QA保留原人工未评分状态，KIE缺参考未评分；原数值/SSLA/Successor三个源码缺陷均有独立反例，未静默修改原分数。当前10个限定开发执行闭环、3个作者评测器接口；完整原benchmark仍未完成。

2026-10-30资源范围续作：[JurisMA](jurisma/README.md)已新增论文§3.2–3.4/Algorithm 1推理重实现，原附录C咨询、冻结KIE文本全局VQA、案件产品均已真实执行；新增62次，L07累计79/100。VQA弃答0；案件4条结构化结果/5处引用只通过Schema及逐字校验，一项存在性概括仍需人工审查。DPO与本地检查点暂缓、非作者源码执行，因此整个L07保持部分完成，不增加上述10个开发闭环。[LawLuo](lawluo/README.md)的源码固定与AST失败、v3/ToLC版本差异均有证据；完整本地分支暂缓，0次调用。批量环境默认排除本地神经资源，51条范围保留。

2026-10-30新增：[R04 GraphRAG](graphrag/README.md)官方v0.1.1无嵌入API分支完成有限开发执行闭环：原Notebook查询2次、冻结KIE文本原索引/查询6次、案件原索引/查询7次，共15/100；两个产品轨道均执行14个原工作流。VQA弃答0；案件3条陈述/3引用仅结构通过，摘要“三方陈述”表述不准确，原回复保留。当前11个有限开发闭环、25个生成配置、3个评测器接口；完整原benchmark仍0，51条范围保留。

资源核查续作：AgentsCourt完整BGE重排与Legal-R1本地vLLM/训练actor按用户要求暂缓，机器可读哈希/行号见各方法resource_boundary.json；旧API组件和项目原型历史记录保留，不冒称原完整系统。
