"""Authenticated case experiments, immutable inputs, exact split guards and explicit status."""
import copy
from urllib.parse import urlsplit
from screenshotlegal.research.contracts import digest,dumps,now,uid
from screenshotlegal.research.store import Conflict
from screenshotlegal.research import audit
from .registry import CandidateRegistry,PACK_METHODS,call_ceiling
from .inputs import FrozenInputBuilder
from .engine import MethodEngine
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES

class AgentExperiments:
    def __init__(self,store,workspace,auth,gateway,documents):
        self.store,self.workspace,self.auth,self.gateway=store,workspace,auth,gateway
        self.registry=CandidateRegistry();self.inputs=FrozenInputBuilder(workspace,documents)
        self.engine=MethodEngine(self)
    def check_access(self,owner,case_id,write=False):
        row=self.workspace.repo.get('auth_users',owner)
        if not row.get('enabled'):raise PermissionError('账号已停用')
        return self.auth.access(self.auth.view(row),case_id,write=write)
    def save_run(self,owner,run):
        with self.store.tx() as db:self.store.put('agent.run',run,owner,db)
    @staticmethod
    def public_model(model):
        return {k:v for k,v in model.items() if k not in ['credential_ref']}
    def prepare(self,user,payload):
        case=self.auth.access(user,payload.case_id,write=True)
        methods=[self.registry.method(m) for m in payload.method_ids]
        frozen=self.inputs.build(case,payload.goal,payload.document_ids,str(payload.law_effective_date))
        if payload.expected_input_digest and payload.expected_input_digest!=frozen['input_digest']:
            raise Conflict('预检后的材料已变化，请重新冻结实验计划')
        if any(m['id'] in PACK_METHODS for m in methods):
            manifest=frozen['matterpack']['manifest']
            if not manifest or not frozen['matterpack']['claims']:
                raise ValueError('所选方法需要已选择的实体法Matterpack；无模板时可运行E00/E01/E02/E14事实整理')
            reviewed=manifest.get('expert_review',{}).get('status') in {'approved','adjudicated'}
            if not reviewed and (not payload.allow_draft_matter or payload.split!='development'):
                raise ValueError('模板尚未完成专家复核；只允许明确启用草稿的development诊断，不能用于holdout评分')
        if any(m['id']=='E19' for m in methods) and (not frozen['legal_corpus'] or any(not a.get('text') for a in frozen['legal_corpus'])):
            raise ValueError('E19需要独立冻结法源原文；层级仅从法源构建，不能从案件或测试答案生成')
        return frozen,methods
    def preview(self,user,payload):
        frozen,methods=self.prepare(user,payload)
        options=payload.method_options.model_dump()|dict(debate_rounds=payload.debate_rounds,retrieval_top_k=payload.retrieval_top_k)
        ceilings={m['id']:call_ceiling(m['id'],payload.budget.model_dump(),options,[len(r['text']) for r in frozen['sources']]) for m in methods}
        return dict(input_digest=frozen['input_digest'],case_title=frozen['case_title'],sources=len(frozen['sources']),
                    document_snapshots=[d['id'] for d in frozen['documents']],source_file_hashes=frozen['source_file_hashes'],
                    case_group_id=payload.case_group_id,split=payload.split,budget=payload.budget.model_dump(),inference_options=payload.inference_options.model_dump(),
                    methods=[dict(id=m['id'],steps=m['steps'],maximum_model_calls=min(payload.budget.max_model_calls,ceilings[m['id']]),unbounded_call_ceiling=ceilings[m['id']],may_exhaust_budget=ceilings[m['id']]>payload.budget.max_model_calls) for m in methods],
                    estimated_call_ceiling=sum(min(payload.budget.max_model_calls,n) for n in ceilings.values()),
                    scoring_status='no_case_gold',limitations=frozen['limitations'])
    def create(self,user,payload):
        self.auth.access(user,payload.case_id,write=True)
        data=payload.model_dump(mode='json');key=data.pop('idempotency_key')
        cached=self.store.cached(user.id,'agent.cohort',key,data)
        if cached:return cached
        frozen,methods=self.prepare(user,payload)
        frozen=dict(frozen,id=frozen['input_digest'])
        with self.store.tx() as db:
            def action():
                bindings=self.store.list('agent.case_binding',user.id,db)
                for b in bindings:
                    same=b['case_id']==payload.case_id or b['case_group_id']==payload.case_group_id or bool(set(b['hashes'])&set(frozen['source_file_hashes']))
                    if same and b['split']!=payload.split:raise Conflict('相同案件组或原件已绑定另一数据划分，禁止开发/留出交叉')
                    if b['case_id']==payload.case_id and b['case_group_id']!=payload.case_group_id:raise Conflict('此案件已绑定另一案件组，不能改组规避隔离')
                binding=dict(id=payload.case_id,case_id=payload.case_id,case_group_id=payload.case_group_id,split=payload.split,hashes=frozen['source_file_hashes'])
                self.store.put('agent.case_binding',binding,user.id,db)
                self.store.put('agent.input',frozen,user.id,db,immutable=True)
                model=self.gateway.freeze(user.id,payload.model_id,db=db)
                thinking=payload.inference_options.enable_thinking
                if thinking is not None:
                    if urlsplit(model['endpoint']).hostname not in {'aiping.cn','www.aiping.cn'}:
                        raise ValueError('此实验思考开关仅实现AI Ping协议；其他供应商需独立适配')
                    model['parameters']['enable_thinking']=thinking
                stable_model={k:model.get(k) for k in ['config_id','endpoint','model','protocol','parameters','billing']}
                model_digest=digest(stable_model)
                cohort=dict(id=uid('agentcohort'),name=payload.name,case_id=payload.case_id,input_digest=frozen['input_digest'],
                            registry_digest=self.registry.digest,run_ids=[],created_at=now())
                for method in methods:
                    run=dict(id=uid('agentrun'),cohort_id=cohort['id'],name=payload.name,case_id=payload.case_id,
                             case_title=frozen['case_title'],case_group_id=payload.case_group_id,split=payload.split,
                             method=method,model=model,model_digest=model_digest,model_revision_declared=payload.model_revision,
                             model_revision_verified=False,response_models=[],protocol_digest=self.registry.code_digest,
                             method_options=payload.method_options.model_dump()|dict(debate_rounds=payload.debate_rounds,retrieval_top_k=payload.retrieval_top_k),
                             allow_draft_matter=payload.allow_draft_matter,inference_options=payload.inference_options.model_dump(),budget=payload.budget.model_dump(),input_id=frozen['id'],
                             input_digest=frozen['input_digest'],perception_digest=frozen['perception_digest'],
                             matterpack_digest=frozen['matterpack_digest'],legal_corpus_digest=frozen['legal_corpus_digest'],
                             status='queued',scoring_status='unscored_demo' if payload.model_id=='demo' else 'awaiting_expert_gold',
                             template_fields_provided=method['id'] in PACK_METHODS,
                             created_at=now(),usage=None,output=None,output_digest=None)
                    job=self.store.enqueue(db,user.id,'agent_experiment',dict(run_id=run['id'],case_id=payload.case_id))
                    run['job_id']=job['id'];self.store.put('agent.run',run,user.id,db)
                    cohort['run_ids'].append(run['id'])
                self.store.put('agent.cohort',cohort,user.id,db,immutable=True)
                audit.emit(db,user.id,'agent.cohort.created','agent.cohort',cohort['id'],
                           details=dict(case_id=payload.case_id,method_ids=payload.method_ids,input_digest=frozen['input_digest']),
                           reason='创建冻结输入的案件级方法对照；没有专家金标，不计法律质量分')
                return cohort
            return self.store.idem(db,user.id,'agent.cohort',key,data,action)
    def public_run(self,row):
        row=copy.deepcopy(row);row['model']=self.public_model(row['model'])
        row['demo']=row['model']['config_id']=='demo'
        row['comparable_usage']=bool(not row['demo'] and row.get('usage') and not row['usage']['missing_usage_calls'] and row['status']=='completed')
        return row
    def rows(self,user):
        result=[]
        for row in self.store.list('agent.run',user.id):
            try:self.auth.access(user,row['case_id'])
            except Exception:continue
            result.append({k:v for k,v in self.public_run(row).items() if k not in ['output','method'] }|dict(method_id=row['method']['id'],reproduction_name=METHOD_MODULES[row['method']['id']]))
        return result[:100]
    def result(self,user,id):
        run=self.store.get('agent.run',id,user.id);self.auth.access(user,run['case_id'])
        frozen=self.store.get('agent.input',run['input_id'],user.id)
        steps=self.store.list('agent.step',user.id,field='run_id',value=id)
        tools=self.store.list('agent.tool',user.id,field='run_id',value=id)
        stale_reasons=[]
        if run['method'].get('implementation_digest')!=self.registry.code_digest or run['method']['registry_digest']!=self.registry.digest:stale_reasons.append('方法代码或注册表版本已变化，旧输出仍保留')
        try:
            current=self.inputs.build(self.workspace.repo.get('cases',run['case_id']),frozen['goal'],
                                      [d['document_id'] for d in frozen['documents']],frozen['law_effective_date'])
            if current['input_digest']!=frozen['input_digest']:stale_reasons.append('当前材料、模板或法源与冻结输入不同，旧输出仍按旧快照展示')
        except (ValueError,KeyError,OSError):stale_reasons.append('当前来源不可用或未完成；旧输入快照保留')
        return dict(reproduction_name=METHOD_MODULES[run['method']['id']],run=self.public_run(run),steps=sorted(steps,key=lambda s:s['created_at']),tools=tools,author_artifacts=self.store.list('agent.author_artifact',user.id,field='run_id',value=id),
                    sources=frozen['sources'],input_manifest={k:v for k,v in frozen.items() if k not in ['sources','matterpack','legal_corpus']},
                    staleness=dict(stale=bool(stale_reasons),reasons=stale_reasons),
                    graph=self.graph(run),metrics_note='存在引用或字符匹配不代表语义支持；质量指标等待专家 CaseGold。')
    @staticmethod
    def graph(run):
        output=run.get('output') or {};entities=[];edges=[]
        for f in output.get('facts',[]):
            entities.append(dict(id=f['id'],kind='fact',title=f['statement'],review_status='unreviewed',source_refs=[c['source_ref_id'] for c in f['citations']]))
            for c in f['citations']:edges.append(dict(source=c['source_ref_id'],target=f['id'],relation='cites',quote=c['quote'],start=c['start'],end=c['end']))
        for link in output.get('evidence_links',[]):
            edges.append(dict(source=link['source_ref_id'],target=link['fact_id'],relation=link['relation'],quote=link['quote'],review_status='unreviewed'))
        for c in output.get('claims',[]):
            entities.append(dict(id=c['id'],kind='claim',title=c['label'],review_status='unreviewed',status=c['applicability']))
            for f in c['fact_ids']:edges.append(dict(source=f,target=c['id'],relation='proposed_basis'))
        for e in output.get('elements',[]):
            entities.append(dict(id=e['id'],kind='element',title=e['label'],review_status='unreviewed',status=e['status'],burden_role=e['burden_role']))
            edges.append(dict(source=e['id'],target=e['claim_id'],relation='element_of'))
            for f in e['fact_ids']:edges.append(dict(source=f,target=e['id'],relation='proposed_basis'))
        return dict(analysis_run_id=run['id'],entities=entities,edges=edges,status='experimental_unreviewed')
    def compare(self,user,ids):
        if not ids or len(ids)>50 or len(ids)!=len(set(ids)):raise ValueError('比较需要1至50个不重复运行')
        results=[self.result(user,id) for id in ids];rows=[r['run'] for r in results]
        keys=['input_digest','model_digest','model_revision_declared','budget','case_group_id','split','protocol_digest','method_options']
        mismatches=[k for k in keys if any(r.get(k)!=rows[0].get(k) for r in rows[1:])]
        if any(r.get('response_models')!=rows[0].get('response_models') for r in rows[1:]):mismatches.append('response_models')
        if any(r['method'].get('registry_digest')!=rows[0]['method'].get('registry_digest') for r in rows[1:]):mismatches.append('registry_digest')
        reasons=[]
        if any(r['staleness']['stale'] for r in results):reasons.append('存在材料、代码或注册表过期结果')
        if not all(r['comparable_usage'] for r in rows):reasons.append('存在Demo、失败或缺失用量的运行')
        if not all(r.get('model_revision_declared') and r.get('model_identity_observed') and r.get('response_models')==[r['model_revision_declared']] for r in rows):
            reasons.append('模型精确修订未声明或与供应商返回的型号不一致')
        return dict(runs=rows,fixed_factors_match=not mismatches,mismatches=mismatches,exclusion_reasons=reasons,
                    legal_quality_comparable=False,quality_reason='尚无专家案例金标，质量指标未评分；供应商型号一致也不等同独立验证权重版本',
                    measured_usage_comparable=not mismatches and not reasons)
    def on_finish(self,job,status,error,db):
        run=self.store.get('agent.run',job['payload']['run_id'],job['owner'],db)
        if status!='completed':
            run.update(status=status,error=error,finished_at=now())
            for step in self.store.list('agent.step',job['owner'],db,field='run_id',value=run['id']):
                if step['status']=='calling_model':
                    step.update(status='unknown',error=error or dict(category='unknown_outcome',message='调用中断，结果与费用未知'))
                    self.store.put('agent.step',step,job['owner'],db)
        self.store.put('agent.run',run,job['owner'],db)
