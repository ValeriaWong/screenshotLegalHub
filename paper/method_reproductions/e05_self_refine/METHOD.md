# e05_self_refine

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[A02] Self-Refine

原有方法/任务：同一模型先生成结果，再提供反馈并迭代修订；不同任务使用各自的原生模板。

原输入大致形态（结构示意，不是 Gold）：本轮选用作者 responsegen.run.iterative_response(context:str,max_attempts:int)：context是双人对话历史。历史原任务样例使用 acronym/run.py 的英文title与max_attempts；其他任务接收数学题、程序、概念集合或评论。

原输出大致形态：responsegen控制器返回 {response文本: {n_attempts,scores,total_score,context}}；三个原生类分别返回(meta,response)、(meta,feedback)、(meta,revised_response)。缩写分支返回缩写及评分轨迹。均不直接返回本项目CaseAnalysisOutput/KIE/VQA schema。

原 benchmark：论文七类任务：Yelp 情感反转、对话响应、PIE 代码优化、CodeNet 可读性、GSM8K、缩写生成、CommonGen；本次原生示例不是整套 benchmark。

论文创新点（作者方法的组成）：无需额外训练/外部反馈模型，由同一模型产生可执行反馈，再据反馈改写。

对本工作的可适配性：可适配修订控制流；法律任务必须另定义引文/反证/缺证反馈标准。缩写自评分不能转为法律准确率。

核查依据：https://arxiv.org/html/2303.17651

作者代码：https://github.com/madaan/self-refine @ 9a206d41e5d2d0c241bb441f41eeadb945afaa55；本地 paper/upstream_sources/self_refine



本文件当前实际实现：执行作者 responsegen 迭代控制器与三原生任务类调用；适配冻结来源案件输出、截图KIE及全图VQA；原benchmark未复现。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。

已接入run_task的输入轨道：kie_image、vqa_image_full；每步输入输出可追溯。

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩；固定 Self-Refine 与 prompt-lib 提交；独立 Python 环境；修复未使用的 Anthropic 客户端构造兼容与 httpx 版本；本地受限 broker 保存实际 DeepSeek 身份，给原 SDK 返回兼容 engine alias；保留原 few-shot 提示，额外添加模型格式指令；禁用整轮自动付费重试；首次失败 1 次调用；随后原 Init/Feedback/Iterate 三类用 3 次调用完成一次修订；原responsegen控制器函数体经AST原样载入，禁用付费整轮重试；原三任务类__call__保留；任务模板改为KIE/VQA/CaseAnalysisOutput；JSON转义保护原字符；图像每步保持冻结输入；产品案件主链和KIE/全图VQA入口已接作者控制器；作者原样例与真实KIE/全图VQA已执行；真实调用及失败记录：results/2026-10-29-per-paper/README.md；各论文100次持久上限共享原生/产品轨道

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证

当前作者原代码状态：author_controller_native_and_product_real_validated

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
