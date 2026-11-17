"""Durable, owner-scoped KIE -> reference association -> VQA pipelines.
Each remote unit owns one job. Local recovery never resends a saved/unknown request.
"""
import copy
import json
from collections import Counter, defaultdict
from .contracts import digest, dumps, now, uid
from .store import Conflict
from .renderer import verified
from .benchmark_import import blob
from .gateway import request_messages, error_view, ModelFailure
from . import benchmark_scoring as scoring
from . import audit

KIND = 'benchmark.pipeline'
NODE = 'benchmark.pipeline.node'
TERMINAL = {'response_received','service_failed','unknown','cancelled','blocked_upstream','blocked_no_match','invalid_input'}
FIELDS = ('timestamp','speaker','content','image','transfer','file')
PROTOCOL = 'benchmark-pipeline.A.v1'


def associate(roi, messages, width, height):
    """Legacy max association, not message-level detection. Never reads answer text."""
    try:
        roi = scoring.box(roi, width, height)
    except (TypeError, ValueError):
        return dict(status='invalid_geometry', best_iou=None, message_id=None)
    best, chosen, diagnostic = 0., None, None
    for m in messages:
        b = scoring.box(m['bbox'], width, height)
        inter = max(0., min(roi[2],b[2])-max(roi[0],b[0])) * max(0., min(roi[3],b[3])-max(roi[1],b[1]))
        ra, pa = (roi[2]-roi[0])*(roi[3]-roi[1]), (b[2]-b[0])*(b[3]-b[1])
        value = inter/(ra+pa-inter+1e-9)
        if value > best:
            best, chosen = value, m['id']
            diagnostic = dict(reference_coverage=inter/ra, prediction_reference_area_ratio=pa/ra,
                              purpose='granularity_diagnostic_only', parent_certified=False)
    status = 'no_message' if not messages else 'zero_overlap' if chosen is None else 'matched' if best >= .6 else 'below_threshold'
    return dict(status=status, best_iou=best, message_id=chosen, diagnostic=diagnostic,
                algorithm='association-iou.live.v1', threshold=.6, epsilon=1e-9)


def reference_valid(t):
    if t['answer_kind'] == 'kie':
        try:
            scoring.kie(t['target'], t['asset']['width'], t['asset']['height'])
            return True
        except (ValueError, TypeError, KeyError):
            return False
    if t['answer_kind'] == 'open_text':
        return isinstance(t.get('target'), str) and bool(t['target'].strip())
    result = scoring.field(t['answer_kind'], t.get('target'), None)
    return result['status'] not in {'invalid_reference','identity_dictionary_required','unscored'}


