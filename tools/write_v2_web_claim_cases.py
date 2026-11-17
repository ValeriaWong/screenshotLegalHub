"""Archive two root-authored examples from fully read official judgments.

This is fixed example assembly, not a general language-model generator.
Inputs are fetched snapshots; originals, court outcomes and quoted wording stay separate.
"""
import copy, hashlib, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import read,save
from legalhub.synthesis import paragraphs
OUT=ROOT/'datasets/v2.0.0/round_004'


def source(number):
    ident=f'web_{number:03d}';d=OUT/'acquisition/web'/ident
    text=(d/'extracted.txt').read_text(encoding='utf-8')
    start=text.index('上海市第一中级人民法院\n民事判决书')
    end=text.index('\n点赞\n下载文书',start)
    body=text[start:end]
    (d/'judgment.txt').write_bytes(body.encode('utf-8'))
    p=read(d/'provenance.json');sha=hashlib.sha256(body.encode()).hexdigest()
    s={'id':f'r4_web_{number:03d}','source_index':ident,'source_kind':'official_web_judgment',
       'language':'zh','platform':'WeChat','jurisdiction':'China',
       'cause':'民事>合同、准合同纠纷>合同纠纷>借款合同纠纷>民间借贷纠纷',
       'case_no':re.search(r'案号：(.*)',body).group(1),'title':'上海市第一中级人民法院民间借贷纠纷二审民事判决书',
       'url':p['url'],'source_file':(d/'judgment.txt').relative_to(ROOT).as_posix(),
       'source_sha256':sha,'judgment_text_sha256':sha,'text':body,'paragraphs':paragraphs(body),
       'snapshot_file':(d/'snapshot.html').relative_to(ROOT).as_posix(),'snapshot_sha256':p['snapshot_sha256'],
       'body_extraction':{'from_extracted_char_start':start,'from_extracted_char_end':end,
           'start_anchor':'上海市第一中级人民法院\n民事判决书','end_anchor':'\n点赞\n下载文书',
           'full_judgment_read_by':'root','full_judgment_confirmed':True},'split':'development'}
    return s


def ref(s,quote):
    start=s['text'].index(quote);end=start+len(quote)
    ps=[p for p in s['paragraphs'] if p['char_start']<end and p['char_end']>start]
    return {'source_id':ps[0]['id'],'source_end_id':ps[-1]['id'],'quote':quote,'char_start':start,'char_end':end}


def message(s,ident,cid,sender,text,day,voice=False):
    m={'id':ident,'conversation_id':cid,'sender_id':sender,'text':text,'kind':'text',
       'timestamp':day+'T00:00:00','date_basis':'source_day','minute_basis':'not_visible',
       'origin_type':'verbatim_quote','source_refs':[ref(s,text)]}
    if voice:m['original_medium']='voice_transcription_in_judgment'
    return m


def claim(s,ident,text,label,answer,reason,mids,quote,missing=None,typ=None):
    return {'id':ident,'claim':text,'task_mode':'image_only','label':label,'answer':answer,
            'reasoning':reason,'evidence_message_ids':mids,'source_refs':[ref(s,quote)],
            'missing_evidence':missing or [],'insufficiency_type':typ}


def commit(s,case,claims,constraints):
    d=OUT/'authoring/root'/s['id'];d.mkdir(parents=True,exist_ok=True)
    case['suitability']={'decision':'candidate','reason':'官方二审判决有明确逐字微信与日期，可检验限定材料的主张支持范围。'}
    case['constraints']=constraints
    case['limitations']=['未取得原始聊天截图，界面为合成研究重建。','不根据当前图片推断完整整案裁判结论。']
    save(d/'source.json',s)
    save(d/'source.reading.json',{'source_chars':len(s['text']),'source_paragraphs':len(s['paragraphs']),
        'full_judgment_read':True,'reader':'root','constraints':constraints,
        'court_reasoning_boundary':'一审与二审裁判结论分别阅读，图片支持范围不等于裁判结果。'})
    save(d/'direct.draft.json',case);save(d/'direct.revised.json',copy.deepcopy(case))
    save(d/'codex.review.json',{'full_judgment_read':True,'issues':[],
        'second_pass_result':'逐条核对原话、发送人、日期及图片题支持范围；未另加对话。',
        'independent_reviewer':False,'difficulty_certified':False})
    save(d/'claims.json',{'claims':claims})
    provenance=read(OUT/'acquisition/web'/s['source_index']/'provenance.json')
    provenance.update(full_judgment_confirmed=True,extraction_is_article_body_verified=True,
                      dialogue_feasibility_review_completed=True,status='root_authored_candidate_pending_render')
    save(OUT/'acquisition/web'/s['source_index']/'provenance.json',provenance)


