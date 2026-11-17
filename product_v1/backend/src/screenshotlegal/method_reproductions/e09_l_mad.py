"""
E09 L-MAD — Nguyen et al. 2026, https://arxiv.org/html/2607.09099v1.
Reproduction level: paper scheduler with actual cited MALLM source components;
L-MAD author repository is unverified. Source/fidelity, original input/output,
benchmarks and all adaptation choices are detailed at the top of
paper/author_reproductions/l_mad/algorithm.py and in that directory's README.md.
Original task: Civil Code premises + legal hypothesis -> Answer:Y/N; COLIEE Task4
R05/R06/R07 accuracy. Innovation: compare neutral persona consensus/ranked voting
under a two-turn memory window, retaining disagreement and one tie-break round.
Actual code: original MALLM SimpleResponseGenerator prompt, ThresholdConsensus,
RankedVoting parsers/scoring, plus a paper-defined bounded scheduler. No generic
staged/adversarial baseline is called by run() or run_task().
Adaptation: binary frozen-KIE-text VQA checks both labels separately; case mode
proposes <=2 anchored facts, verifies source support, then revises on accepted facts.
No direct pixel KIE/four-label shortcut, no law-accuracy inference from consensus.
All protocol variants, raw prompts/responses, votes, agreement windows and failures
are saved by method name; main Answer labels and appendix 判断 labels stay separate.
A08 remains a design citation; its scaling experiments are not reproduced here.

论文出处：L10 Nguyen et al. (2026), *L-MAD: A Systematic Evaluation of Multi-Agent Debate Structures in Legal Reasoning*. https://arxiv.org/abs/2607.09099；A08 Kim et al. (2025), *Towards a Science of Scaling Agent Systems*. https://arxiv.org/abs/2512.08296
复现程度：paper_specification_with_cited_upstream_components；L-MAD论文协议调度＋原MALLM共识/排名/提示组件；三persona、两轮上下文、严格Y/N、混合共识与排名投票；非L-MAD作者源码或原检查点。

原论文与适配核查（2026-10-29）

复现判定：L-MAD论文协议调度＋所引MALLM原组件实际执行；非L-MAD作者源码/检查点，完整COLIEE benchmark未复现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[L10] L-MAD (Nguyen et al., 2026)
原有方法/任务：法条premise与法律hypothesis之间的二分类蕴含判断；比较三persona的混合共识与固定轮次排名投票。
原输入大致形态（结构示意，不是 Gold）：原COLIEE每题Relevant article、Query、Answer。只把法条与问题送给模型；原答案仅评分。本轮原任务为论文2.1节Article9官方英文翻译示例，不是R05/R06/R07年度数据集。
原输出大致形态：正文固定Answer:Y/N与简短公开说明；附录日文提示却要求判断:Y/N，二者分别解析。协议还产生AGREE/DISAGREE、排名与收敛/平局/未知轨迹。
原 benchmark：COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。
论文创新点（作者方法的组成）：在两轮滑动记忆下比较共识与排名投票，保持分歧和最多一轮平局补充讨论，研究协议/规模对法律判断的影响。
对本工作的可适配性：论文协议调度＋实际所引MALLM提示/共识/排名组件；未核实L-MAD作者仓库。混合参数按论文配置，不能直接用不同的MALLM默认值。DeepSeek替换原本地模型、固定附录persona、原示例英文语言差异均披露。二分类KIE文本VQA双向验候选，N不自动推出相反标签；案件先核验最多2项有原文锚点的陈述，再修订，不能由共识推定法律正确。
核查依据：https://arxiv.org/html/2607.09099v1
作者代码：未固定对应作者入口；不得宣称已运行作者代码

[A08] Towards a Science of Scaling Agent Systems
原有方法/任务：跨不同 agentic benchmark 比较单/多 agent 的结构、成本与成功率。
原输入大致形态（结构示意，不是 Gold）：各原生环境的工具任务，接口随 benchmark 变化。
原输出大致形态：任务完成结果、轨迹与成本指标；不是一个固定法律推理算法。
原 benchmark：当前核对版本包含 BrowseComp-Plus、Finance-Agent、PlanCraft、WorkBench，并报告 SWE-bench Verified、Terminal-Bench 小规模扩展。
论文创新点（作者方法的组成）：研究任务分解性、协调开销与模型能力对多 agent 收益的约束。
对本工作的可适配性：可借鉴同预算实验设计，E09 轮次参数不等于复现该研究或其六类 benchmark。
核查依据：https://arxiv.org/html/2512.08296
作者代码：未固定对应作者入口；不得宣称已运行作者代码

本文件当前实际实现：L-MAD论文协议调度＋原MALLM共识/排名/提示组件；三persona、两轮上下文、严格Y/N、混合共识与排名投票；非L-MAD作者源码或原检查点。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
论文算法重实现已接入本文件run()：是；不是作者源码执行。
已接入run_task的输入轨道：vqa_predicted_text (binary only)；每步输入输出可追溯。
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：固定MALLM 11个原文件；AST载入原共识/排名/提示组件，无Torch/嵌入依赖；原混合默认值与L-MAD论文不同，显式配置论文阈值；正文Answer和附录判断分别解析；严格排名和单次平局补充，无自动付费格式重试；双向候选蕴含避免把未获支持自动当作相反标签；案件保留原文锚点和已核验fact集合；原任务与产品按协议分组留存，历史/失败/未知共用100次预算
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证
当前作者原代码状态：LMAD_author_code_unverified_cited_MALLM_components_executed
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""

METHOD_ID = 'E09'
METHOD_NAME = 'e09_l_mad'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'paper_specification_with_cited_upstream_components'
REPRODUCTION_SCOPE = 'L-MAD论文协议调度＋原MALLM共识/排名/提示组件；三persona、两轮上下文、严格Y/N、混合共识与排名投票；非L-MAD作者源码或原检查点。'
PAPER_REFERENCES = [{'paper_id': 'L10', 'reference': 'Nguyen et al. (2026), *L-MAD: A Systematic Evaluation of Multi-Agent Debate Structures in Legal Reasoning*.', 'sources': ['https://arxiv.org/abs/2607.09099'], 'verification': 'paper_listing_verified_not_code_reproduced'}, {'paper_id': 'A08', 'reference': 'Kim et al. (2025), *Towards a Science of Scaling Agent Systems*.', 'sources': ['https://arxiv.org/abs/2512.08296'], 'verification': 'paper_listing_verified_not_code_reproduced'}]






























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'L10', 'method': 'L-MAD (Nguyen et al., 2026)', 'task': '法条premise与法律hypothesis之间的二分类蕴含判断；比较三persona的混合共识与固定轮次排名投票。', 'input': '原COLIEE每题Relevant article、Query、Answer。只把法条与问题送给模型；原答案仅评分。本轮原任务为论文2.1节Article9官方英文翻译示例，不是R05/R06/R07年度数据集。', 'output': '正文固定Answer:Y/N与简短公开说明；附录日文提示却要求判断:Y/N，二者分别解析。协议还产生AGREE/DISAGREE、排名与收敛/平局/未知轨迹。', 'benchmark': 'COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。', 'innovation': '在两轮滑动记忆下比较共识与排名投票，保持分歧和最多一轮平局补充讨论，研究协议/规模对法律判断的影响。', 'repo': None, 'cited_framework_repo': 'mallm', 'source': 'https://arxiv.org/html/2607.09099v1', 'fit': '论文协议调度＋实际所引MALLM提示/共识/排名组件；未核实L-MAD作者仓库。混合参数按论文配置，不能直接用不同的MALLM默认值。DeepSeek替换原本地模型、固定附录persona、原示例英文语言差异均披露。二分类KIE文本VQA双向验候选，N不自动推出相反标签；案件先核验最多2项有原文锚点的陈述，再修订，不能由共识推定法律正确。', 'pinned_author_source': None}, {'paper_id': 'A08', 'method': 'Towards a Science of Scaling Agent Systems', 'task': '跨不同 agentic benchmark 比较单/多 agent 的结构、成本与成功率。', 'input': '各原生环境的工具任务，接口随 benchmark 变化。', 'output': '任务完成结果、轨迹与成本指标；不是一个固定法律推理算法。', 'benchmark': '当前核对版本包含 BrowseComp-Plus、Finance-Agent、PlanCraft、WorkBench，并报告 SWE-bench Verified、Terminal-Bench 小规模扩展。', 'innovation': '研究任务分解性、协调开销与模型能力对多 agent 收益的约束。', 'repo': None, 'source': 'https://arxiv.org/html/2512.08296', 'fit': '可借鉴同预算实验设计，E09 轮次参数不等于复现该研究或其六类 benchmark。', 'pinned_author_source': None}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'LMAD_author_code_unverified_cited_MALLM_components_executed', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': 'L-MAD论文协议调度＋原MALLM共识/排名/提示组件；三persona、两轮上下文、严格Y/N、混合共识与排名投票；非L-MAD作者源码或原检查点。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['固定MALLM 11个原文件；AST载入原共识/排名/提示组件，无Torch/嵌入依赖', '原混合默认值与L-MAD论文不同，显式配置论文阈值', '正文Answer和附录判断分别解析；严格排名和单次平局补充，无自动付费格式重试', '双向候选蕴含避免把未获支持自动当作相反标签；案件保留原文锚点和已核验fact集合', '原任务与产品按协议分组留存，历史/失败/未知共用100次预算'], 'blockers': [], 'source_kind': 'paper_specification_with_cited_upstream_components', 'LMAD_author_code_executed': False, 'cited_upstream_code_executed': True, 'paper_algorithm_interface_connected_to_product': True, 'paper_algorithm_native_real_run_passed': True, 'native_paper_example_only': True, 'native_verification_by_protocol': {'hybrid': {'status': 'completed', 'checks': {'published_native_task_executed': True, 'scope': 'published official-English-translation illustration; not a COLIEE R05/R06/R07 dataset evaluation', 'correct': True, 'strict_main_label_parsed': True, 'reference_sent_to_model': False, 'protocol': 'hybrid', 'local_model_inference': False, 'source_kind': 'paper_specification_with_cited_upstream_components', 'LMAD_author_code_executed': False, 'expert_legal_accuracy': None}, 'original_complete_benchmark': False}, 'ranked': {'status': 'completed', 'checks': {'published_native_task_executed': True, 'scope': 'published official-English-translation illustration; not a COLIEE R05/R06/R07 dataset evaluation', 'correct': True, 'strict_main_label_parsed': True, 'reference_sent_to_model': False, 'protocol': 'ranked', 'local_model_inference': False, 'source_kind': 'paper_specification_with_cited_upstream_components', 'LMAD_author_code_executed': False, 'expert_legal_accuracy': None}, 'original_complete_benchmark': False}}, 'real_product_tracks_completed': ['case_product', 'vqa_predicted_text'], 'real_product_protocols': ['hybrid', 'ranked'], 'paper_algorithm_benchmark_tracks': ['vqa_predicted_text (binary only)'], 'local_model_inference': False, 'real_run_summary': {'paper': 'L10', 'source_kind': 'paper_specification_with_cited_upstream_components', 'author_LMAD_code_executed': False, 'original_complete_benchmark': False, 'expert_legal_accuracy': None, 'local_model_inference': False, 'requests_used_including_failures': 92, 'limit': 100}, 'real_product_results': [{'directory': '1814043722ca8211__vqa_predicted_text__hybrid', 'track': 'vqa_predicted_text', 'protocol': 'hybrid', 'status': 'completed', 'requests': 17, 'prediction': {'answer': None, 'evidence': [{'candidate': 'group_chat', 'entailed': 'N', 'decision': True}, {'candidate': 'private_chat', 'entailed': None, 'decision': False}]}, 'score': {'raw_exact': False, 'normalized_exact': False, 'score': 0, 'status': 'abstained', 'prediction': {'answer': None, 'evidence': [{'candidate': 'group_chat', 'entailed': 'N', 'decision': True}, {'candidate': 'private_chat', 'entailed': None, 'decision': False}]}}, 'final_fact_count': None}, {'directory': '1a6a5128c2ffd31d__case_product__hybrid', 'track': 'case_product', 'protocol': 'hybrid', 'status': 'failed', 'requests': 16, 'prediction': None, 'score': None, 'final_fact_count': None}, {'directory': 'b075523bcd722ec1__case_product__hybrid', 'track': 'case_product', 'protocol': 'hybrid', 'status': 'completed', 'requests': 11, 'prediction': None, 'score': None, 'final_fact_count': 0}, {'directory': 'd60074513de5d1a1__vqa_predicted_text__ranked', 'track': 'vqa_predicted_text', 'protocol': 'ranked', 'status': 'completed', 'requests': 30, 'prediction': {'answer': None, 'evidence': [{'candidate': 'group_chat', 'entailed': None, 'decision': False}, {'candidate': 'private_chat', 'entailed': 'N', 'decision': True}]}, 'score': {'raw_exact': False, 'normalized_exact': False, 'score': 0, 'status': 'abstained', 'prediction': {'answer': None, 'evidence': [{'candidate': 'group_chat', 'entailed': None, 'decision': False}, {'candidate': 'private_chat', 'entailed': 'N', 'decision': True}]}}, 'final_fact_count': None}, {'directory': 'df63d7f9b390e5d5__case_product__hybrid', 'track': 'case_product', 'protocol': 'hybrid', 'status': 'failed', 'requests': 1, 'prediction': None, 'score': None, 'final_fact_count': None}], 'adaptation_limitations': ['未核实L-MAD作者源码；仅所引MALLM组件实际执行', '原任务仅论文英文示例，不是年度COLIEE数据集；DeepSeek/固定persona替换明确披露', '产品二分类文本VQA与事实支持性，不是像素KIE或法律准确率', 'A08仅设计引用，其原实验未复现', '本轮两VQA均弃答0；案件最终facts为空，摘要仍有复述陈述的质量风险；仅执行与结构校验通过，非有效事实提取']}

async def run(context):
    from .lmad_bridge import case_task
    return await case_task(context)

async def run_task(messages,call,attempts=2,tool_trace=None,protocol='hybrid'):
    from .lmad_bridge import benchmark_task
    return await benchmark_task(messages,call,tool_trace,protocol)
