"""This case's reviewed display metadata; no provider calls or invented events."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub.casework import CaseWorkspace
from legalhub import benchmark as b

def bi(zh,en):return {'zh':zh,'en':en}
def main():
    work=CaseWorkspace();material=work.material;analysis=work.current
    def event(id,type,status,title,description,test,nums,laws,terms,meaning_types):
        return dict(id=id,type=type,status=status,title=bi(*title),description=bi(*description),legal_test=bi(*test),
                    sources=[f'M{x:03d}' for x in nums],article_ids=[f'civil-code-2020:{x}' for x in laws],
                    term_keys=terms,meaning_types=meaning_types)
    events=[
      event('sales-invitation','invitation','candidate',('要约邀请 · 告知销售衣服','Invitation to offer · Introducing clothing sales'),
            ('右侧说“卖衣服哦，欢迎来看看”，邀请对方选看。','The right-side participant introduces clothing sales and invites the other participant to browse.'),
            ('更接近订约邀请；是否构成要约仍取决于内容确定性和受约束意图。','This is closer to an invitation to negotiate. An offer would require sufficiently definite content and an intention to be bound.'),[10],[472,473],['parties','goods'],['invitation']),
      event('selection-authority','authorization','undetermined',('授权范围审查 · 请对方推荐选款','Authority review · Asking for recommendations'),
            ('左侧说“你选吧”，又说“你挑两件 我看看”，仍保留查看选款。','The left-side participant asks the other to choose, then says they want to see the two selected items.'),
            ('推荐款式不当然等于授权代理订约或决定最终价款。','Permission to recommend items does not by itself authorize entering a contract or setting the final price.'),[29,30,32],[133,142],['parties','quantity'],['authorization']),
      event('product-invitation','invitation','candidate',('要约邀请 · 展示服装特点','Invitation to offer · Presenting product features'),
            ('右侧介绍羽绒衣服的材质与保暖特点。','The right-side participant describes the material and warmth of the clothing.'),
            ('结合完整交易内容判断宣传是否已满足要约条件；不能仅凭商品介绍认定成交。','The complete terms determine whether the presentation meets the conditions of an offer. A product description alone does not establish a completed agreement.'),[40],[472,473],['goods','specification'],['invitation']),
      event('offer-review','offer','undetermined',('要约审查 · 询价与遮挡报价','Offer review · Price inquiry and obscured response'),
            ('左侧说最后一件好看并询价；右侧紧接的回复被遮挡。','The left-side participant likes the last item and asks its price; the next reply is obscured.'),
            ('询价不当然是要约。报价内容及受约束意图未核实，不能补出成交价或完整要约。','An inquiry is not automatically an offer. The obscured response and intention to be bound must be checked; no agreed price or complete offer is reconstructed.'),[42,43,44],[472],['goods','quantity','price'],['negotiation']),
      event('acceptance-review','acceptance','undetermined',('承诺审查 · “好，稍等一会”','Acceptance review · “Okay, wait a moment”'),
            ('遮挡回复后，右侧说“双面羊绒的”，左侧回答“好，稍等一会”。','After the obscured reply, the right side says it is double-sided cashmere; the left replies, “Okay, wait a moment.”'),
            ('需定位对应要约及同意的具体内容；后续付款也需结合完整约定判断，不能仅凭“好”认定承诺。','The corresponding offer and content of assent must be identified. Later payment also requires the full context; “okay” alone does not establish acceptance.'),[44,46,47],[479,480,483],['goods','specification','price'],['negotiation']),
      event('payment-statement','performance_notice','statement',('付款履行线索 · 自称转款2000','Payment evidence · Reporting a transfer of 2,000'),
            ('左侧索要支付宝，并称转了2000、让手下转的。','The left-side participant requests Alipay details and reports a transfer of 2,000 through a subordinate.'),
            ('这是履行行为的陈述；实际支付、款项性质及是否全额清偿需另行核对，不因此直接认定借贷或合同成立。','This reports a performance act. Actual payment, the nature of the funds and full discharge need corroboration; it does not alone establish a loan or contract formation.'),[50,52,57],[595,626],['payment','parties'],['performance_notice']),
      event('additional-payment','variation','undetermined',('补款 / 变更审查 · 金额不足时反馈','Variation review · Reporting a possible shortfall'),
            ('左侧说“不够你再跟我说哈”，表示金额不足时可以反馈。','The left-side participant asks to be told if the amount is insufficient.'),
            ('是可能补款意向的线索；没有明确差额与完整约定，不认定已变更价款、作出反要约或成立追加付款义务。','This may indicate willingness to discuss a shortfall. Without the amount and complete agreement, it does not establish a price variation, counteroffer or additional payment obligation.'),[52,54],[133,142],['price','payment','variation'],['negotiation']),
      event('receipt-confirmation','receipt_confirmation','statement',('受领确认 · 对方回答“收到了”','Receipt confirmation · “Received”'),
            ('左侧问钱是否收到，右侧回复“收到了”。','The left-side participant asks whether the money arrived, and the right replies, “Received.”'),
            ('支持对方曾作收款确认；不当然是订约承诺或免除余款的表示，亦不等同银行到账证明。','This supports that receipt was acknowledged. It is not automatically acceptance, a waiver of any balance or proof of bank settlement.'),[57,58],[133,142,626],['payment'],['receipt_confirmation'])]
    def term(key,label,status,value,assessment,nums):return dict(key=key,label=bi(*label),status=status,value=bi(*value),assessment=bi(*assessment),sources=[f'M{x:03d}' for x in nums])
    terms=[
      term('parties',('当事人与角色','Parties and roles'),'uncertain',('左侧联系选购，右侧自称卖衣服','Left side enquires about buying; right side presents clothing sales'),('聊天名不等于实名；购买人、付款人、收货人是否同一人待核实。','Chat display names do not establish legal identity. The buyer, payer and recipient may differ.'),[10,23,57]),
      term('goods',('标的 / 商品','Subject matter / goods'),'proposed',('服装；羽绒、双面羊绒等描述','Clothing; descriptions include down and double-sided cashmere'),('最终商品指向、款式与双方确认内容待核实。','Final items, styles and mutually agreed content remain unverified.'),[40,42,46]),
      term('quantity',('数量','Quantity'),'proposed',('左侧提出“两件”，并要求挑两件看看','The left side requests two items for review'),('属于请求或选款阶段表达，不能直接认定最终数量约定。','This is a request during selection, not automatically an agreed final quantity.'),[13,32]),
      term('specification',('质量 / 规格','Quality / specifications'),'proposed',('有材质与保暖宣传，未见明确尺码约定','Material and warmth are described; no clear size agreement is visible'),('宣传陈述与最终合同质量条款需要区分。','Product descriptions must be distinguished from agreed contractual specifications.'),[40,46]),
      term('price',('价款','Price'),'uncertain',('报价回复被遮挡；不能把2000补为成交价','The price reply is obscured; 2,000 cannot be substituted as the agreed price'),('需可读报价及双方完整确认；缺失价款信息不等于合同必然未成立。','A readable price response and full assent are needed. Missing price evidence does not itself prove that no contract was formed.'),[43,44]),
      term('payment',('支付 / 已付款线索','Payment / reported payment'),'statement',('左侧称转了2000，右侧回答收到','A transfer of 2,000 is reported and receipt acknowledged'),('是否实付、全款或部分款、对应哪些商品，均待支付记录及完整约定核对。','Actual settlement, full or partial payment, and allocation to goods require records and the complete agreement.'),[50,52,57,58]),
      term('delivery',('交付地点、期限与收货人','Delivery place, timing and recipient'),'missing',('现有材料没有明确可核实的交付约定','No clear, verifiable delivery terms are available'),('“有人会找你”不等于已经交货或确认收货。','Someone contacting the other party is not evidence of delivery or receipt of goods.'),[]),
      term('variation',('条款变更 / 补款','Variation / additional payment'),'uncertain',('金额不足时反馈，差额与最终安排未明','A possible shortfall may be reported; the amount and final arrangement are unclear'),('保留补款讨论线索，不认定已变更价款或存在反要约。','Preserve the discussion without treating it as an agreed price variation or counteroffer.'),[54])]
    checkpoints=[{'type':kind,'status':'not_seen','label':bi(*label),'note':bi('现有材料未见明确表示；不等于该行为从未发生。','No explicit indication appears in the available materials; this does not establish that it never occurred.'),'event_ids':[]} for kind,label in [('withdrawal',('要约撤回','Withdrawal of offer')),('revocation',('要约撤销','Revocation of offer')),('counteroffer',('反要约 / 新要约','Counteroffer / new offer'))]]
    checkpoints.append({'type':'formation','status':'undetermined','label':bi('合同成立与条款','Formation and agreed terms'),'note':bi('成立时点及完整条款尚未核实；不将价款遮挡直接当作合同未成立。','Formation timing and complete terms are unresolved; an obscured price does not by itself mean no contract was formed.'),'event_ids':['legal:offer-review','legal:acceptance-review']})
    translations={material['metadata']['case_name']:'Clothing selection and transfer conversation',analysis['summary']:'Six screenshots show clothing recommendations, price enquiries and payment communication. The left side reports a transfer of 2,000 through a subordinate; the right acknowledges receipt. These statements support transaction and receipt evidence, but the price reply is obscured. Identity, complete terms, actual payment and delivery remain unverified; contract formation or full discharge cannot be concluded from these statements alone.',material['metadata']['source_order']:'Source-file reading order; image_3 is missing and has not been reconstructed.'}
    english=[
      ('Product presentation: invitation to offer','Displaying products and inviting the other participant to browse and enquire.','Relevant to preliminary promotion and negotiations. The complete agreement and intention to be bound are not visible.','This introduction alone does not establish contract formation.','The goods, price and intention to be bound require the complete context.'),
      ('“You choose”: recommendation or authority to contract?','A request to recommend items; the later request to see two items preserves a further review step.','The context better supports recommendation, not delegated authority to contract, set the final price or pay.','Whether contracting authority exists, and its scope, need clearer words and subsequent conduct.','The authorized person, scope of authority and final approval arrangement are missing.'),
      ('“How much”: an enquiry is not automatically an offer','A comment on a style and a request for its price, within negotiations.','“Okay, wait a moment” may respond to a price, but the obscured reply prevents identifying the complete offer and acceptance.','The available evidence alone does not determine formation timing or the agreed price.','Readable pricing, the intended goods and complete mutual confirmation are needed.'),
      ('“Transferred 2,000”: notification of a reported payment','The speaker reports a transfer and says a subordinate made it.','In the clothing context, this supports a statement about payment. It is not by itself an intention to create or vary a debt.','If linked to a sale and corroborated by payment records, it may be performance evidence; it does not directly prove full discharge or a loan.','Actual payment records and the agreed purpose of the 2,000 are missing.'),
      ('“Received”: the evidential significance of acknowledging funds','The right side acknowledges receipt in reply to a question about a transfer through a subordinate.','Acknowledgement of a factual receipt has evidential value; it is not automatically acceptance or a waiver of any balance.','It supports that receipt was acknowledged. Settlement, amount and full discharge need other evidence.','Payment records, the receiving account and the complete price arrangement are missing.'),
      ('“Tell me if it is insufficient”: conditional communication','Following the reported transfer of 2,000, the speaker asks to be told about a shortfall.','This may indicate willingness to discuss more payment. There is no definite amount or deadline; it is not a delivery enquiry or demand for performance.','An obligation to pay more requires the payment purpose and complete arrangement; this phrase alone does not establish it.','The object of the shortfall, the amount and the existing arrangement remain unverified.')]
    for record,en in zip(analysis['meanings'],english):
        i=record['interpretation'];translations[record['title']]=en[0]
        for field,value in zip(('expression_meaning','legal_significance','possible_effect'),en[1:4]):translations[i[field]]=value
        for value in i['conditions_missing']:translations[value]=en[4]
    fact_en=[('Enquiring about two items and pricing','The right side introduces clothing sales. The left asks for two attractive items and a quote, with no request for the highest-priced items.'),('Requesting recommendations while retaining review','The left says the clothes are for a gift and asks to see recommended items. The right offers to photograph them.'),('Product description and enquiry; price obscured','The right describes clothing; the left likes the last item and asks the price. The next price-position reply is obscured and cannot be reconstructed.'),('Reported transfer and acknowledged receipt','The left reports transferring 2,000 through a subordinate and asks about receipt; the right acknowledges it. These are statements in the conversation.')]
    for record,en in zip(analysis['facts'],fact_en):translations[record['title']]=en[0];translations[record['interpretation']['description']]=en[1]
    for key,en in zip(analysis.get('review',{}).get('corrections',[]),[
        'The draft expanded “best-looking” into “highest-priced” and cited contact-addition prompts. The unsupported statement was removed and sources rebound.',
        'The draft expanded clothing recommendations into delegated authority. Recommendations and authority to enter a contract are now distinguished.',
        'Payment notifications and receipt acknowledgement were overclassified as legal declarations and discharge. Facts and conditional legal effects are separated.',
        'The draft mislabelled a shortfall discussion as delivery intent and a demand. The source context supports conditional communication instead.']):translations[key]=en
    for key,en in zip(analysis['questions_to_verify'],[
        'Obtain a readable original price response and verify goods, quantity and price.',
        'Verify payment records, the receiving account and the connection of the 2,000 to this transaction.',
        'Verify both participants and the third-party payer; do not invent an agency relationship.',
        'Obtain evidence of delivery, the recipient and any subsequent dispute.',
        'Verify the case date and applicable law. “Yesterday” does not determine a calendar date.']):translations[key]=en
    for key,en in zip(analysis['transcription_issues'],[
        'image_3 is missing. Only the six available originals are used; file order is not a complete event chronology.',
        'The M044 price reply is obscured and M051 payment-code information is incomplete. No amount or account is reconstructed.']):translations[key]=en
    overlay={'case_id':material['metadata']['case_id'],'source_hashes':{x['image_id']:x['sha256'] for x in material['images']},'source_corpus_sha256':material['metadata']['source_corpus_sha256'],
      'conversations':[{'id':'display:chat-gongjin','name':bi('公瑾い ↔ 截图持有人','公瑾い ↔ Screenshot holder'),
        'image_ids':[x['image_id'] for x in material['images']],'basis':'reviewed_same_visible_chat_header',
        'identity_status':'display_group_only_real_identities_unverified','note':bi('六张图显示同一会话标题；仅作展示分组，不合并或认证真实身份。','The six screenshots share the visible chat header. This display group does not merge or authenticate legal identities.')}],
      'legal_events':events,'legal_checkpoints':checkpoints,'contract_terms':terms,'translations':translations,
      'review_note':bi('法律节点与条款证据视图由本轮助手对照现有原文补充；不是模型新响应，也不是合同成立或法院结论。','Legal nodes and contract evidence were added in this turn by source review. They are not a new model response or a finding of formation or a court.')}
    b.write(work.home/'presentation.json',overlay)
    print({'legal_events':len(events),'contract_terms':len(terms),'conversations':1,'model_requests':0})
if __name__=='__main__':main()
