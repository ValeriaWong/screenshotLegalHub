"""
E24 / R04 GraphRAG — Edge et al. (2024), From Local to Global.
论文出处：https://arxiv.org/html/2404.16130v1；https://arxiv.org/abs/2404.16130，§§2.1–2.6；作者源码
microsoft/graphrag v0.1.1 @ a81efe58c7c21ff8b17aa9bf1cb78a0750f3065b。
复现程度：直接执行作者无嵌入索引工作流与GlobalSearch，非完整原benchmark。
原方法：分块→实体/关系抽取→元素摘要→Leiden社区→社区报告→带分数map→reduce。
创新点：用查询无关的层级社区报告支持全局总结，非只做邻近向量检索。
原benchmark：Behind the Tech播客与MultiHop-RAG新闻，全局问题的覆盖度、
多样性、赋能与直接性成对评分。当前原任务为官方Operation Dulce Notebook查询。
原输入：文档语料/问题、社区报告与实体元数据；原输出：带报告引用的自然语言答案。
产品适配：冻结预测KIE/案件陈述文本重建原图与社区报告，再独立投影到全局VQA或
CaseAnalysisOutput。没有像素KIE、专家法律准确率或原百万token语料成绩。
模型以DeepSeek替代GPT-4；关闭嵌入/布局/可选claims、SDK重试与付费JSON修复，
串行父进程传输；未用向量后端的导入注册隔离，原抽象类型/工厂类保留。
原查询读作者完整预计算索引，不冒称重建作者索引；产品索引另真实执行与记录。
独立实现及原输入输出：paper/author_reproductions/graphrag/；按r04_graphrag存结果。

原论文与适配核查（2026-10-29）

复现判定：直接运行作者v0.1.1无嵌入索引/全局查询；原Notebook读取作者完整预计算索引，产品索引另执行；完整原benchmark未复现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[R04] GraphRAG
原有方法/任务：面向整篇语料的全局sensemaking/QFS问答，先建实体关系图与层级社区报告，再评分map与reduce。
原输入大致形态（结构示意，不是 Gold）：索引输入为文本语料；查询输入为全局问题、社区报告和实体元数据。官方原例为Operation Dulce预计算索引与主角/冲突问题。
原输出大致形态：自然语言全局答案及报告ID引用；中间含文本块、实体关系、Leiden社区、报告与带分数map结果。
原 benchmark：Behind the Tech播客与MultiHop-RAG新闻的全局问题；LLM成对覆盖度、多样性、赋能和直接性。官方Notebook原例不是原百万token benchmark。
论文创新点（作者方法的组成）：把图的层级社区预总结为可复用报告，再对全局问题生成并按分数归并部分答案，补足单纯向量近邻检索。
对本工作的可适配性：可适配冻结KIE预测文本全局VQA与案件陈述总结；不直接读像素。关闭不必要嵌入分支，保留作者原图/社区/查询控制流，最终Schema投影单列。
核查依据：https://arxiv.org/html/2404.16130v1
作者代码：https://github.com/microsoft/graphrag @ a81efe58c7c21ff8b17aa9bf1cb78a0750f3065b；本地 paper/upstream_sources/graphrag

本文件当前实际实现：直接运行GraphRAG v0.1.1无嵌入索引和全局map/reduce；原Notebook查询使用完整预计算索引，产品冻结文本单独建图；完整原benchmark未复现。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。
已接入run_task的输入轨道：vqa_predicted_text；每步输入输出可追溯。
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：固定官方v0.1.1提交，399个源码/原示例文件逐Git blob校验；Windows使用Python3.11与作者锁依赖，无本地权重；未用向量后端注册隔离，原基类与工厂类保留；原Notebook层级过滤保留全部217实体/5选中报告，真实2次完成map/reduce；作者14个无嵌入索引工作流通过确定传输验证；不是编写简化图替代原算法；原LLM模板替换/历史跟踪保留；禁用传输重试与付费JSON重格式化，失败逐条保存；案件与冻结预测KIE文本单独索引，最终产品Schema投影另列
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：本轮原样例和产品轨道完成；完整原benchmark另行验证
当前作者原代码状态：author_global_query_and_no_embedding_index_workflows
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""
METHOD_ID='E24'
METHOD_NAME='r04_graphrag'
IMPLEMENTATION_STATUS='implemented'
REPRODUCTION_LEVEL='author_global_api_index_and_query'
REPRODUCTION_SCOPE='直接运行GraphRAG v0.1.1无嵌入索引和全局map/reduce；原Notebook查询使用完整预计算索引，产品冻结文本单独建图；完整原benchmark未复现。'
PAPER_REFERENCES=[dict(paper_id='R04',reference='Edge et al. (2024), From Local to Global: A Graph RAG Approach to Query-Focused Summarization.',sources=['https://arxiv.org/abs/2404.16130'],verification='pinned_author_global_api_branch')]




ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'R04', 'method': 'GraphRAG', 'task': '面向整篇语料的全局sensemaking/QFS问答，先建实体关系图与层级社区报告，再评分map与reduce。', 'input': '索引输入为文本语料；查询输入为全局问题、社区报告和实体元数据。官方原例为Operation Dulce预计算索引与主角/冲突问题。', 'output': '自然语言全局答案及报告ID引用；中间含文本块、实体关系、Leiden社区、报告与带分数map结果。', 'benchmark': 'Behind the Tech播客与MultiHop-RAG新闻的全局问题；LLM成对覆盖度、多样性、赋能和直接性。官方Notebook原例不是原百万token benchmark。', 'innovation': '把图的层级社区预总结为可复用报告，再对全局问题生成并按分数归并部分答案，补足单纯向量近邻检索。', 'repo': 'graphrag', 'source': 'https://arxiv.org/html/2404.16130v1', 'fit': '可适配冻结KIE预测文本全局VQA与案件陈述总结；不直接读像素。关闭不必要嵌入分支，保留作者原图/社区/查询控制流，最终Schema投影单列。', 'pinned_author_source': {'repository': 'https://github.com/microsoft/graphrag', 'commit': 'a81efe58c7c21ff8b17aa9bf1cb78a0750f3065b', 'local_path': 'paper/upstream_sources/graphrag'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_global_query_and_no_embedding_index_workflows', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '直接运行GraphRAG v0.1.1无嵌入索引和全局map/reduce；原Notebook查询使用完整预计算索引，产品冻结文本单独建图；完整原benchmark未复现。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': True, 'author_benchmark_tracks': ['vqa_predicted_text'], 'native_author_controller_real_run_passed': True, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['固定官方v0.1.1提交，399个源码/原示例文件逐Git blob校验', 'Windows使用Python3.11与作者锁依赖，无本地权重；未用向量后端注册隔离，原基类与工厂类保留', '原Notebook层级过滤保留全部217实体/5选中报告，真实2次完成map/reduce', '作者14个无嵌入索引工作流通过确定传输验证；不是编写简化图替代原算法', '原LLM模板替换/历史跟踪保留；禁用传输重试与付费JSON重格式化，失败逐条保存', '案件与冻结预测KIE文本单独索引，最终产品Schema投影另列'], 'blockers': [], 'source_kind': 'author_global_api_index_and_query', 'native_verification': {'status': 'completed', 'checks': {'native_original_global_query_executed': True, 'author_index_precomputed': True, 'native_index_regenerated': False, 'selected_reports': 5, 'selected_entities': 217, 'positive_map_points': 3, 'original_map_reduce_executed': True, 'author_code_executed': True, 'local_model_inference': False, 'neural_modules_loaded': [], 'expert_legal_accuracy': None, 'source_kind': 'author_global_api_index_and_query'}, 'original_complete_benchmark': False}, 'real_product_tracks_completed': ['case_product', 'vqa_predicted_text'], 'local_model_inference': False, 'native_scope': 'exact author Operation Dulce query and full precomputed index tables; native index not regenerated', 'native_full_method_completed': False, 'adaptation_limitations': ['原查询使用作者预计算索引；没有重建该原索引或百万token benchmark', 'DeepSeek替代原GPT-4；产品实体类型含platform/message，分块1200/overlap100/one gleaning', '禁用原嵌入/布局/可选claims；仅无向量global分支，不支持像素KIE或本地搜索', '产品投影额外读取冻结锚点，不是未适配原benchmark结果', '真实文本VQA弃答、旧开发参考分0；案件摘要三方陈述与两名说话人/三条陈述不一致，原回复保留', '逐字引用校验不等于模型事实或法律质量，专家评测后补']}

async def run(context):
    from .graphrag_bridge import case_task
    return await case_task(context)

async def run_task(messages,call,attempts=2,tool_trace=None):
    from .graphrag_bridge import benchmark_task
    return await benchmark_task(messages,call,tool_trace)
