"""Generate the three independent author-backed product modules from recorded evidence."""
import ast,json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'product_v1/backend/src/screenshotlegal/method_reproductions'
papers=yaml.safe_load((ROOT/'paper_registry_v1.yaml').read_text(encoding='utf-8'))['papers']
contracts=json.loads(Path(__file__).with_name('paper_contracts.json').read_text(encoding='utf-8'))
index=json.loads((Path(__file__).parent/'results/2026-10-29-per-paper/validation_index.json').read_text(encoding='utf-8'))
for mid,name,pid,mechanism in [
 ('E15','raptor','R03','作者UMAP/GMM软聚类、摘要树与跨层检索'),
 ('E16','lightrag','R05','作者实体关系抽取与合并、图存储和双层检索'),
 ('E21','reflexion','A03','作者CoTAgent反思、跨尝试记忆与重试控制器')]:
    module=mid.lower()+'_'+name
    native=next((r['latest_success'] for r in index['latest'] if r['paper_id']==pid and r['track']=='native'),None)
    product=[r['track'] for r in index['latest'] if r['paper_id']==pid and r['track']!='native' and r['latest_success']]
    checks=(native or {}).get('tests',{}).get('checks',{})
    scope=mechanism+'；原任务真实执行'+('完成' if native else '未完成')+'；产品真实执行轨道：'+('、'.join(product) or '尚未完成')+'；原论文完整benchmark未复现'
    doc=ast.get_docstring(ast.parse((Path(__file__).parent/name/'product_adapter.py').read_text(encoding='utf-8')))
    contract=dict(paper_id=pid,**{k:v for k,v in contracts[pid].items() if k!='paper_id'})
    audit=dict(original_paper_reproduced=False,author_code_execution='author_algorithm_product_adapter',adaptability=contract['fit'],current_project_implementation=scope,
      required_adaptation=['保留冻结来源映射；派生摘要/图描述不能当独立证据','记录原参数、有效参数及逐次输入输出；模型/嵌入替换与原基准分开'],
      our_input_shape='FrozenCaseInput sources' if mid!='E21' else 'FrozenCaseInput sources，或原图及KIE/VQA question',
      our_output_shape='CaseAnalysisOutput 或 VQA JSON' if mid!='E21' else 'CaseAnalysisOutput 或 KIE/VQA JSON',
      author_native_interface_connected_to_product=True,
      author_benchmark_tracks=['kie_image','vqa_image_full','vqa_predicted_text'] if mid=='E21' else ['vqa_predicted_text'],
      native_author_controller_real_run_passed=bool(native),native_task_answer_validated=checks.get('answer_exact_match',False),
      native_verification=checks,real_product_tracks_completed=product,
      completed_debugging=['锁定作者源码/独立环境，实际执行原类和函数','真实输入、模型回复、工具产物和输出见 results/2026-10-29-per-paper/README.md'],
      deferred_evaluation='专家法律金标后补，不作为环境/适配阻塞；完整原benchmark另行验证',
      blockers=[] if native and product else ['原任务或产品真实轨道尚未完成'])
    text='"""论文出处：'+doc+'\n\n复现程度及当前证据：'+scope+'\n"""\n\n'
    values=dict(METHOD_ID=mid,METHOD_NAME=module,IMPLEMENTATION_STATUS='implemented',REPRODUCTION_LEVEL='author_algorithm_adaptation',REPRODUCTION_SCOPE=scope,
      PAPER_REFERENCES=[next(p for p in papers if p['paper_id']==pid)],ORIGINAL_PAPER_CONTRACTS=[contract],ADAPTATION_AUDIT=audit)
    text+='\n'.join(k+' = '+repr(v) for k,v in values.items())+'\n\n'
    text+=f"async def run_task(messages,call,attempts=2,tool_trace=None):\n    from .paper_bridge import benchmark_task\n    return await benchmark_task({name!r},messages,call,attempts,tool_trace)\n\nasync def run(context):\n    from .paper_bridge import case_task\n    return await case_task({name!r},context)\n"
    (BASE/(module+'.py')).write_text(text,encoding='utf-8')
print(json.dumps(dict(updated=['E15','E16','E21'],complete_paper_benchmarks=0)))
