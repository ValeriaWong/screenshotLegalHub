"""
论文出处：LightRAG — Guo et al., https://arxiv.org/abs/2410.05779.
Author https://github.com/HKUDS/LightRAG @ c31a2654f9fff95145d6edf372c1f5af5b6db891 (v1.0.3).
复现程度：作者 extract_entities（含 gleaning/合并）、kg_query 双层检索及
NetworkX/NanoVectorDB/JsonKVStorage 原实现直接执行；使用早期作者版本而非当前新产品。
原任务：长文本文档索引后回答局部/全局问题；论文使用 UltraDomain 多领域语料，
输出自然语言答案。创新：实体关系图 + 高/低层关键词的双层检索和增量合并。
本项目：冻结 KIE 文本或证据文本→图索引→全局 VQA JSON；不直接消费图像，不能算 KIE。
实体/关系描述是模型派生内容，不是法院已认定事实；保留 source_id→冻结原文映射。
适配：仅在字符串外将观察到的全角元组结束符）转为作者 ASCII )，记录转换；不更改字段内容。
适配：模型通过父进程传输；SBERT 多语 CPU embedding 替换论文 embedding；最终回答
增加产品 JSON 约束；索引只用当前冻结任务材料，不混入目标答案或其他案例的库。
不加载作者一体化 __init__ 中未使用的云数据库/供应商包；三个选定存储类和全部
索引/检索函数原样导入。模型真实运行与离线脚本验证分别见 runs/ 与 validation/。

复现程度及当前证据：作者实体关系抽取与合并、图存储和双层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现

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

"""

METHOD_ID = 'E16'
METHOD_NAME = 'e16_lightrag'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'author_algorithm_adaptation'
REPRODUCTION_SCOPE = '作者实体关系抽取与合并、图存储和双层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现'
PAPER_REFERENCES = [{'paper_id': 'R05', 'reference': 'Guo et al. (2024), *LightRAG*.', 'sources': ['https://arxiv.org/abs/2410.05779'], 'verification': 'paper_listing_verified_not_code_reproduced'}]

async def run_task(messages,call,attempts=2,tool_trace=None):
    from .paper_bridge import benchmark_task
    return await benchmark_task('lightrag',messages,call,attempts,tool_trace)





















ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'R05', 'method': 'LightRAG', 'task': '建立实体/关系图与文本索引，以低层/高层双级检索增强回答。', 'input': '文档集合与 query。', 'output': '图/文本检索上下文及生成答案。', 'benchmark': 'UltraDomain 中 Agriculture、CS、Legal、Mix 四域。', 'innovation': '图索引和双层检索结合，支持增量更新及综合/具体问题的知识获取。', 'repo': None, 'source': 'https://arxiv.org/html/2410.05779', 'fit': '可适配冻结KIE文本全局VQA和案件检索；不直接做像素KIE。实体关系是模型派生内容，保留chunk来源映射。', 'pinned_author_source': None}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_algorithm_product_adapter', 'adaptability': '可适配冻结KIE文本全局VQA和案件检索；不直接做像素KIE。实体关系是模型派生内容，保留chunk来源映射。', 'current_project_implementation': '作者实体关系抽取与合并、图存储和双层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现', 'required_adaptation': ['保留冻结来源映射；派生摘要/图描述不能当独立证据', '记录原参数、有效参数及逐次输入输出；模型/嵌入替换与原基准分开'], 'our_input_shape': 'FrozenCaseInput sources', 'our_output_shape': 'CaseAnalysisOutput 或 VQA JSON', 'author_native_interface_connected_to_product': True, 'author_benchmark_tracks': ['vqa_predicted_text'], 'native_author_controller_real_run_passed': True, 'native_task_answer_validated': False, 'native_verification': {'author_controller_completed': True, 'graph_nodes': 335, 'graph_edges': 657, 'reference': ['The procedure for indemnification involves the Indemnified Party promptly notifying the Indemnifying Party of the claim, the Indemnifying Party having the right to assume the defense, and the Indemnified Party having the right to participate in the defense with its own counsel at its own expense.'], 'answer_quality': 'manual_review_required'}, 'real_product_tracks_completed': ['vqa_predicted_text'], 'completed_debugging': ['锁定作者源码/独立环境，实际执行原类和函数', '真实输入、模型回复、工具产物和输出见 results/2026-10-29-per-paper/README.md'], 'deferred_evaluation': '专家法律金标后补，不作为环境/适配阻塞；完整原benchmark另行验证', 'blockers': []}

async def run(context):
    from .paper_bridge import case_task
    return await case_task('lightrag',context)
