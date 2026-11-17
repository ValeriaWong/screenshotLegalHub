"""R04 GraphRAG — Edge et al. (2024), arXiv:2404.16130v1, §§2.1–2.6.
Paper: https://arxiv.org/html/2404.16130v1
Author code: microsoft/graphrag v0.1.1 @ a81efe58c7c21ff8b17aa9bf1cb78a0750f3065b.
Degree: executes pinned author indexing/global-query classes and workflows.
No original million-token benchmark or original GPT-4 quality claim is made.
Original method: token chunks -> LLM entity/relation extraction -> merged element
summaries -> hierarchical Leiden communities -> bottom-up community reports ->
scored map answers -> filtered/ranked reduce answer. This is not direct full-text
prompting with a graph-shaped JSON wrapper. Optional covariates are disabled.
Innovation: query-independent hierarchical community reports support global
sensemaking across a corpus, instead of only nearest-vector retrieval.
Original benchmark: Behind the Tech podcast transcripts and MultiHop-RAG news;
global sensemaking queries, LLM pairwise comprehensiveness/diversity/empowerment
and directness. Our native task is the COMPLETE author Operation Dulce notebook
query at community level 2, using all three original precomputed index tables;
that native run does NOT regenerate the author's index or paper benchmark.
Original input: text corpus at indexing; global question + community hierarchy,
reports/entity metadata at query. Output: narrative answer with report references.
Adaptation: independently frozen KIE text/case statements -> original no-vector
index workflows -> original global search -> separate product JSON projection.
DeepSeek replaces GPT-4; product entities include platform/message concepts;
product chunk 1200/overlap100, one gleaning, serialized API transport. Literal
source spans are rechecked by the product, not inferred from graph citations.
No screenshot pixels, local neural weights, model training or embeddings run.
Windows unused LanceDB/Azure Search eager registration is bypassed in loader.py;
base types and all selected algorithms stay unchanged. Index transport retries
and paid JSON-repair retries are disabled and failures are preserved. Raw phase
inputs/outputs and full original workflow tables are saved per r04_graphrag run.
"""
import asyncio,dataclasses,importlib,json,sys
from pathlib import Path
from types import SimpleNamespace
from loader import load
HERE=Path(__file__).parent


def serial(value):
    import pandas as pd
    if isinstance(value,pd.DataFrame):return json.loads(value.to_json(orient='records',date_format='iso',force_ascii=False))
    if dataclasses.is_dataclass(value):return {field.name:serial(getattr(value,field.name)) for field in dataclasses.fields(value)}
    if isinstance(value,dict):return {str(k):serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial(v) for v in value]
    if hasattr(value,'item'):return value.item()
    return value


def native_tables(folder):
    import pandas as pd
    from graphrag.query.indexer_adapters import read_indexer_entities,read_indexer_reports
    directory=folder/'examples_notebooks/inputs/operation dulce'
    nodes=pd.read_parquet(directory/'create_final_nodes.parquet')
    entities=pd.read_parquet(directory/'create_final_entities.parquet')
    reports=pd.read_parquet(directory/'create_final_community_reports.parquet')
    selected_reports=read_indexer_reports(reports.copy(),nodes.copy(),2)
    selected_entities=read_indexer_entities(nodes.copy(),entities.copy(),2)
    lineage=dict(input_source='author examples_notebooks/global_search.ipynb',community_level=2,
        table_rows=dict(nodes=len(nodes),entities=len(entities),reports=len(reports)),
        selected_reports=len(selected_reports),selected_entities=len(selected_entities),
        index_precomputed_by_author=True,native_index_regenerated=False)
    return selected_reports,selected_entities,lineage


def global_context(reports,entities):
    import tiktoken
    from graphrag.query.structured_search.global_search.community_context import GlobalCommunityContext
    encoder=tiktoken.get_encoding('cl100k_base')
    context=GlobalCommunityContext(community_reports=reports,entities=entities,token_encoder=encoder)
    parameters=dict(use_community_summary=False,shuffle_data=True,include_community_rank=True,
        min_community_rank=0,community_rank_name='rank',include_community_weight=True,
        community_weight_name='occurrence weight',normalize_community_weight=True,
        max_tokens=12000,context_name='Reports')
    return context,parameters,encoder


