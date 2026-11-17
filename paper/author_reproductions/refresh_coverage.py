"""Build full 51-entry coverage and per-configuration status from persisted evidence."""
import json,sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;sys.path.insert(0,str(ROOT/'product_v1/backend/src'))
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES,method_metadata
from screenshotlegal.experiments.registry import CandidateRegistry

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    registry=CandidateRegistry();profiles=json.loads((HERE/'paper_contracts.json').read_text(encoding='utf-8'))
    pinned={s['name']:s for s in json.loads((HERE/'sources.lock.json').read_text(encoding='utf-8'))}
    index=json.loads((HERE/'results/2026-10-29-per-paper/validation_index.json').read_text(encoding='utf-8'))
    pages={p['paper_id']:p['pages'] for p in json.loads((HERE/'primary_sources/2026-10-29/index.json').read_text(encoding='utf-8'))}
    source_map={'L02':'lawluo','L01':'agentscourt','L03':'lawflow','L05':'solar','L08':'verdict','L09':'scale','L11':'legal_r1','L14':'legal_dc','A01':'react','A02':'self_refine','A03':'reflexion','A04':'metagpt','R04':'graphrag','R02':'crag','R03':'raptor','R05':'lightrag','D02':'paddleocr_vl','B02':'lawbench','B01':'legalagentbench','B15':'ragchecker','B04':'legalbench'}
    native={r['paper_id']:r['latest_success'] for r in index['latest'] if r['track']=='native' and r['latest_success']}
    product={p:sorted({r['track'] for r in index['latest'] if r['paper_id']==p and not r['track'].startswith('native') and r['latest_success']}) for p in {r['paper_id'] for r in index['latest']}}
    component={'L01':'庭辩组件完成；Legal-KB检索和判决未完成','L05':'Stage II原数值精确未命中/10%容差命中；Stage I抽取/整合/校验已运行，24类/71属性/21规则待原人工审核；新解释器/训练反馈与中国规则域未完成，累计6/100','L09':'原完整案例双条文分析完成；中国指南与Issue–Factor映射尚未接入'}
    deferred_local={'L11':'作者RL.sh本地vLLM/GPU与训练actor rollout；通用DeepSeek原型不等于原训练策略','L02':'SFT角色/奖励模型/PPO及嵌入；公开ToLC示例为含语法错误及未实现函数的伪代码','D02':'本地0.9B权重及布局推理','L08':'当前原实现的本地嵌入方案','R02':'原T5 evaluator权重推理','L03':'本地工作流监控模型训练；保留API分支待核实','A07':'所引InsTag完整嵌入/聚类分支，远程替代未配置'}
    known_api={'A01','A02','A03','A04','A06','L07','L01','L05','L09','L10','B01','B02','B15','B04','R04'}
    entries=[]
    for paper in registry.papers:
        pid=paper['paper_id'];source=pinned.get(source_map.get(pid));env=HERE/(source_map.get(pid) or pid.lower())/'environment_state.json'
        if pid=='L02':
            identity=json.loads((HERE/'lawluo/source_identity.json').read_text(encoding='utf-8'))
            source=dict(name='lawluo',kind=identity['source_kind'],repository=identity['repository'],commit=identity['commit'],local_path='paper/upstream_sources/lawluo',files={'tolc_demo.py':identity['sha256']},original_path=identity['original_path'],native_runnable=False)
        if pid=='D02':
            model=json.loads((HERE/'paddleocr_vl/model.lock.json').read_text(encoding='utf-8'))
            source=dict(name='paddleocr_vl',kind='official_model_repository',repository='https://huggingface.co/'+model['model'],commit=model['revision'],local_path='paper/.models/paddleocr_vl',files={k:v['sha256'] for k,v in model['files'].items()})
        spec_folder={'A06':'chain_of_agents','L10':'l_mad','L07':'jurisma'}.get(pid)
        specification=json.loads((HERE/spec_folder/'specification.lock.json').read_text(encoding='utf-8')) if spec_folder else None
        if spec_folder:env=HERE/spec_folder/'environment_state.json'
        native_row=native.get(pid);tracks=product.get(pid,[]);development_verified=True
        if pid=='B15':
            rows_b15=[r['latest_success'] for r in index['latest'] if r['paper_id']=='B15' and not r['track'].startswith('native') and r['latest_success']]
            tracks=[r['track'] for r in rows_b15 if r['tests']['checks'].get('full_product_track_completed')]
            nc=(native_row or {}).get('tests',{}).get('checks',{})
            vc=next((r['tests']['checks'] for r in rows_b15 if r['track']=='product_scoring_vqa_predicted_text'),{})
            ac=vc.get('original_author_checks') or {}
            development_verified=bool(nc.get('cases')==2 and nc.get('original_metric_formulas_executed') and nc.get('joint_labels_all_matched') and nc.get('all_eleven_metrics_present') and vc.get('full_product_track_completed') and vc.get('primary_score_unchanged') and ac.get('all_responses_have_claims') and ac.get('joint_labels_all_matched'))
        if pid=='B04':
            product_rows=[r['latest_success'] for r in index['latest'] if r['paper_id']=='B04' and not r['track'].startswith('native') and r['latest_success']]
            tracks=[r['track'] for r in product_rows if r['tests']['checks'].get('full_product_track_completed')]
            nc=(native_row or {}).get('tests',{}).get('checks',{})
            vc=next((r['tests']['checks'] for r in product_rows if r['track']=='product_scoring_vqa_image_full'),{})
            development_verified=bool(nc.get('groups')==12 and nc.get('distinct_tasks')==11 and nc.get('scored_groups')==11 and nc.get('manual_groups')==1 and nc.get('all_162_templates_present') and nc.get('all_162_evaluations_declared') and nc.get('all_effective_replies_complete') and nc.get('no_neural_model_modules') and vc.get('full_product_track_completed') and vc.get('primary_score_not_overwritten') and vc.get('original_attempt_unchanged'))
        if pid=='R04':
            product_rows=[r['latest_success'] for r in index['latest'] if r['paper_id']=='R04' and not r['track'].startswith('native') and r['latest_success']]
            by_track={r['track']:r['tests'].get('checks',{}) for r in product_rows}
            nc=(native_row or {}).get('tests',{}).get('checks',{})
            required={'create_base_text_units','create_base_extracted_entities','create_summarized_entities','create_base_entity_graph','create_final_nodes','create_final_entities','create_final_relationships','create_final_community_reports'}
            development_verified=bool(nc.get('native_original_global_query_executed') and nc.get('selected_entities')==217 and nc.get('selected_reports')==5 and nc.get('positive_map_points',0)>0 and {'case_product','vqa_predicted_text'}<=set(by_track) and all(required<=set(c.get('indexing_workflows',[])) for c in by_track.values()) and by_track['case_product'].get('literal_citations_valid') and by_track['case_product'].get('case_product_schema_valid') and by_track['vqa_predicted_text'].get('product_text_VQA_controller_completed'))
        status=('原任务真实执行＋产品轨道完成（单样本）' if native_row and tracks else component.get(pid,'原任务真实执行完成，适配未完成') if native_row else '作者源码已固定，后续步骤待完成' if source else '未完成作者方法/环境复现')
        if pid=='L09' and 'case_product' in tracks:status='原ECHR样例＋案例产品轨道完成；中国法规替代判例指南的任务适配（非像素KIE）'
        if pid=='D02':status='原0.9B权重核心识别完成（达到输出上限）；完整布局流水线和产品适配未完成'
        if pid=='A04':status='原软件SOP/案例产品已执行；原QA续跑19次，7个测试文件最后2个失败且最终main修订未执行；累计45/100，保持部分完成' if tracks else '作者软件SOP执行完成；自主QA和产品验证未全部完成'
        if pid=='L10':status='论文协议＋所引MALLM原组件：两原示例协议和产品轨道已执行；非L-MAD作者代码/原COLIEE年度benchmark' if native_row and tracks else '原协议组件和独立无权重环境已建立，真实验证进行中'
        if pid=='A06':status='论文Algorithm 1重实现；官方QA原任务完整执行但答案未命中；冻结KIE文本VQA和案件产品执行完成；非作者源码执行' if native_row and tracks else '论文算法重实现与独立环境已建立，原任务/产品验证进行中'
        if pid=='L01':status='作者庭辩组件已真实执行；完整Legal-KB重排需本地BGE权重，按用户要求暂缓；原完整检索/裁判与产品未完成'
        if pid=='R04':status='官方v0.1.1原全局查询2次；产品冻结KIE文本/案件各14个原索引工作流与map/reduce执行完成，累计15/100；VQA弃答0；原查询索引为作者预计算，完整原benchmark未复现' if development_verified else '固定官方源码与无权重环境；原查询/产品原索引分支验证尚未齐备'
        if pid=='L02':status='作者ToLC示例精确固定/AST检查失败；含未定义返回占位，原任务未运行，0次新增模型调用；完整训练/本地模型分支暂缓'
        if pid=='L07':status='论文§3.2–3.4/Algorithm 1推理重实现，非作者代码；原任务/产品API分支状态见逐步记录，DPO与本地训练检查点暂缓，整篇未完成'
        if pid=='A07':status='资源暂缓：原文与提示已固定；所引InsTag完整归一化的嵌入/聚类分支未运行，不能用简化图冒充原方法'
        if pid=='B01':status='作者三控制器原任务工具回放＋三协议冻结KIE文本VQA已执行（均弃答0）；E23网页/API与案件映射已接入；在线原工具服务拒绝连接，保持部分完成'
        if pid=='B02':status='官方19/20类任务×zero/one-shot首样本共38次真实调用；产品分类原评分器已接入，KIE缺参考未评分；2-1本地LTP暂缓' if native_row else '官方数据/评分源码与无权重独立环境已固定，原任务验证进行中'
        if pid=='B15':status='作者默认API分支两完整原例/原11指标已验证；单条格式适配差异和45原回复复用均保存；文本全局VQA证据faithfulness产品开发轨道完成，KIE缺转录未评分；累计'+str(index['budgets']['used'].get('B15',0))+'/100' if development_verified else '作者API评测器原任务/产品适配验证进行中，尚未满足全部开发检查'
        if pid=='B04':status='作者原提示/评分代码已执行；11任务/12组29个原测试样本，截断3条已单独恢复；原Rule QA人工未评分；真实全局VQA原平衡精确匹配补充评分已接HTTP/CLI/导出；KIE缺参考未评分；累计'+str(index['budgets']['used'].get('B04',0))+'/100' if development_verified else '作者原任务与产品原评分器验证中，尚未满足全部开发检查'
        scheduling=dict(state='temporarily_deferred_local_resources' if pid in deferred_local else 'api_or_lightweight_branch' if pid in known_api else 'historical_results_preserved_no_new_local_runs' if pid in ['R03','R05'] else 'dependency_review_pending',reason=deferred_local.get(pid),authority='用户：先略过需要本地计算资源的复现，特别是依赖模型权重本地推理的',completion_claim=False)
        if pid=='L01':scheduling.update(deferred_branches=['BGE-large-zh-v1.5 local reranker'],active_branch='existing API court-dialogue component retained')
        if pid=='L07':scheduling.update(deferred_branches=['DPO training','local fine-tuned checkpoints'],active_branch='remote API inference algorithm only')
        if pid in deferred_local:status+='；当前本地资源分支按用户要求暂缓'
        rows=[m['id'] for m in registry.methods if pid in m.get('references',[])]
        entries.append(dict(**paper,scheduling=scheduling,selected_configurations=rows,implemented_evaluators=(['b15_ragchecker'] if pid=='B15' else ['b02_lawbench'] if pid=='B02' else ['b04_legalbench'] if pid=='B04' else []),original_contract_reviewed=pid in profiles,
          primary_pages=pages.get(pid,[]),author_source_pinned=bool(source),source=source,paper_algorithm_specification=specification,reproduction_source_kind=specification['source_kind'] if specification else source.get('kind','author_source') if source else 'not_implemented',environment=env.relative_to(ROOT).as_posix() if env.exists() else None,
          native_validation=native_row,native_auxiliary_validations=[r['latest'] for r in index['latest'] if r['paper_id']==pid and r['track'].startswith('native') and r['track'] not in ['native','native_replay']],controlled_native_replay=[r['latest_success'] for r in index['latest'] if r['paper_id']==pid and r['track']=='native_replay' and r['latest_success']],real_product_tracks_completed=tracks,status=status,
          original_paper_benchmark_reproduced=False,three_stage_development_completed=bool(native_row and tracks and pid not in ['A04','B02','L07'] and development_verified)))
    configurations=[]
    for method,name in METHOD_MODULES.items():
        meta=method_metadata(method);audit=meta.get('adaptation_assessment') or {}
        configurations.append(dict(method_id=method,name=name,case_author_controller_connected=audit.get('author_native_interface_connected_to_product',False),
          kie_global_vqa_author_tracks=audit.get('author_benchmark_tracks',[]),native_real_verification=audit.get('native_verification','not_completed'),
          real_product_tracks_completed=audit.get('real_product_tracks_completed',[]),blockers=audit.get('blockers',[]),original_complete_benchmark=False,
          expert_legal_evaluation='deferred_by_user; not_an_environment_or_adapter_gate'))
    save(HERE/'IMPLEMENTATION_STATUS.json',configurations)
    evaluator_implementations=[dict(paper_id=pid,name=name,module='screenshotlegal.research.'+module,native_validation_plan_id=(next(e['native_validation'] for e in entries if e['paper_id']==pid) or {}).get('plan_id'),product_tracks=next(e['real_product_tracks_completed'] for e in entries if e['paper_id']==pid),development_completed=next(e['three_stage_development_completed'] for e in entries if e['paper_id']==pid),original_complete_benchmark=False) for pid,name,module in [('B02','b02_lawbench','lawbench_scoring'),('B15','b15_ragchecker','ragchecker_scoring'),('B04','b04_legalbench','legalbench_scoring')]]
    save(HERE/'EVALUATOR_IMPLEMENTATION_STATUS.json',evaluator_implementations)
    coverage=dict(paper_entries=len(entries),experiment_configurations=len(configurations),evaluator_implementations=evaluator_implementations,referenced_distinct_entries=len({p for m in registry.methods for p in m['references']}),
      three_stage_development_completed_papers=[p['paper_id'] for p in entries if p['three_stage_development_completed']],
      author_code_development_completed_papers=[p['paper_id'] for p in entries if p['three_stage_development_completed'] and p['reproduction_source_kind']=='author_source'],
      paper_algorithm_development_completed_papers=[p['paper_id'] for p in entries if p['three_stage_development_completed'] and p['reproduction_source_kind']=='paper_algorithm_reimplementation'],
      cited_component_development_completed_papers=[p['paper_id'] for p in entries if p['three_stage_development_completed'] and p['reproduction_source_kind']=='paper_specification_with_cited_upstream_components'],
      original_paper_benchmarks_reproduced=0,entries=entries)
    save(HERE/'paper_coverage.json',coverage)
    lines=['# 全部51条目覆盖台账','',f"登记 {len(entries)} 条文献；现有 {len(configurations)} 个配置引用 {coverage['referenced_distinct_entries']} 个不同条目；另有{len(evaluator_implementations)}个作者评测器接入。配置/接口数不是复现完成数。",'',
      '当前先略过本地模型权重推理/训练与重计算分支；范围仍保留全部51条目，详见RESOURCE_PRIORITY_2026-10-30.md。',
      '保留所有未完成条目。主页面已下载表示来源可访问，不表示已阅读/实现方法。基准论文也保留待适配状态，不因不是生成方法而自行移出用户范围。',
      '本轮三阶段完成只指独立环境、原任务真实执行、指定产品轨道的开发样本完成；完整原论文benchmark和专家准确率另列。','',
      '|ID|文献|配置|当前实际状态|方法/原任务资料|','|---|---|---|---|---|']
    for p in entries:
        title=p['reference'].replace('|','/');repo=p.get('source');links=[]
        if repo:links.append('[作者源码]('+repo['repository']+'/tree/'+repo['commit']+')')
        if p['paper_id']=='R04':links.append('[作者索引/查询/实际输入输出](graphrag/README.md)')
        if p['paper_id']=='L02':links.append('[原源码/AST失败/资源暂缓](lawluo/README.md)')
        if p['paper_id']=='L07':links.append('[论文推理/差异/真实I/O](jurisma/README.md)')
        if p['paper_id']=='L10':links.append('[论文协议/原组件/输入输出](l_mad/README.md)')
        if p['paper_id']=='A06':links.append('[论文算法/输入输出](chain_of_agents/README.md)')
        if p['paper_id']=='B01':links.append('[作者控制器/回放/产品I/O](legalagentbench/README.md)')
        if p['paper_id']=='A07':links.append('[归一化依赖/暂缓依据](graphreader/README.md)')
        if p['paper_id']=='B04':links.append('[原提示/原评分/任务/产品I/O](legalbench/README.md)')
        if p['paper_id']=='B15':links.append('[作者方法/原任务/产品I/O](ragchecker/README.md)')
        if p['paper_id']=='B02':links.append('[复现/输入输出](lawbench/README.md)')
        for mid in p['selected_configurations']:links.append('[ '+mid+' ](../method_reproductions/'+METHOD_MODULES[mid]+'/METHOD.md)')
        lines.append('|'+ '|'.join([p['paper_id'],title,','.join(p['selected_configurations']) or ','.join(p['implemented_evaluators']) or '尚未建配置',p['status'],' / '.join(links) or '待实施'])+'|')
    lines+=['','[逐次真实输入/输出/回复/测试](results/2026-10-29-per-paper/README.md) · [逐配置审查](ADAPTATION_REVIEW.md)','']
    (HERE/'PAPER_COVERAGE.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:v for k,v in coverage.items() if k not in ['entries','evaluator_implementations']},ensure_ascii=False))
if __name__=='__main__':main()
