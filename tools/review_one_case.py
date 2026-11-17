"""Publish this turn's explicitly attributed review, preserving the real model draft."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub.casework import CaseWorkspace

def reviewed_analysis(work):
    messages=work.material['records']
    def support(*numbers):
        return [{'message_id':f'M{n:03d}','quote':messages[n-1]['text']} for n in numbers]
    def fact(title,description,nums,uncertainties):
        return dict(title=title,description=description,support=support(*nums),uncertainties=uncertainties)
    def meaning(title,kind,declaration,expression,significance,effect,missing,nums,articles):
        return dict(title=title,declaration_type=kind,is_declaration=declaration,expression_meaning=expression,
                    legal_significance=significance,possible_effect=effect,conditions_missing=missing,
                    support=support(*nums),law_ids=[f'civil-code-2020:{x}' for x in articles],confidence='medium')
    return {
        'summary':'现有六张截图呈现服装推荐、选款询价及转款沟通。左侧称转了2000并由手下转款，右侧回答“收到了”。这些话可支持交易及收款陈述，但报价被遮挡，身份、完整约定、真实支付记录和交付情况未核实，不能据此断言合同成立或全部付款义务清偿。',
        'facts':[
            fact('询问选购两件及报价','右侧说卖衣服；左侧请其挑两件好看的，并要求报价。未显示“价格最高”的要求。',(10,12,13,14),['两件的具体款式、尺码及价款尚不明确。']),
            fact('请对方推荐，仍保留查看选款','左侧说用于送人，并请对方选款后给自己看看；右侧表示拍照供查看。',(23,32,33),['推荐款式不等于已授予代理订约权。']),
            fact('商品介绍与询价，报价无法读出','右侧介绍衣服；左侧评价最后一件并询价。随后价格位置被遮挡，不能补出成交价。',(40,42,43),['M044对应原图黑色遮挡，当前材料无法还原报价。']),
            fact('转款陈述及对方收款确认','左侧称转了2000，问钱收到没并称由手下转；右侧回复“收到了”。这记录的是双方陈述。',(52,57,58),['需支付流水核实实际金额、账户及到账。','不能仅凭聊天认定款项性质或全部付款义务清偿。'])],
        'meanings':[
            meaning('商品展示：要约邀请的分析起点','invitation','no','展示商品并邀请对方选看、询价。','可作为订约前宣传与磋商材料；目前未见足以直接成立要约的具体约定和受约束意图。','不能仅凭这段介绍认定合同成立。',['需商品、价款及约束意图等完整信息。'],(10,40),(133,472,473)),
            meaning('“你选吧”：推荐款式还是订约授权','authorization','uncertain','请对方帮助选款；后文“你挑两件 我看看”表明还要查看。','语境更支持选款推荐；不能由此扩张为代理订约、决定最终价款或付款的授权。','是否存在订约授权以及范围，需更明确表示和后续行为。',['缺授权对象、权限及最终确认约定。'],(29,30,32),(133,142)),
            meaning('“多少钱”：询价不当然构成要约','negotiation','no','评价具体款式并询问价钱，属于磋商。','“好，稍等一会”可能回应报价，但报价遮挡，无法定位完整要约及承诺内容。','现有材料不足以单独确定合同成立时点和价款。',['需可辨认报价、商品指向及双方完整确认。'],(42,43,47),(142,472,479,483)),
            meaning('“给你转了2000”：付款事实的告知','performance_notice','no','发言人称已转款，并称让手下转的。','在服装沟通语境下可支持付款行为陈述；本身不等于设立或变更债务的意思表示。','若对应买卖及支付记录可证实，可作为履行线索；不能直接认定全额清偿或借贷。',['缺实际支付记录及2000对应的款项约定。'],(50,52,57),(133,595,626)),
            meaning('“收到了”：收款确认的证据意义','receipt_confirmation','no','针对“钱收到没，让手下转的”，右侧表示收到。','属于受领事实的确认，有证据意义；不因此自动成为订约承诺或免除剩余款项的表示。','可支持对方曾确认收款；真实到账、金额及是否清偿全部义务仍需其他证据。',['缺支付流水、收款账户及完整价款约定。'],(52,57,58),(133,142,626)),
            meaning('“不够再跟我说”：条件沟通，补款义务待定','negotiation','uncertain','结合刚称转了2000，表示金额不足时可反馈。','可以作为可能补款意向的线索；没有明确补足金额或要求对方限期履行，不是收货询问或催告。','是否形成补款承诺须结合款项用途和完整约定，不能据此直接确认追加付款义务。',['“不够”的对象、差额和原有约定均待核实。'],(52,53,54),(133,142))],
        'questions_to_verify':['取得被遮挡报价的可读原始材料，核实商品、数量和价款。','核实2000的流水、收款账户及与本次服装沟通的关系。','核实对话双方及“手下”等第三人的身份和行为，不补造代理关系。','补齐是否交付、何人收取及是否存在后续争议的材料。','核实案件发生日期及适用法律版本；截图“昨天”不足以确定年月日。'],
        'transcription_issues':['文件编号缺少image_3，目前仅使用现有六张原图，不把文件顺序当完整时间线。','M044价格回复被遮挡；M051支付码信息不可完整辨认，本次不得还原金额或账号。']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-run',default='3f49d1fff65b469e');args=parser.parse_args()
    work=CaseWorkspace()
    corrections=['模型初稿把“最好看”扩写为“价格最高”，且未引用选购原话；已删除并重新绑定来源。',
                 '模型初稿把选款推荐扩张为“委托权”；已区分推荐与代理订约授权。',
                 '模型初稿将付款告知、收款确认标为法律意思表示，并断言履行支付义务；已分离事实与条件性法律意义。',
                 '模型初稿把“不够你再跟我说”标题写成收货询问、类型写成催告；已按前后文改为条件沟通。']
    active=work.publish_review(args.source_run,reviewed_analysis(work),corrections)
    print(json.dumps({'review_run':active['run_id'],'source_run':args.source_run,'facts':len(active['facts']),
                      'meanings':len(active['meanings']),'review':active['review']},ensure_ascii=True))
if __name__=='__main__':main()
