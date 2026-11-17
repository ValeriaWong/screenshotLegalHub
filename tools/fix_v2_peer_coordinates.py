"""Apply source-context corrections actually identified by the peer review."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read
from tools.v2_root_review import revise

def locate(source,ref,context,quote):
    assert source['text'].count(context)==1
    assert context.count(quote)==1
    start=source['text'].index(context)+context.index(quote)
    return {**ref,'char_start':start,'char_end':start+len(quote)}

def main():
    specifications={
        'zh_0145':{
            'm010':('张某雪称“对”','对'),
            'm015':('张某雪称“可以交了”','可以交了'),
            'm016':('张某雪称“可以交了”；丁某龙称“好”','好')},
        'zh_0244':{'m010':('4月3日：“韩：框子呢；张：在昆明','框子呢')}}
    for ident,spec in specifications.items():
        d=OUT/'zh'/ident;source=read(d/'source.json');case=read(d/'case.json');c=copy.deepcopy(case)
        for message in c['messages']:
            if message['id'] in spec:
                context,quote=spec[message['id']]
                message['source_refs']=[locate(source,r,context,quote) if r['quote']==quote else r for r in message['source_refs']]
        if ident=='zh_0145':
            next(q for q in c['questions'] if q['id']=='q2')['question']='8月27日对丁某龙问到的钱是否已经支付，戚某友怎么说？'
        issues=[{'severity':'major','message_ids':list(spec),'problem':'同段短句首次字面匹配落到不同发言或日期。','change':'依据peer.review.json中的完整说话人、日期上下文固定准确字符坐标；图内原话保持不变。'}]
        if ident=='zh_0145':issues.append({'severity':'major','question_ids':['q2'],'message_ids':['m020','m021'],'problem':'纯图片问题含图外款项性质“尾款”。','change':'题面只问8月27日问到的钱是否支付，不预先补定款项性质。'})
        print(ident,revise(d,c,issues))

if __name__=='__main__':main()
