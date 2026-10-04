"""Small, frozen, source-reviewed development comparison; no gold enters model input."""
import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub import benchmark as b
from legalhub.case_registry import CaseRegistry
from legalhub.case_chat import RULES,SCHEMA,chat_model,decision_request,decision_questions,evidence_context,resolve_answer
from legalhub.inference import request
OUT=b.ROOT/'reports/case-qa-sample-v2'
CASES=[
 ('5ad6f87311be1056f7197a9f',[
  ('A1','现有聊天中是否有人明确称转了2000？','yes',['M052','M057']),
  ('A2','能否据这些截图确认原告本人实际完成了转账？','unknown',['M052','M057']),
  ('A3','能否确认双方成交价就是2000？','unknown',['M043','M044','M052']),
  ('A4','对方是否明确回答钱“收到了”？','yes',['M057','M058'])]),
 ('58b7dff082ec3972eb9edeb4',[
  ('B1','是否有人提出起码先付一个预付款？','yes',['M007']),
  ('B2','现有可读消息是否出现“已经转账”或“已经收到款”的陈述？','no',['M004','M007']),
  ('B3','能否确认双方已经约定确定的工时费金额？','unknown',['M004']),
  ('B4','是否有人明确称主要做健康行业？','yes',['M009'])]),
 ('55fbc265b7ba227320f083f5',[
  ('C1','现有消息是否有人提出租期3年？','yes',['M048','M051']),
  ('C2','能否确认留房定金已经实际到账？','unknown',['M028','M050']),
  ('C3','是否有人表示29号上午到武汉并当面签合同？','yes',['M045','M047']),
  ('C4','能否确认双方已经签署了书面租赁合同？','unknown',['M047'])])]