def main():
    s=source(1)
    quoted='2019年4月21日周宏顺通过银行转账的方式向杨爱霖名下银行账号为XXXXXXXXXXXXXXX4823的账户转账100,000元。周宏顺曾于2021年7月9日通过微信向杨爱霖表示“在吗？”“借的什么时候还”“回个电话”，但未有回应。'
    case={'participants':[{'id':'zhou','name':'周宏顺','role':'微信催款发送者'},{'id':'yang','name':'杨爱霖','role':'催款对象，判决记未有回应'}],
        'conversations':[{'id':'c1','title':'杨爱霖','viewer_id':'zhou','participant_ids':['zhou','yang'],'is_group':False}],
        'facts':[{'id':'f01','statement':'发送者2021年7月9日催款，判决未记录回复；2019年付款为银行转账。','status':'judicial_finding','source_refs':[ref(s,quoted)]}],
        'messages':[message(s,f'm{i:03d}','c1','zhou',q,'2021-07-09') for i,q in enumerate(['在吗？','借的什么时候还','回个电话'],1)],
        'questions':[{'id':'q1','question':'发送方要求对方做什么？','answer':'回应借款何时归还，并回电话。','message_ids':['m002','m003'],'type':'meaning','whole_case_required':False},
                     {'id':'q2','question':'仅凭这三句能确认借款本金或对方已经认可吗？','answer':'不能，三句未写本金，也没有对方的认可回复。','message_ids':['m001','m002','m003'],'type':'evidence_limit','whole_case_required':True}]}
    claims=[claim(s,'cs1','发送方在询问其所称借款何时归还。','supported','支持这一有限主张。','“借的什么时候还”表现发送方催还，不能扩大为对方也确认借款。',['m002'],quoted),
      claim(s,'cs2','发送方要求对方回电话。','supported','支持。','可见“回个电话”。',['m003'],quoted),
      claim(s,'cs3','对方已经回复并确认这笔钱是借款。','insufficient','当前片段不足以支持。','画面只有发送方文字，没有对方确认；缺失回复不能直接断定对方否认。',['m001','m002','m003'],quoted,['对方针对借款性质的回应'],'consent_not_shown'),
      claim(s,'cs4','这组聊天明确写出了借款本金为10万元。','insufficient','无法由图片确定本金。','三句没有金额；不能把原判决中的银行流水金额补入图片答案。',['m001','m002','m003'],quoted,['可见的借款金额约定或关联流水'],'amount_scope_mismatch'),
      claim(s,'cs5','对方已实际归还所称借款。','insufficient','不能支持已还款。','催问还款时间不是实际履行；截图没有还款确认或交易凭证。',['m002'],quoted,['实际还款凭证与款项关联'],'statement_not_performance')]
    commit(s,case,claims,['只重建2021年7月9日三条原话，不造对方回复。','2019年银行转账不能画成微信转账卡，金额不提供给纯图答案。','分钟00:00只作内部排序，截图不显示，不作为真时间。','二审实际改判支持债权；纯图判别不能直接复制一审未采信结果。'])

    s=source(3);t=s['text']
    father=re.search('2020年8月11日，张某1给程某发送微信语音，内容为“(.*?)”“(.*?)”，程某回复：“(.*?)”',t,re.S)
    mother1=re.search('2018年8月4日，张某1配偶柴某给程某发送微信：“(.*?)”，程某回复：“(.*?)”',t,re.S)
    mother2=re.search('2019年2月23日，柴某发送微信给程某：“(.*?)”程某回复：“(.*?)”',t,re.S)
    assert father and mother1 and mother2
    msgs=[message(s,'m001','c1','father',father[1],'2020-08-11',True),
          message(s,'m002','c1','father',father[2],'2020-08-11',True),
          message(s,'m003','c1','cheng',father[3],'2020-08-11'),
          message(s,'m004','c2','mother',mother1[1],'2018-08-04'),
          message(s,'m005','c2','cheng',mother1[2],'2018-08-04'),
          message(s,'m006','c2','mother',mother2[1],'2019-02-23'),
          message(s,'m007','c2','cheng',mother2[2],'2019-02-23')]
    case={'participants':[{'id':'father','name':'张某1','role':'程某称爸爸'},{'id':'mother','name':'柴某','role':'张某1配偶'},{'id':'cheng','name':'程某','role':'两个会话中的接收方'}],
      'conversations':[{'id':'c1','title':'张某1','viewer_id':'cheng','participant_ids':['cheng','father'],'is_group':False},
                       {'id':'c2','title':'柴某','viewer_id':'cheng','participant_ids':['cheng','mother'],'is_group':False}],
      'facts':[{'id':'f01','statement':'2020年8月11日张某1语音谈生孩子奖励，程某回复感谢。','status':'judicial_finding','source_refs':[ref(s,father[0])]},
               {'id':'f02','statement':'2019年2月23日柴某谈减肥成功后奖励。','status':'judicial_finding','source_refs':[ref(s,mother2[0])]}],
      'messages':msgs,'questions':[{'id':'q1','question':'两位发送方分别谈到什么奖励条件与金额？','answer':'张某1谈生孩子后100万；柴某谈减肥下来后50万元。','message_ids':['m001','m006'],'type':'cross_conversation_conditions','whole_case_required':True},
      {'id':'q2','question':'这些奖励语句能直接证明全部购房款都属于赠与，或奖励已经支付吗？','answer':'不能。奖励有具体条件，未说明全部购房款性质，也没有奖励付款凭证。','message_ids':['m001','m004','m006'],'type':'scope_and_performance_limit','whole_case_required':True}]}
    claims=[claim(s,'cs1','张某1提出生孩子后奖励100万，柴某提出减肥后奖励50万元。','supported','支持两个具体有条件的奖励表述。','跨两个会话辨别金额与对应条件，不能混成无条件150万元。',['m001','m006'],father[1]),
      claim(s,'cs2','张某1在图中承诺无论是否生孩子都立即给100万。','contradicted','可见语句与这个无条件、立即给付的描述相反。','原话把给钱与生孩子关联，并非图中所说的无条件立即支付。',['m001'],father[1],typ='scope_mismatch'),
      claim(s,'cs3','两个会话足以证明所有购房款和保险款都属于无偿赠与。','insufficient','不足以证明全部款项性质。','奖励和居住祝愿未逐笔指向所有购房、保险付款，不能将部分意思表示扩为全案资金属性。',['m001','m004','m006'],mother1[1],['逐笔款项与赠与意思表示的对应关系'],'scope_mismatch'),
      claim(s,'cs4','柴某已经实际把50万元转给张某2。','insufficient','不足以证明已经转账。','“如果他减肥下来了”以及“马上从我帐上转”是条件性安排，未显示条件成就和付款。',['m006','m007'],mother2[1],['减肥条件成就与对应付款凭证'],'statement_not_performance'),
      claim(s,'cs5','程某已经生下孩子，100万元奖励已经到账。','insufficient','当前图片不能支持两个完成事实。','程某感谢与经营生活表态不是孩子出生或奖励到账凭证。',['m001','m003'],father[3],['孩子出生及奖励付款材料'],'statement_not_performance'),
      claim(s,'cs6','程某回复时表示自己已幸福地住在房子里。','supported','支持这项居住表述。','“现在我们就幸幸福福住在里面啦”是其可见陈述，不扩大为房屋产权登记结论。',['m004','m005'],mother1[2])]
    claims[0]['source_refs'].append(ref(s,mother2[1]))
    commit(s,case,claims,['全部七条原话逐字保留，包括语音转写错字；语音截图为转文字界面，不伪造时长。','两个会话内按各自日期排列，跨会话不假定连续分钟。','没有付款卡或赠与到账消息，不补生孩子、减肥成功、夫妻共同债务追认。','一审与二审对共同债务结论不同；不把隐蔽诉辩、借条和银行流水放进纯图题答案。'])
    print('root authored r4_web_001 and r4_web_003')


if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
