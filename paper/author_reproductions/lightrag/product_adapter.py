"""LightRAG — Guo et al., https://arxiv.org/abs/2410.05779.
Author https://github.com/HKUDS/LightRAG @ c31a2654f9fff95145d6edf372c1f5af5b6db891 (v1.0.3).
复现程度：作者 extract_entities（含 gleaning/合并）、kg_query 双层检索及
NetworkX/NanoVectorDB/JsonKVStorage 原实现直接执行；使用早期作者版本而非当前新产品。
原任务：长文本文档索引后回答局部/全局问题；论文使用 UltraDomain 多领域语料，
输出自然语言答案。创新：实体关系图 + 高/低层关键词的双层检索和增量合并。
本项目：冻结 KIE 文本或证据文本→图索引→全局 VQA JSON；不直接消费图像，不能算 KIE。
实体/关系描述是模型派生内容，不是法院已认定事实；保留 source_id→冻结原文映射。
适配：仅在字符串外将观察到的全角元组结束符）转为作者 ASCII )，记录转换；不更改字段内容。
适配：模型通过父进程传输；SBERT 多语 CPU embedding 替换论文 embedding；最终回答
增加产品 JSON 约束；索引只用当前冻结任务材料，不混入目标答案或其他案例的库。
不加载作者一体化 __init__ 中未使用的云数据库/供应商包；三个选定存储类和全部
索引/检索函数原样导入。模型真实运行与离线脚本验证分别见 runs/ 与 validation/。
"""
import asyncio
import contextlib
import json
import os
import sys
import tempfile
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import ROOT, source, call, tool, emit


def canonical_tuple_terminators(raw):
    """Normalize observed fullwidth tuple terminators outside quoted fields only."""
    chars=list(raw);quoted=False;escaped=False
    for i,char in enumerate(raw):
        if escaped:escaped=False;continue
        if char=='\\' and quoted:escaped=True;continue
        if char=='"':quoted=not quoted;continue
        if char=='）' and not quoted:
            tail=raw[i+1:].lstrip()
            if not tail or tail.startswith(('##','<|COMPLETE|>')):chars[i]=')'
    return ''.join(chars)


async def execute(request):
    folder,provenance=source('lightrag')
    # Load only the original selected submodules; avoid optional cloud-provider imports.
    package=types.ModuleType('lightrag');package.__path__=[str(folder/'lightrag')]
    sys.modules['lightrag']=package
    from lightrag.operate import chunking_by_token_size,extract_entities,kg_query
    from lightrag.storage import JsonKVStorage,NanoVectorDBStorage,NetworkXStorage
    from lightrag.utils import EmbeddingFunc,compute_mdhash_id
    from lightrag.base import QueryParam
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(2)
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    models=json.loads((ROOT/'paper/author_reproductions/local_models.lock.json').read_text(encoding='utf-8'))
    model=SentenceTransformer(str(ROOT/models['embedding']['path']),device='cpu')
    async def embedding(texts):return model.encode(texts,normalize_embeddings=True)
    embedding_fn=EmbeddingFunc(embedding_dim=model.get_sentence_embedding_dimension(),max_token_size=512,func=embedding)
    count=0;phase='index';normalizations=[]
    async def llm(prompt,system_prompt=None,history_messages=None,**kwargs):
        nonlocal count
        stage=('keywords' if kwargs.get('keyword_extraction') else phase)+'.'+str(count);count+=1
        messages=[]
        if system_prompt:
            if request.get('mode')=='product':
                system_prompt=request['instruction']+'\n'+system_prompt+'\nReturn only the required JSON. Graph descriptions are derived context; evidence must refer to the frozen source text.'
            messages.append(dict(role='system',content=system_prompt))
        messages.extend(history_messages or [])
        messages.append(dict(role='user',content=prompt))
        parameters=dict(keyword_extraction=bool(kwargs.get('keyword_extraction')),model='gpt-4o-mini')
        parameters.update({k:kwargs[k] for k in ['max_tokens','temperature','stop'] if k in kwargs})
        raw=call(stage,messages,parameters)
        canonical=canonical_tuple_terminators(raw) if phase=='index' else raw
        if canonical!=raw:normalizations.append(dict(stage=stage,rule='fullwidth_tuple_terminator_outside_quotes',canonicalized=canonical))
        return canonical
    with tempfile.TemporaryDirectory(prefix='screenshotlegal-lightrag-') as temporary:
        config=dict(working_dir=temporary,llm_model_func=llm,embedding_batch_num=32,llm_model_max_token_size=32768,
                    tiktoken_model_name='gpt-4o-mini',entity_extract_max_gleaning=1,entity_summary_to_max_tokens=500,
                    addon_params=dict(language=request.get('language','English')),
                    node2vec_params={},vector_db_storage_cls_kwargs={})
        graph=NetworkXStorage(namespace='graph',global_config=config,embedding_func=embedding_fn)
        chunks_db=JsonKVStorage(namespace='chunks',global_config=config,embedding_func=None)
        entities=NanoVectorDBStorage(namespace='entities',global_config=config,embedding_func=embedding_fn,meta_fields={'entity_name'})
        relations=NanoVectorDBStorage(namespace='relations',global_config=config,embedding_func=embedding_fn,meta_fields={'src_id','tgt_id'})
        chunks={};sources={}
        for document in request['documents']:
            for chunk in chunking_by_token_size(document['text'],overlap_token_size=100,max_token_size=1200,tiktoken_model='gpt-4o-mini'):
                key=compute_mdhash_id(chunk['content'],prefix='chunk-')
                chunks[key]={**chunk,'full_doc_id':document['id']}
                sources.setdefault(key,[]).append(document['id'])
        if not chunks:raise ValueError('LightRAG requires nonempty frozen source text')
        await chunks_db.upsert(chunks)
        result_graph=await extract_entities(chunks,graph,entities,relations,config)
        if result_graph is None or not graph._graph.number_of_nodes():
            raise ValueError('Author entity extraction produced no graph; not a successful reproduction')
        phase='answer'
        output=await kg_query(request['question'],graph,entities,relations,chunks_db,
                     QueryParam(mode='hybrid',response_type='Single Paragraph'),config)
        trace=dict(nodes=[dict(id=k,**v) for k,v in graph._graph.nodes(data=True)],
                   edges=[dict(source=a,target=b,**v) for a,b,v in graph._graph.edges(data=True)],
                   chunks=chunks,chunk_source_ids=sources,query_mode='hybrid')
        tool('lightrag.graph_and_sources',trace)
        parsed=json.loads(output) if request.get('mode')=='product' else output
        return dict(event='result',method='lightrag',output=parsed,graph=trace,calls=count,
                    source_commit=provenance['commit'],author_entry='operate.extract_entities + operate.kg_query',
                    embedding_model={k:v for k,v in models['embedding'].items() if k!='files'},transport_normalizations=normalizations,original_complete_benchmark=False)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=asyncio.run(execute(request))
    emit(result)