MODELS=['fast','thinking','diffusiongemma','Kev-4b','SemIf']
def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--single',action='store_true');args=parser.parse_args()
    if args.single:OUT=b.ROOT/'reports/case-qa-sample-v3'
    OUT.mkdir(exist_ok=True);registry=CaseRegistry();materials={id:registry.get(id).material for id,_ in CASES}
    spec={'version':'qa-sample-v3-single-decision-questions' if args.single else 'qa-sample-v2-bounded-decision-options','cases':[{'case_id':id,'questions':[{'id':qid,'question':q,'gold':gold,'gold_relevant_sources':refs} for qid,q,gold,refs in qs],
        'image_hashes':{x['image_id']:x['sha256'] for x in materials[id]['images']},'material_digest':__import__('legalhub.casework',fromlist=['digest']).digest(materials[id])} for id,qs in CASES],
        'models':MODELS,'gold_origin':'assistant_reviewed_original_screenshots_and_transcripts_not_independent_expert_gold','development_sample':True}
    if (OUT/'manifest.json').exists() and b.read(OUT/'manifest.json')!=spec:raise ValueError('Frozen sample changed')
    b.write(OUT/'manifest.json',spec)
    if not args.execute:print(json.dumps({'requests':len(CASES)*len(MODELS),'questions':12,'execute':False}));return
    def run(model,id,qs):
        path=OUT/(model+'-'+id+'.json')
        if path.exists():return b.read(path)
        prior=b.ROOT/'reports/case-qa-sample'/(model+'-'+id+'.json')
        if model in ('fast','thinking') and prior.exists() and b.read(prior).get('status')=='ok':
            row=b.read(prior);row.update(reused_from=prior.relative_to(b.ROOT).as_posix(),reused_response_sha256=b.sha(prior));b.write(path,row);return row
        material=materials[id];state,evidence=evidence_context(material,' '.join(q for _,q,_,_ in qs))
        row={'model_config':model,'case_id':id,'gold_sent':False,'image_inputs':0}
        try:
            if model in ('fast','thinking'):
                config,key=chat_model(model);config.update(max_tokens=3072,stream_deadline_seconds=180)
                prompt=RULES+'\n本案材料：'+json.dumps(state,ensure_ascii=False)+'\n分别回答以下问题：'+json.dumps([{'id':qid,'question':q} for qid,q,_,_ in qs],ensure_ascii=False)+'\n返回JSON {\"answers\":{\"问题ID\":按下列schema的回答}}。每问1-2个简短claims，引用原文M编号。schema：'+json.dumps(SCHEMA,ensure_ascii=False)
                response=request(config,key,prompt,[],retries=0);row['response']=response
                if response.get('http_status')!=200:raise RuntimeError('Provider failure')
                answers=json.loads(response['raw'])['answers']
            else:
                if args.single:
                    raw={};attempts=[]
                    for qid,q,_,_ in qs:
                        try:
                            one=decision_request(model,state,decision_questions(q,evidence));attempts.append({'question_id':qid,**one})
                            for key,value in one['provider_response']['answers'].items():raw[qid+'_'+key]=value
                        except b.ProviderHTTPError as error:
                            attempts.append({'question_id':qid,'http_status':error.http_status,'provider_error':error.provider_error})
                    response={'http_status':200,'latency_seconds':sum(x.get('latency_seconds',0) for x in attempts),'provider_response':{'answers':raw},'individual_requests':attempts}
                else:
                    questions={}
                    for qid,q,_,_ in qs:
                        for key,value in decision_questions(q,evidence).items():questions[qid+'_'+key]=value
                    response=decision_request(model,state,questions)
                row['response']=response;answers={}
                for qid,_,_,_ in qs:
                    raw=response['provider_response']['answers']
                    if qid+'_answer' not in raw or qid+'_source' not in raw:continue
                    source=raw[qid+'_source']['choice'];verdict=raw[qid+'_answer']['choice']
                    answers[qid]={'answer':verdict,'verdict':verdict,'claims':[{'text':verdict,'citations':[] if source=='NONE' else [source]}],'limitations':[]}
            outcomes=[]
            for qid,q,gold,expected in qs:
                a=answers.get(qid,{})
                keys=[key for c in a.get('claims',[]) for key in c.get('citations',[])]
                valid=all(key in evidence for key in keys)
                try:resolved=resolve_answer(a,evidence,material);published=True
                except ValueError:resolved=None;published=False
                if model not in ('fast','thinking') and qid+'_answer' in response['provider_response']['answers']:
                    raw=response['provider_response']['answers'];confidence=raw[qid+'_answer'].get('confidence',0);source_confidence=raw[qid+'_source'].get('confidence',0)
                    published=published and confidence>=.5 and (raw[qid+'_source']['choice']=='NONE' or source_confidence>=.5)
                outcomes.append({'id':qid,'question':q,'gold':gold,'predicted':a.get('verdict'),
                    'correct':a.get('verdict')==gold,'raw_answer':a,'citation_ids':keys,
                    'citations_valid':valid,'citation_hit':bool(set(keys)&set(expected)),
                    'relevant_citations':sum(k in expected for k in keys),'citations_total':len(keys),
                    'publishable':published,'resolved':resolved})
            row.update(status='ok',outcomes=outcomes)
        except Exception as error:
            row.update(status='error',error_type=type(error).__name__,http_status=getattr(error,'http_status',None))
            if hasattr(error,'provider_error'):row['provider_error']=error.provider_error
        b.write(path,row);print(json.dumps({'model':model,'case_id':id,'status':row['status'],'correct':sum(x['correct'] for x in row.get('outcomes',[]))}),flush=True)
        return row
    jobs=[(model,id,qs) for model in MODELS for id,qs in CASES]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda job:run(*job),jobs))
    summary=[]
    for model in MODELS:
        rows=[r for r in results if r['model_config']==model];outcomes=[x for r in rows for x in r.get('outcomes',[])]
        attempts=[a for r in rows for a in (r.get('response',{}).get('individual_requests') or [r.get('response',r)])]
        successful=[a for a in attempts if a.get('http_status')==200]
        latency=[a.get('elapsed_seconds',a.get('latency_seconds')) for a in successful]
        latency=[x for x in latency if x is not None]
        summary.append({'model':model,'questions':12,'correct':sum(x['correct'] for x in outcomes),'accuracy':sum(x['correct'] for x in outcomes)/12,
            'request_successes':len(successful),'requests':len(attempts),'answered_questions':sum(x.get('predicted') in ('yes','no','unknown') for x in outcomes),'citation_hits':sum(x['citation_hit'] for x in outcomes),
            'citation_precision':sum(x['relevant_citations'] for x in outcomes)/max(1,sum(x['citations_total'] for x in outcomes)),
            'publishable':sum(x['publishable'] for x in outcomes),'mean_successful_request_seconds':sum(latency)/len(latency) if latency else None,
            'questions_per_request':4 if model in ('fast','thinking') else 1 if args.single else 4})
    b.write(OUT/'summary.json',{'summary':summary,'sample_questions':12,'cases':3,'provider_requests':sum(len(r.get('response',{}).get('individual_requests',[])) or 1 for r in results if not r.get('reused_from')),'reused_normal_requests':sum(bool(r.get('reused_from')) for r in results),'gold_origin':spec['gold_origin']})
    print(json.dumps(summary))
if __name__=='__main__':main()
