"""Import-only probe of pinned author branches, zero model calls."""
import importlib,json,sys,traceback
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[2]
from loader import load
load()
modules=['graphrag.query.structured_search.global_search.search','graphrag.query.structured_search.global_search.community_context','graphrag.query.indexer_adapters','graphrag.index.graph.extractors.graph.graph_extractor','graphrag.index.graph.extractors.summarize.description_summary_extractor','graphrag.index.verbs.graph.clustering.strategies.leiden','graphrag.index.graph.extractors.community_reports.community_reports_extractor','graphrag.index.run','graphrag.index.create_pipeline_config']
rows=[]
for name in modules:
    try:importlib.import_module(name);rows.append(dict(module=name,status='imported'))
    except Exception as error:rows.append(dict(module=name,status='failed',error_type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
result=dict(python=sys.version.split()[0],modules=rows,neural_modules_loaded=[n for n in ['torch','transformers','sentence_transformers','spacy','onnxruntime'] if n in sys.modules],model_requests=0)
(HERE/'import_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(python=result['python'],modules=[{k:v for k,v in r.items() if k!='traceback'} for r in rows],neural_modules_loaded=result['neural_modules_loaded'])))
