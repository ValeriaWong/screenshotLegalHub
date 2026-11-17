"""
E18 JurisMA inference Algorithm 1; Lu et al., arXiv:2604.10470v1.
论文出处：https://arxiv.org/html/2604.10470v1 §§3.2–3.4/Algorithm 1。
复现程度：论文推理算法重实现，非作者源码或DPO训练系统；整篇未完成。
原方法：要素图→初稿→最多5轮动态FormatCheck/LawSearch→ContentCheck；
同轮两项均执行且格式先于法条检索，Pass/空动作结束后仍做最终修订。
创新点：法律语义图、选择性Agent协作、法条grounding及双部分咨询输出。
原benchmark：修订LawBench；JurisCQAD用于DPO；RuleQA/KoBLEX迁移。
原输入：非正式法律咨询（如论文附录C醉驾历史与子女航空院校申请）；
原输出：Response与完整法条Legal Basis，中间为JSON图与草稿。
产品适配：冻结案件/预测KIE文本替代咨询内容；API选ID后读取真实冻结
法条，最终单独投影为CaseAnalysisOutput或文本VQA。无像素KIE支持。
差异：DeepSeek替换训练模型；提示与目录后端为本项目实现。原训练/
检查点按用户资源要求暂缓，不以同底座prompt冒充训练；法律准确率未知。
实现、原输入输出与验证：paper/author_reproductions/jurisma/；
运行记录：methods/e18_jurisma/。

原论文与适配核查（2026-10-29）

复现判定：论文§3.2–3.4/Algorithm 1推理重实现与独立产品投影；非作者代码，DPO/本地检查点暂缓，整篇未完成。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L07] JurisMA
原有方法/任务：中文法律咨询问答；查询转法律要素图，再动态协作与内容修订。
原输入大致形态（结构示意，不是 Gold）：用户法律咨询问题，可能长、非正式且存在多个争点；不要求先输入截图或 ProofGraph。
原输出大致形态：面向用户的咨询答复和法律依据；要素图是中间结构。
原 benchmark：修订版 LawBench；JurisCQAD 用于训练/DPO。另有 LegalBench-RuleQA 小样本迁移实验。
论文创新点（作者方法的组成）：实体/事件/意图/争点结构、动态任务路由、法条 grounding 与内容修订，并构建咨询偏好数据。
对本工作的可适配性：可将论文§3.2–3.4/Algorithm 1推理算法适配为远程API咨询、冻结预测KIE文本VQA和案件结构映射；DPO与本地检查点暂缓，非作者代码/完整论文复现。
核查依据：https://arxiv.org/html/2604.10470v1
作者代码：未固定对应作者入口；不得宣称已运行作者代码

本文件当前实际实现：实现论文§3.2–3.4/Algorithm 1推理控制流与独立产品投影；作者源码未核实，DPO与本地检查点暂缓，整篇未完成。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
论文算法重实现已接入本文件run()：是；不是作者源码执行。
已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：独立Python3.12.15、0额外依赖，无本地权重/训练/嵌入；按论文Algorithm 1实现T=5、双动作格式先于法条检索、Pass/空动作停止后仍执行ContentCheck；法条目录选ID后读取真实原文；拒绝未知ID与未检索/缩略法条冒充全文；原任务初次最后全文校验失败保留；逐请求精确缓存恢复，只新增ContentCheck调用；最终修订额外提供已检索法条附录，为显式项目适配；案件/VQA结构投影单独记录
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：作者源码未核实；DPO与本地训练检查点按用户指令暂缓；推理API分支不能替代整篇训练系统与原benchmark
当前作者原代码状态：not_executed_no_verified_author_repository
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""
METHOD_ID='E18'
METHOD_NAME='e18_jurisma'
IMPLEMENTATION_STATUS='implemented'
REPRODUCTION_LEVEL='paper_algorithm_inference_adaptation'
REPRODUCTION_SCOPE='实现论文§3.2–3.4/Algorithm 1推理控制流与独立产品投影；作者源码未核实，DPO与本地检查点暂缓，整篇未完成。'
PAPER_REFERENCES=[dict(paper_id='L07',reference='Lu et al. (2026), From Query to Counsel: Structured Reasoning with a Multi-Agent Framework and Dataset for Legal Consultation (JurisMA).',sources=['https://arxiv.org/html/2604.10470v1'],verification='paper_algorithm_inference_reimplementation_training_deferred')]






ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L07', 'method': 'JurisMA', 'task': '中文法律咨询问答；查询转法律要素图，再动态协作与内容修订。', 'input': '用户法律咨询问题，可能长、非正式且存在多个争点；不要求先输入截图或 ProofGraph。', 'output': '面向用户的咨询答复和法律依据；要素图是中间结构。', 'benchmark': '修订版 LawBench；JurisCQAD 用于训练/DPO。另有 LegalBench-RuleQA 小样本迁移实验。', 'innovation': '实体/事件/意图/争点结构、动态任务路由、法条 grounding 与内容修订，并构建咨询偏好数据。', 'repo': None, 'source': 'https://arxiv.org/html/2604.10470v1', 'fit': '可将论文§3.2–3.4/Algorithm 1推理算法适配为远程API咨询、冻结预测KIE文本VQA和案件结构映射；DPO与本地检查点暂缓，非作者代码/完整论文复现。', 'pinned_author_source': None}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'not_executed_no_verified_author_repository', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '实现论文§3.2–3.4/Algorithm 1推理控制流与独立产品投影；作者源码未核实，DPO与本地检查点暂缓，整篇未完成。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['独立Python3.12.15、0额外依赖，无本地权重/训练/嵌入', '按论文Algorithm 1实现T=5、双动作格式先于法条检索、Pass/空动作停止后仍执行ContentCheck', '法条目录选ID后读取真实原文；拒绝未知ID与未检索/缩略法条冒充全文', '原任务初次最后全文校验失败保留；逐请求精确缓存恢复，只新增ContentCheck调用', '最终修订额外提供已检索法条附录，为显式项目适配；案件/VQA结构投影单独记录'], 'blockers': ['作者源码未核实；DPO与本地训练检查点按用户指令暂缓；推理API分支不能替代整篇训练系统与原benchmark'], 'source_kind': 'paper_algorithm_inference_reimplementation_training_deferred', 'paper_algorithm_interface_connected_to_product': True, 'paper_algorithm_native_real_run_passed': True, 'native_verification': {'status': 'completed', 'checks': {'published_consultation_query_executed': True, 'manager_rounds': 5, 'stop_reason': 'iteration_limit', 'maximum_rounds': 5, 'content_check_executed': True, 'retrieved_statutes': 3, 'full_article_literal_checks': True, 'training_reproduced': False, 'native_full_method_completed': False, 'expert_legal_accuracy': None, 'complete_inference_algorithm_execution': True, 'local_model_inference': False, 'source_kind': 'paper_algorithm_inference_reimplementation_training_deferred', 'author_code_executed': False}, 'original_complete_benchmark': False}, 'real_product_tracks_completed': ['case_product', 'vqa_predicted_text'], 'paper_algorithm_benchmark_tracks': ['vqa_predicted_text'], 'local_model_inference': False, 'native_full_method_completed': False, 'training_reproduced': False, 'adaptation_limitations': ['论文推理重实现，不是作者代码或JurisCQAD DPO检查点', '提示为本项目编写，DeepSeek替代原训练模型；法条目录后端不同', '原任务仅论文附录C咨询示例，航空院校审查依据缺失；没有专家法律准确率', '支持冻结KIE预测文本全局VQA，不支持像素KIE；整个L07保持部分完成']}

async def run(context):
    from .jurisma_bridge import case_task
    return await case_task(context)

async def run_task(messages,call,attempts=2,tool_trace=None):
    from .jurisma_bridge import benchmark_task
    return await benchmark_task(messages,call,tool_trace)
