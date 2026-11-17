"""Regeneration consumes an exported correction package, never the panel's live review rows."""
from .contracts import Content, Message, SampleCreate, BatchCreate, digest
from .screenshot_review import VERSION, POLICY

def create_regeneration(studio, owner, payload):
    package=payload.package
    if package.get('contract')!=VERSION or package.get('batch')!='chat-screenshot-review-regen' or package.get('synthetic') is not True:
        raise ValueError('请选择有效的 B 合成数据重生成包')
    jobs=package.get('jobs',[])
    if not isinstance(jobs,list) or not 1 <= len(jobs) <= 10000 or len({j['item_id'] for j in jobs})!=len(jobs):
        raise ValueError('重生成任务清单为空或重复')
    job=next((j for j in jobs if j['item_id']==payload.item_id),None)
    if not job or job.get('synthetic') is not True or not job.get('instruction','').strip():
        raise ValueError('任务不存在、缺少合成标记或总指令')
    dialogue=job.get('corrected_dialogue')
    if not isinstance(dialogue,list) or not dialogue:
        raise ValueError('修正后的对话为空')
    deleted=set(job.get('must_delete_message_ids',[]))
    if any(str(m.get('id')) in deleted for m in dialogue):
        raise ValueError('修正对话仍含要求删除的消息')
    messages=[]
    for index,m in enumerate(dialogue):
        text=m.get('text',m.get('content')) or '[非文本消息，详见保留的多模态字段]'
        messages.append(Message(id=str(m.get('id','m'+str(index+1))),speaker=str(m.get('speaker',m.get('sender_id',m.get('speaker_id','unknown')))),
                                text=text,timestamp=m.get('timestamp',m.get('time')),origin_type='synthetic_completion'))
    fingerprint=digest(package)
    content=Content(title='修正包来源 '+job['item_id'],kind='synthetic',source_text=job.get('judgment_excerpt',''),
                    messages=messages,source_refs=[dict(reference=job.get('source_ref'),package_sha256=fingerprint)],
                    metadata=dict(regeneration_package=package,regeneration_item=job['item_id'],fact_policy=POLICY,synthetic=True))
    # An immutable revision captures only package input. Live panel comments are never read.
    source=studio.review.create(owner,SampleCreate(dataset='regeneration-input',content=content,note='由导出的 B 修正包建立生成输入',
                                                   idempotency_key='regen-source:'+fingerprint+':'+job['item_id']))
    return studio.create_batch(owner,BatchCreate(name=payload.name,dataset='regenerated-synthetic',source_sample_id=source['sample']['id'],
                                                source_revision=source['sample']['revision'],prompt_id=payload.prompt_id,model_id=payload.model_id,
                                                count=1,use_review_feedback=False,constraints=POLICY+'\n'+job['instruction']+'\n'+job.get('review_constraints',''),
                                                idempotency_key=payload.idempotency_key))
