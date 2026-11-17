from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read
from tools.v2_root_review import revise
d=OUT/'zh/zh_0106';c=read(d/'case.json')
c['questions'][1]['question']='说“医药费我也付过”能否确认李某甲已付6423.66或已付全部医疗费？'
revise(d,c,[{'severity':'major','message_ids':['m007','m008','m009'],
    'problem':'题面含截图未展示的判决总医疗费，造成图外信息泄漏。',
    'change':'题面改为是否支付全部医疗费，不带判决总额；保留无法确定付款额的答案。'}])
for ident,qid,text,reason in [
    ('zh_0025','q3','仅这些群消息能确认公司已经抢走客户并造成具体损失吗？','去掉截图没有展示的诉讼损失额375000元。'),
    ('zh_0055','q2','退款沟通涉及哪几次时间和金额？能说所有车辆都退款了吗？','去掉截图没有展示的车辆总数40台。'),
]:
    d=OUT/'zh'/ident;c=read(d/'case.json');q=next(q for q in c['questions'] if q['id']==qid)
    q['question']=text
    if ident=='zh_0055':q['answer']=q['answer'].replace('不能确定40台全部退款','不能确定所有车辆全部退款')
    revise(d,c,[{'severity':'major','message_ids':q['message_ids'],
        'problem':'题面引入了截图之外的判决上下文。','change':reason+'保留证据范围不足的答复。'}])
