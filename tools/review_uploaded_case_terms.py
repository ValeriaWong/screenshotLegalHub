"""Source review of the upload acceptance case. Original model response remains intact."""
import copy
import sys
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub import benchmark as b
from legalhub.case_registry import CaseRegistry
from legalhub.casework import atomic_json
from legalhub.case_presentation import localized
cid=b.read(b.ROOT/'reports/v1.1.0_uploaded_test_case.json')['case_id']
registry=CaseRegistry();work=registry.get(cid);material=work.material
terms=copy.deepcopy(work.current['contract_terms']);index={t['key']:t for t in terms}
changes={
'goods':('uncertain','最后一件（展示指向；成交标的待核）','The last item (display reference; agreed goods unresolved)','聊天提到最后一件并介绍材质；具体买卖对象仍需结合完整选款与约定。','The chat refers to the last item and describes its material. The agreed goods require the complete selection and arrangement.'),
'quantity':('uncertain','购买数量未确定','Purchase quantity unresolved','“最后一件”可以指展示顺序，不能直接证明仅购买一件。','“The last item” can refer to display order; it does not establish that only one item was purchased.'),
'specification':('statement','对方介绍“双面羊绒的”','Described as double-sided cashmere','这是对方对物品的介绍；成交物品及材质是否属实仍需核对。','This is the speaker’s description. The agreed goods and actual material require verification.'),
'payment':('statement','左侧称转2000；右侧回复收到','Reported transfer of 2,000; receipt acknowledged','截图记录付款方式请求、转款陈述和收款回复；实际到账、付款人身份、款项用途及是否付清仍需其他证据。','The screenshots contain a payment-method request, transfer statement and acknowledgement. Settlement, payer identity, purpose and full discharge require other evidence.'),
'delivery':('uncertain','有人联系 / 来找对方；交付方式未确定','Someone contacting / visiting; delivery unresolved','“有人找你”和“他后天来找你”没有明确写取货或实际交付；支付宝付款方式也不是商品交付方式。','Contacting or visiting does not explicitly state collection or actual delivery. Alipay is a payment method, not a delivery method.')
}
for key,(status,value,envalue,assessment,enassessment) in changes.items():
    index[key].update(status=status,value=localized(value,envalue),assessment=localized(assessment,enassessment),provenance='assistant_original_source_review')
overlay={'case_id':cid,'source_hashes':{i['image_id']:i['sha256'] for i in material['images']},
'source_corpus_sha256':material['metadata']['source_corpus_sha256'],'contract_terms':terms,
'review_note':localized('本上传验收案的合同要素经助手对照原图修订；法律节点与其他解释仍是模型初稿，未获专业确认。','Contract terms of this upload test were revised against originals. Legal nodes and other explanations remain unverified model drafts.')}
atomic_json(work.home/'presentation.json',overlay)
b.write(b.ROOT/'reports/v1.1.0_upload_term_review.json',{'case_id':cid,'run_id':work.current['run_id'],'changed_keys':list(changes),'original_response_preserved':True,'model_requests':0,'reason':'Source review corrected quantity, goods, material description, reported-payment and delivery overstatements; not independent expert review.'})
print('source-reviewed contract terms; original response preserved')
