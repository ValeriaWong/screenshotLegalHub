# e09_l_mad

原论文与适配核查（2026-10-29）



复现判定：L-MAD论文协议调度＋所引MALLM原组件实际执行；非L-MAD作者源码/检查点，完整COLIEE benchmark未复现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[L10] L-MAD (Nguyen et al., 2026)

原有方法/任务：法条premise与法律hypothesis之间的二分类蕴含判断；比较三persona的混合共识与固定轮次排名投票。

原输入大致形态（结构示意，不是 Gold）：原COLIEE每题Relevant article、Query、Answer。只把法条与问题送给模型；原答案仅评分。本轮原任务为论文2.1节Article9官方英文翻译示例，不是R05/R06/R07年度数据集。

原输出大致形态：正文固定Answer:Y/N与简短公开说明；附录日文提示却要求判断:Y/N，二者分别解析。协议还产生AGREE/DISAGREE、排名与收敛/平局/未知轨迹。

原 benchmark：COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。

论文创新点（作者方法的组成）：在两轮滑动记忆下比较共识与排名投票，保持分歧和最多一轮平局补充讨论，研究协议/规模对法律判断的影响。

对本工作的可适配性：论文协议调度＋实际所引MALLM提示/共识/排名组件；未核实L-MAD作者仓库。混合参数按论文配置，不能直接用不同的MALLM默认值。DeepSeek替换原本地模型、固定附录persona、原示例英文语言差异均披露。二分类KIE文本VQA双向验候选，N不自动推出相反标签；案件先核验最多2项有原文锚点的陈述，再修订，不能由共识推定法律正确。

核查依据：https://arxiv.org/html/2607.09099v1

作者代码：未固定对应作者入口；不得宣称已运行作者代码



[A08] Towards a Science of Scaling Agent Systems

原有方法/任务：跨不同 agentic benchmark 比较单/多 agent 的结构、成本与成功率。

原输入大致形态（结构示意，不是 Gold）：各原生环境的工具任务，接口随 benchmark 变化。

原输出大致形态：任务完成结果、轨迹与成本指标；不是一个固定法律推理算法。

原 benchmark：当前核对版本包含 BrowseComp-Plus、Finance-Agent、PlanCraft、WorkBench，并报告 SWE-bench Verified、Terminal-Bench 小规模扩展。

论文创新点（作者方法的组成）：研究任务分解性、协调开销与模型能力对多 agent 收益的约束。

对本工作的可适配性：可借鉴同预算实验设计，E09 轮次参数不等于复现该研究或其六类 benchmark。

核查依据：https://arxiv.org/html/2512.08296

作者代码：未固定对应作者入口；不得宣称已运行作者代码



本文件当前实际实现：L-MAD论文协议调度＋原MALLM共识/排名/提示组件；三persona、两轮上下文、严格Y/N、混合共识与排名投票；非L-MAD作者源码或原检查点。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

论文算法重实现已接入本文件run()：是；不是作者源码执行。

已接入run_task的输入轨道：vqa_predicted_text (binary only)；每步输入输出可追溯。

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：固定MALLM 11个原文件；AST载入原共识/排名/提示组件，无Torch/嵌入依赖；原混合默认值与L-MAD论文不同，显式配置论文阈值；正文Answer和附录判断分别解析；严格排名和单次平局补充，无自动付费格式重试；双向候选蕴含避免把未获支持自动当作相反标签；案件保留原文锚点和已核验fact集合；原任务与产品按协议分组留存，历史/失败/未知共用100次预算

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证

当前作者原代码状态：LMAD_author_code_unverified_cited_MALLM_components_executed

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
