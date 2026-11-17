"""Two judgment-grounded chats, written and revised directly by Codex.

No inference API calls. Keep all invented wording and layout timestamps explicit.
"""
from pathlib import Path
import hashlib, json, shutil, sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'datasets/v2.0.0/round_002'
PREV = ROOT / 'datasets/v2.0.0/round_001'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


class Writer:
    def __init__(self, language, case_id):
        self.source = json.loads((PREV/language/case_id/'source.json').read_text(encoding='utf-8'))
        self.case = {'id':case_id, 'language':language, 'platform':self.source['platform'],
                     'cause':self.source['cause'], 'case_no':self.source['case_no'],
                     'author':'Codex: direct writing and self-review, not an independent human rating',
                     'status':'author_revised_pending_user_review', 'messages':[]}

    def add(self, cid, sender, day, time, text='', kind='text', origin='synthetic_completion', anchor=None, **extra):
        source_refs=[]
        if anchor:
            start=self.source['text'].find(anchor)
            if start < 0: raise ValueError(f'Anchor not found: {anchor}')
            source_refs=[{'char_start':start, 'char_end':start+len(anchor), 'quote':anchor,
                         'paragraph_ids':[p['id'] for p in self.source['paragraphs']
                                          if p['char_start'] < start+len(anchor) and p['char_end'] > start]}]
        if origin=='verbatim_quote' and text != anchor:
            raise ValueError('Verbatim message must equal its source anchor')
        m={'id':f"m{len(self.case['messages'])+1:03d}", 'conversation_id':cid, 'sender_id':sender,
           'timestamp':f'{day} {time}', 'date_basis':'source_day' if anchor else 'synthetic_scene',
           'minute_basis':'synthetic_layout_only', 'kind':kind, 'text':text,
           'origin_type':origin, 'source_refs':source_refs, **extra}
        self.case['messages'].append(m)
        return m['id']

    def finish(self, constraints, changes, questions):
        self.case['constraints']=constraints
        self.case['changes']=changes
        self.case['questions']=questions
        self.case['limitations']=[
            '合成的可能聊天，不是原始证据。原话、事实转写、创作衔接分别标记；没有人工新评分。',
            '分钟用于排版与模拟，不代表判决确认的精确时刻；按日信息另行标注。',
            '截图覆盖的是本合成场景，消息缺失不能证明真实世界没有其他谈话。',
            '难度为设计假设，未做独立解题、遮挡消融或 SOTA 评测；题目不能当作已审核金标。']
        directory=OUT/self.case['language']/self.case['id']
        directory.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(PREV/self.case['language']/self.case['id']/'source.json', directory/'source.json')
        save(directory/'case.json',self.case)
        return self.case


