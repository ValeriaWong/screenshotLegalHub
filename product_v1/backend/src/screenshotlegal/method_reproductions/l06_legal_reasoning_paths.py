"""E25 / L06 Capturing Legal Reasoning Paths — independent graph branch.
论文出处：Kondo et al. (2025), arXiv:2508.17340v1 §§2.1–2.3.
作者原资源：rkondo3/CapturingLegalReasoningPaths @918996f82037b7a9d6541ccbdc9553f0308a164d。
复现程度：基于作者原提示/本体的论文流水线重实现；作者未公开Python；
仅API图构建与产品映射，原嵌入/Annoy Fact-Masked检索尚未实现，整篇未完成。
原方法：判决分段与概要→六类节点→法条全称规范化→同段法律-规范、
逐适用的历史规范-适用与事实-适用→RDF→嵌入相似事实的法条检索。
创新点：将事实到法条的中间法律适用作为图节点，按历史上下文连接推理路径。
原benchmark：648份日本行政判决；专家节点/边标注及Fact-Masked法条检索。
原输入：判决章节、案件概要/查询事实；原输出：节点、规范法条、
三类关系、RDF及检索法条。原完整benchmark成绩未复现。
产品输入：冻结KIE预测文本或案件各方原文；输出：VQA JSON/CaseAnalysisOutput。
适配调试：原日文五阶段提示保留；原HTML预处理替为冻结文本分段，原概要缺失
明确留空；按原本体统一法条并保留出现位置，拒绝未知关系端点、未来章节；
未知/改写文本不制造引用offset。DeepSeek替代GPT-4o，无付费格式修复或重试。
未核验聊天不是裁判事实，原Fact类型附带未认定状态。最终产品投影额外调用，
可读冻结锚点定位引用，区别于原生图输出。无像素KIE、本地权重/训练。
独立实现/原输入输出：paper/author_reproductions/legal_reasoning_paths/，
逐次结果按l06_legal_reasoning_paths保存。不能以图路径枚举冒充语义检索。
"""
METHOD_ID='E25'
METHOD_NAME='l06_legal_reasoning_paths'
IMPLEMENTATION_STATUS='implemented'
REPRODUCTION_LEVEL='paper_pipeline_reimplementation_with_author_prompts_ontology'
REPRODUCTION_SCOPE='作者原提示/本体的图构建API分支重实现；作者Python未公开，远程嵌入检索待配置；整篇未完成'
PAPER_REFERENCES=[dict(paper_id='L06',reference='Kondo et al. (2025), Capturing Legal Reasoning Paths from Facts to Law in Court Judgments using Knowledge Graphs.',sources=['https://arxiv.org/abs/2508.17340'],verification='pinned_author_prompts_ontology_dataset_no_python')]
ORIGINAL_PAPER_CONTRACTS=[]
ADAPTATION_AUDIT=dict(original_paper_reproduced=False,author_code_execution='no_author_python_released',source_kind=REPRODUCTION_LEVEL,
    author_native_interface_connected_to_product=False,paper_algorithm_interface_connected_to_product=True,
    author_benchmark_tracks=[],paper_algorithm_benchmark_tracks=['vqa_predicted_text'],
    real_product_tracks_completed=[],local_model_inference=False,native_full_method_completed=False,
    blockers=['远程嵌入配置/Annoy Fact-Masked法条检索未完成；无作者Python流水线，非作者代码执行'],
    deferred_evaluation='专家法律金标后补，不作为图构建执行门槛')
async def run(context):
    from .legal_reasoning_paths_bridge import case_task
    return await case_task(context)
async def run_task(messages,call,attempts=2,tool_trace=None):
    from .legal_reasoning_paths_bridge import benchmark_task
    return await benchmark_task(messages,call,tool_trace)
