# e06_legalreasoner_verifier

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[L04] LegalReasoner

原有方法/任务：从案件请求和事实进行逐步法律推理，并对推理步骤验证、归因和纠正。

原输入大致形态（结构示意，不是 Gold）：案件 claims/facts 与法律背景；LegalHK 包含香港案件，CMDL 为大陆刑事案件。

原输出大致形态：裁判结论与逐步验证/纠错记录；原训练含争点和过程验证标注。

原 benchmark：LegalHK、CMDL，论文采用各自训练/验证/测试划分；不与我们的合成聊天夹具同分布。

论文创新点（作者方法的组成）：争点分解、过程验证器的多维检查及按问题类型选择修正策略；包含训练数据与验证器。

对本工作的可适配性：条件可适配核查思想；未取得/运行对应作者验证器时，同一底座的新上下文不能算原方法。需重新标注民事证据问题并核对法域。

核查依据：https://arxiv.org/html/2506.07443v1

作者代码：未固定对应作者入口；不得宣称已运行作者代码



[L08] VERDICT

原有方法/任务：基于刑事案情预测适用法条、罪名和刑期，使用合议反馈与演化记忆。

原输入大致形态（结构示意，不是 Gold）：作者 CAIL 环境接收 configs['task'] 案情文本和 configs['expected'] 评分标签；模型任务文本只由 task 构造。训练监督与测试模式须分别配置。

原输出大致形态：原格式为 Finish[JSON]，字段 relevant_articles、accusation、term_of_imprisonment；刑期子字段 death_penalty、life_imprisonment、imprisonment。

原 benchmark：CAIL2018（CAIL-Small）、未来时间划分 CJO2025；当前作者 CLI 仅暴露 cail2018。

论文创新点（作者方法的组成）：五角色监督式 Pass/Reject 修订与 Hybrid Jurisprudential Memory / Micro-Directives 演化；不是普通多轮改写。

对本工作的可适配性：不能直接把刑事预测指标用于民事证据链。需重写任务环境/标签/规范检索，并隔离训练记忆与留出案件；E20 未复现 HJM/专家对齐模型。 源码训练验证分支可读取 expected；适配留出评测必须 mode=test 且关闭 training_mode_verification，并另审计 expected/正确性反馈是否经记忆回流。该边界尚未端到端验证。

核查依据：https://github.com/luckyhui235/VERDICT

作者代码：https://github.com/luckyhui235/VERDICT @ 1b6c9d6ecfbe95900076cbfd2eedf94aecaaf952；本地 paper/upstream_sources/verdict



本文件当前实际实现：复现独立上下文核查后修订；未训练 LegalReasoner 过程验证器，未实现完整 VERDICT。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。

KIE/全局VQA原控制器接口：尚未接入

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：LegalReasoner：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代；原训练模型/过程验证器/记忆机制或原任务资源未部署；同一底座 prompt 不能替代原训练

当前作者原代码状态：original_benchmark_not_reproduced

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
