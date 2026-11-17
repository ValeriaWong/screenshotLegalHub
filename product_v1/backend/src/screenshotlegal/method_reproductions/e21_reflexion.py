"""
论文出处：Reflexion — Shinn et al., NeurIPS 2023, https://arxiv.org/abs/2303.11366.
Author: https://github.com/noahshinn/reflexion @ 218cf0ef1df84b05ce379dd4a8e47f17766733a0.
复现程度：直接调用作者 HotpotQA CoTAgent.run/step/reflect 和 episodic memory；
未声称 ALFWorld/HumanEval 分支或原论文分数复现。真实验证见 runs/，脚本化回复仅测传输。
原输入：HotpotQA question、supporting paragraphs、答案键（仅用于环境二元反馈）；
原输出：Finish[answer]、正确/错误反馈、跨尝试反思记忆。原 benchmark：HotpotQA、
ALFWorld、HumanEval 等；本入口选择作者 CotQA_context notebook 的 HotpotQA 分支。
创新：根据失败反馈形成语言反思并带入下一次尝试，不更新模型权重。
本项目输入：原图或冻结 KIE 预测 + 问题；Finish[JSON] -> KIE/VQA JSON。
适配性：可适配，但没有专家标签时只能用 schema/坐标检查作反馈，不能断言答案正确。
只替换模型传输、任务 prompt 和产品反馈判据；原 run/step/reflect 及记忆累积保留。
原 Thought 槽只请求简短公开操作标签；反思只请求可公开的修改意见。

复现程度及当前证据：作者CoTAgent反思、跨尝试记忆与重试控制器；原任务真实执行完成；产品真实执行轨道：kie_image、vqa_image_full；原论文完整benchmark未复现

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

"""

METHOD_ID = 'E21'
METHOD_NAME = 'e21_reflexion'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'author_algorithm_adaptation'
REPRODUCTION_SCOPE = '作者CoTAgent反思、跨尝试记忆与重试控制器；原任务真实执行完成；产品真实执行轨道：kie_image、vqa_image_full；原论文完整benchmark未复现'
PAPER_REFERENCES = [{'paper_id': 'A03', 'reference': 'Shinn et al. (2023), *Reflexion: Language Agents with Verbal Reinforcement Learning*.', 'sources': ['https://arxiv.org/abs/2303.11366'], 'verification': 'paper_listing_verified_not_code_reproduced'}]

async def run_task(messages,call,attempts=2,tool_trace=None):
    from .paper_bridge import benchmark_task
    return await benchmark_task('reflexion',messages,call,attempts,tool_trace)





















ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'A03', 'method': 'Reflexion', 'task': '根据任务环境反馈形成跨尝试反思记忆', 'input': 'HotpotQA question, supporting context, evaluator answer key; 原文还包括 ALFWorld 和编程任务', 'output': 'Finish[answer]、环境二元反馈、反思记忆与后续尝试', 'benchmark': 'HotpotQA、ALFWorld、HumanEval等；本适配选择作者CoT_context分支', 'innovation': '根据失败反馈形成语言反思并存入 episodic memory，在下一次尝试复用，不训练权重', 'repo': 'reflexion', 'source': 'https://arxiv.org/html/2303.11366', 'fit': '可附加原图或冻结KIE文本；产品没有答案键，改用schema/坐标或引文机械检查反馈，不能当作准确率', 'pinned_author_source': {'repository': 'https://github.com/noahshinn/reflexion', 'commit': '218cf0ef1df84b05ce379dd4a8e47f17766733a0', 'local_path': 'paper/upstream_sources/reflexion'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_algorithm_product_adapter', 'adaptability': '可附加原图或冻结KIE文本；产品没有答案键，改用schema/坐标或引文机械检查反馈，不能当作准确率', 'current_project_implementation': '作者CoTAgent反思、跨尝试记忆与重试控制器；原任务真实执行完成；产品真实执行轨道：kie_image、vqa_image_full；原论文完整benchmark未复现', 'required_adaptation': ['保留冻结来源映射；派生摘要/图描述不能当独立证据', '记录原参数、有效参数及逐次输入输出；模型/嵌入替换与原基准分开'], 'our_input_shape': 'FrozenCaseInput sources，或原图及KIE/VQA question', 'our_output_shape': 'CaseAnalysisOutput 或 KIE/VQA JSON', 'author_native_interface_connected_to_product': True, 'author_benchmark_tracks': ['kie_image', 'vqa_image_full', 'vqa_predicted_text'], 'native_author_controller_real_run_passed': True, 'native_task_answer_validated': True, 'native_verification': {'author_controller_completed': True, 'answer_exact_match': True}, 'real_product_tracks_completed': ['kie_image', 'vqa_image_full'], 'completed_debugging': ['锁定作者源码/独立环境，实际执行原类和函数', '真实输入、模型回复、工具产物和输出见 results/2026-10-29-per-paper/README.md'], 'deferred_evaluation': '专家法律金标后补，不作为环境/适配阻塞；完整原benchmark另行验证', 'blockers': []}

async def run(context):
    from .paper_bridge import case_task
    return await case_task('reflexion',context)
