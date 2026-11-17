"""
B01 LegalAgentBench author baselines, product configuration E23.
Li et al., ACL 2025: https://aclanthology.org/2025.acl-long.116/.
Original question + 17 corpora/37 tools -> Final Answer/scratchpad; 300 tasks,
key_answer success and key_middle progress. Contribution is the domain benchmark,
not a new legal reasoning model; ReactAgent, PSAgent, PEAgent are author baselines.
Actual reproduction: pinned author classes/prompts/schema/parser bodies, isolated
Pydantic1.10 environment and DeepSeek transport. Source details and original I/O:
paper/author_reproductions/legalagentbench/product_adapter.py and README.md.
Original online tool service refuses connections; native proof uses exact author
log tool replay only. Product replaces tools with frozen KIE/case list/read, repeats
JSON output policy in each solve message, disables Python eval fallback, and
validates returned source IDs/citations. Not pixel KIE, not a full-paper benchmark
or expert legal accuracy result. Native failures and raw I/O remain method-named.

论文出处：B01 Li et al. (2025), *LegalAgentBench: Evaluating LLM Agents in Legal Domain*. ACL 2025. https://aclanthology.org/2025.acl-long.116/
复现程度：author_controller_with_explicit_tool_adaptation；LegalAgentBench作者三基线控制器及原提示/解析实际执行；原工具回放与冻结文本工具分开，在线17库和完整benchmark未复现。

原论文与适配核查（2026-10-29）

复现判定：作者三控制器实际执行；原任务为工具观察回放，原在线服务与完整benchmark未复现。产品文本工具为显式适配。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[B01] LegalAgentBench author baseline controllers
原有方法/任务：在17个法律/企业语料库与37个工具上完成中文1至5跳和写作任务；作者提供ReAct、Plan-and-Solve、Plan-and-Execute三条基线。
原输入大致形态（结构示意，不是 Gold）：自然语言question；工具描述和表格schema为公开上下文。原数据另有answer/key/key_middle，仅评分端读取。
原输出大致形态：Final Answer、scratchpad、过滤后的答案和过程摘要；原key_answer/key_middle分别对关键词做包含率评分。
原 benchmark：300个原任务；success/progress substring匹配，另有远程BERTScore分支。不是截图KIE或专家案件金标。
论文创新点（作者方法的组成）：法律场景17库37工具、分层任务构造及过程进度率；三条作者基线是对照控制器，不冒称新的法律推理方法。
对本工作的可适配性：作者控制器/提示/模式/解析函数真实执行，DeepSeek替换原API。原工具服务拒绝连接，首任务仅回放作者日志的精确工具观察，不等于在线17库复现。产品改为冻结KIE文本list/read工具并在各步保持JSON契约；像素KIE不适配，专家法律准确率未评测。
核查依据：https://aclanthology.org/2025.acl-long.116/
作者代码：https://github.com/CSHaitao/LegalAgentBench @ ec14d8ab1fc439bfd99cbefba08d8e27dafca534；本地 paper/upstream_sources/legalagentbench

本文件当前实际实现：LegalAgentBench作者三基线控制器及原提示/解析实际执行；原工具回放与冻结文本工具分开，在线17库和完整benchmark未复现。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。
已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：锁定16原文件，独立Pydantic1.10环境；原三类/提示/解析函数经AST执行；原post_request参数不匹配由显式传输修复；只允许JSON动作进入解析，eval备用路径不可达；产品替换冻结KIE/案件文本工具；每步保留输出契约，PS/PE早期格式失败保留；最终事件封装错误通过严格匹配原七条响应零调用恢复；所有变体共享100次上限
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：作者在线法律工具服务拒绝连接；原首任务只回放原日志精确工具观察，不等于17库/37工具端到端复现
当前作者原代码状态：author_controller_controlled_replay_live_service_unavailable
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""
METHOD_ID='E23'
METHOD_NAME='b01_legalagentbench'
IMPLEMENTATION_STATUS='implemented'
REPRODUCTION_LEVEL='author_controller_with_explicit_tool_adaptation'
REPRODUCTION_SCOPE='LegalAgentBench作者三基线控制器及原提示/解析实际执行；原工具回放与冻结文本工具分开，在线17库和完整benchmark未复现。'
PAPER_REFERENCES=[{"paper_id":"B01","reference":"Li et al. (2025), *LegalAgentBench: Evaluating LLM Agents in Legal Domain*. ACL 2025.","sources":["https://aclanthology.org/2025.acl-long.116/"],"verification":"paper_listing_verified_not_code_reproduced"}]












ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'B01', 'method': 'LegalAgentBench author baseline controllers', 'task': '在17个法律/企业语料库与37个工具上完成中文1至5跳和写作任务；作者提供ReAct、Plan-and-Solve、Plan-and-Execute三条基线。', 'input': '自然语言question；工具描述和表格schema为公开上下文。原数据另有answer/key/key_middle，仅评分端读取。', 'output': 'Final Answer、scratchpad、过滤后的答案和过程摘要；原key_answer/key_middle分别对关键词做包含率评分。', 'benchmark': '300个原任务；success/progress substring匹配，另有远程BERTScore分支。不是截图KIE或专家案件金标。', 'innovation': '法律场景17库37工具、分层任务构造及过程进度率；三条作者基线是对照控制器，不冒称新的法律推理方法。', 'repo': 'legalagentbench', 'source': 'https://aclanthology.org/2025.acl-long.116/', 'fit': '作者控制器/提示/模式/解析函数真实执行，DeepSeek替换原API。原工具服务拒绝连接，首任务仅回放作者日志的精确工具观察，不等于在线17库复现。产品改为冻结KIE文本list/read工具并在各步保持JSON契约；像素KIE不适配，专家法律准确率未评测。', 'pinned_author_source': {'repository': 'https://github.com/CSHaitao/LegalAgentBench', 'commit': 'ec14d8ab1fc439bfd99cbefba08d8e27dafca534', 'local_path': 'paper/upstream_sources/legalagentbench'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_controller_controlled_replay_live_service_unavailable', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': 'LegalAgentBench作者三基线控制器及原提示/解析实际执行；原工具回放与冻结文本工具分开，在线17库和完整benchmark未复现。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': True, 'author_benchmark_tracks': ['vqa_predicted_text'], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['锁定16原文件，独立Pydantic1.10环境；原三类/提示/解析函数经AST执行', '原post_request参数不匹配由显式传输修复；只允许JSON动作进入解析，eval备用路径不可达', '产品替换冻结KIE/案件文本工具；每步保留输出契约，PS/PE早期格式失败保留', '最终事件封装错误通过严格匹配原七条响应零调用恢复；所有变体共享100次上限'], 'blockers': ['作者在线法律工具服务拒绝连接；原首任务只回放原日志精确工具观察，不等于17库/37工具端到端复现'], 'source_kind': 'author_controller_with_explicit_tool_adaptation', 'controlled_native_replay_passed': True, 'controlled_native_replay_by_variant': {'react': {'status': 'completed', 'checks': {'original_controller_finished': True, 'tool_observation_replayed': True, 'reference_sent_to_model': False, 'live_service_validated': False, 'scope': 'same task as original CLI; exact author-log tool observation replay only', 'metrics': {'metrics': {'key_answer': {'score': 1.0, 'original_display': '1.0000', 'source_line': 25}, 'key_middle': {'score': 1.0, 'original_display': '1.0000', 'source_line': 43}}, 'source_commit': 'ec14d8ab1fc439bfd99cbefba08d8e27dafca534', 'method': 'original substring-scoring branches, unchanged AST bodies', 'local_model_inference': False}, 'local_model_inference': False, 'original_complete_benchmark': False}, 'original_complete_benchmark': False}, 'plan_and_solve': {'status': 'completed', 'checks': {'original_controller_finished': True, 'tool_observation_replayed': True, 'reference_sent_to_model': False, 'live_service_validated': False, 'scope': 'same task as original CLI; exact author-log tool observation replay only', 'metrics': {'metrics': {'key_answer': {'score': 1.0, 'original_display': '1.0000', 'source_line': 25}, 'key_middle': {'score': 1.0, 'original_display': '1.0000', 'source_line': 43}}, 'source_commit': 'ec14d8ab1fc439bfd99cbefba08d8e27dafca534', 'method': 'original substring-scoring branches, unchanged AST bodies', 'local_model_inference': False}, 'local_model_inference': False, 'original_complete_benchmark': False}, 'original_complete_benchmark': False}, 'plan_and_execute': {'status': 'completed', 'checks': {'original_controller_finished': True, 'tool_observation_replayed': True, 'reference_sent_to_model': False, 'live_service_validated': False, 'scope': 'same task as original CLI; exact author-log tool observation replay only', 'metrics': {'metrics': {'key_answer': {'score': 1.0, 'original_display': '1.0000', 'source_line': 25}, 'key_middle': {'score': 1.0, 'original_display': '1.0000', 'source_line': 43}}, 'source_commit': 'ec14d8ab1fc439bfd99cbefba08d8e27dafca534', 'method': 'original substring-scoring branches, unchanged AST bodies', 'local_model_inference': False}, 'local_model_inference': False, 'original_complete_benchmark': False}, 'original_complete_benchmark': False}}, 'real_product_variants_by_track': {'vqa_predicted_text': ['plan_and_execute', 'plan_and_solve', 'react'], 'case_product': ['react']}, 'original_live_corpora_available': False, 'real_product_tracks_completed': ['case_product', 'vqa_predicted_text'], 'local_model_inference': False, 'adaptation_limitations': ['原服务不可用，工具观察回放不等于在线原任务通过', '三种VQA开发样本均弃答0；原关键词1.0只覆盖同一首任务且无中间关键词', '不是像素KIE或专家法律准确率；完整300题benchmark未复现']}

async def run(context):
    from .legalagentbench_bridge import case_task
    return await case_task(context)

async def run_task(messages,call,attempts=2,tool_trace=None,variant='react'):
    from .legalagentbench_bridge import benchmark_task
    return await benchmark_task(messages,call,tool_trace,variant)
