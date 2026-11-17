"""A06 Chain of Agents — Zhang et al., NeurIPS 2024 / arXiv:2406.02818v1.
Source: https://arxiv.org/html/2406.02818v1 Algorithm 1, §§3.1–3.2,
Appendix B Tables 9–10, Appendix D. No verified author code repository was found
in the paper or official Google Research project post. This is a paper-algorithm
reimplementation, not execution of author CoA Python code or an OPPO namesake.
Original method: split ALL long input in order, initialize CU0='', each worker
reads its own chunk + previous cumulative communication unit + optional query;
a separate manager receives ONLY the last CU and task requirement/query.
Innovation: interleaved reading and cumulative communication across short-window
workers, rather than independent chunks or retrieval followed by generation.
Original benchmarks: HotpotQA, MuSiQue, NarrativeQA, Qasper, QuALITY, QMSum,
GovReport, BookSum, RepoBench-P; QA F1, summarization ROUGE, code similarity.
Original input: long source x, optional query q, task requirement. Output: answer,
summary or code completion plus worker CUs; no screenshot boxes or legal schema.
Our differences: DeepSeek API replaces Vertex models; cl100k_base replaces
unavailable Vertex tokenization, explicitly a proxy. Window 8192, temperature 0,
native generation cap 1024; product cap 2048 and JSON/literal-source instructions
are domain adaptations. No training, embeddings, weights, reranking or RAG.
Product compatibility: frozen KIE TEXT → global VQA, and frozen evidence sources
→ CaseAnalysisOutput with quoted offsets carried in CUs. Pixel KIE is unsupported.
No expert labels are read by workers/manager. Only original benchmark evaluation
reads public reference answers. Full paper benchmark/quality claims remain false.
"""
import hashlib
import json
import os
from pathlib import Path
import tiktoken

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent

def resources():
    specification=json.loads((HERE/'specification.lock.json').read_text(encoding='utf-8'))
    for file,expected in specification['files'].items():
        if hashlib.sha256((HERE/file).read_bytes()).hexdigest()!=expected:
            raise ValueError('Pinned CoA paper specification changed: '+file)
    tokenizer_lock=json.loads((HERE.parent/'tokenizer_resources.lock.json').read_text(encoding='utf-8'))
    entry=next(x for x in tokenizer_lock if x['name']=='cl100k_base')
    if hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
        raise ValueError('Pinned tokenizer data changed')
    os.environ['TIKTOKEN_CACHE_DIR']=str(ROOT/'paper/.cache/tiktoken')
    return tiktoken.get_encoding('cl100k_base'),specification

def worker_prompt(chunk,previous,query,query_based):
    # Query and non-query templates transcribed from the paper's Tables 9/10.
    prefix=chunk+'\nHere is the summary of the previous source text:\n'+previous+'\n'
    if query_based:
        return prefix+'Question: '+query+'\nYou need to read current source text and summary of previous source text (if any) and generate a summary to include them both. Later, this summary will be used for other agents to answer the Query, if any. So please write the summary that can include the evidence for answering the Query:'
    return prefix+'You need to read the current source text and summary of previous source text (if any) and generate a summary to include them both. Later, this summary will be used for other agents to generate a summary for the whole text. Thus, your generated summary should be relatively long.'

def manager_prompt(last,query,requirement,query_based):
    text=requirement+'\nThe following are given passages. However, the source text is too long and has been summarized. You need to answer based on the summary:\n'+last
    return text+('\nQuestion: '+query if query_based else '')+'\nAnswer:'

def run(request,generate):
    encoding,specification=resources()
    text=request['text'];query=request.get('question','');requirement=request['task_requirement']
    query_based=request.get('query_based',True)
    window=request.get('window_tokens',8192);generation=request.get('max_output_tokens',1024)
    if not isinstance(text,str) or not text:raise ValueError('CoA requires nonempty source text')
    if not 1024<=window<=8192 or not 128<=generation<window:raise ValueError('Unsupported explicit development window/output cap')
    worker_policy=request.get('worker_policy','');manager_policy=request.get('manager_policy','')
    def messages(prompt,policy):return ([dict(role='system',content=policy)] if policy else [])+[dict(role='user',content=prompt)]
    def tokens(value):return len(encoding.encode(value,disallowed_special=()))
    def count(items):return 3+sum(4+tokens(m['role'])+tokens(m['content']) for m in items)
    # Reserve one maximum-sized previous CU and one output. Explicit Chat template
    # proxy overhead is included; these are not claimed to be DeepSeek token counts.
    empty=count(messages(worker_prompt('','',query,query_based),worker_policy))
    chunk_limit=window-generation-generation-empty-32
    if chunk_limit<16:raise ValueError('Policy/query leaves no source chunk capacity')
    all_tokens=encoding.encode(text,disallowed_special=());pieces=[];offset=0;position=0
    while position<len(all_tokens):
        end=min(position+chunk_limit,len(all_tokens))
        while True:
            data=b''.join(encoding.decode_single_token_bytes(t) for t in all_tokens[position:end])
            try:chunk=data.decode('utf-8');break
            except UnicodeDecodeError:end-=1
        if end<=position:raise ValueError('Unable to split source at a Unicode boundary')
        pieces.append(dict(index=len(pieces),start=offset,end=offset+len(chunk),text=chunk,token_count=end-position))
        offset+=len(chunk);position=end
    if ''.join(c['text'] for c in pieces)!=text:raise ValueError('Source chunk coverage differs from original text')
    if len(pieces)+1>request.get('max_calls',100):raise ValueError('Chunk workers plus manager exceed explicit call budget before inference')
    previous='';communications=[];requests=[]
    for piece in pieces:
        visible=messages(worker_prompt(piece['text'],previous,query,query_based),worker_policy)
        length=count(visible)
        if length+generation>window:raise ValueError('Actual worker proxy window exceeded; no truncation or extra call')
        stage='worker.'+str(piece['index']).zfill(4)
        record=dict(stage=stage,chunk_index=piece['index'],previous_cu_index=piece['index']-1 if piece['index'] else None,proxy_input_tokens=length)
        requests.append(record)
        value=generate(stage,visible,dict(temperature=0,max_tokens=generation))
        if not isinstance(value,str) or not value.strip():raise ValueError('Worker returned empty/non-text CU')
        previous=value;communications.append(dict(index=piece['index'],text=value,proxy_tokens=tokens(value)))
    visible=messages(manager_prompt(previous,query,requirement,query_based),manager_policy)
    length=count(visible)
    if length+generation>window:raise ValueError('Manager last-CU proxy window exceeded; no source reread or CU truncation')
    requests.append(dict(stage='manager',last_cu_index=len(pieces)-1,proxy_input_tokens=length,source_chunks_supplied=False,all_cus_supplied=False))
    final=generate('manager',visible,dict(temperature=0,max_tokens=generation))
    if not isinstance(final,str) or not final.strip():raise ValueError('Manager returned empty/non-text output')
    return dict(method='chain_of_agents',source_kind='paper_algorithm_reimplementation',
        author_code_executed=False,paper_url=specification['paper_url'],output=final,
        source_sha256=hashlib.sha256(text.encode()).hexdigest(),chunks=pieces,
        communication_units=communications,requests=requests,calls=len(requests),
        window_tokens=window,chunk_capacity_tokens=chunk_limit,tokenizer_proxy='cl100k_base',
        local_model_inference=False,original_complete_benchmark=False)
