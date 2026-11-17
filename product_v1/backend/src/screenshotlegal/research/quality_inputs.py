"""Versioned quality input; source inventory is never the list of images under review."""
from .contracts import dumps
from .gateway import request_messages
VERSION = 'quality-input.v2'
LEGACY = 'quality-input.v1'

def freeze_input(revision, manifest, coverage):
    c=revision['content'];pages=manifest['pages'] if manifest else []
    if coverage!='text' and not pages: raise ValueError('待审图片清单为空')
    reviewed=dict(sample_id=revision['sample_id'],revision=revision['number'],content_hash=revision['content_hash'],
                  visual_role=manifest['visual_role'] if manifest else 'text',manifest_id=(manifest.get('id') or manifest['sha256']) if manifest else None,
                  expected_pages=len(pages),pages=[{k:p.get(k) for k in ['id','page','sha256','width','height','mime_type']} for p in pages])
    allowed=['title','category','language','platform','questions']+(['messages'] if coverage!='visual' else [])
    task=dict(input_contract_version=VERSION,review_scope=coverage,reviewed_object=reviewed,
              content={k:c[k] for k in allowed},source_context=dict(source_text=c['source_text'],source_refs=c['source_refs'],
              source_asset_count=len(c['original_assets']),note='来源资产数量仅说明来源，不是待审页数；未列入reviewed_object的图片不属于本次检查。'))
    if pages:task['images']=[{k:p[k] for k in ['path','sha256','mime_type','page']} for p in pages]
    return task

def messages(store, payload):
    p=payload;r=p['revision'];version=p.get('input_contract_version',LEGACY)
    system=p['prompt']['markdown']+'\n按结构返回 JSON：verdict=pass/revise/reject/pending, score=0..100或null, dimensions={}, findings, suggestions, process。此为模型评估，不可认证人工金标。'
    if version==VERSION:
        task=p['review_input']
        if task['input_contract_version']!=version: raise ValueError('评估输入版本不一致')
        expected=task['reviewed_object']['pages'];images=task.get('images',[])
        if len(images)!=task['reviewed_object']['expected_pages'] or [(x['page'],x['sha256']) for x in images]!=[(x['page'],x['sha256']) for x in expected]:raise ValueError('待审清单与发送图片不一致')
        system+='\n只检查reviewed_object明确列出的对象和页数。source_context仅供核对来源，不要按source_asset_count要求补图，不把来源原图与合成图混作一个待审对象。逐项写明实际可见依据；没有评估的维度留空。'
        user=request_messages(store,task)[1]['content'] if images else dumps(task)
        return [dict(role='system',content=system),dict(role='user',content=user)]
    if version!=LEGACY:raise ValueError('不支持的评估输入版本')
    # Pending old jobs keep their original serializer and protocol; no silent reinterpretation.
    user=dumps(dict(content=r['content'],revision=r['number'],content_hash=r['content_hash']))
    if p.get('coverage','text')!='text':
        body=r['content'] if p['coverage']=='multimodal' else {k:r['content'][k] for k in ['source_text','source_refs','questions']}
        user=request_messages(store,dict(question='核查给定截图质量并按要求返回JSON',context=body,images=p['manifest']['pages']))[1]['content']
    return [dict(role='system',content=system),dict(role='user',content=user)]
