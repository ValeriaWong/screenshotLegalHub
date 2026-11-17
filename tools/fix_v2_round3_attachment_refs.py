"""Apply source references verified by root against the actual table/letter context."""
import copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read
from tools.v2_root_review import revise

if __name__=='__main__':
    d=OUT/'zh/zh_0006';c=copy.deepcopy(read(d/'case.json'))
    m=next(m for m in c['messages'] if m['id']=='m007')
    refs=[{'source_id':'p0029','quote':'合作协议约定贵公司需向我公司缴纳保证金300万元'},
          {'source_id':'p0029','quote':'贵公司仅支付170万元，尚欠130万元未支付'},
          {'source_id':'p0029','quote':'现特致函贵公司于2021年8月12日前所欠保证金130万元支付至我公司'}]
    if m['source_refs']!=refs:
        m['source_refs']=refs
        revise(d,c,[{'severity':'major','message_ids':['m007'],'problem':'附件列出300万元及2021年8月12日期限，但引用只有已付170/未付130。',
                     'change':'核对告知函p0029，分别补入300万元约定与支付期限的字面引用。'}])
    d=OUT/'zh/zh_0026';c=copy.deepcopy(read(d/'case.json'))
    m=next(m for m in c['messages'] if m['id']=='m002')
    if not any(r.get('source_id')=='p0281' for r in m['source_refs']):
        m['source_refs']=[{'source_id':'p0280','quote':'河南中玉种业'},
                          {'source_id':'p0281','quote':'73834元'},
                          {'source_id':'p0283','quote':'该支付凭证已发送对账群，且备注玉米种尾款'}]
        c['source_metadata_warnings']=c.get('source_metadata_warnings',[])+[
            '历史案由与标题写损害股东利益责任纠纷，正文称损害公司利益责任纠纷；保留来源标签，需复核分类。']
        revise(d,c,[{'severity':'major','message_ids':['m002'],'problem':'附件73834元及收款对象没有对应的表格单元引用；存在来源案由冲突。',
                     'change':'核对p0280–p0283完整表格行，补齐收款对象和金额引用，并单列分类冲突。'}])
    print('Verified source references corrected; original sources preserved.')
