"""Build a strict allowlisted input; case notes, old answers and reviewer gold never cross."""
from screenshotlegal.domain.common.models import digest

class FrozenInputBuilder:
    def __init__(self,workspace,documents):
        self.workspace,self.documents=workspace,documents
    def build(self,case,goal,document_ids,effective_date):
        from screenshotlegal.domain.evidence.sources import freeze_sources
        w=self.workspace;cid=case['id']
        evidence=freeze_sources(w,self.documents,cid,document_ids)
        sources=evidence['sources'];documents=evidence['documents'];hashes=evidence['source_file_hashes']
        if not sources: raise ValueError('没有可分析的转录或已解析文本；请先处理资料或选择文档')
        if len(sources)>500 or sum(len(s['text']) for s in sources)>150000:
            raise ValueError('当前材料超出试验快照上限，请缩小资料范围；系统不会静默截断证据')
        selection=w.repo.optional('matter_selections',cid)
        pack=w.matters.get(selection['matter_pack_id'],selection.get('version','1.0.0')) if selection else dict(manifest={},claims=[],authorities=[],digest=digest(None))
        authorities=[{k:(a.get(k).isoformat() if hasattr(a.get(k),'isoformat') else a.get(k)) for k in ['id','type','title','article','jurisdiction','valid_from','valid_to','source_url','source_digest','verification_status','text','source_role','review']} for a in pack['authorities']]
        excluded=[dict(id=a['id'],reason='out_of_effective_date') for a in authorities if (a.get('valid_from') and a['valid_from']>effective_date) or (a.get('valid_to') and a['valid_to']<effective_date)]
        excluded_ids={a['id'] for a in excluded};authorities=[a for a in authorities if a['id'] not in excluded_ids]
        frozen=dict(law_effective_date=effective_date,authority_exclusions=excluded,schema_version='case-experiment-input.v1',case_id=cid,case_title=case['title'],goal=goal,
                    sources=sources,documents=documents,source_file_hashes=sorted(hashes),
                    perception_digest=digest(sources),legal_corpus=authorities,legal_corpus_digest=digest(authorities),
                    matterpack={k:pack[k] for k in ['manifest','claims','digest','factor_hierarchy'] if k in pack},
                    matterpack_digest=pack['digest'],gold_visibility='evaluation_only',
                    limitations=['仅使用当前选定材料；未引用的案件备注、旧分析、审核答案不进入输入。',
                                 '法律模板为输入知识，不把模板已提供的举证规则计为模型自主推断。',
                                 '当前法源可能含未复核草稿，不能当作已认证法律意见。'])
        frozen['input_digest']=digest(frozen)
        return frozen

def citation_units(text,start=0):
    """Mechanical quotation boundaries; no extraction or semantic filtering.
    Positions count Unicode code points, including punctuation and emoji.
    """
    result=[];begin=0
    for i,char in enumerate(text):
        if char in '。！？；\n' or i-begin+1>=160:
            result.append(dict(quote=text[begin:i+1],start=start+begin,end=start+i+1));begin=i+1
    if begin<len(text):result.append(dict(quote=text[begin:],start=start+begin,end=start+len(text)))
    return result

class SourceReader:
    def __init__(self,frozen):self.frozen=frozen;self.refs={s['id']:s for s in frozen['sources']}
    def execute(self,tool,args):
        if tool=='source_read':
            ref=self.refs.get(args.get('source_ref_id'))
            if ref is None:raise ValueError('来源不属于本次输入')
            start=args.get('start',0);limit=args.get('max_chars',3000)
            if type(start)is not int or type(limit)is not int or start<0 or limit<1 or limit>5000 or start>len(ref['text']):raise ValueError('读取范围无效')
            end=min(len(ref['text']),start+limit)
            return dict(source_ref_id=ref['id'],text=ref['text'][start:end],start=start,end=end,char_unit='unicode_code_point',
                        citation_units=citation_units(ref['text'][start:end],start),text_digest=ref['text_digest'],parse_run_id=ref.get('parse_run_id'),
                        next_request=dict(tool='source_read',args=dict(source_ref_id=ref['id'],start=end,max_chars=limit)) if end<len(ref['text']) else None)
        if tool in ['case_search','authority_search']:
            query=args.get('query','')
            if not isinstance(query,str) or not query.strip() or len(query)>200:raise ValueError('检索词无效')
            from screenshotlegal.infrastructure.retrieval.fts import tokenize
            limit=args.get('limit',5)
            if type(limit) is not int or not 1<=limit<=10:raise ValueError('检索数量必须在1至10之间')
            terms=set(tokenize(query));rows=self.frozen['sources'] if tool=='case_search' else self.frozen['legal_corpus']
            ranked=sorted(((len(terms&set(tokenize(s.get('text') or str(s.get('title',''))+' '+str(s.get('article',''))))),s) for s in rows),key=lambda v:-v[0])
            return [dict(source_ref_id=s['id'],preview=s['text'][:300],preview_start=0,preview_end=min(300,len(s['text'])),citation_units=citation_units(s['text'][:300]),text_digest=s['text_digest']) if tool=='case_search' else s for score,s in ranked[:limit] if score]
        raise ValueError('工具未授权；仅允许冻结材料内检索、读取和法源检索')
