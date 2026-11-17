"""Directly authored source-constrained cases. No external model or templated case-summary generation.

Case wording and questions below are manually written after reading each full judgment.
Source strings are literal lookups; no fuzzy quote repair or invented source locators.
"""
from pathlib import Path
import copy,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read,save,normalize,status


class Draft:
    def __init__(self,ident,participants,conversations,reason):
        self.directory=OUT/'zh'/ident
        self.source=read(self.directory/'source.json')
        self.case={'suitability':{'decision':'candidate','reason':reason},'participants':participants,
                   'conversations':conversations,'facts':[],'messages':[],'questions':[],
                   'constraints':[],'limitations':[],'changes':[]}

    def ref(self,pid,quote):
        paragraph=next(p for p in self.source['paragraphs'] if p['id']==pid)
        assert quote in paragraph['text'],(pid,quote)
        return {'source_id':pid,'quote':quote}

    def msg(self,sender,text,when=None,pid=None,quote=None,origin=None,conv='c1',**extra):
        origin=origin or ('judgment_paraphrase' if pid else 'synthetic_completion')
        message={'id':f'm{len(self.case["messages"])+1:03d}','conversation_id':conv,'sender_id':sender,
                 'timestamp':when,'date_basis':'source_day' if when else 'unknown',
                 'minute_basis':'synthetic_layout_only' if when else 'not_visible',
                 'kind':'text','text':text,'origin_type':origin,
                 'source_refs':[self.ref(pid,quote)] if pid else []}
        message.update(extra);self.case['messages'].append(message)
        return message['id']

    def transfer(self,sender,amount,when,pid,quote,conv='c1',minute=False):
        return self.msg(sender,f'微信转账{amount}元',when,pid,quote,conv=conv,kind='transfer',
                        transfer={'amount':amount,'currency':'CNY','receipt_status':'not_reconstructed'},
                        minute_basis='source_minute' if minute else 'synthetic_layout_only')

    def question(self,question,answer,ids,kind,whole=False):
        self.case['questions'].append({'id':f'q{len(self.case["questions"])+1}','question':question,
                                       'answer':answer,'message_ids':ids,'type':kind,'whole_case_required':whole})

    def fact(self,statement,pid,quote,kind='judicial_finding'):
        self.case['facts'].append({'id':f'f{len(self.case["facts"])+1:02d}',
            'statement':statement,'status':kind,'source_refs':[self.ref(pid,quote)]})

    def finish(self,edits):
        initial=copy.deepcopy(self.case);save(self.directory/'direct.draft.json',initial)
        for change in edits:
            message=next(m for m in self.case['messages'] if m['id']==change['message_id'])
            assert message['text']==change['before']
            message['text']=change['after']
        final,errors=normalize(self.case,self.source)
        assert not errors,errors
        final['author']='Codex direct full-judgment reading and writing; two-pass self revision; no external API'
        final['status']='direct_author_candidate_pending_user_review'
        final['second_pass_edits']=edits
        save(self.directory/'case.json',final)
        save(self.directory/'codex.review.json',{'method':'direct source reading, writing and actual second-pass edits',
             'issues':[{'severity':'major','message_ids':[e['message_id']],
                        'problem':e['reason']+'；初稿：'+e['before'],'change':e['after']} for e in edits],
             'full_judgment_read':True,'source_chars':len(self.source['text']),
             'new_human_score':None,'independent_reviewer':False,'difficulty_certified':False})
        save(self.directory/'case.checks.json',{'errors':[],'source_spans_exact':True,'human_review':False,'difficulty_certified':False})
        status(self.directory,'reviewed',method='codex_direct_writing_and_self_revision')


