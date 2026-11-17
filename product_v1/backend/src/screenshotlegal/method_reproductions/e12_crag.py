"""
E12 · Corrective retrieval gate

论文出处：
- R02: Yan et al. (2024), *Corrective Retrieval Augmented Generation*.
  https://arxiv.org/abs/2401.15884

复现程度：project_mechanism。
复现 correct/incorrect/ambiguous 检索质量动作与闭域纠正；无专用训练 evaluator、Web 扩展和细粒度知识重组。

整理说明：仅拆分既有方法逻辑，不新增训练或法律质量结论。
运行/回复/测试产物目录：methods/e12_crag/

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[R02] CRAG
原有方法/任务：评估检索质量，按 correct/incorrect/ambiguous 调用纠正和知识精炼后生成。
原输入大致形态（结构示意，不是 Gold）：question 与初始检索 passages。
原输出大致形态：答案/标签和纠正后知识；原流程含训练的 T5 evaluator、知识分解重组与 Web 搜索。
原 benchmark：PopQA、Biography、PubHealth、ARC-Challenge；分别使用任务准确率或 FactScore 等原指标。
论文创新点（作者方法的组成）：以轻量检索评估器触发不同纠错动作，并结合细粒度知识精炼与必要的外部搜索。
对本工作的可适配性：闭域案内证据不能从 Web 补造。现有 E12 同底座三分类不等于原 T5 evaluator；若禁网会成为明确的 CRAG 变体。
核查依据：https://arxiv.org/html/2401.15884v3
作者代码：https://github.com/HuskyInSalt/CRAG @ de7c2961ae624a1483a138c5798e1f6d0c4fb0e0；本地 paper/upstream_sources/crag

本文件当前实际实现：复现 correct/incorrect/ambiguous 检索质量动作与闭域纠正；无专用训练 evaluator、Web 扩展和细粒度知识重组。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：未运行原 T5 evaluator 与细粒度知识精炼；闭域变体不能等同允许 Web 搜索的原 CRAG
当前作者原代码状态：original_benchmark_not_reproduced
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""


METHOD_ID = 'E12'
METHOD_NAME = 'e12_crag'
IMPLEMENTATION_STATUS = 'implemented'
REPRODUCTION_LEVEL = 'project_mechanism'
REPRODUCTION_SCOPE = '复现 correct/incorrect/ambiguous 检索质量动作与闭域纠正；无专用训练 evaluator、Web 扩展和细粒度知识重组。'
PAPER_REFERENCES = [{'paper_id': 'R02', 'reference': 'Yan et al. (2024), *Corrective Retrieval Augmented Generation*.', 'sources': ['https://arxiv.org/abs/2401.15884'], 'verification': 'paper_listing_verified_not_code_reproduced'}]





























ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'R02', 'method': 'CRAG', 'task': '评估检索质量，按 correct/incorrect/ambiguous 调用纠正和知识精炼后生成。', 'input': 'question 与初始检索 passages。', 'output': '答案/标签和纠正后知识；原流程含训练的 T5 evaluator、知识分解重组与 Web 搜索。', 'benchmark': 'PopQA、Biography、PubHealth、ARC-Challenge；分别使用任务准确率或 FactScore 等原指标。', 'innovation': '以轻量检索评估器触发不同纠错动作，并结合细粒度知识精炼与必要的外部搜索。', 'repo': 'crag', 'source': 'https://arxiv.org/html/2401.15884v3', 'fit': '闭域案内证据不能从 Web 补造。现有 E12 同底座三分类不等于原 T5 evaluator；若禁网会成为明确的 CRAG 变体。', 'pinned_author_source': {'repository': 'https://github.com/HuskyInSalt/CRAG', 'commit': 'de7c2961ae624a1483a138c5798e1f6d0c4fb0e0', 'local_path': 'paper/upstream_sources/crag'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'original_benchmark_not_reproduced', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '复现 correct/incorrect/ambiguous 检索质量动作与闭域纠正；无专用训练 evaluator、Web 扩展和细粒度知识重组。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': False, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': False, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'], 'blockers': ['未运行原 T5 evaluator 与细粒度知识精炼；闭域变体不能等同允许 Web 搜索的原 CRAG']}

async def run(context):
    visible = context.visible
    options = context.options
    answer = context.answer
    staged = context.staged
    retrieve = context.retrieve
    hierarchy = visible.get('matterpack', {}).get('factor_hierarchy')
    query = await answer('retrieval_query', '按争点与法律要件提出一个检索查询，返回 {"query":字符串,"factor_ids":[字符串]}。只用给定规则结构，不预判案件事实。', dict(goal=visible['goal'], matterpack=visible.get('matterpack'), factor_hierarchy=hierarchy), dict(query=visible['goal'][:200], factor_ids=[hierarchy[0]['factors'][0]['id']] if hierarchy else []))
    chosen = await retrieve(query['query'], 'factor', options['retrieval_top_k'])
    verdict = await answer('retrieval_gate', '判断检索材料，返回 {"confidence":"correct|incorrect|ambiguous","keep_source_ids":[字符串],"revised_query":字符串}。correct表示存在相关材料，incorrect表示全部不相关，ambiguous表示有用性不确定；只保留与争点相关的来源。', dict(goal=visible['goal'], passages=chosen), dict(confidence='correct', keep_source_ids=[p['id'] for p in chosen], revised_query=query['query']))
    confidence = verdict.get('confidence')
    keep = verdict.get('keep_source_ids')
    if confidence not in {'correct', 'incorrect', 'ambiguous'} or not isinstance(keep, list) or (not set(keep) <= {p['id'] for p in chosen}):
        raise ValueError('检索质量判断格式无效')
    chosen = [p for p in chosen if p['id'] in keep] if confidence != 'incorrect' else []
    if confidence != 'correct':
        corrected = await retrieve(verdict['revised_query'], 'corrective', options['retrieval_top_k'])
        chosen = list({r['id']: r for r in chosen + corrected}.values())
    material = dict(visible, sources=chosen, retrieval_scope='selected_frozen_passages', factor_selection=query)
    return await staged(material)
