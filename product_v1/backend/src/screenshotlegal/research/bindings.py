"""Public binding fingerprints for review, gold certification and release."""
from .contracts import digest
from .store import Conflict
from .renderer import verified

def gold_digest(content,question):
    ids=set(question['message_ids'])
    return digest(dict(question={k:question[k] for k in ['id','question','answer','task_type','message_ids']},
                       messages=[m for m in content['messages'] if not ids or m['id'] in ids],
                       source_text=content['source_text'],source_refs=content['source_refs']))

def current_binding(store,owner,sample,revision,db=None,expected_manifest=None):
    manifest=store.optional('review.manifest',sample.get('published_manifest') or '',owner,db)
    if not manifest or manifest['revision']!=revision['number'] or sample['revision']!=revision['number']:
        raise Conflict('当前版本图片尚未就绪，不能确认图片审核或发布')
    if expected_manifest is not None and expected_manifest!=manifest['id']:
        raise Conflict('审核图片版本已改变，请重新打开当前图片确认')
    if manifest.get('text_hash')!=revision['content_hash'] or not manifest.get('validation',{}).get('valid'):
        raise Conflict('图片缺少当前契约的有效性检查，请重新渲染并复核')
    for p in manifest['pages']: verified(store.root,p)
    binding=dict(sample_id=sample['id'],revision=revision['number'],content_hash=revision['content_hash'],
                 manifest_id=manifest['id'],manifest_hash=manifest['sha256'],asset_hashes=[p['sha256'] for p in manifest['pages']],
                 visual_role=manifest.get('visual_role','legacy_unbound'))
    binding['sha256']=digest(binding)
    return binding,manifest
