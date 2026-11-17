# e02_staged_without_matterpack

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[A04] MetaGPT

原有方法/任务：软件开发SOP协作；E22执行作者Team/Role/Memory与软件原任务，E02保留项目流程基线。

原输入大致形态（结构示意，不是 Gold）：软件需求或带函数签名/测试约束的编程任务。

原输出大致形态：需求/设计/代码/测试等软件产物；不是案件事实或法律分析。

原 benchmark：HumanEval、MBPP、SoftwareDev。

论文创新点（作者方法的组成）：把角色分工、标准操作流程、结构化通信和可执行反馈组合到软件开发团队。

对本工作的可适配性：作者通用团队、结构化ActionOutput与消息订阅可作领域迁移；E22显式替换四角色证据SOP。默认软件流程18次，额外作者审查1次后4项功能通过；原QaEngineer续跑19次仍有测试失败和最终未执行修订，累计45/100；交互终端和整篇方法未验收。

核查依据：https://arxiv.org/html/2308.00352v7

作者代码：https://github.com/FoundationAgents/MetaGPT @ 820fee5df6697b4e85e90c787940de111c3ed05b；本地 paper/upstream_sources/metagpt



本文件当前实际实现：本项目固定三阶段工作流；参考 MetaGPT 的流程分工，不含其软件开发角色或原任务。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。

KIE/全局VQA原控制器接口：尚未接入

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩

能否直接适配：非单篇论文复现的项目基线

尚未完成/阻塞：原项目基线，无作者复现任务

当前作者原代码状态：not_applicable_project_baseline

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
