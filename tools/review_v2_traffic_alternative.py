from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save
d=OUT/'zh/zh_0086';s=read(d/'alternatives/0085/source.json')
refs=[{'source_id':'p0024','quote':'非机动车交通事故损害责任纠纷一案'},
      {'source_id':'p0043','quote':'微信聊天截图一组，拟证明文昌镇政府对宣城供电公司履行了催促、监督的事实。因该组证据非属二审中新发现的证据且也未超出一审认定的案件事实范围，对该两组证据本院不予采信。'}]
for r in refs:assert r['quote'] in next(p['text'] for p in s['paragraphs'] if p['id']==r['source_id'])
save(d/'root.alternatives.review.json',{'author':'root','full_judgment_read':True,'new_human_score':None,
    'alternatives':[{'source_index':85,'source_chars':len(s['text']),'source_paragraphs':len(s['paragraphs']),
        'decision':'defer','reason':'候补确为非机动车交通事故民事判决，可修正原代表的行政文书选择问题。但全文p0043仅给出微信截图的证明目的及未采信处理，未披露发送人、对话日期、正文或对方回复。p0040有2021年函件与2022年预算书的事实，不能把书证日期冒充微信发送时间，也不能把双方上诉中对费用和承诺的相反说法写成互相认可的微信原话。候补仍缺足以构造聊天证据任务的交流内容。',
        'source_refs':refs}],
    'source_label_action':'retain raw historical cause; candidate source fixes civil/administrative selection mismatch only, not dialogue availability',
    'scope':'full independent alternative read; original selected source unchanged'})
print('traffic alternative fully read; defer recorded')
