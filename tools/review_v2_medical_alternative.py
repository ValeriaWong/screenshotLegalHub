from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save
d=OUT/'zh/zh_0101';s=read(d/'alternatives/0100/source.json')
save(d/'root.alternatives.review.json',{'author':'root','full_judgment_read':True,'new_human_score':None,
    'alternatives':[{'source_index':100,'source_chars':len(s['text']),'source_paragraphs':len(s['paragraphs']),
        'decision':'defer','reason':'全文p0015只披露患者辩称专家在微信发药物照片，没有药品名称、图片内容、具体日期或医生回复；明确治疗建议的其他材料是出院医嘱与通话录音。不能把这些书证、电话原话移作微信处方或专家承诺。p0020仅列微信聊天/支付证据目录，未载支付内容。p0026确认网购药物与骨病治疗相关，但不是医生微信原话。可以保留作医疗费用证据来源，现不足以构造具有完整可见锚点的聊天证据案例。',
        'source_refs':[{'source_id':'p0015','quote':'韩某与被答辩人请到的专家金东旭医生的微信聊天截图内容：金东旭发给答辩人需购买的药物照片等'},
            {'source_id':'p0026','quote':'对于韩某的网购药物2408.26元，经查，从时间来看，系韩某于上诉人处出院后购买；从用途来看，系用于治疗骨病或与治疗骨病有关。'}]}],
    'scope':'independent alternative source read; original primary source remains unchanged'})
for r in read(d/'root.alternatives.review.json')['alternatives'][0]['source_refs']:
    assert r['quote'] in next(p['text'] for p in s['paragraphs'] if p['id']==r['source_id'])
print('medical alternative fully read; defer recorded')
