# 作者原代码复现与产品适配

当前执行优先级：[先略过本地模型权重推理/训练与重计算分支](RESOURCE_PRIORITY_2026-10-30.md)，优先AIPING远程API方法；历史结果保留。

按用户要求逐篇完成“可运行环境 → 原任务验证 → 产品适配”。当前11个指定开发轨道执行闭环：7篇作者生成/检索核心方法（ReAct、Self-Refine、Reflexion、RAPTOR、GraphRAG、LightRAG、SCALE）＋2个作者基准/评测器（LegalBench、RAGChecker）＋CoA论文算法重实现＋L-MAD论文协议/所引MALLM组件。两个评测器均保留原任务与产品输入差异；KIE真实缺转录时未评分。这不是11篇作者完整工程或原benchmark成绩复现。全部51个登记条目继续保留在[覆盖台账](PAPER_COVERAGE.md)；25个生成配置与3个评测器接口也不等于完成数。

|论文|实现入口与来源等级|已完成的真实执行|产品轨道|
|---|---|---|---|
|A01 ReAct|[Notebook控制器适配](react/product_adapter.py)|HotpotQA原题EM命中；Completion→Chat、工具与User-Agent差异有记录|原图KIE、全图VQA；案件run仍为原型|
|A02 Self-Refine|[原迭代控制器适配](self_refine/product_adapter.py)|原缩写任务两轮完整4步，另有真实图像任务|原图KIE、全图VQA；案件链已接入|
|A03 Reflexion|[原CoTAgent控制器](reflexion/product_adapter.py)|作者Hotpot上下文题EM命中；产品VQA实际触发失败→反思→再次尝试|原图KIE、全图VQA；案件链有离线集成验证|
|R03 RAPTOR|[作者建树与检索](raptor/product_adapter.py)|完整Cinderella原示例：17叶子，3层摘要节点16/15/14，共45次摘要；答案质量待人工审查|冻结KIE预测文本VQA；案件链有离线集成验证|
|R04 GraphRAG|[作者14个原索引工作流与GlobalSearch](graphrag/README.md)，无嵌入API分支|原Notebook完整预计算表，217实体/5报告，map/reduce实际2次；原索引未重建|冻结KIE文本索引/问答6次（弃答0）；案件索引/问答7次，3条陈述/3引用结构通过；摘要有数量表述错误；累计15/100|
|R05 LightRAG|[作者图构建与双层检索](lightrag/product_adapter.py)|完整UltraDomain法律文档，335节点/657关系；自然语言问答完成，质量待人工审查|冻结KIE预测文本VQA；案件链有离线集成验证|
|L09 SCALE|[作者阶段与法源路径](scale/case_adapter.py)|原ECHR完整案例双条文；真实中国法源案例产品6步，累计66/100次请求；仅结构/逐字引用校验|case_product；法规替代ECHR指南的显式适配，不是像素KIE|
|A06 CoA|[论文Algorithm 1重实现](chain_of_agents/algorithm.py)，非作者源码|官方LongBench完整54062字符，2 worker＋manager共3次调用；答案未命中，官方F1=0.3333|冻结KIE文本VQA（首次弃答0，补齐公开选项后1）；case_product结构和3项事实引用校验通过|
|L10 L-MAD|[论文协议＋所引MALLM原组件](l_mad/README.md)，非L-MAD作者代码|hybrid/ranked各命中同一个论文示例N；非COLIEE年度数据验证，累计92/100次|冻结KIE文本二分类VQA两协议均弃答0；案件单事实流程结构通过但facts为空；保留两次失败|
|B15 RAGChecker|[作者默认API评测器](ragchecker/README.md)，不是生成Agent|原两个完整示例及全部11指标；单条无标签/截断及最终格式适配记录均保留，累计56/100|全局VQA原证据文字对实际冻结KIE输入的faithfulness；KIE缺转录参考未评分|
|B04 LegalBench|[原作者提示与评分函数](legalbench/README.md)，API传输为本项目增加|11任务/12组29样本；3截断已单独恢复，累计32/100；原Rule QA人工未评分，原评分3缺陷明确保留|整图分类原normalized balanced EM补充评分；HTTP/CLI/流水线/导出已接入；KIE缺参考未评分|

