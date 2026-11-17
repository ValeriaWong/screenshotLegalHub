# b01_legalagentbench

原论文与适配核查（2026-10-29）



复现判定：作者三控制器实际执行；原任务为工具观察回放，原在线服务与完整benchmark未复现。产品文本工具为显式适配。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[B01] LegalAgentBench author baseline controllers

原有方法/任务：在17个法律/企业语料库与37个工具上完成中文1至5跳和写作任务；作者提供ReAct、Plan-and-Solve、Plan-and-Execute三条基线。

原输入大致形态（结构示意，不是 Gold）：自然语言question；工具描述和表格schema为公开上下文。原数据另有answer/key/key_middle，仅评分端读取。

原输出大致形态：Final Answer、scratchpad、过滤后的答案和过程摘要；原key_answer/key_middle分别对关键词做包含率评分。

原 benchmark：300个原任务；success/progress substring匹配，另有远程BERTScore分支。不是截图KIE或专家案件金标。

论文创新点（作者方法的组成）：法律场景17库37工具、分层任务构造及过程进度率；三条作者基线是对照控制器，不冒称新的法律推理方法。

对本工作的可适配性：作者控制器/提示/模式/解析函数真实执行，DeepSeek替换原API。原工具服务拒绝连接，首任务仅回放作者日志的精确工具观察，不等于在线17库复现。产品改为冻结KIE文本list/read工具并在各步保持JSON契约；像素KIE不适配，专家法律准确率未评测。

核查依据：https://aclanthology.org/2025.acl-long.116/

作者代码：https://github.com/CSHaitao/LegalAgentBench @ ec14d8ab1fc439bfd99cbefba08d8e27dafca534；本地 paper/upstream_sources/legalagentbench



本文件当前实际实现：LegalAgentBench作者三基线控制器及原提示/解析实际执行；原工具回放与冻结文本工具分开，在线17库和完整benchmark未复现。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。

已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：锁定16原文件，独立Pydantic1.10环境；原三类/提示/解析函数经AST执行；原post_request参数不匹配由显式传输修复；只允许JSON动作进入解析，eval备用路径不可达；产品替换冻结KIE/案件文本工具；每步保留输出契约，PS/PE早期格式失败保留；最终事件封装错误通过严格匹配原七条响应零调用恢复；所有变体共享100次上限

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：作者在线法律工具服务拒绝连接；原首任务只回放原日志精确工具观察，不等于17库/37工具端到端复现

当前作者原代码状态：author_controller_controlled_replay_live_service_unavailable

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
