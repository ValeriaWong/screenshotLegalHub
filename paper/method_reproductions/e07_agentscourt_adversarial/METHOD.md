# e07_agentscourt_adversarial

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[L01] AgentsCourt

原有方法/任务：从给定案情模拟法庭辩论、检索法律知识并生成裁判分析。

原输入大致形态（结构示意，不是 Gold）：SimuCourt 中的案情与案件类型/审级等任务信息，通常是已整理的案件叙述。

原输出大致形态：案件分析、适用法条、裁判结果；刑事任务涉及罪名、刑期和罚金。

原 benchmark：SimuCourt，420 份中文裁判文书，涉及民事、行政、刑事及审级设置；配套 Legal-KB。

论文创新点（作者方法的组成）：法庭辩论模拟、法律资源增强与裁判迭代结合；不等于增加两个对立角色。

对本工作的可适配性：仅条件适配辩论机制。聊天中的主张/否认必须保留认识状态，不能先改成法院已认定事实；裁判标签也不能直接充当证据链 Gold。

核查依据：https://aclanthology.org/2024.findings-emnlp.549/

作者代码：https://github.com/Zhitao-He/AgentsCourt @ 7c14d6960abfdfdd7366250905da8dbcb416d6d6；本地 paper/upstream_sources/agentscourt



[L10] L-MAD (Nguyen et al., 2026)

原有方法/任务：法条premise与法律hypothesis之间的二分类蕴含判断；比较三persona的混合共识与固定轮次排名投票。

原输入大致形态（结构示意，不是 Gold）：原COLIEE每题Relevant article、Query、Answer。只把法条与问题送给模型；原答案仅评分。本轮原任务为论文2.1节Article9官方英文翻译示例，不是R05/R06/R07年度数据集。

原输出大致形态：正文固定Answer:Y/N与简短公开说明；附录日文提示却要求判断:Y/N，二者分别解析。协议还产生AGREE/DISAGREE、排名与收敛/平局/未知轨迹。

原 benchmark：COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。

论文创新点（作者方法的组成）：在两轮滑动记忆下比较共识与排名投票，保持分歧和最多一轮平局补充讨论，研究协议/规模对法律判断的影响。

对本工作的可适配性：论文协议调度＋实际所引MALLM提示/共识/排名组件；未核实L-MAD作者仓库。混合参数按论文配置，不能直接用不同的MALLM默认值。DeepSeek替换原本地模型、固定附录persona、原示例英文语言差异均披露。二分类KIE文本VQA双向验候选，N不自动推出相反标签；案件先核验最多2项有原文锚点的陈述，再修订，不能由共识推定法律正确。

核查依据：https://arxiv.org/html/2607.09099v1

作者代码：未固定对应作者入口；不得宣称已运行作者代码



本文件当前实际实现：复现双方独立意见、一轮交换和起草者整合；未复现作者训练、知识增强和原始判决任务。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。

KIE/全局VQA原控制器接口：尚未接入

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：L-MAD (Nguyen et al., 2026)：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代；作者 Legal-KB、原检索组件及 SimuCourt 原协议尚未端到端运行

当前作者原代码状态：original_benchmark_not_reproduced

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
