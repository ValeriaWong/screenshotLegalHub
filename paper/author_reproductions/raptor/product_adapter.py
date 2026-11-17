"""RAPTOR — Sarthi et al., ICLR 2024, https://arxiv.org/abs/2401.18059.
Author: https://github.com/parthsarthi03/raptor @ 7da1d48a7e1d7dec61a63c9d9aae84e2dfaa5767.

复现程度：直接运行作者 ClusterTreeBuilder、RAPTOR_Clustering 和 TreeRetriever；
沿作者公开 BaseSummarizationModel/SBertEmbeddingModel 扩展接口替换模型。
不是“摘要 prompt”近似；原论文完整成绩未复现。实际执行状态看同目录 runs/。
原任务：长文档 + 文本问题 -> 答案、检索上下文；原 benchmark 为 NarrativeQA、
QASPER、QuALITY；作者 demo/sample.txt 为 Cinderella 原生示例（不是 benchmark）。
创新：UMAP 降维、GMM 软聚类、递归生成摘要、跨树层检索。
原 I/O 示例：Cinderella 文本 + How did Cinderella reach her happy ending? -> 文本答案。
本项目输入：冻结 KIE 预测文本或证据文本 + 全局问题；输出仍保留原节点、父子关系、
检索节点及叶节点引用；最后回答受产品 JSON schema 约束。它不能直接识别像素，
不作为 KIE 提取方法；不读取目标答案或专家金标。
适配：多文档逐文档分块保留来源 ID；摘要可改变表达，引用必须下溯到原始叶节点。
本地 CPU SBERT 为多语言 MiniLM，与论文 ada-002 不同；摘要/QA 由父进程选择并记录。
小样本可调整 reduction_dimension，默认仍为作者值 10；不得把无摘要层的树称作已
验证递归聚类。为重放固定NumPy/Torch种子224和Numba单线程；未改作者UMAP/GMM函数。
本文件不会隐式下载模型、调用供应商或读供应商密钥。
"""
import contextlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from author_runtime import ROOT, source, call, tool, emit


def execute(request):
    folder, provenance = source('raptor')
    sys.path.insert(0, str(folder))
    os.environ.setdefault('OPENAI_API_KEY', 'unused-local-transport')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['NUMBA_NUM_THREADS'] = '1'
    import numba
    numba.set_num_threads(1)
    import numpy as np
    import torch
    from raptor.EmbeddingModels import SBertEmbeddingModel
    from raptor.SummarizationModels import BaseSummarizationModel
    from raptor.cluster_tree_builder import ClusterTreeBuilder, ClusterTreeConfig
    from raptor.tree_retriever import TreeRetriever, TreeRetrieverConfig
    from raptor.tree_structures import Tree
    from raptor.utils import split_text
    torch.set_num_threads(2)
    np.random.seed(224)
    torch.manual_seed(224)
    lock = json.loads((ROOT/'paper/author_reproductions/local_models.lock.json').read_text(encoding='utf-8'))
    model = lock['embedding']
    embedding = SBertEmbeddingModel(str(ROOT/model['path']))
    summaries = []
    class Summarizer(BaseSummarizationModel):
        def summarize(self, context, max_tokens=100):
            stage = 'summary.' + str(len(summaries))
            messages = [dict(role='system', content='You are a helpful assistant.'),
                        dict(role='user', content=f'Write a summary of the following, including as many key details as possible: {context}:')]
            value = call(stage, messages, dict(max_tokens=max_tokens, model='gpt-3.5-turbo'))
            summaries.append(dict(stage=stage, input=context, output=value))
            return value
    parameters = dict(max_tokens=request.get('chunk_tokens', 100), num_layers=request.get('num_layers', 5),
                      reduction_dimension=request.get('reduction_dimension', 10), summarization_length=100)
    builder = ClusterTreeBuilder(ClusterTreeConfig(**parameters, summarization_model=Summarizer(),
                 embedding_models={'SBERT': embedding}, cluster_embedding_model='SBERT'))
    documents = request['documents']
    if not documents or any(not doc['text'].strip() for doc in documents):
        raise ValueError('RAPTOR requires nonempty source documents')
    leaves = {}
    provenance_by_leaf = {}
    # Same author splitter and create_node, grouped by source to avoid mixing IDs.
    for doc in documents:
        for chunk in split_text(doc['text'], builder.tokenizer, builder.max_tokens):
            i = len(leaves)
            _, leaves[i] = builder.create_node(i, chunk)
            provenance_by_leaf[i] = doc['id']
    all_nodes = dict(leaves)
    layers = {0: list(leaves.values())}
    roots = builder.construct_tree(leaves, all_nodes, layers, use_multithreading=False)
    tree = Tree(all_nodes, roots, leaves, builder.num_layers, layers)
    retriever = TreeRetriever(TreeRetrieverConfig(embedding_model=embedding, context_embedding_model='SBERT'), tree)
    context, selected = retriever.retrieve(request['question'], max_tokens=3500, top_k=10,
                        collapse_tree=True, return_layer_information=True)
    def leaf_indices(index):
        node = all_nodes[index]
        return sorted({j for child in node.children for j in leaf_indices(child)}) if node.children else [index]
    selected_leaf_indices = sorted({i for node in selected for i in leaf_indices(node['node_index'])})
    records = [dict(index=n.index, text=n.text, children=sorted(n.children),
                    leaf_indices=leaf_indices(n.index), source_ids=sorted({provenance_by_leaf[i] for i in leaf_indices(n.index)}))
               for n in sorted(all_nodes.values(), key=lambda n: n.index)]
    trace = dict(nodes=records, selected=selected, leaf_sources=provenance_by_leaf,
                 original_leaf_evidence=[dict(node_index=i, source_id=provenance_by_leaf[i], text=leaves[i].text) for i in selected_leaf_indices],
                 retrieved_context=context, parameters=parameters, layers={str(k):len(v) for k,v in layers.items()})
    tool('raptor.tree_and_retrieval', trace)
    if request.get('mode') == 'product':
        messages = [dict(role='system', content=request['instruction']),
                    dict(role='user', content=json.dumps(dict(question=request['question'],
                         derived_summaries=context, evidence=trace['original_leaf_evidence'],
                         note='Summaries are derived context, not independently established facts. Cite only frozen original evidence.'), ensure_ascii=False))]
    else:
        messages = [dict(role='system', content='You are Question Answering Portal'),
                    dict(role='user', content=f"Given Context: {context} Give the best full answer amongst the option to question {request['question']}")]
    answer = call('answer', messages, dict(model='gpt-3.5-turbo', temperature=0))
    output = json.loads(answer) if request.get('mode') == 'product' else answer
    return dict(event='result', output=output, method='raptor', source_commit=provenance['commit'],
                author_entry='ClusterTreeBuilder.construct_tree + TreeRetriever.retrieve',
                source_files=provenance['files'], tree=trace, summaries=summaries,
                embedding_model={k:v for k,v in model.items() if k!='files'},
                original_complete_benchmark=False)

if __name__ == '__main__':
    request = json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):
        result = execute(request)
    emit(result)
