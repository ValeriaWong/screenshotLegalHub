"""Validated, read-only method/paper catalog. A listed paper is never an installed adapter."""
from pathlib import Path
import yaml
from screenshotlegal.settings import ROOT
from screenshotlegal.research.contracts import digest
from screenshotlegal.method_reproductions.catalog import method_metadata

IMPLEMENTATION_VERSION='agent-experiment.v6'

IMPLEMENTED={
    'E25':('paper_legal_reasoning_paths_graph',['author_node_prompts','canonical_provisions','local_provision_norm','scoped_history_application_edges','ontology_graph','separate_product_projection']),
    'E24':('author_graphrag_global_v011',['author_token_chunks','author_entity_relation_graph','author_element_summaries','author_leiden_communities','author_community_reports','author_scored_map_reduce','product_projection']),
    'E23':('author_legalagentbench_v1',['author_controller_variant','frozen_evidence_tools','structured_final_answer']),
    'E00':('single_shot',['answer']),
    'E01':('controlled_tools',['tool_loop']),
    'E02':('staged_no_pack',['identify','map_evidence','synthesize']),
    'E03':('staged_with_pack',['identify','map_evidence','synthesize']),
    'E05':('author_self_refine',['author.init','author.feedback','author.revise','author.feedback']),
    'E06':('independent_context_verifier',['identify','map_evidence','synthesize','verify','revise']),
    'E07':('adversarial_review',['stages','independent_positions','exchange','reconcile']),
    'E08':('neutral_judge',['stages','independent_positions','exchange','reconcile','judge']),
    'E09':('paper_lmad_protocols_v1',['bounded_fact_proposal','binary_source_support','cited_MALLM_hybrid_or_ranked','verified_fact_revision']),
    'E10':('factor_guided_retrieval',['factor_query','search_read','stages']),
    'E11':('legal_r1_routing',['lawyer_loop','legal_assistant_tools','retrieval_judge']),
    'E12':('corrective_retrieval',['query','retrieve','quality_gate','corrective_retrieve','stages']),
    'E14':('paper_coa_algorithm1_v1',['token_window_chunks','sequential_cumulative_CU_workers','last_CU_only_manager']),
    'E15':('author_raptor',['author_cluster_summary_tree','author_cross_layer_retrieval','answer']),
    'E16':('author_lightrag',['author_entity_relation_extraction','author_hybrid_query','answer']),
    'E22':('author_metagpt',['extract_evidence','map_legal_elements','schema_literal_feedback','review_evidence','finalize_counsel']),
    'E21':('author_reflexion',['author_attempt','schema_or_literal_feedback','author_episodic_reflection']),
    'E18':('paper_jurisma_inference_algorithm1',['element_graph','initial_draft','manager_format_then_statute_routes_T5','content_check','separate_product_projection']),
    'E19':('author_scale',['independent_guide_hierarchy','author_issue_selection','author_factor_selection','author_paragraph_retrieval','author_iterative_analysis','output_projection']),
    'E20':('verdict_collegial_review',['court_clerk','judicial_assistant','case_judge','collegial_review','redraft','presiding_judge']),
}
PACK_METHODS=set(IMPLEMENTED)-{'E00','E01','E02','E14','E15','E16','E21','E23','E24','E25'}

def call_ceiling(method,budget,options,source_lengths):
    if method=='E00':return 1
    if method in {'E01','E09','E14','E15','E16','E19','E23','E24','E25'}:return budget['max_model_calls']
    if method=='E22':return 4
    if method=='E21':return 3*options['refinement_rounds']-1
    if method in {'E02','E03'}:return 3
    if method=='E05':return 2*options['refinement_rounds']
    if method=='E06':return 5
    if method=='E07':return 8
    if method=='E08':return 9
    if method=='E10':return 4
    if method=='E11':return options['retrieval_rounds']+1
    if method=='E12':return 5
    if method=='E18':return min(29,budget['max_model_calls'])
    if method=='E20':return 3+2*options['refinement_rounds']
    raise ValueError('方法尚未实现')

