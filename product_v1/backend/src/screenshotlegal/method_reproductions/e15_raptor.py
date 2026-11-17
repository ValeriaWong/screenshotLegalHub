"""
论文出处：RAPTOR — Sarthi et al., ICLR 2024, https://arxiv.org/abs/2401.18059.
Author: https://github.com/parthsarthi03/raptor @ 7da1d48a7e1d7dec61a63c9d9aae84e2dfaa5767.

复现程度：直接运行作者 ClusterTreeBuilder、RAPTOR_Clustering 和 TreeRetriever；
沿作者公开 BaseSummarizationModel/SBertEmbeddingModel 扩展接口替换模型。
不是“摘要 prompt”近似；原论文完整成绩未复现。实际执行状态看同目录 runs/。
原任务：长文档 + 文本问题 -> 答案、检索上下文；原 benchmark 为 NarrativeQA、
QASPER、QuALITY；作者 demo/sample.txt 为 Cinderella 原生示例（不是 benchmark）。
创新：UMAP 降维、GMM 软聚类、递归生成摘要、跨树层检索。
原 I/O 示例：Cinderella 文本 + How did Cinderella reach her happy ending? -> 文本答案。
本项目输入：冻结 KIE 预测文本或证据文本 + 全局问题；输出仍保留原节点、父子关系、
检索节点及叶节点引用；最后回答受产品 JSON schema 约束。它不能直接识别像素，
不作为 KIE 提取方法；不读取目标答案或专家金标。
适配：多文档逐文档分块保留来源 ID；摘要可改变表达，引用必须下溯到原始叶节点。
本地 CPU SBERT 为多语言 MiniLM，与论文 ada-002 不同；摘要/QA 由父进程选择并记录。
小样本可调整 reduction_dimension，默认仍为作者值 10；不得把无摘要层的树称作已
验证递归聚类。为重放固定NumPy/Torch种子224和Numba单线程；未改作者UMAP/GMM函数。
本文件不会隐式下载模型、调用供应商或读供应商密钥。

复现程度及当前证据：作者UMAP/GMM软聚类、摘要树与跨层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[R03] RAPTOR
原有方法/任务：对长文递归聚类与摘要建树，跨层检索后回答。
原输入大致形态（结构示意，不是 Gold）：待索引文档集合与 question。
原输出大致形态：摘要树、检索节点/文本与最终答案。
原 benchmark：NarrativeQA、QASPER、QuALITY。
论文创新点（作者方法的组成）：递归摘要形成多层语义索引，结合软聚类，在不同抽象层次检索。
对本工作的可适配性：可适配冻结KIE文本全局VQA和案件证据检索；不能直接做像素KIE。摘要节点下溯冻结原文叶子；独立来源ID随树记录。
核查依据：https://arxiv.org/html/2401.18059
作者代码：https://github.com/parthsarthi03/raptor @ 7da1d48a7e1d7dec61a63c9d9aae84e2dfaa5767；本地 paper/upstream_sources/raptor

本文件当前实际实现：作者UMAP/GMM软聚类、摘要树与跨层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现
本项目输入：FrozenCaseInput sources
本项目输出：CaseAnalysisOutput 或 VQA JSON
原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。
已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。
评测边界：专家法律金标后补，不作为环境/适配阻塞；完整原benchmark另行验证
如何适配/还需改什么：保留冻结来源映射；派生摘要/图描述不能当独立证据；记录原参数、有效参数及逐次输入输出；模型/嵌入替换与原基准分开
已做的适配调试：锁定作者源码/独立环境，实际执行原类和函数；真实输入、模型回复、工具产物和输出见 results/2026-10-29-per-paper/README.md
能否直接适配：可适配冻结KIE文本全局VQA和案件证据检索；不能直接做像素KIE。摘要节点下溯冻结原文叶子；独立来源ID随树记录。
尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证
当前作者原代码状态：author_algorithm_product_adapter
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""

METHOD_ID = 'E15'
METHOD_NAME = 'e15_raptor'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'author_algorithm_adaptation'
REPRODUCTION_SCOPE = '作者UMAP/GMM软聚类、摘要树与跨层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现'
PAPER_REFERENCES = [{'paper_id': 'R03', 'reference': 'Sarthi et al. (2024), *RAPTOR*.', 'sources': ['https://arxiv.org/abs/2401.18059'], 'verification': 'paper_listing_verified_not_code_reproduced'}]

async def run_task(messages,call,attempts=2,tool_trace=None):
    from .paper_bridge import benchmark_task
    return await benchmark_task('raptor',messages,call,attempts,tool_trace)





















ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'R03', 'method': 'RAPTOR', 'task': '对长文递归聚类与摘要建树，跨层检索后回答。', 'input': '待索引文档集合与 question。', 'output': '摘要树、检索节点/文本与最终答案。', 'benchmark': 'NarrativeQA、QASPER、QuALITY。', 'innovation': '递归摘要形成多层语义索引，结合软聚类，在不同抽象层次检索。', 'repo': 'raptor', 'source': 'https://arxiv.org/html/2401.18059', 'fit': '可适配冻结KIE文本全局VQA和案件证据检索；不能直接做像素KIE。摘要节点下溯冻结原文叶子；独立来源ID随树记录。', 'pinned_author_source': {'repository': 'https://github.com/parthsarthi03/raptor', 'commit': '7da1d48a7e1d7dec61a63c9d9aae84e2dfaa5767', 'local_path': 'paper/upstream_sources/raptor'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_algorithm_product_adapter', 'adaptability': '可适配冻结KIE文本全局VQA和案件证据检索；不能直接做像素KIE。摘要节点下溯冻结原文叶子；独立来源ID随树记录。', 'current_project_implementation': '作者UMAP/GMM软聚类、摘要树与跨层检索；原任务真实执行完成；产品真实执行轨道：vqa_predicted_text；原论文完整benchmark未复现', 'required_adaptation': ['保留冻结来源映射；派生摘要/图描述不能当独立证据', '记录原参数、有效参数及逐次输入输出；模型/嵌入替换与原基准分开'], 'our_input_shape': 'FrozenCaseInput sources', 'our_output_shape': 'CaseAnalysisOutput 或 VQA JSON', 'author_native_interface_connected_to_product': True, 'author_benchmark_tracks': ['vqa_predicted_text'], 'native_author_controller_real_run_passed': True, 'native_task_answer_validated': False, 'native_verification': {'author_controller_completed': True, 'summary_layers': 3, 'answer_quality': 'manual_review_required'}, 'real_product_tracks_completed': ['vqa_predicted_text'], 'completed_debugging': ['锁定作者源码/独立环境，实际执行原类和函数', '真实输入、模型回复、工具产物和输出见 results/2026-10-29-per-paper/README.md'], 'deferred_evaluation': '专家法律金标后补，不作为环境/适配阻塞；完整原benchmark另行验证', 'blockers': []}

async def run(context):
    from .paper_bridge import case_task
    return await case_task('raptor',context)
