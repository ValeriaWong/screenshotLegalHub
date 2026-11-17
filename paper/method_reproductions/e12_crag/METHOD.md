# e12_crag

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[R02] CRAG

原有方法/任务：评估检索质量，按 correct/incorrect/ambiguous 调用纠正和知识精炼后生成。

原输入大致形态（结构示意，不是 Gold）：question 与初始检索 passages。

原输出大致形态：答案/标签和纠正后知识；原流程含训练的 T5 evaluator、知识分解重组与 Web 搜索。

原 benchmark：PopQA、Biography、PubHealth、ARC-Challenge；分别使用任务准确率或 FactScore 等原指标。

论文创新点（作者方法的组成）：以轻量检索评估器触发不同纠错动作，并结合细粒度知识精炼与必要的外部搜索。

对本工作的可适配性：闭域案内证据不能从 Web 补造。现有 E12 同底座三分类不等于原 T5 evaluator；若禁网会成为明确的 CRAG 变体。

核查依据：https://arxiv.org/html/2401.15884v3

作者代码：https://github.com/HuskyInSalt/CRAG @ de7c2961ae624a1483a138c5798e1f6d0c4fb0e0；本地 paper/upstream_sources/crag



本文件当前实际实现：复现 correct/incorrect/ambiguous 检索质量动作与闭域纠正；无专用训练 evaluator、Web 扩展和细粒度知识重组。

本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus

本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties

原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。

KIE/全局VQA原控制器接口：尚未接入

评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞

如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标

已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩

能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链

尚未完成/阻塞：未运行原 T5 evaluator 与细粒度知识精炼；闭域变体不能等同允许 Web 搜索的原 CRAG

当前作者原代码状态：original_benchmark_not_reproduced

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