class CandidateRegistry:
    def __init__(self,directory=None):
        self.root=Path(directory or ROOT/'benchmark')
        raw=(self.root/'candidates.yaml').read_bytes()
        papers=(self.root/'paper_registry.yaml').read_bytes()
        self.config=yaml.safe_load(raw);self.paper_config=yaml.safe_load(papers)
        if not isinstance(self.config,dict) or self.config.get('schema_version')!='1.0': raise ValueError('候选配置版本不支持')
        self.papers=self.paper_config.get('papers',[])
        self.methods=self.config.get('candidates',[])
        pids=[p['paper_id'] for p in self.papers];ids=[m['id'] for m in self.methods]
        if len(pids)!=len(set(pids)) or len(ids)!=len(set(ids)): raise ValueError('候选或论文 ID 重复')
        if any(ref not in pids for m in self.methods for ref in m.get('references',[])): raise ValueError('方法引用不存在的论文')
        for p in self.papers:
            if not p.get('sources') or any(not isinstance(url,str) or not url.startswith('https://') for url in p['sources']):
                raise ValueError('论文来源必须为 HTTPS')
        self.digest=digest([raw.decode(),papers.decode()])
        code_root=Path(__file__).parent.parent
        code_files=sorted(list(Path(__file__).parent.glob('*.py'))+list((code_root/'method_reproductions').glob('*.py')))
        from screenshotlegal.method_reproductions.author_bridge import source_manifest
        self.code_digest=digest([[(str(p.relative_to(code_root)).replace(chr(92),'/'),p.read_text(encoding='utf-8')) for p in code_files],source_manifest()])
    def method(self,id):
        row=next((m for m in self.methods if m['id']==id),None)
        if row is None: raise KeyError('方法不存在')
        if id not in IMPLEMENTED: raise ValueError('方法仅已登记，尚未实现，不可创建运行')
        return dict(row,**method_metadata(id),implementation=IMPLEMENTED[id][0],steps=IMPLEMENTED[id][1],implementation_version=IMPLEMENTATION_VERSION,registry_digest=self.digest,implementation_digest=self.code_digest,requires_matterpack=id in PACK_METHODS,requires_factor_hierarchy=False,builds_hierarchy_from_frozen_law=id=='E19')
    def public(self):
        return dict(registry_version=self.config['registry_version'],digest=self.digest,
                    common_contract=self.config['common_contract'],tracks=self.config.get('benchmark_tracks',[]),
                    candidates=[dict(m,**method_metadata(m['id']),
                                     implementation_version=IMPLEMENTATION_VERSION if m['id'] in IMPLEMENTED else None,
                                     requires_matterpack=m['id'] in PACK_METHODS,requires_factor_hierarchy=False,builds_hierarchy_from_frozen_law=m['id']=='E19',
                                     steps=IMPLEMENTED[m['id']][1] if m['id'] in IMPLEMENTED else [],
                                     paper_claim=('本项目基线，非单篇论文复现' if m['id'] in {'E00','E02','E03'} else '作者控制器任务适配；原论文benchmark尚未复现' if m['id'] in {'E05','E15','E16','E19','E21','E22','E24'} else '作者控制器＋冻结文本工具；原在线语料未复现，原论文benchmark尚未复现' if m['id']=='E23' else '论文协议＋所引MALLM原组件；非L-MAD作者源码，原论文benchmark尚未复现' if m['id']=='E09' else '论文推理Algorithm 1重实现；DPO/本地检查点暂缓，原论文benchmark尚未复现' if m['id']=='E18' else '作者原提示/本体的图构建重实现；嵌入检索未完成，非作者Python代码' if m['id']=='E25' else '论文Algorithm 1重实现（非作者代码），原论文benchmark尚未复现' if m['id']=='E14' else '案件机制原型；KIE/VQA已接作者控制器；原论文benchmark尚未复现' if m['id']=='E01' else '项目机制原型；原论文benchmark尚未复现')) for m in self.methods],
                    papers=[dict(p,verification_provided=p.get('verification'),runtime_verification='not_reproduced') for p in self.papers],
                    warnings=['论文条目和作者效果不构成本系统复现成绩。',
                              '独立 verifier 指上下文隔离，仍使用同一底座模型，不宣称错误独立。',
                              '案件级研究试跑没有专家 CaseGold，法律质量指标保持未评分。'])