async def query(reports,entities,question,generate,observe):
    from graphrag.query.llm.base import BaseLLM
    from graphrag.query.structured_search.global_search.search import GlobalSearch
    context,parameters,encoder=global_context(reports,entities)
    stages=[]
    class QueryTransport(BaseLLM):
        def generate(self,messages,streaming=True,callbacks=None,**kwargs):
            stage=('query.map.' if 'response_format' in kwargs else 'query.reduce.')+str(len(stages)).zfill(4)
            stages.append(stage)
            return generate(stage,messages,kwargs)
        async def agenerate(self,messages,streaming=True,callbacks=None,**kwargs):
            return self.generate(messages,streaming,callbacks,**kwargs)
    engine=GlobalSearch(llm=QueryTransport(),context_builder=context,token_encoder=encoder,
        max_data_tokens=12000,map_llm_params=dict(max_tokens=1000,temperature=0.0),
        reduce_llm_params=dict(max_tokens=2000,temperature=0.0),allow_general_knowledge=False,
        json_mode=True,context_builder_params=parameters,concurrent_coroutines=1,response_type='multiple paragraphs')
    result=await engine.asearch(question)
    saved=serial(result)
    observe('graphrag.global_search',saved)
    if not stages:raise ValueError('Original global search made no model calls')
    return dict(output=result.response,execution=saved,stages=stages,
        positive_map_points=sum(isinstance(point,dict) and point.get('score',0)>0 for m in result.map_responses for point in (m.response if isinstance(m.response,list) else [])))


async def build_index(request,generate,observe):
    import pandas as pd
    from graphrag.config.models import GraphRagConfig
    from graphrag.index.create_pipeline_config import create_pipeline_config,all_embeddings
    from graphrag.index.run import run_pipeline_with_config
    from graphrag.index.storage import MemoryPipelineStorage
    from graphrag.index.cache import InMemoryCache
    loader=importlib.import_module('graphrag.index.llm.load_llm')
    sdk=importlib.import_module('graphrag.llm.openai.openai_chat_llm')
    sdk._MAX_GENERATION_RETRIES=0
    async def no_paid_reformat(self,*args,**kwargs):raise ValueError('Automatic paid JSON reformat disabled; original response retained')
    sdk.OpenAIChatLLM._try_clean_json_with_llm=no_paid_reformat
    calls=[]
    async def create(**parameters):
        stage='index.'+str(len(calls)).zfill(4);calls.append(stage)
        messages=parameters.pop('messages')
        raw=generate(stage,messages,parameters)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw),finish_reason='stop')])
    async def no_embeddings(**_kwargs):raise ValueError('Embedding branch is disabled for the selected global workflow')
    broker=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),embeddings=SimpleNamespace(create=no_embeddings))
    loader.create_openai_client=lambda **_kwargs:broker
    settings=GraphRagConfig(
        root_dir=str(HERE),
        llm=dict(type='openai_chat',api_key='UNUSED_PARENT_BROKER',model='gpt-4-turbo-preview',
            max_tokens=4096,temperature=0.0,model_supports_json=True,max_retries=0,concurrent_requests=1),
        embeddings=dict(target='all',skip=sorted(all_embeddings)),
        chunks=dict(size=1200,overlap=100,group_by_columns=['id']),
        entity_extraction=dict(max_gleanings=1,entity_types=request.get('entity_types',['organization','person','geo','event','platform','message'])),
        claim_extraction=dict(enabled=False),embed_graph=dict(enabled=False),umap=dict(enabled=False),
        parallelization=dict(num_threads=1,stagger=0),
        storage=dict(type='memory'),cache=dict(type='memory'),reporting=dict(type='console'))
    config=create_pipeline_config(settings)
    observe('graphrag.pipeline_config',serial(config.model_dump()))
    documents=request['documents']
    dataset=pd.DataFrame([dict(id=d['id'],text=d['text'],title=d['id']) for d in documents])
    if dataset.empty:raise ValueError('Index requires nonempty frozen source documents')
    tables={};workflow_records=[]
    async for result in run_pipeline_with_config(config,dataset=dataset,storage=MemoryPipelineStorage(),cache=InMemoryCache(),emit=[]):
        record=dict(workflow=result.workflow,errors=[str(e) for e in result.errors or []],table=serial(result.result))
        workflow_records.append(record);observe('graphrag.index_workflow',record)
        if result.errors:raise ValueError('Original index workflow failed: '+result.workflow)
        tables[result.workflow]=result.result
    required=['create_base_text_units','create_base_extracted_entities','create_summarized_entities','create_base_entity_graph','create_final_nodes','create_final_entities','create_final_relationships','create_final_community_reports']
    if any(name not in tables for name in required):raise ValueError('Original index workflow did not complete every required stage')
    nodes=tables['create_final_nodes'];entities=tables['create_final_entities'];reports=tables['create_final_community_reports']
    if nodes.empty or reports.empty:raise ValueError('No original graph nodes/community reports were produced')
    # Global weights use occurrence metadata, never these optional embedding vectors.
    if 'description_embedding' not in entities:entities=entities.assign(description_embedding=None)
    from graphrag.query.indexer_adapters import read_indexer_entities,read_indexer_reports
    selected_reports=read_indexer_reports(reports.copy(),nodes.copy(),2)
    selected_entities=read_indexer_entities(nodes.copy(),entities.copy(),2)
    return selected_reports,selected_entities,dict(workflows=workflow_records,stages=calls,
        required_workflows=required,selected_reports=len(selected_reports),selected_entities=len(selected_entities),
        local_neural_inference=False,text_embeddings_computed=False,graph_embeddings_computed=False)


