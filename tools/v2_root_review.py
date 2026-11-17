"""Transparent root corrections and a review queue for source/image leakage.

Does not treat string/number checks as legal fidelity or certified difficulty.
"""
import copy,json,re,sys
from decimal import Decimal
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read,save,normalize,status,processing_items


def revise(directory,candidate,issues):
    before=read(directory/'case.json')
    if candidate==before:return False
    archive=directory/'root.versions';archive.mkdir(exist_ok=True)
    version=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    save(archive/(version+'.before.json'),before)
    final,errors=normalize(candidate,read(directory/'source.json'));assert not errors,errors
    for key in ['author','case_no','raw_source_case_no','case_no_status','source_metadata_warnings']:
        if key in candidate:final[key]=candidate[key]
    final['status']='root_corrected_candidate_pending_user_review'
    previous=read(directory/'root.review.json') if (directory/'root.review.json').exists() else {
        'method':'root inspected candidate and cited source passages; actual corrections',
        'new_human_score':None,'difficulty_certified':False,'issues':[],'versions':[]}
    previous['issues'].extend(issues);previous['versions'].append({'id':version,'before':'root.versions/'+version+'.before.json'})
    final['root_edits']=previous['issues']
    save(directory/'root.review.json',previous);save(directory/'case.json',final)
    status(directory,'reviewed',method='agent_direct_writing_then_root_correction',author=final.get('author'),difficulty_certified=False)
    return True


def scan():
    queue=[];corrected=[]
    for item in processing_items():
        directory=OUT/'zh'/item['id']
        if item['id']=='zh_0146' or not (directory/'case.json').exists():continue
        state=read(directory/'status.json')
        if state['phase'] not in ['reviewed','rendered','render_failed']:continue
        before=read(directory/'case.json');c=copy.deepcopy(before);issues=[]
        for conv in c['conversations']:
            old=conv['title'];new=re.sub(r'[（(]合成(?:中性)?群名[）)]','',old).strip()
            if new!=old:
                conv['title']=new;issues.append({'severity':'major','message_ids':[],
                    'problem':'图内群名出现生成元说明：'+old,'change':'图内仅保留中性群名：'+new+'；合成属性留在来源页。'})
        for m in c['messages']:
            a=m.get('attachment')
            if a:
                old=a.get('footer','')
                if any(word in old for word in ['判决','重建','原件未取得','合成','研究样本','真实性还原','未列统筹单号','账户号码未列']):
                    a['footer']=''
                    issues.append({'severity':'major','message_ids':[m['id']],
                                   'problem':'附件图内 footer 泄漏生成来源：'+old,
                                   'change':'删除图内元说明；reconstruction_notice 与来源页继续保留。'})
                quotes=''.join(r['quote'] for r in m.get('source_refs',[]))
                quotes_numbers=quotes.replace(',','').replace('，','')
                amounts={Decimal(n) for n in re.findall(r'\d+(?:\.\d+)?',quotes_numbers)}
                amounts.update(Decimal(n)*10000 for n in re.findall(r'(\d+(?:\.\d+)?)\s*万',quotes_numbers))
                for key,value in a['rows']:
                    numbers=re.findall(r'\d+(?:\.\d+)?',str(value).replace(',','').replace('，',''))
                    missing=[n for n in numbers if Decimal(n) not in amounts]
                    if missing:queue.append({'case_id':item['id'],'message_id':m['id'],'type':'attachment_value_reference_review',
                                             'field':key,'value':value,'not_in_cited_quote':missing,
                                             'note':'可能涉及单位换算或缺少字段引用，需核对上下文；不是自动判定造假。'})
            if m['origin_type']!='verbatim_quote' and any(w in m['text'] for w in ['根据判决','判决记载','据判决','合成场景','原件未取得']):
                queue.append({'case_id':item['id'],'message_id':m['id'],'type':'visible_generation_metadata','text':m['text']})
        if revise(directory,c,issues):corrected.append(item['id'])
    save(OUT/'root_review_queue.json',{'corrected_cases_this_scan':corrected,'items':queue,
         'source_fidelity_certified':False,'purpose':'source/display review leads, not legal truth labels'})
    print(json.dumps({'corrected':corrected,'queue_items':len(queue)},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');scan()
