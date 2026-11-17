"""Review Desk owns revisions, drafts, quality records and quality prompts."""
from .contracts import *
from .store import Conflict
from .renderer import verified
from .geometry import canonical, validate as validate_layout
from .bindings import current_binding, gold_digest

class ReviewDesk:
    def __init__(self, store):
        self.store = store

    def sample(self, owner, id, db=None):
        return self.store.get('review.sample',id,owner,db)

    def revision(self, owner, id, number, db=None):
        self.sample(owner,id,db)
        return self.store.get('review.revision',id+':'+str(number),owner,db)

    def detail(self, owner, id):
        s = self.sample(owner,id)
        rev=self.revision(owner,id,s['revision'])
        try: binding,_=current_binding(self.store,owner,s,rev)
        except (Conflict,ValueError): binding=None
        qualities=self.store.list('review.quality',owner,field='sample_id',value=id)
        for q in qualities:
            q['input_scope_status']='legacy_scope_ambiguous' if q['method']=='model' and q.get('coverage') in ['visual','multimodal'] and (q.get('binding') or {}).get('visual_role')=='synthetic_render' and q.get('input_contract_version')!='quality-input.v2' else 'explicit' if q.get('input_contract_version')=='quality-input.v2' else 'not_applicable'
            q['binding_status']='current' if binding and (q.get('binding') or {}).get('sha256')==binding['sha256'] else 'legacy_unbound' if not q.get('binding') else 'stale'
        batch=self.store.optional('studio.batch',s.get('batch_id') or '',owner)
        generation_feedback=[]
        for c in (batch or {}).get('review_feedback',[]):
            current=next((v for v in self.comment_rows(owner,c['sample_id']) if v['id']==c['id']),c)
            generation_feedback.append(current)
        return dict(sample=s,revision=rev,binding=binding,generation_feedback=generation_feedback,
                    gold_certifications=self.store.list('review.gold',owner,field='sample_id',value=id),
                    comment_events=self.store.list('review.comment.event',owner,field='sample_id',value=id),
                    revisions=self.store.list('review.revision',owner,field='sample_id',value=id),
                    quality=qualities,
                    comments=self.comment_rows(owner,id),
                    jobs=self.store.jobs(owner,sample_id=id))

    def list_samples(self, owner):
        return self.store.list('review.sample',owner)

    def validate_assets(self, owner, content, db):
        for asset in content.get('original_assets',[]):
            saved = self.store.get('review.asset',asset.get('id',''),owner,db)
            verified(self.store.root,saved)

    def _revision(self, db, owner, sample, content, params, note, editor, layout=None):
        self.validate_assets(owner,content,db)
        content=dict(content,original_assets=[self.store.get('review.asset',a['id'],owner,db) for a in content['original_assets']])
        old = self.revision(owner,sample['id'],sample['revision'],db) if sample.get('revision') else None
        if old and old['content']['kind']=='original':
            for field in ['kind','source_text','source_refs','original_assets']:
                if ([(a['id'],a['sha256']) for a in content[field]] if field=='original_assets' else content[field]) != ([(a['id'],a['sha256']) for a in old['content'][field]] if field=='original_assets' else old['content'][field]):
                    raise Conflict('真实原件、来源原文和原始引用不可覆盖，请编辑转录或另建派生样本')
        invalidated=[]
        if old:
            previous={q['id']:q for q in old['content']['questions']}
            questions=[]
            for q in content['questions']:
                before=previous.get(q['id'])
                if before and gold_digest(old['content'],before)!=gold_digest(content,q):
                    q=dict(q,gold=False);invalidated.append(q['id'])
                questions.append(q)
            content=dict(content,questions=questions)
            if old['content']['messages']!=content['messages'] and content.get('visual_role','auto') in ['auto','original'] and content['original_assets']:
                content['visual_role']='transcription_overlay' if layout and any(p['boxes'] for p in layout) else 'synthetic_render'
        number = sample.get('revision',0)+1
        layout=validate_layout(layout or [],content)
        diff = {key:dict(before=old['content'].get(key) if old else None,after=value) for key,value in content.items() if not old or old['content'].get(key)!=value}
        revision = dict(id=sample['id']+':'+str(number),sample_id=sample['id'],number=number,
                        parent=number-1 or None,content=content,content_hash=digest(content),diff=diff,
                        note=note,editor=editor,created_at=now(),render=params,renderer_version=RENDERER,
                        invalidated_gold=invalidated,layout=layout,layout_hash=digest(layout),layout_diff=dict(before=old.get('layout',[]) if old else [],after=layout))
        self.store.put('review.revision',revision,owner,db,immutable=True)
        job = self.store.enqueue(db,owner,'render',dict(sample_id=sample['id'],revision=revision,render=params,
                                 idempotency_digest=digest([sample['id'],number,RENDERER,params,layout])))
        sample.update(revision=number,title=content['title'],category=content['category'],tags=content['tags'],
                      language=content['language'],platform=content['platform'],updated_at=now(),
                      status='needs_review',render_job_id=job['id'])
        self.store.put('review.sample',sample,owner,db)
        if old:
            quality = dict(id=uid('quality'),sample_id=sample['id'],revision=number,method='correction',
                           verdict='pending',score=None,dimensions={},findings='纠正已保存；旧版审核与金标须复核。',
                           suggestions=note,process=dumps(dict(fields=diff,layout=revision['layout_diff'])),editor=editor,created_at=now(),supersedes=None)
            self.store.put('review.quality',quality,owner,db,immutable=True)
        return dict(sample=sample,revision=revision,job_id=job['id'])

    def create(self, owner, payload, *, batch_id=None, prompt_id=None, db=None):
        data = payload.model_dump()
        def action(conn):
            sample = dict(id=uid('sample'),dataset=payload.dataset,batch_id=batch_id,prompt_id=prompt_id,
                          revision=0,published_manifest=None,created_at=now())
            return self._revision(conn,owner,sample,data['content'],data['render'],payload.note,owner,data['layout'])
        if db is not None:
            return action(db)
        with self.store.tx() as conn:
            return self.store.idem(conn,owner,'sample.create',payload.idempotency_key,data,lambda:action(conn))

    def edit(self, owner, id, payload):
        data = payload.model_dump()
        with self.store.tx() as db:
            def action():
                sample = self.sample(owner,id,db)
                if sample['revision']!=payload.expected_revision:
                    raise Conflict('样本已有新版本；已保留双方内容，请合并后再保存')
                old=self.revision(owner,id,sample['revision'],db)
                manifest=self.store.optional('review.manifest',sample.get('published_manifest') or '',owner,db)
                current=canonical(manifest['pages'],{m['id'] for m in old['content']['messages']}) if manifest and manifest['revision']==sample['revision'] else old.get('layout',[])
                layout=current if payload.layout is None else canonical(data['layout'])
                if payload.layout is not None and layout!=current:
                    if not payload.coordinates_unlocked:
                        raise Conflict('坐标处于锁定状态；请先取消勾选锁定坐标')
                    if not manifest or payload.layout_manifest_id!=manifest['id']:
                        raise Conflict('坐标对应的图片版本已变化，请基于当前图片重新调整')
                    if manifest['revision']!=sample['revision']:
                        job=self.store.job(sample['render_job_id'],owner,db)
                        if job['status'] not in ['failed','cancelled'] or not old.get('layout'):
                            raise Conflict('当前版本还在渲染，暂时不能调整旧图坐标')
                    if [(p['page'],p['width'],p['height'],[b['message_id'] for b in p['boxes']]) for p in layout]!=[(p['page'],p['width'],p['height'],[b['message_id'] for b in p['boxes']]) for p in current]:
                        raise Conflict('手动调整只能移动或缩放现有消息框，不能替换页面或消息映射')
                ids={m['id'] for m in data['content']['messages']}
                layout=canonical(layout,ids)
                return self._revision(db,owner,sample,data['content'],data['render'],payload.note,owner,layout)
            return self.store.idem(db,owner,'sample.edit:'+id,payload.idempotency_key,data,action)

    def upgrade_renderer(self, owner, id, payload):
        with self.store.tx() as db:
            def action():
                sample=self.sample(owner,id,db)
                if sample['revision']!=payload.expected_revision:
                    raise Conflict('样本已有新版本，请刷新后核对排版')
                old=self.revision(owner,id,sample['revision'],db)
                previous=old.get('renderer_version','pillow-chat.v3')
                if previous==RENDERER: raise Conflict('当前版本已采用新版排版')
                if previous!='pillow-chat.v3': raise Conflict('不支持自动升级此排版版本')
                _,manifest=current_binding(self.store,owner,sample,old,db)
                if manifest.get('visual_role') not in ['synthetic_render','transcription_overlay']:
                    raise Conflict('原始图片不进行排版升级；请保留原件')
                return self._revision(db,owner,sample,old['content'],old['render'],
                    '显式升级排版 '+previous+' → '+RENDERER+'；文字不变，旧图片及审核发布记录保留，新版需重新审核',
                    owner,old.get('layout',[]))
            return self.store.idem(db,owner,'renderer.upgrade:'+id,payload.idempotency_key,payload.model_dump(),action)

    def use_original(self,owner,id,expected_revision,layout,geometry_hash,key):
        with self.store.tx() as db:
            def action():
                sample=self.sample(owner,id,db)
                if sample['revision']!=expected_revision: raise Conflict('样本已有新版本，请重新核对原图')
                revision=self.revision(owner,id,expected_revision,db)
                content=dict(revision['content'],visual_role='original',original_layout=layout)
                content['metadata']=dict(content.get('metadata',{}),original_geometry_hash=geometry_hash)
                return self._revision(db,owner,sample,content,revision['render'],'接入已核验导入原图与坐标；旧版本保留',owner,layout)
            return self.store.idem(db,owner,'restore.original:'+id,key,dict(expected_revision=expected_revision,geometry_hash=geometry_hash),action)

    def comment(self, owner, id, payload):
        data=payload.model_dump(mode='json')
        with self.store.tx() as db:
            def action():
                revision=self.revision(owner,id,payload.revision,db)
                message=next((m for m in revision['content']['messages'] if m['id']==payload.message_id),None)
                if payload.message_id and not message:
                    raise ValueError('评论引用了不存在的消息')
                if not payload.body.strip():
                    raise ValueError('评论不能为空')
                if payload.manifest_id:
                    manifest=self.store.get('review.manifest',payload.manifest_id,owner,db)
                    if manifest['sample_id']!=id or manifest['revision']!=payload.revision:
                        raise Conflict('评论图片与样本版本不一致')
                    if payload.page is not None and not any(p['page']==payload.page and any(b['message_id']==payload.message_id and (payload.bbox is None or list(payload.bbox)==b['bbox']) for b in p['boxes']) for p in manifest['pages']):
                        raise Conflict('评论消息框与图片映射不一致')
                if payload.supersedes:
                    old=self.store.get('review.comment',payload.supersedes,owner,db)
                    if old['sample_id']!=id or old['revision']!=payload.revision or old['message_id']!=payload.message_id:
                        raise Conflict('只能修订同一样本版本和消息的评论')
                    if any(c.get('supersedes')==old['id'] for c in self.store.list('review.comment',owner,db,field='sample_id',value=id)):
                        raise Conflict('评论已有新修订')
                row=dict(id=uid('comment'),sample_id=id,**data,editor=owner,created_at=now(),
                         content_hash=revision['content_hash'],message_snapshot=message)
                row.pop('idempotency_key')
                previous_quality=None
                if payload.supersedes:
                    previous_quality=next((q for q in self.active_quality(owner,db) if q.get('comment_id')==old['id']),None)
                quality=dict(id=uid('quality'),sample_id=id,revision=payload.revision,method='comment',verdict='pending',score=None,
                             dimensions={},findings='审核评论',suggestions=payload.body,process='独立评论；未修改样本文本或坐标',
                             editor=owner,created_at=row['created_at'],comment_id=row['id'],supersedes=previous_quality['id'] if previous_quality else None)
                row['quality_id']=quality['id']
                self.store.put('review.comment',row,owner,db,immutable=True)
                self.store.put('review.quality',quality,owner,db,immutable=True)
                return row
            return self.store.idem(db,owner,'comment:'+id,payload.idempotency_key,data,action)

    def comment_rows(self, owner, id, db=None):
        rows=self.store.list('review.comment',owner,db,field='sample_id',value=id)
        events=self.store.list('review.comment.event',owner,db,field='sample_id',value=id)
        latest={}
        for e in events: latest.setdefault(e['comment_id'],e)
        replaced={c.get('supersedes') for c in rows}
        return [dict(c,state='superseded' if c['id'] in replaced else latest.get(c['id'],{}).get('status','open'),
                     state_event_id=latest.get(c['id'],{}).get('id'),processing=latest.get(c['id'])) for c in rows]

    def process_comment(self, owner, id, comment_id, payload):
        with self.store.tx() as db:
            def action():
                self.sample(owner,id,db)
                comment=next((c for c in self.comment_rows(owner,id,db) if c['id']==comment_id),None)
                if not comment: raise KeyError('Comment not found')
                if comment['state']=='superseded': raise Conflict('评论已被修订，请处理新评论')
                if comment['state_event_id']!=payload.expected_event_id: raise Conflict('评论处理状态已有变化，请刷新后重试')
                candidate=None
                if payload.candidate_sample_id:
                    if not payload.candidate_revision: raise ValueError('验证候选需要明确版本')
                    candidate=self.revision(owner,payload.candidate_sample_id,payload.candidate_revision,db)
                    sample=self.sample(owner,payload.candidate_sample_id,db)
                    batch=self.store.optional('studio.batch',sample.get('batch_id') or '',owner,db)
                    if not batch or comment_id not in [c['id'] for c in batch.get('review_feedback',[])]: raise Conflict('该候选的生成快照未采用这条评论')
                row=dict(id=uid('comment_event'),sample_id=id,comment_id=comment_id,**payload.model_dump(),
                         editor=owner,created_at=now(),verification='human' if candidate else 'manual_disposition',
                         candidate_content_hash=candidate['content_hash'] if candidate else None)
                row.pop('idempotency_key')
                previous_quality=next((q for q in self.active_quality(owner,db) if q.get('comment_id')==comment_id),None)
                quality=dict(id=uid('quality'),sample_id=id,revision=comment['revision'],method='comment',verdict='pending',score=None,dimensions={},findings='评论处理：'+payload.status,suggestions=payload.reason,process=dumps(row),comment_id=comment_id,comment_state=payload.status,editor=owner,created_at=row['created_at'],supersedes=previous_quality['id'] if previous_quality else None)
                row['quality_id']=quality['id']
                self.store.put('review.quality',quality,owner,db,immutable=True)
                self.store.put('review.comment.event',row,owner,db,immutable=True)
                return row
            return self.store.idem(db,owner,'comment.process:'+comment_id,payload.idempotency_key,payload.model_dump(),action)

    def feedback(self, owner, sample_ids):
        result=[]
        for id in set(sample_ids):
            current=self.sample(owner,id)['revision']
            result.extend(c for c in self.comment_rows(owner,id) if c['state'] in ['open','adopted'] and c['use_for_generation'] and (c.get('applicability','revision')=='source' or c['revision']==current))
        return result

    def save_draft(self, owner, id, payload):
        key = id+':'+owner
        with self.store.tx() as db:
            s = self.sample(owner,id,db)
            previous = self.store.optional('review.draft',key,owner,db)
            if s['revision']!=payload.base_revision or (previous or {}).get('version',0)!=payload.expected_version:
                raise Conflict('草稿或样本已更新；保留本地草稿，请对照服务器版本合并')
            row = dict(id=key,sample_id=id,**payload.model_dump(),version=payload.expected_version+1,updated_at=now())
            self.store.put('review.draft',row,owner,db)
            return row

    def prompts(self, owner, purpose):
        return self.store.list(purpose+'.prompt',owner)

    def prompt(self, owner, purpose, id, db=None):
        return self.store.get(purpose+'.prompt',id,owner,db)

    def save_prompt(self, owner, purpose, payload):
        data = payload.model_dump()
        with self.store.tx() as db:
            def action():
                history = [p for p in self.store.list(purpose+'.prompt',owner,db) if p['name']==payload.name]
                latest = max(history,key=lambda p:p['version']) if history else None
                if (latest or {}).get('version',0)!=payload.expected_version:
                    raise Conflict('Prompt 已有新版本；刷新历史后再保存')
                if payload.based_on_id:
                    based=self.prompt(owner,purpose,payload.based_on_id,db)
                    if based['name']!=payload.name: raise Conflict('参考Prompt不属于当前名称')
                for id in payload.feedback_ids:
                    self.store.get('review.quality',id,owner,db)
                row = dict(id=uid('prompt'),purpose=purpose,**data,version=payload.expected_version+1,
                           parent_id=latest['id'] if latest else None,created_at=now(),editor=owner,
                           sha256=digest(payload.markdown))
                row.pop('idempotency_key')
                self.store.put(purpose+'.prompt',row,owner,db,immutable=True)
                return row
            return self.store.idem(db,owner,purpose+'.prompt',payload.idempotency_key,data,action)

    def prompt_markdown(self, owner, purpose, name):
        rows = sorted([p for p in self.prompts(owner,purpose) if p['name']==name],key=lambda p:p['version'])
        return '\n\n---\n\n'.join('# '+p['name']+' · v'+str(p['version'])+'\n\n'+p['markdown']+
            '\n\n## 修改意见与依据\n\n'+p['note']+'\n\n- 时间：'+p['created_at']+
            '\n- 父版本：'+str(p['parent_id'])+'\n- 质量记录：'+', '.join(p['feedback_ids'])+'\n- SHA256：'+p['sha256'] for p in rows)

    def quality(self, owner, id, payload):
        data = payload.model_dump()
        with self.store.tx() as db:
            def action():
                sample=self.sample(owner,id,db)
                revision=self.revision(owner,id,payload.revision,db)
                if payload.content_hash and payload.content_hash!=revision['content_hash']: raise Conflict('审核文本已变化')
                binding=None
                if payload.review_scope in ['visual','both']:
                    if payload.verdict=='pass' and not payload.manifest_id: raise Conflict('图片通过必须明确确认当前图片版本')
                    if payload.manifest_id: binding,_=current_binding(self.store,owner,sample,revision,db,payload.manifest_id)
                if payload.supersedes:
                    old=self.store.get('review.quality',payload.supersedes,owner,db)
                    if old['sample_id']!=id or old['revision']!=payload.revision: raise Conflict('只能修订同一样本版本的质量记录')
                    if any(q.get('supersedes')==old['id'] for q in self.store.list('review.quality',owner,db)): raise Conflict('这条质量记录已有修订')
                protocol=dict(method='human',rubric_id=payload.rubric_id,coverage=payload.review_scope)
                row=dict(id=uid('quality'),sample_id=id,method='human',**data,binding=binding,
                         protocol=protocol,protocol_id=digest(protocol),editor=owner,created_at=now())
                row.pop('idempotency_key')
                if payload.confirm_gold:
                    if payload.verdict!='pass' or payload.review_scope!='both' or not binding: raise Conflict('金标确认需要文本与当前图片均人工通过')
                    for q in revision['content']['questions']:
                        if q['gold']:
                            cert=dict(id=uid('gold'),sample_id=id,revision=payload.revision,question_id=q['id'],
                                      question_hash=gold_digest(revision['content'],q),binding=binding,quality_id=row['id'],editor=owner,created_at=now())
                            self.store.put('review.gold',cert,owner,db,immutable=True)
                self.store.put('review.quality',row,owner,db,immutable=True)
                if sample['revision']==payload.revision:
                    approved=payload.verdict=='pass' and payload.review_scope=='both' and binding
                    sample['status']='approved' if approved else {'pass':'needs_review','revise':'needs_revision','reject':'rejected','pending':'needs_review'}[payload.verdict]
                    self.store.put('review.sample',sample,owner,db)
                return row
            return self.store.idem(db,owner,'quality:'+id,payload.idempotency_key,data,action)

    def queue_quality(self, owner, id, payload, model_snapshot):
        with self.store.tx() as db:
            data=payload.model_dump()
            def action():
                revision=self.revision(owner,id,payload.revision,db)
                prompt=self.prompt(owner,'review',payload.prompt_id,db)
                binding=None;manifest=None
                if payload.coverage!='text':
                    if not model_snapshot['supports_vision']: raise ValueError('视觉评估需要支持图片的模型')
                    if not payload.manifest_id: raise Conflict('请先选择当前图片版本')
                    binding,manifest=current_binding(self.store,owner,self.sample(owner,id,db),revision,db,payload.manifest_id)
                from .quality_inputs import VERSION,freeze_input
                review_input=freeze_input(revision,manifest,payload.coverage)
                protocol=dict(method='model',input_contract_version=VERSION,coverage=payload.coverage,prompt_hash=prompt['sha256'],model={k:model_snapshot[k] for k in ['config_id','endpoint','model','parameters']},timeout_policy=model_snapshot.get('timeout_policy'))
                return self.store.enqueue(db,owner,'quality',dict(sample_id=id,revision=revision,prompt=prompt,model=model_snapshot,
                        coverage=payload.coverage,input_contract_version=VERSION,review_input=review_input,binding=binding,manifest=manifest,protocol=protocol,protocol_id=digest(protocol)))
            return self.store.idem(db,owner,'quality.run:'+id,payload.idempotency_key,data,action)

    def active_quality(self, owner, db=None):
        rows = self.store.list('review.quality',owner,db)
        superseded = {q.get('supersedes') for q in rows}
        return [q for q in rows if q['id'] not in superseded]

    def create_release(self, owner, payload):
        with self.store.tx() as db:
            def action():
                entries=[]
                for id in dict.fromkeys(payload.sample_ids):
                    sample=self.sample(owner,id,db);revision=self.revision(owner,id,sample['revision'],db)
                    binding,manifest=current_binding(self.store,owner,sample,revision,db)
                    qualities=[q for q in self.active_quality(owner,db) if q['sample_id']==id and q['revision']==sample['revision'] and q['method']=='human']
                    latest=max(qualities,key=lambda q:q['created_at']) if qualities else None
                    if not latest or latest['verdict']!='pass' or latest.get('review_scope')!='both' or (latest.get('binding') or {}).get('sha256')!=binding['sha256']:
                        raise Conflict('发布需要当前文本和图片绑定的人工审核通过：'+sample['title'])
                    certs=[]
                    for q in revision['content']['questions']:
                        if not q['gold']: continue
                        candidates=[c for c in self.store.list('review.gold',owner,db,field='sample_id',value=id) if c['revision']==sample['revision'] and c['question_id']==q['id'] and c['question_hash']==gold_digest(revision['content'],q) and c['binding']['sha256']==binding['sha256'] and c['quality_id']==latest['id']]
                        if not candidates: raise Conflict('题目金标需在当前审核中明确重新确认：'+q['id'])
                        certs.append(candidates[0])
                    entries.append(dict(sample_id=id,dataset=sample['dataset'],batch_id=sample.get('batch_id'),revision=revision,
                                        manifest=manifest,binding=binding,quality_id=latest['id'],quality_snapshot=latest,gold_certifications=certs))
                row=dict(id=uid('release'),name=payload.name,created_at=now(),created_by=owner,contract='research.v2',entries=entries)
                row['sha256']=digest(entries)
                self.store.put('review.release',row,owner,db,immutable=True)
                return row
            return self.store.idem(db,owner,'release',payload.idempotency_key,payload.model_dump(),action)

    def releases(self, owner):
        return self.store.list('review.release',owner)

    def release(self, owner, id):
        return self.store.get('review.release',id,owner)

    def comparison(self, owner):
        """Descriptive cohorts: never pool judge protocols or repaired and initial outputs."""
        samples=self.list_samples(owner);qualities=self.active_quality(owner);groups={}
        jobs=[self.store.job(j['id'],owner) for j in self.store.jobs(owner) if j['kind']=='quality']
        for s in samples:
            for stage,number in [('initial',1)]+([('revised',s['revision'])] if s['revision']>1 else []):
                current=[q for q in qualities if q['sample_id']==s['id'] and q['revision']==number and q['method'] in ['human','model']]
                attempts=[j for j in jobs if j['payload']['sample_id']==s['id'] and j['payload']['revision']['number']==number]
                protocols=({q.get('protocol_id','legacy_unbound') for q in current} | {j['payload'].get('protocol_id','legacy_unbound') for j in attempts}) or {'unreviewed'}
                for protocol in protocols:
                    key=(s.get('batch_id') or 'imported',s.get('prompt_id') or 'none',stage,protocol)
                    items=[q for q in current if q.get('protocol_id','legacy_unbound')==protocol]
                    q=max(items,key=lambda q:q['created_at']) if items else None
                    g=groups.setdefault(key,dict(batch_id=key[0],prompt_id=key[1],stage=stage,protocol_id=protocol,
                         protocol=(q or {}).get('protocol') or next((j['payload'].get('protocol') for j in attempts if j['payload'].get('protocol_id','legacy_unbound')==protocol),None),quality_attempts=0,failed_attempts=0,unknown_attempts=0,samples=0,reviewed_samples=0,human=[],model=[],corrections=0,pass_count=0,revision_count=0,quality_ids=[],sample_ids=[]))
                    protocol_jobs=[j for j in attempts if j['payload'].get('protocol_id','legacy_unbound')==protocol]
                    g['quality_attempts']+=len(protocol_jobs);g['failed_attempts']+=sum(j['status'] in ['failed','cancelled'] for j in protocol_jobs);g['unknown_attempts']+=sum(j['status']=='unknown' for j in protocol_jobs)
                    g['samples']+=1;g['sample_ids'].append(s['id']);g['corrections']+=number-1
                    if q:
                        g['quality_ids'].append(q['id'])
                        if q.get('score') is not None: g[q['method']].append(q['score'])
                        if q['method']=='human':
                            g['reviewed_samples']+=1;g['pass_count']+=q['verdict']=='pass';g['revision_count']+=q['verdict']=='revise'
        result=[]
        for g in groups.values():
            for method in ['human','model']:
                scores=g.pop(method);g[method+'_scored']=len(scores);g[method+'_mean']=round(sum(scores)/len(scores),2) if scores else None
            g['human_pass_rate']=g['pass_count']/g['reviewed_samples'] if g['reviewed_samples'] else None
            g['sample_set_hash']=digest(sorted(g['sample_ids']))
            g['cohort_total']=sum((s.get('batch_id') or 'imported')==g['batch_id'] and (g['stage']=='initial' or s['revision']>1) for s in samples)
            g['coverage']=len(g['quality_ids'])/g['cohort_total'] if g['cohort_total'] else 0
            g['comparison_note']='仅同协议、同初稿/修订阶段、同样本集合可直接对比；人工修订不归因为生成Prompt改进'
            result.append(g)
        return result
