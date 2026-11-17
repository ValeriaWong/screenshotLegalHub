"""Remove generated follow-up declarations that alter evidence timing or legal meaning."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read
from tools.v2_root_review import revise

for ident,mid,reason in [
    ('zh_0022','m007','生成的“那金额对上了”把中性衔接写成对账确认。已有原文约束的余额回复足够，删除新增确认。'),
    ('zh_0132','m009','原文异议在转账之前；生成的付款后重复“不认扣”新增争议的时间位置，删除这条。题目仅用付款前原话判断扣款异议，不推断转账后回应。'),
]:
    d=OUT/'zh'/ident;c=read(d/'case.json');c['messages']=[m for m in c['messages'] if m['id']!=mid]
    for q in c['questions']:q['message_ids']=[i for i in q['message_ids'] if i!=mid]
    if ident=='zh_0022':
        m=next(m for m in c['messages'] if m['id']=='m003')
        if not any('全部作废' in r['quote'] for r in m['source_refs']):
            m['source_refs'].append({'source_id':'p0030','quote':'备注：以此单为准，原所出具的收条、欠条、对账单全部作废。'})
    revise(d,c,[{'severity':'major','message_ids':[mid],'problem':'创作衔接含法律意义确认或改变声明发生位置。','change':reason}])