async def run(request,generate,observe=lambda action,result:None):
    folder,identity=load()
    mode=request['mode']
    if mode in ['native_query','plan_native']:
        reports,entities,lineage=native_tables(folder)
        if mode=='plan_native':
            context,parameters,encoder=global_context(reports,entities)
            chunks,records=context.build_context(**parameters)
            return dict(status='planned',inference_executed=False,maximum_requests=len(chunks)+1,
                context_batches=len(chunks),context=chunks,lineage=lineage,source_commit=identity['commit'])
        indexing=None
    else:
        reports,entities,indexing=await build_index(request,generate,observe)
        lineage=dict(input_source='frozen product text',index_regenerated_from_frozen_sources=True)
    result=await query(reports,entities,request['question'],generate,observe)
    native_output=result['output'];projection=None
    if request.get('projection'):
        spec=request['projection']
        messages=[dict(role='system',content=spec['instruction']),dict(role='user',content=json.dumps(dict(native_global_answer=native_output,frozen_source_anchors=spec['anchors'],task=spec.get('task')),ensure_ascii=False))]
        raw=generate('product_projection',messages,dict(temperature=0,max_tokens=4096))
        text=raw.strip()
        if text.startswith(chr(96)*3):text='\n'.join(text.splitlines()[1:-1])
        projection=json.loads(text)
        if not isinstance(projection,dict):raise ValueError('Product projection is not an object')
    neural=[name for name in ['torch','transformers','sentence_transformers','spacy','onnxruntime'] if name in sys.modules]
    if neural:raise ValueError('Unexpected local neural runtime: '+','.join(neural))
    return dict(method='graphrag',source_kind='author_global_api_index_and_query',author_code_executed=True,
        source_commit=identity['commit'],lineage=lineage,indexing=indexing,query=result,
        native_output=native_output,output=projection if projection is not None else native_output,
        product_projection_separate=projection is not None,local_model_inference=False,
        text_embeddings_computed=False,graph_embeddings_computed=False,neural_modules_loaded=neural,
        original_complete_benchmark=False,expert_legal_accuracy=None,
        original_entries=['graphrag.index.run.run_pipeline_with_config (product indexing)',
            'graphrag.query.indexer_adapters.read_indexer_reports/read_indexer_entities',
            'GlobalCommunityContext.build_context','GlobalSearch.asearch/_map_response_single_batch/_reduce_response'])
