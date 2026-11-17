# e16_lightrag

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[R05] LightRAG

原有方法/任务：建立实体/关系图与文本索引，以低层/高层双级检索增强回答。

原输入大致形态（结构示意，不是 Gold）：文档集合与 query。

原输出大致形态：图/文本检索上下文及生成答案。

原 benchmark：UltraDomain 中 Agriculture、CS、Legal、Mix 四域。

论文创新点（作者方法的组成）：图索引和双层检索结合，支持增量更新及综合/具体问题的知识获取。

对本工作的可适配性：可适配冻结KIE文本全局VQA和案件检索；不直接做像素KIE。实体关系是模型派生内容，保留chunk来源映射。

核查依据：https://arxiv.org/html/2410.05779

作者代码：未固定对应作者入口；不得宣称已运行作者代码



本文件当前实际实现：作者实体关系抽取与合并、图存储和双层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现

本项目输入：FrozenCaseInput sources

本项目输出：CaseAnalysisOutput 或 VQA JSON

原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。

已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。

评测边界：专家法律金标后补，不作为环境/适配阻塞；完整原benchmark另行验证

如何适配/还需改什么：保留冻结来源映射；派生摘要/图描述不能当独立证据；记录原参数、有效参数及逐次输入输出；模型/嵌入替换与原基准分开

已做的适配调试：锁定作者源码/独立环境，实际执行原类和函数；真实输入、模型回复、工具产物和输出见 results/2026-10-29-per-paper/README.md

能否直接适配：可适配冻结KIE文本全局VQA和案件检索；不直接做像素KIE。实体关系是模型派生内容，保留chunk来源映射。

尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证

当前作者原代码状态：author_algorithm_product_adapter

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