def loan():
    d=Draft('zh_0156',[{'id':'meng','name':'孟某','role':'转款人及借款诉讼原告'},
        {'id':'yang','name':'杨某1','role':'接收部分转账并安排向他人付款的人'}],
        [{'id':'c1','title':'杨某1','viewer_id':'meng','participant_ids':['meng','yang'],'is_group':False}],
        '有逐字聊天、精确转款分钟及反向借款记录，可检验转款与借贷合意的区别。')
    d.fact('2020年12月10日、2022年3月31日、2023年1月18日三次孟某向杨某1转款，金额分别10000、15000、10000元。',
           'p0017',d.source['paragraphs'][16]['text'])
    d.fact('2022年11月孟某先向杨某1借2000元，随后归还。','p0019',d.source['paragraphs'][18]['text'])
    d.fact('2023年12月26日出现10000元转账、改转彭某的指示；来源没有该10000元的接收或撤回结果。',
           'p0022','次日7时49分：孟某向杨某1转账10000元。杨某1发送彭某账号，同时表示撤回给其的10000元转账。')
    d.msg('meng','先转你一万','2020-12-10 10:15','p0017','2020年12月10日，孟某通过微信向杨某1转账10000元。')
    d.transfer('meng',10000,'2020-12-10 10:16','p0017','2020年12月10日，孟某通过微信向杨某1转账10000元。')
    d.msg('yang','孟总，办四公司某分公司的事准备好了吗？','2022-03-30 18:07','p0022',
          '孟总，办四公司某分公司的事准备好了吗？',origin='verbatim_quote')
    d.transfer('meng',15000,'2022-03-31 15:54','p0022','次日下午15时54分孟某向杨某1转账15000元。',minute=True)
    d.msg('meng','现在能借我五千吗？','2022-11-20 16:06','p0019','2022年11月20日，孟某通过微信向杨某1表示要借款5000元')
    d.msg('yang','我这只有两千','2022-11-20 16:14','p0019','杨某1表示只有2000元，随即将2000元转给孟某。')
    d.transfer('yang',2000,'2022-11-20 16:15','p0019','杨某1表示只有2000元，随即将2000元转给孟某。')
    d.transfer('meng',2000,'2022-11-23 09:26','p0019','11月23日，孟某通过微信偿还杨某12000元。')
    d.msg('meng','两千还你了','2022-11-23 09:27','p0019','11月23日，孟某通过微信偿还杨某12000元。')
    d.transfer('meng',10000,'2023-01-18 13:35','p0017','2023年1月18日，孟某通过微信向杨某1转账10000元。')
    d.msg('yang','准备好了吗？','2023-12-25 17:32','p0022','准备好了吗？',origin='verbatim_quote')
    d.msg('meng','稍等稍等，我估计他得晚点儿，我刚才中午给他打了一个电话，他没说这事儿，但是那天他说了，他说礼拜一给我。',
          '2023-12-25 17:38','p0022','稍等稍等，我估计他得晚点儿，我刚才中午给他打了一个电话，他没说这事儿，但是那天他说了，他说礼拜一给我。',origin='verbatim_quote')
    d.msg('yang','行。','2023-12-25 17:39','p0022','行。',origin='verbatim_quote')
    d.transfer('meng',10000,'2023-12-26 07:49','p0022','次日7时49分：孟某向杨某1转账10000元。',minute=True)
    d.msg('yang','别转给我，刚才那一万撤回，转彭某那个账号','2023-12-26 07:51','p0022',
          '杨某1发送彭某账号，同时表示撤回给其的10000元转账。')
    d.msg('meng','我转彭某了，两万','2023-12-26 08:12','p0018',
          '2023年12月26日，孟某按照杨某1指示向案外人彭某名下转账20000元。')
    d.question('2022年11月的两笔2000元是谁向谁支付的？能否当作孟某借给杨某1的两笔钱？',
               '11月20日杨某1给孟某2000元，11月23日孟某把2000元还给杨某1；是反向借款和归还，不能把两笔都记成孟某向杨某1出借。',
               ['m005','m006','m007','m008','m009'],'direction_and_event_linking')
    d.question('2023年12月26日有哪些转款与改收款指示？能否把图中的10000元和20000元相加，认定杨某1收了30000元？',
               '7:49孟某向杨某1发起10000元转账，杨某1要求撤回并改转彭某账号；孟某随后说已向彭某转20000元。图中没有10000元被收取或撤回成功的记录，不能认定杨某1收到30000元。',
               ['m014','m015','m016'],'recipient_and_evidence_limit',True)
    d.question('哪笔转款前面直接出现了办公司事项？仅凭这些图能否把全部转款都确定为借款？',
               '2022年3月30日问办四公司某分公司的事，次日15:54转15000元。不同转款的上下文和方向不同；部分转款没有款项性质约定，不能把全部转款直接当借款。',
               ['m003','m004','m007','m014','m015','m016'],'context_and_evidence_limit',True)
    d.case['constraints']=[
        '2023年12月26日10000元只有撤回指示，不生成成功撤回、收款或再次归还记录。实际20000元转向彭某，不生成彭某账号。',
        '一审对不同款项的认定与二审结论不进入截图；聊天转账不自动命名为借款、还旧债或好处费。',
        '2022年11月23日原文“偿还杨某12000元”是匿名姓名杨某1紧接2000元，结合前文2000元借款理解；保留原文字符串供复核。',
        '仅2022年3月31日15:54及2023年12月26日7:49分钟来自来源，其余分钟合成；转账卡金额依判决事实重建，未取得原始凭证。']
    d.case['limitations']=['5万元现金借条未纳入本场景，不凭空生成收款聊天。原截图、账号和转账卡接收状态未取得。',
        '只有一条会话，多图数量不证明跨会话或多跳难度达标。']
    d.finish([{'message_id':'m015','before':'别转给我，刚才那一万撤回，转彭某那个账号',
               'after':'刚才那一万撤回，转彭某那个账号','reason':'删去可被理解为已经拒收的补充；原文只记载撤回指示，卡片状态不生成。'}])