def chinese():
    w=Writer('zh','zh_sales_146');c=w.case
    c['participants']=[{'id':'li','name':'李某某','role':'设备公司法定代表人'},
                       {'id':'chen','name':'陈某某','role':'工程公司会计'},
                       {'id':'liu','name':'刘某某','role':'工程公司项目经理'}]
    c['conversations']=[{'id':'accounts','title':'李某某','viewer_id':'chen','participant_ids':['chen','li']},
                        {'id':'site','title':'李某某','viewer_id':'liu','participant_ids':['liu','li']}]
    add=w.add
    contract='世佳源-润达恒业灌溉泵变.pdf'
    add('accounts','li','2023-09-10','10:22','陈会计，先看下这个')
    add('accounts','li','2023-09-10','10:22',contract,kind='file',origin='judgment_attachment_reconstruction',
        anchor='通过微信发送了“世佳源-润达恒业灌溉泵变”合同文本，约定卧式离心泵参数为“N=45千瓦”',
        file_type='PDF', file_metadata_basis='title and PDF type reconstructed; size intentionally omitted')
    add('accounts','chen','2023-09-10','11:06','我这会儿在外面，回来再看')
    add('accounts','chen','2023-09-12','09:15','数量变了，重出一下合同。',origin='verbatim_quote',anchor='数量变了，重出一下合同。')
    add('accounts','li','2023-09-12','09:18','好的，好的，本来下午就出这个合同，结果候总也说了，数量变了，我就等这个消息了，下午或者晚上晚点安排。',
        origin='verbatim_quote',anchor='好的，好的，本来下午就出这个合同，结果候总也说了，数量变了，我就等这个消息了，下午或者晚上晚点安排。')
    add('accounts','li','2023-09-12','17:35',contract,kind='file',origin='judgment_attachment_reconstruction',
        anchor='该合同文本已盖新疆某某设备有限公司公章',file_type='PDF')
    add('accounts','li','2023-09-12','17:36','这个是新的，我们这边章盖好了',origin='judgment_paraphrase',anchor='该合同文本已盖新疆某某设备有限公司公章')
    add('accounts','li','2023-09-12','17:36','泵那一项在这',kind='attachment_excerpt',origin='judgment_attachment_reconstruction',
        anchor='产品卧式离心泵，型号：SLW200-400GB，Q=262方，H=38米，N=45千瓦，数量：14台，单价13,500元，合计189,000元',
        attachment={'title':'产品购销合同 · 条目节选','rows':[['产品','卧式离心泵'],['型号','SLW200-400GB'],['流量 / 扬程','Q=262方 / H=38米'],['功率','N=45千瓦'],['数量 / 单价','14台 / 13,500元'],['本项合计','189,000元']],
                    'footer':'仅列示水泵条目', 'reconstruction_notice':'据判决记载重建的附件节选；原 PDF 未取得。裁切与发图动作属合成，不是原始文件。'})
    add('accounts','chen','2023-09-12','18:03','好，我先走付款流程')
    add('accounts','li','2023-09-12','18:08','先付8万4，剩下的乌鲁木齐发货前付清',origin='judgment_paraphrase',
        anchor='付款方式：合同签订后需方支付30％即84,000元，乌鲁木齐发货前付清。')
    add('accounts','chen','2023-09-14','11:03','李总，8万4银行转了',origin='judgment_paraphrase',
        anchor='分别于2023年9月14日、2023年10月27日、2024年3月28日向新疆某某设备有限公司通过银行转账方式支付84,000元、60,000元、136,000元合计280,000元')
    add('accounts','chen','2023-09-14','11:03','你让财务看一下')
    add('accounts','li','2023-09-14','11:26','行，我问下')
    add('accounts','chen','2023-10-27','14:20','今天又转了6万，还是公司那个账户',origin='judgment_paraphrase',
        anchor='分别于2023年9月14日、2023年10月27日、2024年3月28日向新疆某某设备有限公司通过银行转账方式支付84,000元、60,000元、136,000元合计280,000元')
    add('accounts','li','2023-10-27','15:02','嗯，我给财务说')
    add('accounts','chen','2024-03-28','09:35','剩下13万6也转了',origin='judgment_paraphrase',
        anchor='分别于2023年9月14日、2023年10月27日、2024年3月28日向新疆某某设备有限公司通过银行转账方式支付84,000元、60,000元、136,000元合计280,000元')
    add('accounts','chen','2024-03-28','09:36','李总，货这边你跟刘总对接吧，别漏东西')
    add('accounts','li','2024-03-28','10:11','好')
    add('site','li','2023-09-19','14:50','刘总，样本发你')
    add('site','li','2023-09-19','14:50','SLW新系列单级单吸卧式离心泵2023版.pdf',kind='file',
        origin='judgment_attachment_reconstruction',anchor='发送微信消息“SLW新系列单级单吸卧式离心泵2023版”PDF文本',file_type='PDF')
    add('site','li','2023-09-19','14:52','',kind='attachment_excerpt',origin='judgment_attachment_reconstruction',
        anchor='该参数截图显示：SLW200-400GB，37，1480。',
        attachment={'title':'SLW 系列 · 参数节选','rows':[['型号','SLW200-400GB'],['电机功率 (kW)','37'],['转速 (r/min)','1480']],
                    'footer':'参数表局部', 'reconstruction_notice':'原图未取得；仅按判决给出的三项值重建，表头、样式、裁切属合成。'})
    # No artificial "未回复" bubble, no fabricated buyer approval, no extra delivery photograph.
    add('site','liu','2024-03-30','17:04','货都到了',origin='judgment_paraphrase',anchor='2024年3月30日，新疆某某工程有限责任公司收到全部案涉货物。')
    add('site','liu','2024-03-30','17:04','李总你有空回我一下')
    add('site','li','2024-03-31','08:55','刘总，我的那个纸质版的样本没找到，售后明天调试水泵，我让他问了下，应该是45千瓦的，因为去年后面发出来的有一部分是37瓦的，我让技术明天再确认哪一部分是37千瓦的。',origin='verbatim_quote',anchor='刘总，我的那个纸质版的样本没找到，售后明天调试水泵，我让他问了下，应该是45千瓦的，因为去年后面发出来的有一部分是37瓦的，我让技术明天再确认哪一部分是37千瓦的。')
    add('site','liu','2024-03-31','09:02','那人家说你还是有45吗？你为啥给我进37啊。',origin='verbatim_quote',anchor='那人家说你还是有45吗？你为啥给我进37啊。')
    add('site','li','2024-03-31','09:05','下这个单子时，上海某某有限公司说了，他们这个新的样本早都出来，新的产品都是按照37千瓦泵的，不在配45千瓦。给我们都是按照37千瓦生产的，这个是没有问题的应该。',origin='verbatim_quote',anchor='下这个单子时，上海某某有限公司说了，他们这个新的样本早都出来，新的产品都是按照37千瓦泵的，不在配45千瓦。给我们都是按照37千瓦生产的，这个是没有问题的应该。')
    add('site','liu','2024-03-31','09:08','看了没有，还说没问题，人家按图纸查，不是按你厂家查。',origin='verbatim_quote',anchor='看了没有，还说没问题，人家按图纸查，不是按你厂家查。')
    add('site','li','2024-03-31','09:10','等到明天新疆分公司和上海总部这确认，看哪些发出来是45的，哪些是37的。',origin='verbatim_quote',anchor='等到明天新疆分公司和上海总部这确认，看哪些发出来是45的，哪些是37的。')
    constraints=[
        '原话七条按判决一审认定事实段逐字保留，包含“37瓦”“不在配”原有用词；不得为口语感添加 emoji。',
        '9/10、9/12、9/19、三笔银行付款、3/30 到货、3/31 原话日期与判决一致。分钟仍是合成。',
        '会计与项目经理分开会话；同一供方的人物对应由头像、标题与角色表关联。',
        '9/19 发参数后不制造回复；不编造 9/18 买方同意，不把单方发图解释成双方合意。',
        '原合同全文、数量变化截图、到货铭牌照片未取得；不制作貌似已恢复的原件。合同条目图是明确标注的重建附件。',
        '已列明合同项目金额之和不等于总价，不能自行补出差額条目；本次只呈现水泵条目，不制造完整合同。',
        '止于 3/31 的争执；不把判决结论、庭审陈述或律师函全文塞回当时聊天。']
    changes=[
        {'before':'round_001 m006–m008 连续三条念合同参数和付款条款。','after':'m006 文件卡 + m008 合成合同条目图；m010 只保留会计需要的付款说明。','reason':'会计收文件、走流程；供方不会像摘要一样连报全部条目。合同条目仍可从图读取。','feedback':'prompt_v5!L148：表达较为书面化；prompt_v0!N148：加入到货查验、铭牌拍照、拒收通知（后两项无原始材料，不据此冒充照片/原话）。'},
        {'before':'round_001 m020 把“（刘某某未回复）”当界面文字。','after':'m019–m021 为发送消息，下一条直接跳到 2024-03-30；没有任何未回复旁白。','reason':'缺失通过会话间隔呈现，法院认定放在来源页，截图不替模型宣布答案。','feedback':'多版本汇总表!K148、L148 历史修正仍含旁白，本次没有照搬。'},
        {'before':'付款“第二笔60000”“尾款136000，款清了，尽快发货”，每条均像证据摘要。','after':'m011“8万4银行转了”；m014“今天又转了6万”；m016“剩下13万6也转了”。','reason':'保留事实金额及银行渠道，省略反复自证总价；需要跨日加总。','feedback':'prompt_v5!L148：表达较为书面化。'},
        {'before':'原话末尾标点被裁掉，之后又编了一段律师函协商。','after':'七条完整原话 m004–m005、m024–m028 保留终止标点；止于原话。','reason':'不拿“自然化”修改原证据，也不通过新增协商推动案情。','feedback':'多版本汇总表!L148：包括标点、口语；不加“刘总同意”等新事实。'}]
    questions=[
        {'id':'q1','question':'最初合同条目与后来样本对同一型号分别显示什么功率？来自哪两组会话？请使用截图中的称呼。',
         'answer':'陈会计与李某某会话的合同条目 SLW200-400GB 为45千瓦；刘总与李某某会话的参数节选为37kW。不能从单字头像补出未显示的全名。', 'message_ids':['m008','m021'],'type':'cross_conversation'},
        {'id':'q2','question':'图示银行付款合计多少？最后一笔付款是否在图示到货之前？',
         'answer':'84,000+60,000+136,000=280,000元；最后一笔3月28日，图示到货3月30日，在到货之前。','message_ids':['m011','m014','m016','m022'],'type':'timeline_and_arithmetic'},
        {'id':'q3','question':'这些截图能否证明买方同意改用37千瓦？请区分单方发样本与买方意思表示。',
         'answer':'本组图没有买方同意的消息。9月19日只见供方发样本/参数，次年3月31日买方质疑为何供37。不能据此证实变更合意，也不能证明真实世界没有其他交流。','message_ids':['m020','m021','m025'],'whole_case_required':True,'type':'evidence_limit'}]
    return w.finish(constraints,changes,questions)