原始输入、逐次请求、模型实际回复、输出、工具结果、测试与出处，均按方法名称保存在[真实执行索引](results/2026-10-29-per-paper/README.md)。它同时列出成功和失败记录，不删除早期失败。Self-Refine原缩写的实际修订结果另保留native_output.json。

当前供应商使用用户已配置的AIPING与DeepSeek-V4.1-Flash-1017。每篇论文原任务和产品轨道共用100次供应商请求上限；历史、失败、未知及在途预留均计数，不因日期、计划版本或恢复而重置。早期本地FLAN-T5实验的145次本地生成单独记录，不计为供应商请求。密钥仅在父进程网关解密，不交给作者子进程。

[运行器](run_per_paper_validation.py) · [原任务恢复器](resume_native_plan.py) · [预算账本汇总](build_validation_index.py) · [逐配置方法说明](ADAPTATION_REVIEW.md) · [源码提交/校验值](sources.lock.json) · [独立环境检查](setup_environment.py)

尚未达到三阶段终态的工作：

- [LegalAgentBench](legalagentbench/README.md)：作者三控制器原任务工具回放与三条冻结KIE文本VQA完成执行，累计77/100；VQA均弃答0，真实案件3项陈述事实/3引用通过结构与逐字检查。E23网页/API已接入；在线原工具服务拒绝连接，保持部分完成，未增加整篇完成数。

- [MetaGPT](metagpt/README.md)：原默认软件SOP18次真实调用、额外作者审查1次后核心功能验证、案件产品4步真实执行均有记录，累计45/100；新增原QA续跑19次，7个测试文件最终仍有2个失败，main最后修订未重跑；交互终端验收未完成，因此未增加整篇完成数。

- [LawBench](lawbench/README.md)：独立无权重环境、19类×zero/one-shot首条共38次真实调用、原评分函数与CLI已执行；产品全局分类补充评分与KIE缺参考未评分记录均保留。2-1本地LTP暂缓，未加入整篇完成数。

- [SOLAR](solar/README.md)：Stage II精确值未命中、10%容差命中。新增原Stage I真实4次，24类/71属性/21规则通过原结构校验，停在原人工审核输入处，累计6/100；新解释器、训练反馈、中国产品规则域尚未完成。
- AgentsCourt：原庭辩组件完成；Legal-KB检索、判决与中国截图产品链未完成。
- PaddleOCR-VL（按用户新指令暂缓本地权重分支）：原0.9B权重和CPU环境已锁定，原权重识别原始页面完成，输出1616字符并达到1024-token上限；完整布局流水线、消息KIE与产品问答适配未完成。
- LawFlow（本地监控模型训练暂缓；API分支可继续）：作者三个Notebook入口已固定；工作流监控训练与产品适配未完成。
- 其余条目逐项见覆盖台账，不因缺专家金标而停止环境和适配工作，也不把未完成条目标为成功。

完整原论文benchmark复现数仍为0。这与原任务单样例、产品执行验证分别记录。KIE缺少人工消息转录目标时仅验证结构/坐标及旧区域关联；全局VQA旧参考分为开发参考。专家法律准确率按用户要求后补，结构有效和引文范围有效不等于内容或法律正确。

2026-10-30资源范围续作：[JurisMA](jurisma/README.md)已新增论文§3.2–3.4/Algorithm 1推理重实现，原附录C咨询、冻结KIE文本全局VQA、案件产品均已真实执行；新增62次，L07累计79/100。VQA弃答0；案件4条结构化结果/5处引用只通过Schema及逐字校验，一项存在性概括仍需人工审查。DPO与本地检查点暂缓、非作者源码执行，因此整个L07保持部分完成，不增加上述10个开发闭环。[LawLuo](lawluo/README.md)的源码固定与AST失败、v3/ToLC版本差异均有证据；完整本地分支暂缓，0次调用。批量环境默认排除本地神经资源，51条范围保留。
