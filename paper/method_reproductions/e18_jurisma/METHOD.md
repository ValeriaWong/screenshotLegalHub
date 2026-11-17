# e18_jurisma

原论文与适配核查（2026-10-29）



复现判定：论文§3.2–3.4/Algorithm 1推理重实现与独立产品投影；非作者代码，DPO/本地检查点暂缓，整篇未完成。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[L07] JurisMA

原有方法/任务：中文法律咨询问答；查询转法律要素图，再动态协作与内容修订。

原输入大致形态（结构示意，不是 Gold）：用户法律咨询问题，可能长、非正式且存在多个争点；不要求先输入截图或 ProofGraph。

原输出大致形态：面向用户的咨询答复和法律依据；要素图是中间结构。

原 benchmark：修订版 LawBench；JurisCQAD 用于训练/DPO。另有 LegalBench-RuleQA 小样本迁移实验。

论文创新点（作者方法的组成）：实体/事件/意图/争点结构、动态任务路由、法条 grounding 与内容修订，并构建咨询偏好数据。

对本工作的可适配性：可将论文§3.2–3.4/Algorithm 1推理算法适配为远程API咨询、冻结预测KIE文本VQA和案件结构映射；DPO与本地检查点暂缓，非作者代码/完整论文复现。

核查依据：https://arxiv.org/html/2604.10470v1

作者代码：未固定对应作者入口；不得宣称已运行作者代码



本文件当前实际实现：实现论文§3.2–3.4/Algorithm 1推理控制流与独立产品投影；作者源码未核实，DPO与本地检查点暂缓，整篇未完成。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

论文算法重实现已接入本文件run()：是；不是作者源码执行。

已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：独立Python3.12.15、0额外依赖，无本地权重/训练/嵌入；按论文Algorithm 1实现T=5、双动作格式先于法条检索、Pass/空动作停止后仍执行ContentCheck；法条目录选ID后读取真实原文；拒绝未知ID与未检索/缩略法条冒充全文；原任务初次最后全文校验失败保留；逐请求精确缓存恢复，只新增ContentCheck调用；最终修订额外提供已检索法条附录，为显式项目适配；案件/VQA结构投影单独记录

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：作者源码未核实；DPO与本地训练检查点按用户指令暂缓；推理API分支不能替代整篇训练系统与原benchmark

当前作者原代码状态：not_executed_no_verified_author_repository

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