class Pipeline:
    def __init__(self, benchmark):
        self.benchmark, self.store, self.gateway = benchmark, benchmark.store, benchmark.gateway
        self._tasks = {}

    def rows(self, owner, pipeline_id, db=None, image_key=None):
        if db is None:
            with self.store.read() as conn:
                return self.rows(owner,pipeline_id,conn,image_key)
        sql = "SELECT body FROM records WHERE kind=? AND owner=? AND json_extract(body,'$.pipeline_id')=?"
        args = [NODE,owner,pipeline_id]
        if image_key:
            sql += " AND json_extract(body,'$.image_key')=?"; args.append(image_key)
        return [json.loads(r[0]) for r in db.execute(sql+' ORDER BY rowid',args)]

    def task(self,node,db=None):
        key=(node['owner'],node['task_bundle_id'])
        if key not in self._tasks:
            row=self.store.get('benchmark.pipeline.task',key[1],key[0],db)
            if row['sha256']!=node['task_bundle_sha256'] or digest(row['tasks'])!=row['sha256']:raise ValueError('冻结任务校验失败')
            if len(self._tasks)>=32:self._tasks.pop(next(iter(self._tasks)))
            self._tasks[key]={t['task_id']:t for t in row['tasks']}
        return self._tasks[key][node['task_id']]

    def _input(self,owner,node):
        row=self.store.get('benchmark.input',node['input_id'],owner)
        if digest(row['input'])!=node['input_hash']:raise ValueError('冻结输入校验失败')
        return row['input']

    def _prepare(self, owner, p, enforce_budget=True):
        d = self.benchmark.dataset(owner,p['dataset_id'])
        raw = self.benchmark.load(d['tasks'])
        by_id = {t['task_id']:t for t in raw if t.get('migration_record_type')!='review_note'}
        requested = p.get('task_ids') or [];images=p.get('image_names') or []
        if len(requested)!=len(set(requested)) or len(images)!=len(set(images)):
            raise ValueError('任务或样本重复')
        if sum([bool(p.get('all_tasks')),bool(requested),bool(images)])!=1:
            raise ValueError('请选择样本、明确任务或整个数据集中的一种范围')
        if images:
            known={t['image_name'] for t in by_id.values()}
            if any(name not in known for name in images):raise ValueError('样本不属于该数据集')
            chosen=[i for i,t in by_id.items() if t['image_name'] in set(images)]
            for name in images:
                if sum(by_id[i]['task_family']=='kie.extract' for i in chosen if by_id[i]['image_name']==name)!=1:
                    raise ValueError('样本完整评测需要且只能有一个KIE来源任务')
        else:chosen = list(by_id) if p.get('all_tasks') else requested
        if not chosen or any(i not in by_id for i in chosen):
            raise ValueError('任务范围为空或不属于该数据集')
        if p.get('iou_threshold',.6)!=.6:
            raise ValueError('A基线冻结IoU=0.6；新阈值须另建协议')
        release = self.store.get('benchmark.release',p['release_id'],owner) if p.get('release_id') else None
        if release and release['dataset_id']!=d['id']:
            raise ValueError('发布版本与数据集不一致')
        if p.get('mode')=='official_reviewed' and not release:
            raise ValueError('正式参考运行必须绑定人工发布版本')
        published = {e['task']['task_id']:e for e in release['entries']} if release else {}
        frozen = {};verified_assets=set()
        def freeze(t, implicit=False):
            a = published.get(t['task_id'],{}).get('annotation')
            if release and not implicit:
                if not a: raise ValueError('所选任务不属于该发布版本')
                t = published[t['task_id']]['task']
            if t['asset_status']=='candidate_identity_unverified' and (not p.get('allow_unverified_assets') or p.get('mode')=='official_reviewed'):
                raise ValueError('范围包含身份待核对补图；仅开发运行可显式允许，正式运行须先核对')
            asset_key=(t['asset']['path'],t['asset']['sha256'])
            if asset_key not in verified_assets:
                verified(self.store.root,t['asset']);verified_assets.add(asset_key)
            out = dict(task_id=t['task_id'],dataset_id=d['id'],image_name=t['image_name'],task_family=t['task_family'],
                       answer_kind=t['answer_kind'],label=t.get('source_label'),asset=copy.deepcopy(t['asset']),
                       asset_status=t['asset_status'],source_task_hash=digest(t),source_refs=t.get('source_refs') or [t.get('source_ref')],
                       question=a['question'] if a else t['question'],target=a['target'] if a else t['target'],
                       roi=a['bbox_xyxy'] if a else t.get('bbox_xyxy'),region_id=t.get('region_id'),
                       output_schema=t['output_schema'],annotation=a,reference_status='human_reviewed' if a and a['verdict']=='pass' else 'legacy_unverified',
                       allowed_values=t.get('allowed_values') or [],question_eligibility=(a or {}).get('question_eligibility','unverified'))
            out['reference_valid']=reference_valid(out)
            try:
                if out['region_id']:scoring.box(out['roi'],out['asset']['width'],out['asset']['height'])
                out['geometry_valid']=True
            except (ValueError,TypeError):out['geometry_valid']=False
            return out
        for i in chosen: frozen[i]=freeze(by_id[i])
        groups = defaultdict(list)
        for t in frozen.values(): groups[t['image_name']].append(t)
        kie_by_image = {t['image_name']:t for t in raw if t.get('task_family')=='kie.extract'}
        specs=[]
        for image, tasks in groups.items():
            if len({t['asset']['sha256'] for t in tasks})!=1:raise ValueError('同一逻辑图片混入不同字节版本，须分开规划')
            needs = any(t['task_family']=='kie.extract' or t['region_id'] for t in tasks)
            image_key = digest([owner,d['id'],d['tasks']['sha256'],image,tasks[0]['asset']['sha256'],'original_pixels.v1'])
            kie_task = next((t for t in tasks if t['task_family']=='kie.extract'),None)
            if needs and not kie_task:
                if image not in kie_by_image: raise ValueError('该图缺少KIE来源任务')
                kie_task=freeze(kie_by_image[image],True);tasks.append(kie_task)
            if needs:
                specs.append(dict(key=image_key+':kie',image_key=image_key,image_name=image,task_id=kie_task['task_id'],stage='kie',variant='kie_image',dependency=None))
            for t in tasks:
                if t['task_family']=='kie.extract': continue
                regional = bool(t['region_id'])
                specs.append(dict(key=image_key+':'+t['task_id'],image_key=image_key,image_name=image,task_id=t['task_id'],stage='vqa',
                                  variant='reference_guided_prediction' if regional else 'full_image',association_key=image_key+':'+digest([t['region_id'],t['roi']]) if regional else None,dependency=image_key+':kie' if regional else None))
                if regional and p.get('regional_controls'):
                    specs.append(dict(key=image_key+':'+t['task_id']+':control',image_key=image_key,image_name=image,task_id=t['task_id'],stage='vqa',variant='full_image_control',dependency=None))
        counts=dict(Counter(s['variant'] for s in specs))
        if enforce_budget and len(specs)>p['max_calls']: raise ValueError('最大调用预算不足：需要最多 '+str(len(specs))+' 次；关联和评分不计调用')
        prompts={}
        for family in ['kie','vqa']:
            if not any(s['stage']==family for s in specs): continue
            prompt=self.store.get('evaluation.task_prompt',p[family+'_prompt_id'],owner)
            if prompt['family']!=family: raise ValueError('Prompt类型不一致')
            prompts[family]=prompt
        return d, groups, specs, prompts, release, counts

    def preview(self, owner, p):
        d,groups,specs,prompts,release,counts=self._prepare(owner,p,False)
        result=dict(dataset_id=d['id'],images=len(groups),selected_tasks=len({s['task_id'] for s in specs}),selection_unit='sample' if p.get('image_names') else 'dataset' if p.get('all_tasks') else 'task',
                    planned_units=len(specs),maximum_calls=len(specs),variants=counts,protocol=PROTOCOL,
                    reference_guided=True,automatic_retries=0,concurrency=1,new_model_calls=0,
                    question_eligibility='unverified unless reviewed; full-image does not imply end-to-end',
                    warnings=['参考区域引导不能作为纯端到端成绩','所有失败/低IoU保留计划分母','费用依赖模型配置；未知不按零计'])
        result['plan_fingerprint']=digest([p,d['tasks']['sha256'],[(k,v['sha256']) for k,v in prompts.items()],release['sha256'] if release else None])
        with self.store.tx() as db:
            audit.emit(db,owner,'benchmark.pipeline.preview',KIND,d['id'],details=result,reason='预览静态任务/依赖和调用预算；未请求模型')
        return result

    def _full_input(self,t,variant):
        return dict(question=t['question'],task_type=t['task_family'],input_protocol='benchmark-input.v2',track=variant,
                    output_schema=t['output_schema'],images=[dict(**{k:t['asset'][k] for k in ['path','sha256','mime_type']},page=1)])

    def _put_input(self,owner,node,task_input,db):
        row=dict(id=node['id']+':input',pipeline_id=node['pipeline_id'],node_id=node['id'],image_key=node['image_key'],
                 input_scope='matched_message' if node['variant']=='reference_guided_prediction' else 'full_image',
                 reference_guided=node['variant']=='reference_guided_prediction',question_eligibility=self.task(node,db)['question_eligibility'],
                 recipe_version='benchmark-input.v2',input=task_input,input_hash=digest(task_input),created_at=now(),
                 match_id=node.get('match_id'),prediction_id=node.get('prediction_id'))
        self.store.put('benchmark.input',row,owner,db,immutable=True)
        node.update(input_id=row['id'],input_hash=row['input_hash'])

    def _queue(self,owner,node,db):
        job=self.store.enqueue(db,owner,'benchmark_pipeline',dict(pipeline_id=node['pipeline_id'],node_id=node['id']))
        node.update(job_id=job['id'],status='ready')
        self.store.put(NODE,node,owner,db)

    def create(self,owner,p):
        p=copy.deepcopy(p)
        if not p.get('image_names'):p.pop('image_names',None)  # Preserve pre-sample idempotency fingerprints.
        cached=self.store.cached(owner,'benchmark.pipeline.create',p['idempotency_key'],p)
        if cached: return cached
        d,groups,specs,prompts,release,counts=self._prepare(owner,p)
        with self.store.tx() as db:
            def action():
                model=self.gateway.freeze(owner,p['model_id'],vision=True,db=db)
                pipeline_id=uid('pipeline');ids={s['key']:uid('pnode') for s in specs};refs={}
                for name,tasks in groups.items():
                    bundle=dict(id=uid('ptasks'),pipeline_id=pipeline_id,image_name=name,tasks=tasks,sha256=digest(tasks),created_at=now())
                    self.store.put('benchmark.pipeline.task',bundle,owner,db,immutable=True);refs[name]=dict(id=bundle['id'],sha256=bundle['sha256'])
                manifest=blob(self.store,dumps(dict(dataset_id=d['id'],dataset_task_hash=d['tasks']['sha256'],image_tasks=refs,selected_task_ids=p.get('task_ids') or list({s['task_id'] for s in specs}))).encode())
                row=dict(id=pipeline_id,flow_id=pipeline_id,dataset_id=d['id'],name=p['name'],mode=p['mode'],protocol=PROTOCOL,
                         status='queued',created_at=now(),manifest=manifest,model=model,prompts=prompts,variants=counts,
                         association_planned_regions=len({s['association_key'] for s in specs if s.get('association_key')}),max_calls=p['max_calls'],reserved_calls=0,new_model_calls=0,planned_units=len(specs),images=len(groups),
                         release_id=release['id'] if release else None,release_hash=release['sha256'] if release else None,
                         selection_unit='sample' if p.get('image_names') else 'dataset' if p.get('all_tasks') else 'task',selected_image_names=list(groups),parent_pipeline_id=None,automatic_retries=0,concurrency=1,stop_reason=None,score_set_id=uid('scoreset'))
                row['plan_hash']=digest(row)
                self.store.put(KIND,row,owner,db)
                self.store.put('benchmark.scoreset',dict(id=row['score_set_id'],pipeline_id=pipeline_id,reference_manifest=manifest,
                               reason='首次冻结评分协议/参考/标签空间',scorer_version=scoring.VERSION,created_at=now(),overrides={}),owner,db,immutable=True)
                for s in specs:
                    node={k:v for k,v in s.items() if k not in ['key','dependency']}
                    node.update(id=ids[s['key']],pipeline_id=pipeline_id,flow_id=pipeline_id,owner=owner,task_bundle_id=refs[s['image_name']]['id'],task_bundle_sha256=refs[s['image_name']]['sha256'],
                                dependency_id=ids.get(s['dependency']),status='pending',created_at=now(),schema_status='pending',scoring_status='pending')
                    t=self.task(node,db)
                    node['title']=node['image_name']+' · '+('消息抽取' if node['stage']=='kie' else '区域引导问答' if node['dependency_id'] else '整图问答')
                    node.update(answer_kind=t['answer_kind'],label=t['label'],reference_valid=t['reference_valid'] and (node['variant']!='reference_guided_prediction' or t['geometry_valid']),reference_status=t['reference_status'])
                    if not node['dependency_id']:
                        self._put_input(owner,node,self._full_input(self.task(node,db),node['variant']),db)
                        self._queue(owner,node,db)
                    else: self.store.put(NODE,node,owner,db)
                return self.summary(row)
            return self.store.idem(db,owner,'benchmark.pipeline.create',p['idempotency_key'],p,action)

    @staticmethod
    def summary(row):
        return {k:v for k,v in row.items() if k not in ['model','prompts','manifest']} | dict(model_name=row.get('model',{}).get('name'))

    def _lease(self,owner,job,db):
        current=self.store.job(job['id'],owner,db)
        if current['lease_token']!=job.get('lease_token') or current['status']!='running': raise Conflict('Worker lease lost')
        return current

    def _refresh(self,owner,pipeline,db):
        states=Counter()
        pipeline['has_local_issues']=bool(db.execute("SELECT 1 FROM records WHERE kind=? AND owner=? AND json_extract(body,'$.pipeline_id')=? AND json_extract(body,'$.has_issue')=1 LIMIT 1",(NODE,owner,pipeline['id'])).fetchone())
        for r in db.execute("SELECT json_extract(body,'$.status'),count(*) FROM records WHERE kind=? AND owner=? AND json_extract(body,'$.pipeline_id')=? GROUP BY json_extract(body,'$.status')",(NODE,owner,pipeline['id'])):
            states[r[0]]=r[1]
        if not sum(states[k] for k in ['pending','ready','running']) and not pipeline.get('pending_local_jobs',0):
            if pipeline['status'] not in ['cancelled','aborted']:
                pipeline['status']='completed_with_issues' if any(states[k] for k in TERMINAL-{'response_received'}) or pipeline.get('has_local_issues') else 'completed'
            pipeline['finished_at']=now()
        elif pipeline['status'] not in ['cancelled','aborted']: pipeline['status']='running'
        pipeline['execution_counts']=dict(states)
        self.store.put(KIND,pipeline,owner,db)

    def _stop(self,owner,pipeline,db,reason,status='aborted'):
        pipeline.update(status=status,stop_reason=reason)
        for n in self.rows(owner,pipeline['id'],db):
            if n['status'] in ['pending','ready']:
                n.update(status='cancelled',reason=reason,finished_at=now());self.store.put(NODE,n,owner,db)
                if n.get('job_id'):
                    j=self.store.job(n['job_id'],owner,db);j.update(status='cancelled',cancel_requested=True);self.store.save_job(db,j)
            elif n['status']=='running' and n.get('job_id'):
                j=self.store.job(n['job_id'],owner,db);j['cancel_requested']=True;self.store.save_job(db,j)
        self._refresh(owner,pipeline,db)

    def stop(self,owner,id,p):
        with self.store.tx() as db:
            def action():
                row=self.store.get(KIND,id,owner,db)
                if row['status'] in ['queued','running']: self._stop(owner,row,db,p['reason'],'cancelled')
                return self.summary(row)
            return self.store.idem(db,owner,'benchmark.pipeline.stop:'+id,p['idempotency_key'],p,action)

    def _children(self,owner,pipeline,node,db,prediction=None):
        children=[n for n in self.rows(owner,pipeline['id'],db,node['image_key']) if n.get('dependency_id')==node['id']]
        matches={};stopped=pipeline['status'] in ['cancelled','aborted']
        for child in children:
            if child['status'] not in (['pending','blocked_upstream','cancelled'] if stopped else ['pending','blocked_upstream']):continue
            if prediction is None or not prediction['eligible_for_dependency']:
                child.update(status='cancelled' if stopped else 'blocked_upstream',reason='流程已停止；该题未发送' if stopped else 'KIE服务/结构/本地处理未提供有效预测',finished_at=now());self.store.put(NODE,child,owner,db);continue
            t=self.task(child,db);key=digest([t['region_id'],t['roi']])
            if key not in matches:
                data=prediction['parsed']
                match=associate(t['roi'],data['conversation'],t['asset']['width'],t['asset']['height'])
                match.update(id=prediction['id']+':'+key,pipeline_id=pipeline['id'],image_key=child['image_key'],region_id=t['region_id'],
                             prediction_id=prediction['id'],prediction_hash=prediction['parsed_sha256'],reference_geometry_hash=digest(t['roi']),reference_roi=t['roi'],
                             created_at=now(),reference_status=t['reference_status'])
                self.store.put('benchmark.match',match,owner,db,immutable=True);matches[key]=match
            match=matches[key];child.update(match_id=match['id'],prediction_id=prediction['id'])
            if match['status']!='matched':
                child.update(status='cancelled' if stopped else 'invalid_input' if match['status']=='invalid_geometry' else 'blocked_no_match',reason=('流程已停止；关联诊断：' if stopped else '')+match['status'],finished_at=now())
                self.store.put(NODE,child,owner,db);continue
            selected=next(m for m in prediction['parsed']['conversation'] if m['id']==match['message_id'])
            task_input=dict(question=t['question'],task_type=t['task_family'],input_protocol='benchmark-input.v2',track='vqa_matched_message',
                            output_schema=t['output_schema'],messages=[{k:selected.get(k) for k in ('id',)+FIELDS}])
            self._put_input(owner,child,task_input,db)
            if stopped:
                child.update(status='cancelled',reason='流程已停止；已冻结输入，未调用，可显式新建问答分支',finished_at=now());self.store.put(NODE,child,owner,db)
            else:
                child.pop('reason',None);child.pop('finished_at',None);self._queue(owner,child,db)

    def _score(self,owner,pipeline,node,attempt,db,score_set=None,task=None):
        t=task or self.task(node,db);sid=score_set or pipeline['score_set_id'];id=node['id']+':'+sid
        if task is None:
            ss=self.store.get('benchmark.scoreset',sid,owner,db);override=ss.get('reference_overrides',{}).get(node['id'])
            if override:
                t=copy.deepcopy(t);t.update(target=override['target'],reference_valid=override['reference_valid'],reference_status='human_reviewed')
        if self.store.optional('benchmark.score',id,owner,db): return id
        try:
            result=scoring.score(t,attempt['response']['raw'],t['target'],t['asset']['width'],t['asset']['height'])
            if not t['reference_valid']: result=dict(result,score=None,status='invalid_reference')
            if attempt['response'].get('demo'): result=dict(result,score=None,status='unscored_demo')
        except Exception:
            raise  # Execution status must stay response_received on local scorer failure.
        row=dict(id=id,pipeline_id=pipeline['id'],run_id=pipeline['id'],node_id=node['id'],score_set_id=sid,attempt_id=attempt['id'],
                 dataset_id=pipeline['dataset_id'],task_id=node['task_id'],target=t['target'],target_hash=digest(t['target']),
                 reference_valid=t['reference_valid'],reference_status=t['reference_status'],allowed_values=t['allowed_values'],
                 annotation_id=(t.get('annotation') or {}).get('id'),answer_kind=t['answer_kind'],label=t['label'],variant=node['variant'],
                 scorer_version=scoring.VERSION,result=result,created_at=now())
        self.store.put('benchmark.score',row,owner,db,immutable=True)
        node['scoring_status']=result['status'];return id

    def _local(self,owner,pipeline,node,attempt,db):
        t=self.task(node,db)
        try:
            parsed=scoring.kie(attempt['response']['raw'],t['asset']['width'],t['asset']['height']) if node['stage']=='kie' else scoring.parse(attempt['response']['raw'])
            if node['stage']=='vqa' and 'answer' not in parsed: raise ValueError('缺少answer')
            node['schema_status']='valid';attempt['parsed']=parsed
        except (ValueError,TypeError,KeyError,OverflowError) as error:
            parsed=None;node['schema_status']='invalid';attempt['parsed']=None;node['validation_error']=str(error)
        if node['stage']=='kie':
            errors=[]
            if parsed is None:
                try:
                    raw=scoring.parse(attempt['response']['raw'])
                    for i,m in enumerate(raw.get('conversation',[])):
                        try: scoring.kie(dict(dialog_name=raw.get('dialog_name'),conversation=[m]),t['asset']['width'],t['asset']['height'])
                        except (ValueError,TypeError,KeyError) as e: errors.append(dict(message_index=i,reason=str(e)))
                except (ValueError,TypeError,KeyError): pass
            prediction=dict(id=node['id']+':prediction',pipeline_id=pipeline['id'],image_key=node['image_key'],node_id=node['id'],attempt_id=attempt['id'],
                            raw=dict(kind='benchmark.attempt',id=attempt['id'],sha256=digest(attempt['response'])),parsed=parsed,parsed_sha256=digest(parsed),
                            request_hash=attempt['request_hash'],parser_version='strict.v1',coordinate_protocol='original_pixels.v1',image_size=[t['asset']['width'],t['asset']['height']],
                            coordinate_derivations=[dict(message_id=m['id'],original=m['message_bbox'],normalized=m['bbox']) for m in (parsed or {}).get('conversation',[])],validation_errors=errors,
                            eligible_for_dependency=parsed is not None and not attempt['response'].get('demo'),created_at=attempt['finished_at'])
            self.store.put('benchmark.prediction',prediction,owner,db,immutable=True);node['prediction_id']=prediction['id']
            self._children(owner,pipeline,node,db,prediction)
        self._score(owner,pipeline,node,attempt,db)
        attempt.update(schema_status=node['schema_status'],scoring_status=node['scoring_status'])
        self.store.put('benchmark.attempt',attempt,owner,db)

    async def execute(self,worker,job,checkpoint,alive):
        owner=job['owner'];node=self.store.get(NODE,job['payload']['node_id'],owner)
        pipeline=self.store.get(KIND,node['pipeline_id'],owner)
        if node['status'] in TERMINAL and not node.get('local_error'): return
        await alive()
        attempt=self.store.optional('benchmark.attempt',node['id']+':attempt',owner)
        if not attempt:
            try:
                inp=self._input(owner,node);messages=request_messages(self.store,inp);messages[0]['content']=pipeline['prompts'][node['stage']]['markdown']
            except (OSError,ValueError):raise ModelFailure('source_file','冻结输入图片或产物校验失败；请先修复来源') from None
            with self.store.tx() as db:
                current=self._lease(owner,job,db);pipeline=self.store.get(KIND,pipeline['id'],owner,db)
                if current['cancel_requested'] or pipeline['status'] in ['cancelled','aborted']: return
                inflight=db.execute("SELECT 1 FROM records WHERE kind=? AND owner=? AND json_extract(body,'$.pipeline_id')=? AND json_extract(body,'$.status')='running' AND id!=? LIMIT 1",(NODE,owner,pipeline['id'],node['id'])).fetchone()
                if inflight:
                    import time
                    if current['phase']!='waiting_turn':audit.emit(db,owner,'benchmark.pipeline.waiting_turn',NODE,node['id'],event_key=node['id']+':waiting_turn',details=dict(pipeline_id=pipeline['id'],node_id=node['id']),reason='按冻结并发1等待上一请求结束')
                    current.update(status='queued',phase='waiting_turn',updated_at=now())
                    body={k:v for k,v in current.items() if k!='lease_token'}
                    db.execute('UPDATE jobs SET status=?,lease_until=?,body=? WHERE id=? AND lease_token=?',('queued',time.time()+.3,dumps(body),job['id'],job['lease_token']))
                    job['deferred']=True;return
                if pipeline['reserved_calls']>=pipeline['max_calls']:
                    self._stop(owner,pipeline,db,'调用预算耗尽，不再发送');return
                pipeline['reserved_calls']+=1
                if pipeline['model']['config_id']!='demo': pipeline['new_model_calls']+=1
                pipeline['status']='running';self.store.put(KIND,pipeline,owner,db)
                attempt=dict(id=node['id']+':attempt',pipeline_id=pipeline['id'],flow_id=pipeline['id'],node_id=node['id'],run_id=pipeline['id'],
                             dataset_id=pipeline['dataset_id'],task_id=node['task_id'],task_family=self.task(node)['task_family'],image_sha256=self.task(node)['asset']['sha256'],
                             request_id=uid('request'),request_hash=digest(messages),input_hash=node['input_hash'],status='calling_model',created_at=now())
                self.store.put('benchmark.attempt',attempt,owner,db)
                node.update(status='running',attempt_id=attempt['id']);self.store.put(NODE,node,owner,db)
                current['phase']='calling_model';self.store.save_job(db,current,job['lease_token'])
            try:
                response=await self.gateway.call(owner,pipeline['model'],messages,'benchmark_pipeline',attempt['request_id'])
                attempt.update(status='completed',response=response,finished_at=now())
                with self.store.tx() as db:
                    self._lease(owner,job,db);self.store.put('benchmark.attempt',attempt,owner,db)
            except ModelFailure as error:
                view=error_view(error);attempt.update(status='unknown' if view.get('unknown') else 'failed',error=view,finished_at=now())
                with self.store.tx() as db:
                    self._lease(owner,job,db);pipeline=self.store.get(KIND,pipeline['id'],owner,db)
                    self.store.put('benchmark.attempt',attempt,owner,db);node.update(status='unknown' if view.get('unknown') else 'service_failed',reason=view['message'],finished_at=now())
                    node['has_issue']=bool(node.get('local_error')) or node.get('schema_status')=='invalid'
                    self.store.put(NODE,node,owner,db);self._children(owner,pipeline,node,db)
                    billing_unknown=pipeline['model']['config_id']!='demo' and (view.get('evidence') or {}).get('cost_estimate') is None
                    if view.get('unknown') or view['category'] in ['auth','source_file'] or billing_unknown:
                        self._stop(owner,pipeline,db,view['message']+('；费用未确认，停止后续计费' if billing_unknown else ''))
                    self._refresh(owner,pipeline,db)
                raise
        elif attempt['status']=='calling_model':
            request=self.store.optional('evaluation.request',attempt['request_id'],owner)
            if request and request.get('input_hash')==attempt['request_hash'] and request.get('response') and request['status']=='completed' and request.get('model_snapshot')==pipeline['model']:
                attempt.update(status='completed',response=request['response'],finished_at=request['finished_at'],recovered_gateway_response=True)
                with self.store.tx() as db:
                    self._lease(owner,job,db);self.store.put('benchmark.attempt',attempt,owner,db)
            else:
                with self.store.tx() as db:
                    self._lease(owner,job,db);pipeline=self.store.get(KIND,pipeline['id'],owner,db)
                    attempt.update(status='unknown',finished_at=now());self.store.put('benchmark.attempt',attempt,owner,db)
                    node.update(status='unknown',reason='调用已开始但无可验证的保存响应；不自动重发',finished_at=now());self.store.put(NODE,node,owner,db)
                    self._children(owner,pipeline,node,db);self._stop(owner,pipeline,db,node['reason'])
                raise ModelFailure('unknown_outcome',node['reason'],False,True)
        if attempt['status']!='completed': return
        with self.store.tx() as db:
            self._lease(owner,job,db);pipeline=self.store.get(KIND,pipeline['id'],owner,db)
            node=self.store.get(NODE,node['id'],owner,db);recovering_local=node.get('local_processing') in ['queued','running'];node.update(status='response_received',finished_at=attempt['finished_at']);node.pop('local_error',None)
            try:
                # Savepoint prevents partial local fanout/score after an internal processing error.
                db.execute('SAVEPOINT pipeline_local')
                self._local(owner,pipeline,node,attempt,db)
                db.execute('RELEASE pipeline_local')
            except Exception as error:
                db.execute('ROLLBACK TO pipeline_local');db.execute('RELEASE pipeline_local')
                node['local_error']=error_view(error);pipeline['has_local_issues']=True
                self._children(owner,pipeline,node,db)
            if node['schema_status']=='invalid': pipeline['has_local_issues']=True
            node['local_processing']='failed' if node.get('local_error') else 'completed'
            if recovering_local:pipeline['pending_local_jobs']=max(0,pipeline.get('pending_local_jobs',0)-1)
            node['has_issue']=bool(node.get('local_error')) or node['schema_status']=='invalid'
            self.store.put(NODE,node,owner,db)
            response=attempt['response'];bill=pipeline['model'].get('billing') or {}
            known_usage=isinstance(response.get('usage'),dict) and all(isinstance(response['usage'].get(k),int) for k in ['prompt_tokens','completion_tokens'])
            if pipeline['model']['config_id']!='demo' and (not known_usage or response.get('cost_estimate') is None or any(bill.get(k) is None for k in ['input_token_price','output_token_price'])):
                self._stop(owner,pipeline,db,'本次费用/usage不完整，停止后续计费；不按零处理')
            self._refresh(owner,pipeline,db)
        await checkpoint('node',node['id'],'results_saved')

    def on_job_finish(self,job,status,error,db):
        owner=job['owner'];node=self.store.get(NODE,job['payload']['node_id'],owner,db)
        if node['status'] in TERMINAL:
            if node.get('local_processing') in ['queued','running']:
                pipeline=self.store.get(KIND,node['pipeline_id'],owner,db);pipeline['pending_local_jobs']=max(0,pipeline.get('pending_local_jobs',0)-1)
                node.update(local_processing='failed',local_error=error or dict(message='本地恢复被中断，可以再次零调用恢复'),has_issue=True)
                self.store.put(NODE,node,owner,db);self._refresh(owner,pipeline,db)
            return
        pipeline=self.store.get(KIND,node['pipeline_id'],owner,db)
        a=self.store.optional('benchmark.attempt',node['id']+':attempt',owner,db)
        if a and a.get('response'):
            node.update(status='response_received',local_error=error or dict(message='本地处理被中断，可零调用恢复'))
            pipeline['has_local_issues']=True
        elif a:
            node.update(status='unknown',reason='调用中断，结果/费用未知，不自动重发')
            a['status']='unknown';self.store.put('benchmark.attempt',a,owner,db)
        else: node.update(status='cancelled' if status in ['completed','cancelled'] else 'invalid_input',reason=(error or {}).get('message','未发送'))
        node['has_issue']=bool(node.get('local_error')) or node.get('schema_status')=='invalid'
        self.store.put(NODE,node,owner,db);self._children(owner,pipeline,node,db)
        if node['status']=='unknown' or (error or {}).get('category')=='source_file': self._stop(owner,pipeline,db,node.get('reason') or '来源校验失败')
        self._refresh(owner,pipeline,db)

    def list(self,owner):
        return [self.summary(r) for r in self.store.list(KIND,owner)]

    def detail(self,owner,id,offset=0,limit=30,image_key='',score_set_id=''):
        p=self.store.get(KIND,id,owner)
        if offset<0 or not 1<=limit<=100: raise ValueError('无效分页')
        sid=score_set_id or p['score_set_id'];ss=self.store.get('benchmark.scoreset',sid,owner)
        if ss['pipeline_id']!=id: raise ValueError('评分集合不属于本运行')
        with self.store.read() as db:
            rows=self.rows(owner,id,db,image_key) if image_key else None
            if rows is None:
                count=db.execute("SELECT count(*) FROM records WHERE kind=? AND owner=? AND json_extract(body,'$.pipeline_id')=?",(NODE,owner,id)).fetchone()[0]
                page=[json.loads(r[0]) for r in db.execute("SELECT body FROM records WHERE kind=? AND owner=? AND json_extract(body,'$.pipeline_id')=? ORDER BY rowid LIMIT ? OFFSET ?",(NODE,owner,id,limit,offset))]
            else: count=len(rows);page=rows[offset:offset+limit]
            items=[]
            for n in page:
                t=self.task(n);out={k:v for k,v in n.items() if k not in ['task_ref','input_ref','owner','task_bundle_id','task_bundle_sha256']}
                out.update(question=t['question'],answer_kind=t['answer_kind'],label=t['label'],reference_status=t['reference_status'],question_eligibility=t['question_eligibility'],
                           asset_id=t['asset']['id'],asset_width=t['asset']['width'],asset_height=t['asset']['height'])
                if n.get('match_id'): out['match']=self.store.get('benchmark.match',n['match_id'],owner,db)
                if n.get('attempt_id'):
                    a=self.store.get('benchmark.attempt',n['attempt_id'],owner,db)
                    out['attempt']={k:v for k,v in a.items() if k not in ['parsed','response']}
                    out['has_response']=bool(a.get('response'))
                scoreid=ss.get('overrides',{}).get(n['id'],n['id']+':'+sid)
                score=self.store.optional('benchmark.score',scoreid,owner,db)
                if score:out['score']=dict(id=score['id'],score_set_id=score['score_set_id'],reference_status=score['reference_status'],target_hash=score['target_hash'],scorer_version=score['scorer_version'],result={k:score['result'].get(k) for k in ['status','score','reason']})
                items.append(out)
        return dict(pipeline=self.summary(p),items=items,total=count,next_offset=offset+limit if offset+limit<count else None,
                    report=self.report(owner,id,sid),score_set_id=sid,
                    score_sets=[{k:v for k,v in r.items() if k not in ['overrides','reference_manifest']} for r in self.store.list('benchmark.scoreset',owner,field='pipeline_id',value=id)])

    def sample_results(self,owner,id,offset=0,limit=20):
        self.store.get(KIND,id,owner)
        if offset<0 or not 1<=limit<=100:raise ValueError('无效分页')
        with self.store.read() as db:
            where="kind=? AND owner=? AND json_extract(body,'$.pipeline_id')=?";args=[NODE,owner,id]
            total=db.execute("SELECT count(DISTINCT json_extract(body,'$.image_key')) FROM records WHERE "+where,args).fetchone()[0]
            keys=db.execute("SELECT json_extract(body,'$.image_key') AS image_key,json_extract(body,'$.image_name') AS name FROM records WHERE "+where+" GROUP BY image_key,name ORDER BY name,image_key LIMIT ? OFFSET ?",[*args,limit,offset]).fetchall()
            items=[]
            for key in keys:
                nodes=self.rows(owner,id,db,key['image_key']);stages={'kie':Counter(),'vqa':Counter()};regions={}
                for n in nodes:
                    stages[n['stage']][n['status']]+=1
                    region_key=n.get('association_key')
                    if not region_key and n['variant']=='reference_guided_prediction':
                        frozen=self.task(n,db);region_key=digest([frozen.get('region_id'),frozen.get('roi')])
                    if region_key:
                        m=self.store.get('benchmark.match',n['match_id'],owner,db) if n.get('match_id') else None
                        regions[region_key]=m['status'] if m else n['status']
                pending=any(n['status'] not in TERMINAL or n.get('local_processing') in ['queued','running'] for n in nodes)
                issue=any(n['status']!='response_received' or n.get('has_issue') for n in nodes)
                t=self.task(nodes[0],db)
                items.append(dict(image_key=key['image_key'],image_name=key['name'],asset_id=t['asset']['id'],planned_units=len(nodes),responded=sum(n['status']=='response_received' for n in nodes),
                    status='running' if pending else 'completed_with_issues' if issue else 'completed',
                    kie=dict(stages['kie']),vqa=dict(stages['vqa']),association=dict(Counter(regions.values())),planned_regions=len(regions)))
        return dict(items=items,total=total,next_offset=offset+limit if offset+limit<total else None)

    def node_detail(self,owner,id,node_id):
        self.store.get(KIND,id,owner);n=self.store.get(NODE,node_id,owner)
        if n['pipeline_id']!=id: raise KeyError('节点不属于本运行')
        t=self.task(n)
        prediction=self.store.optional('benchmark.prediction',n.get('prediction_id',''),owner)
        if prediction and prediction.get('parsed'):prediction=dict(prediction,output=prediction['parsed'])
        return dict(node=n,task=t,input=self._input(owner,n) if n.get('input_id') else None,
                    attempt=self.store.optional('benchmark.attempt',n.get('attempt_id',''),owner),
                    prediction=prediction,
                    supplemental_scores=[r for kind in ['benchmark.lawbench_score','benchmark.legalbench_score'] for r in self.store.list(kind,owner,field='pipeline_id',value=id) if r['attempt_id']==n.get('attempt_id')],
                    match=self.store.optional('benchmark.match',n.get('match_id',''),owner))

    def report(self,owner,id,score_set_id=''):
        p=self.store.get(KIND,id,owner);sid=score_set_id or p['score_set_id'];ss=self.store.get('benchmark.scoreset',sid,owner)
        if ss['pipeline_id']!=id: raise ValueError('评分集合不属于本运行')
        with self.store.read() as db:
            nodes=self.rows(owner,id,db)
            allscores=self.store.list('benchmark.score',owner,db,field='pipeline_id',value=id)
            scoremap={s['id']:s for s in allscores}
            attempts={a['id']:a for a in self.store.list('benchmark.attempt',owner,db,field='pipeline_id',value=id)}
            matches={m['id']:m for m in self.store.list('benchmark.match',owner,db,field='pipeline_id',value=id)}
            for match_id in {n.get('match_id') for n in nodes}-{None}:
                if match_id not in matches:matches[match_id]=self.store.get('benchmark.match',match_id,owner,db)
        groups={};cost=0.;latency=0.;unknown_cost=0;currencies=set();classification={}
        for n in nodes:
            t=n;group_key=n['variant']+' / '+(t['label'] or 'kie')
            g=groups.setdefault(group_key,dict(variant=n['variant'],field=t['label'] or 'kie',answer_kind=t['answer_kind'],
                    planned=0,reference_valid=0,reference_unverified=0,responded=0,response_ref=0,scored_ref=0,correct=0,pending_judgement=0,
                    execution={},score_sum=0.,scores=0,reference_guided=n['variant']=='reference_guided_prediction'))
            g['planned']+=1;g['execution'][n['status']]=g['execution'].get(n['status'],0)+1
            scoreid=ss.get('overrides',{}).get(n['id'],n['id']+':'+sid)
            sc=scoremap.get(scoreid)
            override=ss.get('reference_overrides',{}).get(n['id'],{})
            valid=sc['reference_valid'] if sc else override.get('reference_valid',t['reference_valid']);g['reference_valid']+=bool(valid)
            g['reference_unverified']+=(sc or override or t).get('reference_status')!='human_reviewed'
            if n['status']=='response_received':
                g['responded']+=1;g['response_ref']+=bool(valid)
                if valid and (not sc or sc['result'].get('score') is None):g['pending_judgement']+=1
            if sc and sc['result'].get('score') is not None and valid:
                score=sc['result']['score'];g['scores']+=1;g['score_sum']+=score;g['scored_ref']+=1;g['correct']+=score==1
                if t['answer_kind']=='categorical':
                    predicted=sc['result'].get('prediction',{}).get('answer')
                    c=classification.setdefault(group_key,dict(pairs=[],labels=set(sc['allowed_values'])))
                    c['pairs'].append((sc['target'],predicted if isinstance(predicted,str) and predicted in c['labels'] else '[invalid_output]'))
            if n.get('attempt_id'):
                a=attempts[n['attempt_id']];response=a.get('response') or (a.get('error') or {}).get('evidence') or {}
                if p['model']['config_id']!='demo':
                    price=response.get('cost_estimate')
                    if price is None:unknown_cost+=1
                    else:cost+=price
                    if response.get('cost_currency'):currencies.add(response['cost_currency'])
                latency+=response.get('latency_ms') or 0
        for g in groups.values():
            nr=g['reference_valid'];g['response_coverage']=g['responded']/g['planned'] if g['planned'] else None
            g['score_coverage']=g['scored_ref']/nr if nr else None
            binary=g['answer_kind'] not in ['kie','open_text']
            g['conditional_accuracy']=g['correct']/g['response_ref'] if binary and g['response_ref'] and not g['pending_judgement'] else None
            g['mean_scored']=g.pop('score_sum')/g['scores'] if g['scores'] else None
            g['binary_delivery_bounds']=[g['correct']/nr,(g['correct']+g['pending_judgement'])/nr] if binary and nr else None
            g['binary_correct_delivery']=g['correct']/nr if binary and nr and not g['pending_judgement'] and all(k in TERMINAL for k in g['execution']) else None
            g['quality_final']=bool(nr and not g['pending_judgement'] and all(k in TERMINAL for k in g['execution']))
        states=Counter(n['status'] for n in nodes);total=len(nodes);regions={}
        for n in nodes:
            if n.get('association_key'):
                regions[n['association_key']]=matches[n['match_id']]['status'] if n.get('match_id') else n['status']
        region_states=Counter(regions.values());region_total=p.get('association_planned_regions')
        association=dict(planned_regions=region_total,status_counts=dict(region_states),observed_match_regions=len(matches),matched_regions=region_states['matched'],
                         coverage=region_states['matched']/region_total if region_total else None,planned_attribute_questions=sum(n['variant']=='reference_guided_prediction' for n in nodes))
        return dict(planned_units=total,kie_images=sum(n['stage']=='kie' for n in nodes),vqa_planned=sum(n['stage']=='vqa' for n in nodes),
                    association=association,execution=dict(states),conserved=sum(states.values())==p['planned_units'],groups=list(groups.values()),score_set_id=sid,
                    classification={k:scoring.classification_report(v['pairs'],sorted(v['labels'])) for k,v in classification.items() if v['labels']},
                    cost=dict(known_estimate=cost if p['model']['config_id']!='demo' else None,unknown_requests=unknown_cost,
                              complete=unknown_cost==0 and p['model']['config_id']!='demo',currencies=sorted(currencies),call_reservations=p['reserved_calls'],confirmed_responses=sum(bool(a.get('response')) for a in attempts.values()),
                              estimated_latency_ms_total=latency,allocation='all requests in this branch; reused parent inputs have no new charge'),
                    ranking_enabled=False,notice='参考引导/未复核参考/量表分分别报告；运行成功不代表质量通过')

    def resume_local(self,owner,id,p):
        with self.store.tx() as db:
            def action():
                row=self.store.get(KIND,id,owner,db);chosen=set(p.get('node_ids') or [])
                nodes=[n for n in self.rows(owner,id,db) if n.get('local_error') and n.get('local_processing') not in ['queued','running'] and (not chosen or n['id'] in chosen)]
                if not nodes or chosen and chosen!={n['id'] for n in nodes}:raise ValueError('只能恢复已保存响应的本地失败阶段')
                for n in nodes:
                    a=self.store.get('benchmark.attempt',n['attempt_id'],owner,db)
                    if not a.get('response'):raise ValueError('没有保存响应，不能零调用恢复')
                    job=self.store.enqueue(db,owner,'benchmark_pipeline',dict(pipeline_id=id,node_id=n['id']))
                    n.update(job_id=job['id'],local_processing='queued');self.store.put(NODE,n,owner,db)
                row['pending_local_jobs']=row.get('pending_local_jobs',0)+len(nodes)
                if row['status'] not in ['cancelled','aborted']:
                    row.update(status='running',has_local_issues=False);row.pop('finished_at',None)
                self.store.put(KIND,row,owner,db)
                return self.summary(row)
            return self.store.idem(db,owner,'benchmark.pipeline.resume_local:'+id,p['idempotency_key'],p,action)

    def retry(self,owner,id,p):
        with self.store.tx() as db:
            def action():
                old=self.store.get(KIND,id,owner,db)
                if old['status'] in ['queued','running'] or old.get('pending_local_jobs',0):raise Conflict('原流程或本地恢复仍在执行')
                nodes=self.rows(owner,id,db);selected=set(p['node_ids']);byid={n['id']:n for n in nodes}
                if not selected or not selected<=byid.keys():raise ValueError('请选择本流程明确的失败节点')
                for i in selected:
                    n=byid[i]
                    if n['status']=='response_received' and n.get('local_error'):raise ValueError('本地失败应零调用恢复，不重新请求模型')
                    if n['status'] not in ['service_failed','unknown','cancelled','blocked_upstream','invalid_input'] and not (n['status']=='response_received' and n['schema_status']=='invalid'):
                        raise ValueError('成功或无匹配结果不能作为失败节点隐式重答')
                selected|={n['id'] for n in nodes if n.get('dependency_id') in selected}
                chosen=[n for n in nodes if n['id'] in selected]
                if len(chosen)>p['max_calls']:raise ValueError('新分支预算不足以覆盖所选失败和受影响后代')
                for n in chosen:
                    if n.get('dependency_id') not in selected and not n.get('input_id'):raise ValueError('必须先显式重试失败KIE，不能绕过缺失输入')
                pid=uid('pipeline');ids={n['id']:uid('pnode') for n in chosen};row=copy.deepcopy(old)
                row.update(selection_unit='failure_branch',selected_image_names=sorted({n['image_name'] for n in chosen}))
                row.update(id=pid,flow_id=pid,parent_pipeline_id=id,name=old['name']+' · 显式失败分支',status='queued',created_at=now(),planned_units=len(chosen),
                           images=len({n['image_key'] for n in chosen}),association_planned_regions=len({n['association_key'] for n in chosen if n.get('association_key')}),max_calls=p['max_calls'],reserved_calls=0,new_model_calls=0,stop_reason=None,has_local_issues=False,score_set_id=uid('scoreset'),reason=p['reason'])
                row.pop('finished_at',None);row.pop('execution_counts',None);row['plan_hash']=digest(row)
                self.store.put(KIND,row,owner,db)
                self.store.put('benchmark.scoreset',dict(id=row['score_set_id'],pipeline_id=pid,reference_manifest=row['manifest'],reason=p['reason'],scorer_version=scoring.VERSION,created_at=now(),overrides={}),owner,db,immutable=True)
                for original in chosen:
                    n={k:v for k,v in original.items() if k not in ['job_id','attempt_id','prediction_id','local_error','finished_at','validation_error','reason','input_id']}
                    n.update(id=ids[original['id']],pipeline_id=pid,flow_id=pid,parent_node_id=original['id'],schema_status='pending',scoring_status='pending',has_issue=False,created_at=now(),status='pending')
                    if n.get('dependency_id') in selected:
                        n['dependency_id']=ids[n['dependency_id']]
                        for k in ['input_ref','input_hash','match_id']:n.pop(k,None)
                        self.store.put(NODE,n,owner,db)
                    else:
                        if original.get('prediction_id') and n['stage']=='vqa':n['prediction_id']=original['prediction_id']
                        n['dependency_id']=None;n['reused_parent_input_id']=original.get('input_id')
                        self._put_input(owner,n,self._input(owner,original),db);self._queue(owner,n,db)
                return self.summary(row)
            return self.store.idem(db,owner,'benchmark.pipeline.retry:'+id,p['idempotency_key'],p,action)

    def rescore(self,owner,id,p):
        with self.store.tx() as db:
            def action():
                pipeline=self.store.get(KIND,id,owner,db)
                if pipeline['status'] in ['queued','running'] or pipeline.get('pending_local_jobs',0):raise Conflict('执行和本地恢复结束后才能固定新的评分集合')
                nodes=self.rows(owner,id,db);base=self.store.get('benchmark.scoreset',pipeline['score_set_id'],owner,db);overrides=p.get('annotation_ids') or {};known={n['task_id'] for n in nodes}
                if not set(overrides)<=known:raise ValueError('标注覆盖包含不属于本流程的任务')
                sid=uid('scoreset');new_refs=copy.deepcopy(base.get('reference_overrides',{}))
                for n in nodes:
                    t=copy.deepcopy(self.task(n))
                    if n['id'] in new_refs:
                        prior=self.store.get('benchmark.annotation',new_refs[n['id']]['annotation_id'],owner,db)
                        t.update(target=prior['target'],annotation=prior,reference_status='human_reviewed',reference_valid=new_refs[n['id']]['reference_valid'])
                    if n['task_id'] in overrides:
                        a=self.store.get('benchmark.annotation',overrides[n['task_id']],owner,db)
                        if a['verdict']!='pass' or a['dataset_id']!=pipeline['dataset_id'] or a['task_id']!=t['task_id'] or a['asset_sha256']!=t['asset']['sha256']:raise ValueError('新参考与任务/图片不绑定')
                        if a['question']!=t['question']:raise ValueError('问题已变化，须新建运行，不能离线换题评分')
                        if n['variant']=='reference_guided_prediction' and scoring.box(a['bbox_xyxy'],t['asset']['width'],t['asset']['height'])!=scoring.box(t['roi'],t['asset']['width'],t['asset']['height']):raise ValueError('参考区域已变化，须重建关联和输入，不能离线改输入身份')
                        t.update(target=a['target'],annotation=a,reference_status='human_reviewed');t['reference_valid']=reference_valid(t)
                        new_refs[n['id']]=dict(target=t['target'],reference_valid=t['reference_valid'],reference_status='human_reviewed',annotation_id=a['id'],target_hash=digest(t['target']))
                    a=self.store.optional('benchmark.attempt',n.get('attempt_id',''),owner,db)
                    if a and a.get('response'):self._score(owner,pipeline,n,a,db,sid,t)
                row=dict(id=sid,pipeline_id=id,parent_score_set_id=pipeline['score_set_id'],reference_manifest=pipeline['manifest'],reference_overrides=new_refs,
                         overrides={},reason=p['reason'],scorer_version=scoring.VERSION,created_at=now())
                self.store.put('benchmark.scoreset',row,owner,db,immutable=True)
                pipeline['score_set_id']=sid;self.store.put(KIND,pipeline,owner,db)
                return row
            return self.store.idem(db,owner,'benchmark.pipeline.rescore:'+id,p['idempotency_key'],p,action)

    def export(self,owner,id,score_set_id=''):
        pipeline=self.store.get(KIND,id,owner);sid=score_set_id or pipeline['score_set_id']
        with self.store.tx() as db:audit.emit(db,owner,'benchmark.pipeline.export',KIND,id,details=dict(pipeline_id=id,score_set_id=sid),reason='导出计划、全部阶段/响应/评分和修改过程')
        nodes=self.rows(owner,id)
        with self.store.read() as db:
            def unique(kind,key):
                return [self.store.get(kind,value,owner,db) for value in dict.fromkeys(n.get(key) for n in nodes) if value]
            return dict(pipeline=pipeline,manifest=self.benchmark.load(pipeline['manifest']),report=self.report(owner,id,sid),nodes=nodes,
                        task_bundles=unique('benchmark.pipeline.task','task_bundle_id'),inputs=unique('benchmark.input','input_id'),
                        predictions=unique('benchmark.prediction','prediction_id'),matches=unique('benchmark.match','match_id'),
                        attempts=self.store.list('benchmark.attempt',owner,db,field='pipeline_id',value=id),
                        scores=self.store.list('benchmark.score',owner,db,field='pipeline_id',value=id),
                        supplemental_scores=[r for kind in ['benchmark.lawbench_score','benchmark.legalbench_score'] for r in self.store.list(kind,owner,db,field='pipeline_id',value=id)],
                        score_sets=self.store.list('benchmark.scoreset',owner,db,field='pipeline_id',value=id),export_protocol='benchmark-pipeline-export.v1')

    def quality(self,owner,p):
        attempt=self.store.get('benchmark.attempt',p['attempt_id'],owner)
        pipeline=self.store.get(KIND,attempt['pipeline_id'],owner)
        node=self.store.get(NODE,attempt['node_id'],owner);t=self.task(node)
        if pipeline['status'] in ['queued','running'] or pipeline.get('pending_local_jobs',0):raise Conflict('流程和本地恢复结束后再冻结人工量表评分')
        if attempt['status']!='completed' or attempt['response'].get('demo') or t['answer_kind']!='open_text':raise ValueError('仅真实返回的开放题可人工量表评估')
        dims=p['dimensions'];required={'faithfulness','relevance','support','no_unsupported_claims','uncertainty'}
        if set(dims)!=required or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=4 for v in dims.values()):raise ValueError('完整填写五项0至4的量表分数')
        prompt=self.store.get('review.prompt',p['prompt_id'],owner) if p.get('prompt_id') else dict(id='human-open-rubric.v1',markdown='事实忠实、相关性、证据支持、无无据假设、不确定性表达，每项0至4；不认证法律结论。')
        with self.store.tx() as db:
            def action():
                current=self.store.get(KIND,pipeline['id'],owner,db);base=self.store.get('benchmark.scoreset',current['score_set_id'],owner,db)
                row=dict(id=uid('benchmarkquality'),pipeline_id=current['id'],run_id=current['id'],node_id=node['id'],dataset_id=current['dataset_id'],task_id=t['task_id'],
                         image_name=t['image_name'],attempt_id=attempt['id'],method='human',verdict='reviewed',dimensions=dims,process=p['process'],findings=p['findings'],suggestions=p['suggestions'],
                         prompt=prompt,response_hash=digest(attempt['response']['raw']),input_hash=node['input_hash'],asset_sha256=t['asset']['sha256'],editor=owner,created_at=now())
                self.store.put('benchmark.quality',row,owner,db,immutable=True)
                sid=uid('scoreset');score_id=node['id']+':'+sid;overrides={}
                for n in self.rows(owner,current['id'],db):
                    prior_id=base.get('overrides',{}).get(n['id'],n['id']+':'+base['id'])
                    if self.store.optional('benchmark.score',prior_id,owner,db):overrides[n['id']]=prior_id
                overrides[node['id']]=score_id
                previous=self.store.optional('benchmark.score',base.get('overrides',{}).get(node['id'],node['id']+':'+base['id']),owner,db)
                score=dict(previous or {},id=score_id,pipeline_id=current['id'],run_id=current['id'],node_id=node['id'],dataset_id=current['dataset_id'],task_id=t['task_id'],score_set_id=sid,
                           attempt_id=attempt['id'],quality_id=row['id'],target=(previous or {}).get('target',t['target']),target_hash=digest((previous or {}).get('target',t['target'])),
                           reference_valid=(previous or {}).get('reference_valid',t['reference_valid']),reference_status=(previous or {}).get('reference_status',t['reference_status']),
                           allowed_values=t['allowed_values'],answer_kind=t['answer_kind'],label=t['label'],variant=node['variant'],scorer_version='human-open-rubric.v1',created_at=now(),
                           result=dict(status='rubric_reviewed',score=sum(dims.values())/20,dimensions=dims,legal_correctness=None))
                self.store.put('benchmark.score',score,owner,db,immutable=True)
                self.store.put('benchmark.scoreset',dict(id=sid,pipeline_id=current['id'],parent_score_set_id=base['id'],reference_manifest=base['reference_manifest'],reference_overrides=base.get('reference_overrides',{}),overrides=overrides,
                               reason=p['process'],scorer_version='human-open-rubric.v1',created_at=now()),owner,db,immutable=True)
                current['score_set_id']=sid;self.store.put(KIND,current,owner,db);return row
            return self.store.idem(db,owner,'benchmark.pipeline.quality:'+attempt['id'],p['idempotency_key'],p,action)

    def persist_report(self,owner,id,score_set_id=''):
        p=self.store.get(KIND,id,owner)
        if p['status'] in ['queued','running']:return None
        report=self.report(owner,id,score_set_id)
        if any(report['execution'].get(s) for s in ['pending','ready','running']):return None
        artifact=blob(self.store,dumps(report).encode());sid=report['score_set_id'];rid=id+':report:'+sid+':'+artifact['sha256']
        row=dict(id=rid,pipeline_id=id,score_set_id=sid,report=artifact,report_hash=artifact['sha256'],created_at=now())
        with self.store.tx() as db:
            existing=self.store.optional('benchmark.pipeline.report',rid,owner,db)
            if existing:return existing
            self.store.put('benchmark.pipeline.report',row,owner,db,immutable=True)
        return row

    def reconcile(self,owner,id,p):
        """Adopt independently durable late responses without a new provider call."""
        with self.store.tx() as db:
            def action():
                pipeline=self.store.get(KIND,id,owner,db);chosen=set(p.get('node_ids') or [])
                nodes=[n for n in self.rows(owner,id,db) if n['status']=='unknown' and (not chosen or n['id'] in chosen)]
                if not nodes or chosen and chosen!={n['id'] for n in nodes}:raise ValueError('请选择本流程结果未知的节点')
                for node in nodes:
                    attempt=self.store.get('benchmark.attempt',node['attempt_id'],owner,db)
                    response=self.store.optional('evaluation.request',attempt['request_id'],owner,db)
                    if not response or response['status']!='completed' or not response.get('response') or response.get('input_hash')!=attempt['request_hash'] or response.get('model_snapshot')!=pipeline['model']:
                        raise ValueError('尚无归属、输入哈希和模型均一致的已保存响应；不发起新调用')
                    attempt.update(status='completed',response=response['response'],finished_at=response['finished_at'],recovered_gateway_response=True)
                    self.store.put('benchmark.attempt',attempt,owner,db)
                    node.update(status='response_received',finished_at=attempt['finished_at']);node.pop('local_error',None)
                    try:
                        db.execute('SAVEPOINT reconcile_local');self._local(owner,pipeline,node,attempt,db);db.execute('RELEASE reconcile_local')
                    except Exception as error:
                        db.execute('ROLLBACK TO reconcile_local');db.execute('RELEASE reconcile_local');node['local_error']=error_view(error)
                    node['has_issue']=bool(node.get('local_error')) or node['schema_status']=='invalid'
                    node['reconciliation_reason']=p['reason'];self.store.put(NODE,node,owner,db)
                    audit.emit(db,owner,'benchmark.pipeline.response_reconciled',NODE,node['id'],details=dict(pipeline_id=id,node_id=node['id'],model_call_id=attempt['request_id']),reason=p['reason'])
                self._refresh(owner,pipeline,db);return self.summary(pipeline)
            return self.store.idem(db,owner,'benchmark.pipeline.reconcile:'+id,p['idempotency_key'],p,action)
