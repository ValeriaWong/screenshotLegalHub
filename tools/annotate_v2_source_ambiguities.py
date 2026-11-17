"""Expose the remaining source attribution/media limits without guessing."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read
from tools.v2_root_review import revise

def main():
    d=OUT/'zh/zh_0025';c=copy.deepcopy(read(d/'case.json'))
    m=next(m for m in c['messages'] if m['id']=='m004')
    m['speaker_basis']='conflicting_judgment_attribution_not_certified'
    c['source_ambiguities']=[{'message_id':'m004','type':'speaker_conflict','details':'p0033写关某彬发送，p0047另案记述潘彩兰发送。当前依p0033展示，不能认证唯一归属；该消息不应纳入已认证说话人评测。','review':'../../peer.repeated_long_quotes.review.json'}]
    print('zh_0025',revise(d,c,[{'severity':'major','message_ids':['m004'],'problem':'重复原话在判决不同段的发送者记述不一致。','change':'保留当前p0033来源及原话，把未解决的主体归属冲突明确标注，禁止当唯一说话人金标。'}]))
    d=OUT/'zh/zh_alt_0330';c=copy.deepcopy(read(d/'case.json'))
    for m in c['messages']:
        if m['id'] in ['m001','m002']:m['original_medium']='QQ group screen sharing; private notification/forwarding medium unspecified'
    constraint='原过程发生在QQ群共享屏幕；告知、转发给刘某2的具体平台未披露。当前微信界面是研究场景重建，不能认证为原微信记录。'
    if constraint not in c['constraints']:c['constraints'].append(constraint)
    print('zh_alt_0330',revise(d,c,[{'severity':'major','message_ids':['m001','m002'],'problem':'原过程载体为QQ群，私下告知转发的平台未明确。','change':'补明original_medium和界面重建限制，不将本图当原微信事实证明。'}]))

if __name__=='__main__':main()