def wedding():
    d=Draft('zh_0217',[{'id':'liu','name':'刘某','role':'赠与及彩礼给付人'},
        {'id':'li','name':'李某倩','role':'收受人及询价人'},
        {'id':'staff','name':'珠宝店工作人员','role':'询价对象；原文未载姓名'}],
        [{'id':'c1','title':'刘某','viewer_id':'li','participant_ids':['li','liu'],'is_group':False},
         {'id':'c2','title':'珠宝店工作人员','viewer_id':'li','participant_ids':['li','staff'],'is_group':False}],
        '判决有婚前婚后不同给付与向商家询价的截图证据，可检验给付时点、用途及询价和估值的区别；无逐字聊天，因此全部注明转写或创作。')
    d.fact('婚前给付30万元彩礼及列出的四项首饰；后者原购置价54751元。','p0019',d.source['paragraphs'][18]['text'])
    d.case['facts'][-1]['source_refs'].append(d.ref('p0018','并给付李某倩300000元彩礼'))
    d.fact('女方称1月23日、1月28日为结婚购置家居用品合计15987元。','p0012',
           '2023年1月23日购买罗莱床上用品四件套支付了4017元；2023年1月28日购买了茶几、沙发、自动洗衣机等支付了11970元，以上共计15987元。','party_allegation')
    d.fact('女方称询价合计31400元，不是法院认定的鉴定或评估值。','p0031',
           '其诉称现值31400元系其与商家工作人员的询价，不属于对相关物品的鉴定或评估价值。')
    d.msg('liu','今天这个戒指是给你的','2022-12-31 20:08','p0018',
          '2022年12月31日刘某向李某倩求婚时给付李某倩价值3829元的戒指一枚')
    d.msg('li','嗯，我戴上试试','2022-12-31 20:09')
    d.msg('liu','三十万彩礼我给你了',None,'p0018',
          '结婚前刘某为李某倩购买五金饰品，包括一个金镯子、一条铂金项链、一个铂金戒指、一个钻戒，并给付李某倩300000元彩礼')
    # The source does not identify a payment day; retain an unknown timestamp.
    d.msg('liu','那几样首饰一共54751',None,'p0019',
          '李某倩认可刘某购买上述五金饰品当时的价值为54751元。')
    d.msg('li','金镯子、铂金项链、铂金戒指和钻戒，我放好了',None,'p0019',
          '结婚前刘某为李某倩购买五金饰品，包括一个金镯子、一条铂金项链、一个铂金戒指、一个钻戒，现在在李某倩处')
    d.msg('li','今天去买了床上用品，4017','2023-01-23 15:27','p0012',
          '2023年1月23日购买罗莱床上用品四件套支付了4017元')
    d.msg('li','茶几沙发洗衣机这些，今天一共11970','2023-01-28 17:36','p0012',
          '2023年1月28日购买了茶几、沙发、自动洗衣机等支付了11970元')
    d.msg('liu','电脑买了，银色的','2023-05-27 16:24','p0018',
          '2023年5月27日刘某为李某倩购买一台银色苹果笔记本电脑。')
    d.msg('li','好，回头拿给我','2023-05-27 16:31')
    d.msg('li','想问下之前买的几样首饰，现在回收大概多少',None,'p0024',
          '李某倩与商家工作人员的聊天记录微信截屏，拟证明现在铂金项链，铂金戒指、钻戒的现金价值均已贬值',conv='c2')
    d.msg('staff','是哪几样？有之前的票吗',conv='c2')
    d.msg('li','钻戒现在大概6000，铂金戒指600，铂金项链800，是这个价吗',None,'p0012',
          '据李某倩询价，钻戒现值为6000元左右，铂金戒指600元左右，铂金项链800元左右',conv='c2')
    d.msg('li','金镯子按24000算？那这几样加起来31400左右',None,'p0012',
          '金镯子24000元左右，以上现值共计31400元',conv='c2')
    d.msg('staff','具体得看实物，再看成色和重量',conv='c2')
    d.question('首饰54751元和后来31400元是同一种信息吗？图中能否确定最终回收价或鉴定价值？',
               '54751是婚前购置金额的说法；31400是李某倩向商家问价时自己按四项数字相加的估计。商家没有确认总价，图中没有成交或正式鉴定，不能认定最终回收价或鉴定价值。',
               ['m004','m005','m010','m012','m013','m014'],'cross_conversation_and_valuation',True)
    d.question('哪些给付与婚前结婚安排有关？哪些是有明确日期的另外给付？能否仅凭截图决定返还金额？',
               '婚前安排提到30万元彩礼及四项首饰54751元；另有2022年12月31日求婚时给的戒指和2023年5月27日买的电脑。它们的时点、情境不同；图中没有完整婚姻生活及返还约定，不能据此确定应返还金额。',
               ['m001','m003','m004','m005','m008'],'purpose_timeline_and_evidence_limit',True)
    d.question('李某倩提到的两次家居支出合计多少？能否把聊天里的金额直接当作已核验的票据？',
               '4017+11970=15987元。是她在聊天里说的金额，截图没有收据、明细和交付去向，不能等同于核验票据。',
               ['m006','m007'],'arithmetic_and_statement_status')
    d.case['constraints']=[
        '源文未载逐字聊天，本案无“原话”消息；不得把询价商家姓名、承诺或回答冒充原始聊天。',
        '30万元给付及54751元首饰发生在婚前，但来源未给具体日，不设置1月17日付款或首饰赠与时间。',
        '2023年1月23日与1月28日家居支出只见女方上诉陈述；图内用第一人称陈述，不能生成已核验收据或对方认可。',
        '31400元为当事人询价后的主张，不生成商家确认总价或正式评估书。',
        '“五金”名义下原判决只列四种首饰，照列四种，不补一件；求婚戒指和婚后戒指不混入这四项。',
        '询价日期未知，不生成相对婚前/婚后交易的精确时间；其他已知日期的分钟均为合成。判决的返还比例与结果不入截图。']
    d.case['limitations']=['询价回复为中性创作，截图仅为可能场景，不是原微信还原；源文没有原始商家报价。',
        '原文对8470/8740元表述不一致；不生成该单项收据或确认哪一个正确。',
        '为避免不足来源的共同生活、病史、拉黑争执被写成新事实，未生成相关冲突聊天。']
    d.finish([{'message_id':'m001','before':'今天这个戒指是给你的','after':'今天求婚那个戒指，大小合适不？',
               'reason':'初稿情境太弱；改成事后问大小的口语，保留来源明确的求婚目的，不写法律标签或后来的返还结论。'},
              {'message_id':'m009','before':'好，回头拿给我','after':'好',
               'reason':'删除未记载的未来交付安排；判决只有购买与物品在女方处，未说明该次微信交付过程。'}])


if __name__=='__main__':
    loan();wedding();print('Two additional cases directly written and self-revised; literal source checks passed.')
