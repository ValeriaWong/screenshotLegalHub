from uuid import uuid4
import yaml
from screenshotlegal.domain.common.models import now, CaseRecord
from screenshotlegal.settings import ROOT
from screenshotlegal.plugins.matterpacks.registry import MatterRegistry
from screenshotlegal.plugins.skills.registry import SkillRegistry
from screenshotlegal.application.services.compiler import CaseCompiler
from screenshotlegal.infrastructure.storage.evidence import EvidenceStorage
from screenshotlegal.infrastructure.retrieval.fts import Retriever
from screenshotlegal.runtime.executor import Runtime
from screenshotlegal.runtime.review_gate import create_gate
from screenshotlegal.plugins.perception.adapters import ManualFixtureAdapter, MockPerceptionAdapter, OpenAICompatibleVisionAdapter
from screenshotlegal.infrastructure.model.providers import OpenAICompatibleProvider
from screenshotlegal.application.services.proof import graph
from screenshotlegal.domain.evidence.assessments import LawyerAssessment, Reconciliation
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.infrastructure.model.secrets import ModelSecrets

class Workspace:
    def __init__(self,settings,repo):
        self.settings,self.repo=settings,repo
        self.matters=MatterRegistry(ROOT/'matterpacks')
        self.skills=SkillRegistry(ROOT/'backend/src/screenshotlegal/plugins/skills/manifests',settings)
        self.compiler=CaseCompiler(self.matters,self.skills)
        self.storage=EvidenceStorage(settings);self.retriever=Retriever(repo)
        self.runtime=Runtime(repo,self.skills,settings)
        self.secrets=ModelSecrets(settings.data_dir)
        self.profile=yaml.safe_load((ROOT/'profiles/cn_civil_default.yaml').read_text(encoding='utf-8'))

    def preferences(self,user_id='local'):
        return Preferences(self.settings,self.repo,user_id,self.secrets)

    def create_case(self,request,owner_id=None):
        row=CaseRecord(id=str(uuid4()),title=request.title,description=request.description,created_at=now(),owner_id=owner_id)
        self.repo.put('cases',row.id,row.model_dump(),row.id)
        return row

    def evidence(self,case_id):
        self.repo.get('cases',case_id)
        return self.repo.list('evidence_items',case_id=case_id)

    def upload(self,case_id,filename,mime,content):
        self.repo.get('cases',case_id)
        item=self.storage.save(case_id,filename,mime,content)
        previous=self.repo.optional('evidence_items',case_id+':'+item.id)
        if previous:
            from screenshotlegal.domain.evidence.models import EvidenceItem
            return EvidenceItem.model_validate(previous)
        self.repo.put('evidence_items',case_id+':'+item.id,item.model_dump(),case_id,immutable=True)
        return item

    async def perceive(self,case_id,adapter='mock',fixtures=None,model_id=None,user_id='local',evidence_ids=None):
        if adapter not in ['mock','manual','openai-compatible']:
            raise ValueError('Unknown perception adapter')
        self.repo.get('cases',case_id)
        pid=str(uuid4());results=[]
        evidence_items=self.evidence(case_id)
        if evidence_ids is not None:
            if not set(evidence_ids)<={e['id'] for e in evidence_items}:
                raise ValueError('Selected evidence does not belong to this case')
            evidence_items=[e for e in evidence_items if e['id'] in evidence_ids]
        provider=None
        if adapter=='openai-compatible':
            evidence_items=[e for e in evidence_items if e['kind']=='image']
            if not evidence_items:
                raise ValueError('No screenshots available for vision processing')
            provider=OpenAICompatibleProvider(self.preferences(user_id).provider_settings(model_id,vision=True),self.repo,user_id)
        for evidence in evidence_items:
            if adapter=='manual' and evidence['id'] not in (fixtures or {}):
                continue
            if adapter=='openai-compatible':
                if evidence['kind']!='image':
                    raise ValueError('Vision adapter accepts images only')
                result=await OpenAICompatibleVisionAdapter(provider,self.storage).perceive(evidence,pid)
            else:
                rows=(fixtures or {}).get(evidence['id'])
                result=await (ManualFixtureAdapter() if adapter=='manual' else MockPerceptionAdapter()).perceive(evidence,rows or [] if adapter=='manual' else rows)
            records=[]
            for message in result.messages:
                records.append(('messages',case_id+':'+message.id,message.model_dump(),case_id,'',True))
            for ref in result.source_refs:
                records.append(('source_refs',case_id+':'+ref.id,ref.model_dump(),case_id,'',True))
            if adapter!='mock' or (fixtures or {}).get(evidence['id']) is not None:
                records.append(('active_perceptions',case_id+':'+evidence['id'],dict(perception_id=pid,message_ids=[m.id for m in result.messages]),case_id,'',False))
            self.repo.batch(records);results.append(result)
        self.retriever.index(case_id,self.active_messages(case_id))
        return dict(id=pid,messages=sum(len(r.messages) for r in results),warnings=[w for r in results for w in r.warnings])

    def active_messages(self,case_id):
        messages=self.repo.list('messages',case_id=case_id)
        selections={}
        for evidence in self.evidence(case_id):
            selected=self.repo.optional('active_perceptions',case_id+':'+evidence['id'])
            if selected is not None:
                selections[evidence['id']]=set(selected['message_ids'])
        return [m for m in messages if m['evidence_id'] not in selections or m['id'] in selections[m['evidence_id']]]

    def operation_events(self,owner):
        from .operation_events import pending
        return pending(self.repo,owner)

    def select_matter(self,case_id,selection):
        self.repo.get('cases',case_id)
        pack=self.matters.get(selection.matter_pack_id,selection.version)
        record=dict(**selection.model_dump(),digest=pack['digest'],selected_at=now(),gate='matter-selection',status='APPROVED')
        self.repo.put('matter_selections',case_id,record,case_id)
        return record

    def compile(self,case_id,overrides=None):
        self.repo.get('cases',case_id)
        selection=self.repo.optional('matter_selections',case_id) or dict(matter_pack_id='core.evidence.facts',version='1.0.0')
        plan=self.compiler.compile(case_id,selection,self.profile,overrides)
        self.repo.put('case_plans',case_id,plan.model_dump(mode='json'),case_id)
        return plan

    def start_run(self,case_id,request):
        case=self.repo.get('cases',case_id)
        plan=self.repo.optional('case_plans',case_id) or self.compile(case_id).model_dump(mode='json')
        pack=self.matters.get(plan['matter_pack_id'],plan['matter_pack_version'])
        if pack['digest']!=plan['matter_pack_digest']:
            raise ValueError('Matter changed: compile again')
        evidence=self.evidence(case_id)
        for e in evidence:
            self.storage.verified_path(e)
        from screenshotlegal.documents.service import Documents
        from screenshotlegal.domain.evidence.sources import freeze_sources
        documents=Documents(self)
        for document_id in dict.fromkeys(request.document_ids):documents.publish(case_id,document_id,case.get('owner_id') or 'system')
        frozen=freeze_sources(self,documents,case_id,request.document_ids)
        evidence=list({e['id']:e for e in [*frozen['assets'],*evidence]}.values())
        if not frozen['sources']:
            raise ValueError('No transcripts or selected parsed documents available')
        messages=self.active_messages(case_id)
        source_refs=[]
        for source in frozen['sources']:
            ref=dict(source,quote=source['text'],evidence_page=source.get('page_no'))
            source_refs.append(ref)
            if source['source_kind']=='document':
                self.repo.put('source_refs',case_id+':'+source['id'],ref,case_id,immutable=True)
        run=dict(id=str(uuid4()),case_id=case_id,matter_pack_id=plan['matter_pack_id'],matter_pack_version=plan['matter_pack_version'],matter_pack_digest=plan['matter_pack_digest'],analysis_profile=plan['analysis_profile'],analysis_profile_digest=plan['analysis_profile_digest'],case_plan_digest=plan['plan_digest'],plan=plan,
            model_config_snapshot=dict(provider='deterministic',enable_real_model=self.settings.enable_real_model,allow_external_egress=self.settings.allow_external_egress,model=self.settings.model_name),
            input_snapshot=dict(case=case,matter=pack,evidence=evidence,messages=messages,source_refs=source_refs,documents=frozen['documents']),started_at=now(),completed_at=None,status='WAITING_REVIEW',critical_gate=request.critical_gate)
        self.repo.put('analysis_runs',run['id'],run,case_id,run['id'])
        gate=create_gate(self.repo,run,'compile-review',self.settings.auto_approve_gates)
        if gate['status']=='APPROVED':
            self.runtime.schedule(run['id'])
        return run

    def review(self,case_id,request):
        entities=graph(self.repo,case_id).entities
        target=next((e for e in entities if e.id==request.target_id),None)
        if target is None:
            raise KeyError('Review target not found')
        if target.output_digest!=request.output_digest:
            raise ValueError('Review target changed; reload before reviewing')
        if request.action=='edited' and not request.text.strip():
            raise ValueError('Edited review requires replacement text')
        decision=dict(id=str(uuid4()),case_id=case_id,target_id=request.target_id,action=request.action,reviewed_output_digest=target.output_digest,text=request.text,reviewer=request.reviewer,analysis_run_id=target.analysis_run_id,created_at=now())
        assessment=LawyerAssessment.model_validate(decision).model_dump()
        self.repo.batch([('review_decisions',decision['id'],decision,case_id,target.analysis_run_id,True),('lawyer_assessments',decision['id'],assessment,case_id,target.analysis_run_id,True)])
        return decision

    def reconcile(self,case_id,request):
        self.repo.get('cases',case_id)
        known={r['id'] for r in self.repo.list('source_refs',case_id=case_id)}
        if not set(request.source_ref_ids)<=known:
            raise ValueError('Reconciliation contains a foreign SourceRef')
        if request.case_id!=case_id or len(set(request.source_ref_ids))<2:
            raise ValueError('Reconciliation requires distinct sources in the current case')
        self.repo.put('reconciliations',case_id+':'+request.id,request.model_dump(),case_id,immutable=True)
        return request
