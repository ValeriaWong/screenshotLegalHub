# e01_react

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[A01] ReAct

原有方法/任务：知识问答、事实核验及交互环境决策。

原输入大致形态（结构示意，不是 Gold）：问答为 question；交互任务为目标与环境 observation。结构示意：question='某人的出生地是什么？'。

原输出大致形态：工具 action/observation 轨迹与最终答案或任务完成状态；不是带 SourceRef 的案件证明图。

原 benchmark：HotpotQA、FEVER、ALFWorld、WebShop；原任务分别采用回答/核验或环境成功率指标。

论文创新点（作者方法的组成）：交替进行任务分析与工具行动，利用真实环境观察更新后续行动。

对本工作的可适配性：条件可适配工具决策层；须把案内证据读取与法源检索分开，并保留观察到的陈述而非默认其为真。

核查依据：https://arxiv.org/html/2210.03629

作者代码：https://github.com/ysymyth/ReAct @ 6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9；本地 paper/upstream_sources/react



本文件当前实际实现：案件run仍为项目受控工具原型；KIE/全图VQA的run_task执行作者Notebook webthink控制器，工具适配为冻结原图目录与像素局部读取；原benchmark未复现。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。

已接入run_task的输入轨道：kie_image、vqa_image_full；每步输入输出可追溯。

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩；独立gym/numpy环境；原WikiEnv与HotPotQAWrapper成功载入7405道dev题；原Notebook webthink函数体原样载入；截图变体用冻结原图目录和真实像素局部读取替换Wikipedia工具；KIE/全图VQA入口已接run_task；原图和局部图的哈希、坐标、逐步请求/响应保留，边界错误会停止；真实调用及失败记录：results/2026-10-29-per-paper/README.md；各论文100次持久上限共享原生/产品轨道

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：案件run(context)仍为项目原型；KIE/全图VQA为作者控制器

当前作者原代码状态：author_controller_native_and_product_real_validated

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
