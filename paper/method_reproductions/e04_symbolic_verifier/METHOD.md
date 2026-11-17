# e04_symbolic_verifier

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[L05] SOLAR / On Verifiable Legal Reasoning

原有方法/任务：形式化法条并将案件事实映射为可验证的符号推理。

原输入大致形态（结构示意，不是 Gold）：SARA numeric 的美国税法条文和纳税人事实，例如收入/报税身份/扣除项。

原输出大致形态：规则/本体中间表示及税额等结论；Stage II 使用预先构建的 TBox。

原 benchmark：LegalBench 的 SARA numeric，论文研究 96 个税务计算案例；不是民事证明责任数据。

论文创新点（作者方法的组成）：知识获取与知识应用分离，用 TBox/ABox 及符号推理约束生成和计算。

对本工作的可适配性：不能直接用于通用聊天证据判断。独立作者Stage II已运行，Stage I原图已生成SARA TBox并停在真实人工审核输入处；新解释器/训练反馈及中国民事规则域未完成。E04案件主链尚未接入，不能将SARA税法本体作为中国截图KIE/VQA规则包。

核查依据：https://arxiv.org/html/2509.00710

作者代码：https://github.com/albsadowski/solar @ 067f8f78b128dc7647c8a54b2560a612fae91a87；本地 paper/upstream_sources/solar



本文件当前实际实现：尚未实现形式化规则表示及符号验证器；文件仅登记出处，不能运行。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。

KIE/全局VQA原控制器接口：尚未接入

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：独立Python3.13.14、49个锁定依赖；无本地权重；原Stage II真实2次；新增Stage I真实4次，累计6/100；原校验反馈date类型3问题，原整合修订后问题0；完整输入输出和待审TBox均保存；保留原human_review输入门槛，没有自动批准或将其写成产品适配完成

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链；当前模块未实现

尚未完成/阻塞：Stage I已生成24类/71属性/21规则并通过原结构校验，等待原作者human_review输入；新解释器/训练反馈未执行；固定SARA税法规则不能直接用于中国截图任务，须建立相应规则域

当前作者原代码状态：author_stage_ii_and_stage_i_pre_review_executed_pending_review_and_product

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