def english():
    w=Writer('en','en_probate_283');c=w.case
    c['participants']=[{'id':'oo','name':'Oormila','role':'daughter / claimant'},
                       {'id':'sr','name':'Srimila','role':'daughter'},
                       {'id':'sk','name':'Srikumaran','role':'son / executor'},
                       {'id':'sh','name':'Sharmila','role':'daughter'}]
    c['conversations']=[{'id':'siblings','title':'Siblings','viewer_id':'oo','participant_ids':['oo','sr','sk','sh'],'is_group':True},
                        {'id':'brother','title':'Srikumaran','viewer_id':'oo','participant_ids':['oo','sk']}]
    add=w.add
    add('siblings','sk','2016-07-03','18:17',"I've added everyone here. Easier for updates about papa.",origin='judgment_paraphrase',
        anchor='On 3\nrd\nJuly 2016 Srikumaran set up a sibling WhatsApp group')
    add('siblings','sk','2016-07-03','18:18',"Please keep this one for him")
    add('siblings','oo','2016-07-03','19:02',"ok")
    add('siblings','oo','2016-08-28','10:09',"Any update this morning?")
    add('siblings','sk','2016-08-28','10:24',"I'll message when I hear")
    quote='People I know this is the last thing anyone wants to think about but I think it’s important that papa signs a will. I know roughly how he wanted to split it but that’s not important for now what is, is that if he doesn’t have one, he looses almost 50% to tax and government. I think it best in this situation to write it all to [mother]. And then when he is well he can over write that will anytime. I’m thinking of speaking to [mother] and preparing a basic will and getting papaz finger print. Please let me know what u all think.'
    add('siblings','sr','2016-08-28','11:46',quote,origin='verbatim_quote',anchor=quote)
    add('siblings','sh','2016-08-28','12:03',"Yes, I think that's best for mum",origin='judgment_paraphrase',anchor='Sharmila and Oormila replied saying they were in favour.')
    add('siblings','oo','2016-08-28','12:19',"I'm ok with that too",origin='judgment_paraphrase',anchor='Sharmila and Oormila replied saying they were in favour.')
    add('siblings','sr','2016-08-28','12:34',"I'll speak to her")
    add('siblings','oo','2016-08-28','12:36',"Message here when you have")
    # Do not invent a response confirming execution, fingerprint, or dispatch of a will.
    add('siblings','oo','2016-08-29','09:18',"I'm going in to see papa today",origin='judgment_paraphrase',
        anchor='The Deceased was visited on 29')
    add('siblings','sr','2016-08-29','09:42',"I'm going too. What time are you thinking?")
    add('siblings','oo','2016-08-29','09:50',"Not sure yet, I'll text you")
    add('siblings','sr','2016-08-29','09:52',"ok")
    # A later private scene built around a single surviving quote. No fake document delivery.
    add('brother','oo','2017-12-03','18:07',"Can we talk about this please")
    add('brother','sk','2017-12-03','18:29',"I'm not free just now")
    add('brother','oo','2017-12-03','18:32',"When then?")
    add('brother','sk','2017-12-03','18:48',"We should talk properly. This is going round in circles")
    quote2='That’s exactly my problem, I can’t speak to idiots! Ur the executor so I need you to give me what papa said was for me.'
    add('brother','oo','2017-12-03','18:51',quote2,origin='verbatim_quote',anchor=quote2)
    add('brother','sk','2017-12-03','19:16',"I'm not going to argue on here")
    add('brother','oo','2017-12-03','19:18',"I just want a straight answer")
    constraints=[
        '28 Aug 2016 Srimila 的原话整段只做一条，不把判决编辑的连续文本擅自切成多个真实发送动作；保留 looses、papaz、u 和 [mother]。',
        '原话中的税率是人物的说法，不是本数据集提供的税务结论，也不据此建法律规则题。',
        '姐妹赞成由判决支持，具体短句为转写，不编成放弃遗产份额的承诺。',
        '8 Aug 遗嘱的执行、发现时间及知悉时间有争议；不制造当日签署确认、发现遗嘱照片或送达全文的消息。',
        'Srikumaran 所称 1 Dec 2016 22:41 消息仅属其证词。当前场景不把这项证词扩写成已恢复的原始聊天。',
        '没有添加亲属承认伪造/放弃/指定份额等改变争议的关键新证据。',
        '3 Dec 2017 原话前后是创作衔接，其前因无法从原判决恢复；场景只提供一种可能。',
        '保留家人称 papa、mum 和短回复；Srimila 虽为律师，聊天里仍按实际女儿角色呈现，不新增诉讼律师。']
    changes=[
        {'before':'round_001 把 Srimila 的 28 Aug 原话拆成数条，并用其他消息讲述遗嘱、债务和分配。','after':'m006 为完整单条；m007–m010 仅赞成和联络，不宣布执行结果。','reason':'真实家庭对话允许长消息；原话不能为了排版擅自制造新发送动作。','feedback':'参照归档历史反馈的原话保留原则；不是该英文案件的新人工评分。'},
        {'before':'round_001 m022–m026 由证人所称的一条消息扩成“Srimila found it”“It’s dated 8 August”等完整问答。','after':'不编出这段确认细节的问答；私聊围绕 2017 年确有记载的一条请求。','reason':'这些扩写会改变对当事人何时知道何种遗嘱细节的判断；不能把事后证词视为已恢复的聊天。','feedback':'判决正文 §25–29 对发现、知悉、首次看见时间的不同陈述。'},
        {'before':'多条消息承担案件摘要：列举病程、债务、遗产分配。','after':'m004–m005 问消息；m011–m014 安排探望；m015–m021 约谈与回避。','reason':'家人有既有背景，不会每次重讲案件事实；衔接不加入新的分配承诺。','feedback':'迁移历史“过于书面化”及“增加停顿语、重复语”的建议，不强制套用 emoji。'}]
    questions=[
        {'id':'q1','question':'Who proposed the will arrangement on 28 August, and what was proposed? Is the screenshot proof that the proposal was carried out?',
         'answer':'Srimila proposed a basic will leaving it to [mother], possibly using papa’s fingerprint. The group shows support but no execution confirmation; the screenshot does not prove a will was made or signed.','message_ids':['m006','m007','m008'],'type':'proposal_vs_execution'},
        {'id':'q2','question':'Does Oormila’s group response show that she abandoned every later estate claim? Compare it with her private message to Srikumaran.',
         'answer':'No explicit waiver appears. She supports the August proposal but in December 2017 asks the executor to give her what papa said was for her. These messages alone do not settle her legal entitlement.','message_ids':['m006','m008','m019'],'type':'cross_conversation'},
        {'id':'q3','question':'Can these chats establish when Oormila first received or inspected the will document?',
         'answer':'No. There is a proposal and a later reference to the executor, but no document delivery or acknowledgement of inspecting a will. Knowledge of an executor cannot establish receipt of the document.','message_ids':['m006','m019'],'whole_case_required':True,'type':'evidence_limit'}]
    return w.finish(constraints,changes,questions)


def main():
    cases=[chinese(),english()]
    save(OUT/'manifest.json',{'round':'round_002','method':'direct Codex writing + source constraint review + screenshot visual review',
          'new_model_calls':0,'previous_round_preserved':True,'v1_untouched':True,'case_ids':[x['id'] for x in cases],
          'purpose':'两案内容与截图复审，不是新一轮批量模型生成，不是人工认证或难度认证。'})
    print(json.dumps({'cases':len(cases),'messages':sum(len(c['messages']) for c in cases)},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
