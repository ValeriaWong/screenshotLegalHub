"""Codex's direct source review of the two pilot outputs; no API calls."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read,save,status,normalize


def finish(directory,candidate,edits):
    candidate,errors=normalize(candidate,read(directory/'source.json'))
    assert not errors,errors
    candidate['author']='Codex direct source review and rewriting of pilot draft; not an independent human rating'
    candidate['second_pass_edits']=edits
    save(directory/'case.json',candidate)
    save(directory/'codex.review.json',{'method':'direct source inspection and actual wording edits','issues':edits,'new_human_score':None})
    status(directory,'reviewed',method='codex_direct_revision',source_spans_exact=True,difficulty_certified=False)


def main():
    directory=OUT/'zh/zh_0002';c=read(directory/'revision.invalid.json');edits=[]
    for fact in c['facts']:
        for ref in fact['source_refs']:
            if fact['id'] in ['f03','f05']:
                # The model used ASCII quotes. Restore the exact source quotation marks,
                # choosing source text directly, not fuzzy matching or altering chat.
                if fact['id']=='f03':ref['quote']='被上诉人两次向上诉人利邦物流公司的监事、收取5万元款项的黄家海（利邦物流公司的唯一股东、执行董事梁某的丈夫）提出要求退还“压金”，黄家海并未对被上诉人提出的退还“压金”提出异议'
                else:ref['quote']='2022年2月5日，利邦物流公司向何某转账1909元，转账说明“12月已结清”。2022年2月7日，利邦物流公司向何某转账5784.6元，转账说明“物资款已结清”。'
                edits.append({'severity':'minor','message_ids':[],'problem':fact['id']+'事实引用引号被模型改成ASCII','change':'恢复判决原有中文引号；不修改消息原话。'})
    for m in c['messages']:
        if m['id'] in ['m003','m004','m005']:m['minute_basis']='source_minute'
        if m['id']=='m008':m['minute_basis']='source_approximate_minute'
    c['questions']=[
        {'id':'q1','question':'何某20:30追问退还5万元后，黄家海何时第一次回复？中间隔了多久？','answer':'黄家海21:03回复，间隔33分钟；他说“出了税再说，还没确定要交多少税”。','message_ids':['m003','m005'],'type':'timeline_and_arithmetic','whole_case_required':False},
        {'id':'q2','question':'何某两次把5万元称作什么？黄家海围绕什么事项回应？','answer':'何某两次称“压金”；黄家海回应税额未确定、会计公司正在核算，并让何某问曾大瞳。没有看到一项确定的退款日程。','message_ids':['m003','m005','m008','m009','m010'],'type':'intent','whole_case_required':True},
        {'id':'q3','question':'仅凭图中聊天，能否确定当初双方约定的完整退款条件及最终应退金额？','answer':'不能。图中有5万元转款和“压金”的追问，但没有当初完整退款条款、税额核算结果或最终退款结算。','message_ids':['m001','m003','m008','m009'],'type':'evidence_limit','whole_case_required':True}]
    edits.append({'severity':'major','message_ids':['m003','m005','m008'],'problem':'旧问题带入看不见的诉讼主张，且把全局没有承诺标成局部可证。','change':'题目改为可见时间、两次追问与核算，完整条件标为不能确定；保留判决实际记载的20:30、21:03，22:07为约数。'})
    finish(directory,c,edits)

    directory=OUT/'zh/zh_0130';c=read(directory/'draft.json');edits=[]
    wording={'m004':'我先看下','m005':'材料再发你一下','m009':'表我收到了，其他的我再看看'}
    for m in c['messages']:
        if m['id'] in wording:
            before=m['text'];m['text']=wording[m['id']]
            edits.append({'severity':'major','message_ids':[m['id']],'problem':'衔接加入未见于聊天原文的拒绝或“因拒绝改发”原因链：'+before,'change':m['text']})
        if m['origin_type']=='verbatim_quote':
            # Narrow the citation to the entire actual utterance, keeping all characters.
            for ref in m['source_refs']:ref['quote']=m['text']
        if m['kind']=='file' and m['id'] in ['m002','m003','m006','m007']:
            m['text']=m['text'].rsplit('.',1)[0];m['file_type']='文档'
        if m.get('attachment'):
            m['attachment']['footer']='佣金汇总'
            m['text']='佣金这项在这'
    edits.append({'severity':'major','message_ids':['m008'],'problem':'附件内出现“判决可见汇总值”，泄漏生成来源。','change':'图内仅显示佣金汇总，重建声明留在来源页。'})
    c['constraints']+=['原判决事实段记载4月1日发辞职申请书、4月2日发解除协议；分析段又称4月1日发解除协议。本场景按事实段渲染，保留来源矛盾。',
        '调职原话写兰州安宁；二审理由出现“调至青海”。不把青海塞入原话，也不消除这个来源矛盾。',
        '文件格式仅在判决明确给出时显示扩展名；其他文件用中性文档卡，不冒充取得原件。']
    c['questions']=[
        {'id':'q1','question':'张翔发来的调职通知要求何时、到哪里报到？郭某如何回复？','answer':'要求2024年4月15日上午9:00到兰州安宁销售中心报到；郭某4月12日回复“我家在酒泉，我不同意。”','message_ids':['m010','m012'],'type':'intent_and_timeline','whole_case_required':False},
        {'id':'q2','question':'先收到结束劳动关系的文件还是先收到调职通知？这两组材料分别来自谁？','answer':'先收到付晨源4月1日的辞职申请书及4月2日的解除劳动合同协议书，再收到张翔4月12日的调职通知；发文件不等于郭某提出辞职或签署协议。','message_ids':['m002','m006','m010'],'type':'cross_conversation','whole_case_required':False},
        {'id':'q3','question':'图中的佣金金额是多少？能否确定双方已经约定好付款日期或以回款为条件？','answer':'重建佣金汇总图显示未计发总佣金110836元；未见付款日期或以回款为条件的约定，不能仅因对方收到表格就推定已经同意这些条件。','message_ids':['m007','m008','m009'],'type':'evidence_limit','whole_case_required':True}]
    finish(directory,c,edits)
    print('Two pilots directly reviewed; all quote spans and message references checked.')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
