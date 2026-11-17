"""Annotate every project method with original task contracts and adaptation audit.

This changes documentation/provenance only; it does not claim the project run()
function is an author's original implementation.
"""
import ast
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'product_v1/backend/src'))
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES,method_metadata

profiles=json.loads((REPO/'paper/author_reproductions/paper_contracts.json').read_text(encoding='utf-8'))
sources=json.loads((REPO/'paper/author_reproductions/sources.lock.json').read_text(encoding='utf-8'))
sources={s['name']:s for s in sources}
marker='原论文与适配核查（2026-10-29）'
execution_index=json.loads((REPO/'paper/author_reproductions/results/2026-10-29-per-paper/validation_index.json').read_text(encoding='utf-8'))

def annotate():
    rows=[]
    for method,name in METHOD_MODULES.items():
        meta=method_metadata(method);file=REPO/meta['implementation_file']
        original=file.read_text(encoding='utf-8');tree=ast.parse(original)
        remove=[]
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'ORIGINAL_PAPER_CONTRACTS','ADAPTATION_AUDIT'} for t in node.targets):remove.append(node)
        parts=original.splitlines(keepends=True)
        for node in reversed(remove):del parts[node.lineno-1:node.end_lineno]
        original=''.join(parts);tree=ast.parse(original)
        doc_node=tree.body[0];old_doc=doc_node.value.value
        old_doc=old_doc.split('\n原论文与适配核查（')[0].strip()
        if '论文出处' not in old_doc:
            old_doc+='\n\n论文出处：'+('；'.join(p['paper_id']+' '+p['reference']+' '+', '.join(p['sources']) for p in meta['paper_sources']) or '项目基线，无对应单篇论文')
        if '复现程度' not in old_doc:old_doc+='\n复现程度：'+meta['reproduction_level']+'；'+meta['reproduction_scope']
        contracts=[]
        for p in meta['paper_sources']:
            item=dict(paper_id=p['paper_id'],**profiles[p['paper_id']])
            source=sources.get(item.get('repo'))
            item['pinned_author_source']=source and {k:source[k] for k in ['repository','commit','local_path']}
            contracts.append(item)
        baseline=method in {'E00','E02','E03'}
        current=meta['reproduction_scope']
        compatible='非单篇论文复现的项目基线' if baseline else '条件适配；原输入/标签/评价协议不能直接等同截图证据链'
        if meta['implementation_status']=='planned':compatible+='；当前模块未实现'
        native_status='not_applicable_project_baseline' if baseline else 'original_benchmark_not_reproduced'
        if method=='E05':native_status='author_controller_integrated_case_kie_global_vqa_native_example_partial'
        if method=='E01':native_status='author_controller_integrated_kie_global_vqa_native_agent_model_run_pending'
        blockers=[]
        for c in contracts:
            if not c.get('pinned_author_source'):blockers.append(c['method']+'：尚未固定/执行对应作者代码入口，不能用同名第三方项目替代')
        if method in {'E06','E11','E18','E20'}:blockers.append('原训练模型/过程验证器/记忆机制或原任务资源未部署；同一底座 prompt 不能替代原训练')
        if method=='E19':blockers.append('缺少独立且经审查的中国民事法律指南与 Issue–Factor→guide 映射')
        if method in {'E07','E08'}:blockers.append('作者 Legal-KB、原检索组件及 SimuCourt 原协议尚未端到端运行')
        if method=='E12':blockers.append('未运行原 T5 evaluator 与细粒度知识精炼；闭域变体不能等同允许 Web 搜索的原 CRAG')
        if method in {'E13','E17'}:blockers.append('当前只有明确拒绝执行的登记文件，没有对应算法实现')
        if method=='E09':blockers.append('未复现原 Answer:Y/N 标签解析及共识/投票协议对照')
        if method=='E05':blockers.append('原缩写任务已完成一次三模块修订；原控制器真实完整运行尚待新增调用，未跑原数据集完整评测')
        if method=='E01':blockers.append('独立环境和原任务已加载；原Notebook控制器的真实模型HotpotQA样例尚未运行，图像适配待真实模型验证')
        audit=dict(original_paper_reproduced=False,author_code_execution=native_status,adaptability=compatible,
                   current_project_implementation=current,
                   required_adaptation=['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实',
                       '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动',
                       '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'],
                   our_input_shape='FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus',
                   our_output_shape='CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties',
                   author_native_interface_connected_to_product=(method=='E05'),
                   author_benchmark_tracks=['kie_image','vqa_image_full'] if method in {'E01','E05'} else [],
                   native_author_controller_real_run_passed=False,
                   deferred_evaluation='用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞',
                   native_author_component_example_passed=(method=='E05'),
                   completed_debugging=['项目现有流程/预算/引用校验已运行；这些不是作者 benchmark 成绩'],
                   blockers=blockers)
        if method=='E05':
            audit['completed_debugging'] += ['固定 Self-Refine 与 prompt-lib 提交；独立 Python 环境',
                '修复未使用的 Anthropic 客户端构造兼容与 httpx 版本',
                '本地受限 broker 保存实际 DeepSeek 身份，给原 SDK 返回兼容 engine alias',
                '保留原 few-shot 提示，额外添加模型格式指令；禁用整轮自动付费重试',
                '首次失败 1 次调用；随后原 Init/Feedback/Iterate 三类用 3 次调用完成一次修订']
        if method=='E05':
            audit['completed_debugging'] += ['原responsegen控制器函数体经AST原样载入，禁用付费整轮重试；原三任务类__call__保留', '任务模板改为KIE/VQA/CaseAnalysisOutput；JSON转义保护原字符；图像每步保持冻结输入', '产品案件主链和KIE/全图VQA入口已接作者控制器；工程验证使用确定传输夹具，尚未新增真实调用']
        if method=='E01':
            audit['completed_debugging'] += ['独立gym/numpy环境；原WikiEnv与HotPotQAWrapper成功载入7405道dev题', '原Notebook webthink函数体原样载入；截图变体用冻结原图目录和真实像素局部读取替换Wikipedia工具', 'KIE/全图VQA入口已接run_task；原图和局部图的哈希、坐标、逐步请求/响应保留，边界错误会停止']
        if method in {'E15','E16','E21'}:
            audit=meta['adaptation_assessment']
            native_status=audit['author_code_execution']
            compatible=audit['adaptability']
            blockers=audit['blockers']
        if method=='E04':
            audit['blockers']=['SOLAR原Stage II和固定税法解释器已建立独立入口；真实模型原任务未验证。SARA规则不能直接用于中国截图KIE/全局VQA；须提供相应规则域。']
            blockers=audit['blockers']
        if method in {'E01','E05'}:
            pid={'E01':'A01','E05':'A02'}[method]
            native=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']==pid and r['track']=='native'),None)
            product=[r['track'] for r in execution_index['latest'] if r['paper_id']==pid and not r['track'].startswith('native') and r['latest_success']]
            audit.update(native_author_controller_real_run_passed=bool(native),native_verification=(native or {}).get('tests',{}),real_product_tracks_completed=product)
            native_status='author_controller_native_and_product_real_validated' if native and len(product)==2 else 'author_controller_partially_validated'
            audit['author_code_execution']=native_status
            blockers=['案件run(context)仍为项目原型；KIE/全图VQA为作者控制器'] if method=='E01' else []
            audit['blockers']=blockers
            audit['completed_debugging']=[s.replace('工程验证使用确定传输夹具，尚未新增真实调用','作者原样例与真实KIE/全图VQA已执行') for s in audit['completed_debugging']]
            audit['completed_debugging']+=['真实调用及失败记录：results/2026-10-29-per-paper/README.md；各论文100次持久上限共享原生/产品轨道']
        if method=='E04':
            acquisition=next((r['latest'] for r in execution_index['latest'] if r['paper_id']=='L05' and r['track']=='native_acquisition'),None)
            audit['native_verification']='SARA Stage II真实执行完成；精确数值未命中，论文10%容差命中；Stage I原抽取/整合/校验已运行至实际人工输入边界'
            audit['native_acquisition_verification']=(acquisition or {}).get('tests',{})
            audit['author_code_execution']='author_stage_ii_and_stage_i_pre_review_executed_pending_review_and_product'
            native_status=audit['author_code_execution']
            audit['blockers']=['Stage I已生成24类/71属性/21规则并通过原结构校验，等待原作者human_review输入；新解释器/训练反馈未执行','固定SARA税法规则不能直接用于中国截图任务，须建立相应规则域']
            audit['completed_debugging']=['独立Python3.13.14、49个锁定依赖；无本地权重','原Stage II真实2次；新增Stage I真实4次，累计6/100','原校验反馈date类型3问题，原整合修订后问题0；完整输入输出和待审TBox均保存','保留原human_review输入门槛，没有自动批准或将其写成产品适配完成']
            blockers=audit['blockers']
        if method=='E19':
            native=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']=='L09' and r['track']=='native'),None)
            product=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']=='L09' and r['track']=='case_product'),None)
            audit.update(native_author_controller_real_run_passed=bool(native),native_verification=(native or {}).get('tests',{}),
                         author_native_interface_connected_to_product=True,real_product_tracks_completed=['case_product'] if product else [],
                         product_verification=(product or {}).get('tests',{}),local_model_inference=False,
                         author_code_execution='author_native_and_case_product_real_validated' if native and product else 'author_components_product_pending_validation')
            native_status=audit['author_code_execution']
            blockers=[] if product else ['真实产品样本待验证']
            audit['blockers']=blockers
            audit['completed_debugging']=['作者StageProcessing(3/4)、ReasoningStage及段落函数体不变','Stage I/II原提示仅处理独立法源；中文研究提示及JSON投影差异完整保存','官方法源原文、快照及SHA256补齐；仍为unverified/unreviewed','实际AIPING产品6步完成；原生与产品共享100次账本']
            audit['adaptation_limitations']=['中国法规集合替代ECHR判例指南，不验证原论文先例覆盖收益','仅案例产品轨道；没有像素KIE接口或专家法律准确率']
        if method=='E22':
            native=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']=='A04' and r['track']=='native'),None)
            product=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']=='A04' and r['track']=='case_product'),None)
            qa=next((r['latest'] for r in execution_index['latest'] if r['paper_id']=='A04' and r['track']=='native_qa'),None)
            audit.update(author_native_interface_connected_to_product=True,native_author_controller_real_run_passed=bool(native),
                native_qa_verification=(qa or {}).get('tests',{}),native_verification=(native or {}).get('tests',{}),real_product_tracks_completed=['case_product'] if product else [],
                product_verification=(product or {}).get('tests',{}),local_model_inference=False,native_full_method_completed=False,
                author_code_execution='author_software_sop_and_case_product_validated_native_qa_executed_with_failures' if native and product else 'author_framework_validation_partial')
            native_status=audit['author_code_execution']
            blockers=['v0.3.0原QA续跑19次；2/7测试文件最后执行失败，main最终截断修订未重跑；原Engineer不支持自主开发代码修复；交互终端未验收']
            audit['blockers']=blockers
            audit['completed_debugging']=['独立Python3.11、166个作者源文件与25依赖锁定；无本地权重','真实软件原流程18次调用，Windows编码收集失败后0调用恢复','原游戏缺occupied方法；独立功能探针触发1次原WriteCodeReview，核心4检查通过；首次失败保留','中间阶段与最终Schema冲突修正；首次产品3次失败与后续4步成功均保存','两层Tenacity完全unwrap；失败只调用一次测试通过','原Team/Environment/Role/Memory/Action结构化解析执行；四角色案件SOP及机械引用反馈']
            audit['adaptation_limitations']=['软件任务Action替换为证据任务，非原软件benchmark条件','原QA已执行但仍有失败；从额外作者审查后的项目续跑，非fresh startup；最终测试版本未执行不得沿用旧通过']
        if method=='E09':
            native_rows=[r for r in execution_index['latest'] if r['paper_id']=='L10' and r['track']=='native' and r['latest_success']]
            products=[r for r in execution_index['latest'] if r['paper_id']=='L10' and r['track']!='native' and r['latest_success']]
            native_variants={r.get('variant') for r in native_rows}
            audit.update(author_code_execution='LMAD_author_code_unverified_cited_MALLM_components_executed',
                source_kind='paper_specification_with_cited_upstream_components',LMAD_author_code_executed=False,cited_upstream_code_executed=True,
                paper_algorithm_interface_connected_to_product=True,author_native_interface_connected_to_product=False,
                native_author_controller_real_run_passed=False,paper_algorithm_native_real_run_passed={'hybrid','ranked'}<=native_variants,
                native_paper_example_only=True,native_verification_by_protocol={r['variant']:r['latest_success']['tests'] for r in native_rows},
                real_product_tracks_completed=sorted({r['track'] for r in products}),
                real_product_protocols=sorted({r.get('variant') for r in products if r.get('variant')}),
                author_benchmark_tracks=[],paper_algorithm_benchmark_tracks=['vqa_predicted_text (binary only)'],local_model_inference=False)
            observed=json.loads((REPO/'paper/author_reproductions/l_mad/run_summary.json').read_text(encoding='utf-8'))
            audit['real_run_summary']={k:v for k,v in observed.items() if k!='runs'}
            audit['real_product_results']=[{k:r[k] for k in ('directory','track','protocol','status','requests','prediction','score','final_fact_count')} for r in observed['runs'] if r['track']!='native']
            native_status=audit['author_code_execution']
            blockers=[] if {'hybrid','ranked'}<=native_variants and products else ['两个原协议与产品轨道真实验证尚未齐备']
            audit['blockers']=blockers
            audit['completed_debugging']=['固定MALLM 11个原文件；AST载入原共识/排名/提示组件，无Torch/嵌入依赖','原混合默认值与L-MAD论文不同，显式配置论文阈值','正文Answer和附录判断分别解析；严格排名和单次平局补充，无自动付费格式重试','双向候选蕴含避免把未获支持自动当作相反标签；案件保留原文锚点和已核验fact集合','原任务与产品按协议分组留存，历史/失败/未知共用100次预算']
            audit['adaptation_limitations']=['未核实L-MAD作者源码；仅所引MALLM组件实际执行','原任务仅论文英文示例，不是年度COLIEE数据集；DeepSeek/固定persona替换明确披露','产品二分类文本VQA与事实支持性，不是像素KIE或法律准确率','A08仅设计引用，其原实验未复现','本轮两VQA均弃答0；案件最终facts为空，摘要仍有复述陈述的质量风险；仅执行与结构校验通过，非有效事实提取']
        if method=='E23':
            native_rows=[r for r in execution_index['latest'] if r['paper_id']=='B01' and r['track']=='native_replay' and r['latest_success']]
            products=[r for r in execution_index['latest'] if r['paper_id']=='B01' and not r['track'].startswith('native') and r['latest_success']]
            audit.update(author_code_execution='author_controller_controlled_replay_live_service_unavailable',author_native_interface_connected_to_product=True,
                source_kind='author_controller_with_explicit_tool_adaptation',native_author_controller_real_run_passed=False,
                controlled_native_replay_passed={r.get('variant') for r in native_rows}>={'react','plan_and_solve','plan_and_execute'},
                controlled_native_replay_by_variant={r['variant']:r['latest_success']['tests'] for r in native_rows},
                real_product_variants_by_track={t:sorted({r.get('variant') for r in products if r['track']==t}) for t in {r['track'] for r in products}},
                original_live_corpora_available=False,author_benchmark_tracks=['vqa_predicted_text'],
                real_product_tracks_completed=sorted({r['track'] for r in products}),local_model_inference=False)
            native_status=audit['author_code_execution']
            blockers=['作者在线法律工具服务拒绝连接；原首任务只回放原日志精确工具观察，不等于17库/37工具端到端复现']
            audit['blockers']=blockers
            audit['completed_debugging']=['锁定16原文件，独立Pydantic1.10环境；原三类/提示/解析函数经AST执行','原post_request参数不匹配由显式传输修复；只允许JSON动作进入解析，eval备用路径不可达','产品替换冻结KIE/案件文本工具；每步保留输出契约，PS/PE早期格式失败保留','最终事件封装错误通过严格匹配原七条响应零调用恢复；所有变体共享100次上限']
            audit['adaptation_limitations']=['原服务不可用，工具观察回放不等于在线原任务通过','三种VQA开发样本均弃答0；原关键词1.0只覆盖同一首任务且无中间关键词','不是像素KIE或专家法律准确率；完整300题benchmark未复现']
        if method=='E24':
            native=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']=='R04' and r['track']=='native' and r['latest_success']),None)
            products=[r for r in execution_index['latest'] if r['paper_id']=='R04' and not r['track'].startswith('native') and r['latest_success']]
            audit.update(author_code_execution='author_global_query_and_no_embedding_index_workflows',source_kind='author_global_api_index_and_query',
                author_native_interface_connected_to_product=True,native_author_controller_real_run_passed=bool(native),
                native_verification=(native or {}).get('tests',{}),real_product_tracks_completed=[r['track'] for r in products],
                author_benchmark_tracks=['vqa_predicted_text'],local_model_inference=False,native_scope='exact author Operation Dulce query and full precomputed index tables; native index not regenerated',native_full_method_completed=False)
            native_status=audit['author_code_execution']
            blockers=[] if {'case_product','vqa_predicted_text'}<={r['track'] for r in products} else ['冻结文本产品索引/查询/投影的真实模型验证尚未全部完成']
            audit['blockers']=blockers
            audit['completed_debugging']=['固定官方v0.1.1提交，399个源码/原示例文件逐Git blob校验','Windows使用Python3.11与作者锁依赖，无本地权重；未用向量后端注册隔离，原基类与工厂类保留','原Notebook层级过滤保留全部217实体/5选中报告，真实2次完成map/reduce','作者14个无嵌入索引工作流通过确定传输验证；不是编写简化图替代原算法','原LLM模板替换/历史跟踪保留；禁用传输重试与付费JSON重格式化，失败逐条保存','案件与冻结预测KIE文本单独索引，最终产品Schema投影另列']
            audit['adaptation_limitations']=['原查询使用作者预计算索引；没有重建该原索引或百万token benchmark','DeepSeek替代原GPT-4；产品实体类型含platform/message，分块1200/overlap100/one gleaning','禁用原嵌入/布局/可选claims；仅无向量global分支，不支持像素KIE或本地搜索','产品投影额外读取冻结锚点，不是未适配原benchmark结果','真实文本VQA弃答、旧开发参考分0；案件摘要三方陈述与两名说话人/三条陈述不一致，原回复保留','逐字引用校验不等于模型事实或法律质量，专家评测后补']
        if method=='E18':
            native=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']=='L07' and r['track']=='native' and r['latest_success'] and r['latest_success']['tests'].get('checks',{}).get('complete_inference_algorithm_execution')),None)
            product=[r['track'] for r in execution_index['latest'] if r['paper_id']=='L07' and not r['track'].startswith('native') and r['latest_success']]
            audit.update(author_code_execution='not_executed_no_verified_author_repository',source_kind='paper_algorithm_inference_reimplementation_training_deferred',
                paper_algorithm_interface_connected_to_product=True,author_native_interface_connected_to_product=False,
                native_author_controller_real_run_passed=False,paper_algorithm_native_real_run_passed=bool(native),
                native_verification=(native or {}).get('tests',{}),real_product_tracks_completed=product,
                author_benchmark_tracks=[],paper_algorithm_benchmark_tracks=['vqa_predicted_text'],local_model_inference=False,native_full_method_completed=False,training_reproduced=False)
            native_status=audit['author_code_execution']
            blockers=['作者源码未核实；DPO与本地训练检查点按用户指令暂缓；推理API分支不能替代整篇训练系统与原benchmark']
            audit['blockers']=blockers
            audit['completed_debugging']=['独立Python3.12.15、0额外依赖，无本地权重/训练/嵌入','按论文Algorithm 1实现T=5、双动作格式先于法条检索、Pass/空动作停止后仍执行ContentCheck','法条目录选ID后读取真实原文；拒绝未知ID与未检索/缩略法条冒充全文','原任务初次最后全文校验失败保留；逐请求精确缓存恢复，只新增ContentCheck调用','最终修订额外提供已检索法条附录，为显式项目适配；案件/VQA结构投影单独记录']
            audit['adaptation_limitations']=['论文推理重实现，不是作者代码或JurisCQAD DPO检查点','提示为本项目编写，DeepSeek替代原训练模型；法条目录后端不同','原任务仅论文附录C咨询示例，航空院校审查依据缺失；没有专家法律准确率','支持冻结KIE预测文本全局VQA，不支持像素KIE；整个L07保持部分完成']
        if method=='E14':
            native=next((r['latest_success'] for r in execution_index['latest'] if r['paper_id']=='A06' and r['track']=='native'),None)
            product=[r['track'] for r in execution_index['latest'] if r['paper_id']=='A06' and r['track']!='native' and r['latest_success']]
            audit.update(author_code_execution='not_executed_no_verified_author_repository',source_kind='paper_algorithm_reimplementation',
                paper_algorithm_interface_connected_to_product=True,author_native_interface_connected_to_product=False,
                native_author_controller_real_run_passed=False,paper_algorithm_native_real_run_passed=bool(native),
                native_verification=(native or {}).get('tests',{}),real_product_tracks_completed=product,
                native_qa_reference_result='first answer differs from reference; official QA F1=1/3; not an accuracy pass' if native else 'pending',
                author_benchmark_tracks=[],paper_algorithm_benchmark_tracks=['vqa_predicted_text'],local_model_inference=False)
            native_status=audit['author_code_execution']
            blockers=[] if native and product else ['论文算法的真实原任务与产品轨道验证尚未全部完成']
            audit['blockers']=blockers
            audit['completed_debugging']=['按Algorithm 1及Tables 9/10实现，不执行未经核实的同名仓库','完整token文本覆盖、Unicode无损分块、逐轮CU与last-CU-only manager通过工程验证','旧字符分块计划拒绝以新代码运行；模型输出cap与温度向网关实际传递','冻结KIE文本VQA与案例JSON引用契约单独适配，无本地权重']
            audit['adaptation_limitations']=['论文算法重实现，非作者源码执行','DeepSeek替换Vertex模型；cl100k代理不等于供应商分词器','产品增加JSON与引用契约；没有像素KIE抽取或专家法律准确率']
        if method in {'E07','E08'}:
            audit['native_component_verification']='SimuCourt首例庭辩组件真实执行完成；完整Legal-KB检索和判决未完成；产品入口仍为原型'
        verdict='复现判定：原论文 benchmark 未复现。run(context)与run_task现执行作者控制器的任务适配；原任务真实完整验证尚待新增调用。' if method=='E05' else '复现判定：原论文 benchmark 未复现。本文件 run(context) 是项目基线/机制原型，不能视作作者原实现。'
        if method in {'E01','E05','E15','E16','E19','E21','E22'}:verdict='复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。'
        if method=='E23':verdict='复现判定：作者三控制器实际执行；原任务为工具观察回放，原在线服务与完整benchmark未复现。产品文本工具为显式适配。'
        if method=='E09':verdict='复现判定：L-MAD论文协议调度＋所引MALLM原组件实际执行；非L-MAD作者源码/检查点，完整COLIEE benchmark未复现。'
        if method=='E24':verdict='复现判定：直接运行作者v0.1.1无嵌入索引/全局查询；原Notebook读取作者完整预计算索引，产品索引另执行；完整原benchmark未复现。'
        if method=='E18':verdict='复现判定：论文§3.2–3.4/Algorithm 1推理重实现与独立产品投影；非作者代码，DPO/本地检查点暂缓，整篇未完成。'
        if method=='E14':verdict='复现判定：论文Algorithm 1及Table 9/10的重实现，非作者源码执行；完整原论文benchmark未复现。'
        sections=[old_doc,'',marker,'',
                  verdict,
                  '已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。','']
        if not contracts:
            sections += ['原方法/benchmark：无对应单篇论文，属于本项目单次回答基线。','原输入/输出：不适用；本项目输入冻结来源，输出 CaseAnalysisOutput。']
        for c in contracts:
            sections += [f"[{c['paper_id']}] {c['method']}",
                '原有方法/任务：'+c['task'],
                '原输入大致形态（结构示意，不是 Gold）：'+c['input'],
                '原输出大致形态：'+c['output'],
                '原 benchmark：'+c['benchmark'],
                '论文创新点（作者方法的组成）：'+c['innovation'],
                '对本工作的可适配性：'+c['fit'],
                '核查依据：'+c['source']]
            pin=c.get('pinned_author_source')
            sections += ['作者代码：'+(pin['repository']+' @ '+pin['commit']+'；本地 '+pin['local_path'] if pin else '未固定对应作者入口；不得宣称已运行作者代码'),'']
        sections += ['本文件当前实际实现：'+current,
                     '本项目输入：'+audit['our_input_shape'],
                     '本项目输出：'+audit['our_output_shape'],
                     ('论文算法重实现已接入本文件run()：是；不是作者源码执行。' if audit.get('paper_algorithm_interface_connected_to_product') else '原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。' if audit['author_native_interface_connected_to_product'] else '原生接口已接入本文件run()：否；此处案件主链仍为项目基线/原型。'),
                     ('已接入run_task的输入轨道：'+'、'.join(audit.get('paper_algorithm_benchmark_tracks') or audit['author_benchmark_tracks'])+'；每步输入输出可追溯。' if audit.get('paper_algorithm_benchmark_tracks') or audit['author_benchmark_tracks'] else 'KIE/全局VQA原控制器接口：尚未接入'),
                     '评测边界：'+audit['deferred_evaluation'],
                     '如何适配/还需改什么：'+'；'.join(audit['required_adaptation']),
                     '已做的适配调试：'+'；'.join(audit['completed_debugging']),
                     '能否直接适配：'+compatible,
                     '尚未完成/阻塞：'+'；'.join(blockers or (['本轮原样例和产品轨道完成；完整原benchmark另行验证'] if method in {'E05','E09','E14','E15','E16','E19','E21','E24'} else ['原项目基线，无作者复现任务'])),
                     '当前作者原代码状态：'+native_status,
                     '复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。',
                     '']
        doc='"""\n'+'\n'.join(sections).replace('"""','\\" \\" \\"')+'\n"""\n'
        rest=''.join(original.splitlines(keepends=True)[doc_node.end_lineno:])
        # The audit fields are separate from executable control flow.
        position=rest.index('async def run(')
        additions='ORIGINAL_PAPER_CONTRACTS = '+repr(contracts)+'\nADAPTATION_AUDIT = '+repr(audit)+'\n\n'
        new=doc+rest[:position]+additions+rest[position:]
        file.write_text(new,encoding='utf-8')
        method_dir=REPO/'paper/method_reproductions'/name
        method_dir.mkdir(parents=True,exist_ok=True)
        (method_dir/'METHOD.md').write_text('# '+name+'\n\n'+'\n\n'.join(sections[2:]),encoding='utf-8')
        rows.append(dict(method_id=method,reproduction_name=name,source=meta['implementation_file'],original_contracts=contracts,adaptation=audit))
    target=REPO/'paper/author_reproductions/adaptation_review.json'
    target.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 原论文方法与本项目适配审查','','这里按当前全部实验配置披露原任务与适配；配置数不是论文复现完成数。原清单51个条目全部保留在PAPER_COVERAGE.md。','',
           'original_paper_reproduced 指完整原论文benchmark，当前均为false。真实原样例、产品轨道与工程测试分别见 results/2026-10-29-per-paper/README.md；每篇共享100次请求上限。专家法律金标按用户要求后补。','',
           '| 配置 | 逐项说明 | 原代码状态 | 原 benchmark |','|---|---|---|---|']
    for row in rows:
        benchmarks='；'.join(c['method']+': '+c['benchmark'] for c in row['original_contracts']) or '本项目基线'
        lines.append('| '+row['reproduction_name']+' | [METHOD.md](../method_reproductions/'+row['reproduction_name']+'/METHOD.md) | '+row['adaptation']['author_code_execution']+' | '+benchmarks+' |')
    lines+=['','## 作者评测器（独立于生成配置）','','[B02 LawBench](lawbench/README.md) · [B04 LegalBench](legalbench/README.md) · [B15 RAGChecker](ragchecker/README.md) · [评测器实现状态](EVALUATOR_IMPLEMENTATION_STATUS.json)','','评测器有独立原任务/产品适配，不因不能输出CaseAnalysisOutput而移出51条范围；不伪装为新的生成Agent配置。']
    (REPO/'paper/author_reproductions/ADAPTATION_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(method_files=len(rows),original_paper_benchmarks_reproduced=0),ensure_ascii=False))

if __name__=='__main__':annotate()
