# e11_legal_r1

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[L11] Legal-R1

原有方法/任务：法律问题上的主动法源选择、检索充分性判断和证据轨迹回答。

原输入大致形态（结构示意，不是 Gold）：作者 infer_pipeline.py 默认读训练/RL JSON；实际取 row['Open-ended Verifiable Question']。同一行还含 Ground-True Answer、Complex_CoT，仅可保留作评测/参考，不能混入用户问题。规范库/类案库另行加载。

原输出大致形态：原 rollout 保存 original_question、turns、final_answer 及参考标签字段；最终回答从轨迹生成。它不是原图解析或带字符坐标的 ProofGraph。

原 benchmark：LawBench、LexEval；法条检索另有 provision-oriented 查询。原规范库与 LeCaRDv2 类案库须版本匹配。

论文创新点（作者方法的组成）：训练 Lawyer 检索策略（masked SFT、轨迹强化学习），结合 authority/diversity-aware Assistant 和 Judge。

对本工作的可适配性：可条件迁移法源检索，但案内证据必须另轨读取。未载入作者训练模型/检索库就不能算原 Legal-R1；当前 E11 是项目路由原型。 原入口的默认训练数据路径并非 LawBench/LexEval 的完整评测入口；需要另行配置原 benchmark 与评分器。

核查依据：https://arxiv.org/html/2610.18611v1

作者代码：https://github.com/killerqueen-wonder/Legal-R1 @ a2bf5054841a108b5f1a3be10fe1cd8a336ed806；本地 paper/upstream_sources/legal_r1



本文件当前实际实现：复现 Lawyer 检索规划、冻结工具执行与 Judge 读取轨迹；未执行 masked SFT、GRPO、MMR/PSI 或作者检查点。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。

KIE/全局VQA原控制器接口：尚未接入

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：原训练模型/过程验证器/记忆机制或原任务资源未部署；同一底座 prompt 不能替代原训练

当前作者原代码状态：original_benchmark_not_reproduced

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
