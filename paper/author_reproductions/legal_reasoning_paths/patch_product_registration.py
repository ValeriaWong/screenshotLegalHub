from pathlib import Path
ROOT=Path.cwd();base=ROOT/'product_v1/backend/src/screenshotlegal'
def update(file,changes):
 p=ROOT/file;s=p.read_text(encoding='utf-8')
 for old,new in changes:
  if old not in s:raise ValueError(str(p)+': expected patch not found: '+old[:80])
  s=s.replace(old,new)
 p.write_text(s,encoding='utf-8')
update('product_v1/backend/src/screenshotlegal/method_reproductions/catalog.py',[("'E24': 'r04_graphrag'}","'E24': 'r04_graphrag', 'E25': 'l06_legal_reasoning_paths'}")])
update('product_v1/backend/src/screenshotlegal/experiments/registry.py',[
 ("IMPLEMENTED={","IMPLEMENTED={\n    'E25':('paper_legal_reasoning_paths_graph',['author_node_prompts','canonical_provisions','local_provision_norm','scoped_history_application_edges','ontology_graph','separate_product_projection']),"),
 ("'E21','E23','E24'}","'E21','E23','E24','E25'}"),
 ("'E19','E23','E24'}","'E19','E23','E24','E25'}"),
 ("else '论文Algorithm 1重实现（非作者代码），原论文benchmark尚未复现'","else '作者原提示/本体的图构建重实现；嵌入检索未完成，非作者Python代码' if m['id']=='E25' else '论文Algorithm 1重实现（非作者代码），原论文benchmark尚未复现'")])
update('product_v1/backend/src/screenshotlegal/research/benchmark_methods.py',[
 ("names={'E24':","names={'E25':'l06_legal_reasoning_paths','E24':"),
 ("calls={'E24':","calls={'E25':20,'E24':"),
 ("'E18','E23','E24']","'E18','E23','E24','E25']"),
 ("if method=='E18':result.update(","if method=='E25':result.update(source_kind='paper_pipeline_reimplementation_with_author_prompts_ontology',author_code_executed=False,embedding_retrieval_executed=False,native_full_method_completed=False)\n    if method=='E18':result.update("),
 ("environment({'E24':","environment({'E25':'legal_reasoning_paths','E24':"),
 ("controllers={'E24':","controllers={'E25':'L06 exact author prompts + scoped-history typed RDF pipeline reimplementation; embedding retrieval pending','E24':"),
 ("if method['id']=='E24':","if method['id'] in ['E24','E25']:"),
 ("from screenshotlegal.method_reproductions.graphrag_bridge import demo_reply","from importlib import import_module\n                    demo_reply=import_module('screenshotlegal.method_reproductions.'+('graphrag_bridge' if method['id']=='E24' else 'legal_reasoning_paths_bridge')).demo_reply")])
update('product_v1/backend/src/screenshotlegal/research/benchmark.py',[("tracks={'E24':","tracks={'E25':['vqa_predicted_text'],'E24':")])
update('product_v1/backend/src/screenshotlegal/api/benchmark.py',[("'E21','E23','E24']","'E21','E23','E24','E25']")])
update('product_v1/backend/src/screenshotlegal/experiments/engine.py',[
 ("'E18','E23','E24'}","'E18','E23','E24','E25'}"),
 ("if raw and method=='E24':","if raw and method in {'E24','E25'}:"),
 ("if method=='E24':","if method in {'E24','E25'}:"),
 ("from screenshotlegal.method_reproductions.graphrag_bridge import demo_reply","from importlib import import_module\n                demo_reply=import_module('screenshotlegal.method_reproductions.'+('graphrag_bridge' if method=='E24' else 'legal_reasoning_paths_bridge')).demo_reply")])
update('product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py',[
 ("    names += ['paper/author_reproductions/graphrag/'","    names += ['paper/author_reproductions/legal_reasoning_paths/'+n for n in ['algorithm.py','native_input.json','product_adapter.py','requirements.lock.txt']]\n    names += ['product_v1/backend/src/screenshotlegal/method_reproductions/legal_reasoning_paths_bridge.py']\n    names += ['paper/author_reproductions/graphrag/'")])
addition="""
  - id: E25
    title: Legal Reasoning Paths paper graph-construction branch
    priority: P1
    family: scoped_legal_reasoning_graph
    reproduction: paper_pipeline_reimplementation_with_author_prompts_ontology
    references: [L06]
    changes: [author_prompts_and_ontology, canonical_provisions, scoped_history_edges, typed_rdf_graph, embedding_retrieval_pending, separate_product_projection]

"""
for file in ['method_candidates_v1.yaml','product_v1/benchmark/candidates.yaml']:update(file,[('benchmark_tracks:',addition+'benchmark_tracks:')])
update('product_v1/frontend/src/features/research/BenchmarkPanel.tsx',[
 ('"E18", "E23", "E24"]','"E18", "E23", "E24", "E25"]'),
 ('(method === "E24" ? 40','(method === "E25" ? 20 : method === "E24" ? 40'),
 ('<option value="E24">','<option value="E25">Legal Reasoning Paths：原提示图构建，检索待完成</option><option value="E24">'),
 ('result.data.run.method?.id === "E24" ?','result.data.run.method?.id === "E25" ? "Legal Reasoning Paths 原提示图构建（嵌入检索未完成）" : result.data.run.method?.id === "E24" ?')])
print('Product E25 source/registry/frontend patches applied')
