# e21_reflexion

原论文与适配核查（2026-10-29）



复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。

已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。



[A03] Reflexion

原有方法/任务：根据任务环境反馈形成跨尝试反思记忆

原输入大致形态（结构示意，不是 Gold）：HotpotQA question, supporting context, evaluator answer key; 原文还包括 ALFWorld 和编程任务

原输出大致形态：Finish[answer]、环境二元反馈、反思记忆与后续尝试

原 benchmark：HotpotQA、ALFWorld、HumanEval等；本适配选择作者CoT_context分支

论文创新点（作者方法的组成）：根据失败反馈形成语言反思并存入 episodic memory，在下一次尝试复用，不训练权重

对本工作的可适配性：可附加原图或冻结KIE文本；产品没有答案键，改用schema/坐标或引文机械检查反馈，不能当作准确率

核查依据：https://arxiv.org/html/2303.11366

作者代码：https://github.com/noahshinn/reflexion @ 218cf0ef1df84b05ce379dd4a8e47f17766733a0；本地 paper/upstream_sources/reflexion



本文件当前实际实现：作者CoTAgent反思、跨尝试记忆与重试控制器；原任务真实执行完成；产品真实执行轨道：kie_image、vqa_image_full；原论文完整benchmark未复现

本项目输入：FrozenCaseInput sources，或原图及KIE/VQA question

本项目输出：CaseAnalysisOutput 或 KIE/VQA JSON

原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。

已接入run_task的输入轨道：kie_image、vqa_image_full、vqa_predicted_text；每步输入输出可追溯。

评测边界：专家法律金标后补，不作为环境/适配阻塞；完整原benchmark另行验证

如何适配/还需改什么：保留冻结来源映射；派生摘要/图描述不能当独立证据；记录原参数、有效参数及逐次输入输出；模型/嵌入替换与原基准分开

已做的适配调试：锁定作者源码/独立环境，实际执行原类和函数；真实输入、模型回复、工具产物和输出见 results/2026-10-29-per-paper/README.md

能否直接适配：可附加原图或冻结KIE文本；产品没有答案键，改用schema/坐标或引文机械检查反馈，不能当作准确率

尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证

当前作者原代码状态：author_algorithm_product_adapter

复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。
