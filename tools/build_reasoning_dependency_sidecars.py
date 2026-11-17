"""Bind six existing development questions to observable prerequisite graphs.

All products are new sidecars. Render coverage is never called legal sufficiency.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ['zh/zh_sales_146', 'en/en_probate_283']

# (node_id, operation, source message IDs, prerequisites, target judgment)
GRAPHS = {
    ('zh_sales_146','q1'): [
        ('f_contract','read_attachment',['m008'],[], '合同条目：SLW200-400GB，N=45千瓦'),
        ('f_sample','read_attachment',['m021'],[], '样本：SLW200-400GB，37kW'),
        ('f_roles','local_role_anchor',['m001','m019'],[], '只采用图示陈会计、刘总及李某某称呼'),
        ('i_model','object_alignment',[],['f_contract','f_sample'], '同一型号字符串；不据此证明同一真实订单全部条款'),
        ('c_comparison','comparison',[],['i_model','f_roles'], '两组会话材料功率分别45与37；不自动证明变更合意'),
    ],
    ('zh_sales_146','q2'): [
        ('f_payments','read_amount_date',['m011','m014','m016'],[], '三笔付款消息及可见日期；银行实际到账另查'),
        ('f_arrival','read_date',['m022'],[], '图示2024-03-30货都到了'),
        ('i_sum','arithmetic',[],['f_payments'], '84000+60000+136000=280000'),
        ('i_order','date_comparison',[],['f_payments','f_arrival'], '最后付款消息3月28日在图示到货3月30日之前'),
        ('c_answer','compound_factual_answer',[],['i_sum','i_order'], '合计28万且最后付款在到货之前；不是发货前付清的证明'),
    ],
    ('zh_sales_146','q3'): [
        ('f_sample','unilateral_statement',['m020','m021'],[], '供方发送样本/参数'),
        ('f_objection','counterevidence',['m025'],[], '刘总质疑为何进37'),
        ('i_scope','full_provided_record_scan',[],[], '检查全部提供的会话，不能用引用页代替全记录'),
        ('i_assent','intent_and_condition',[],['f_sample','f_objection','i_scope'], '单方发送不等于买方同意，当前提供记录未见明确同意'),
        ('c_limit','evidence_limit',[],['i_assent'], '本组不足证明变更合意；不等于真实世界从无其他交流'),
    ],
    ('en_probate_283','q1'): [
        ('f_proposal','read_proposal_speaker',['m006'],[], 'Srimila提出准备遗嘱与指纹安排'),
        ('f_support','read_response',['m007','m008'],[], '群内出现支持回复；绿色回复身份需另查'),
        ('i_scope','full_provided_record_scan',[],[], '检查提供记录内是否有制作/签署确认'),
        ('i_execution','proposal_vs_execution',[],['f_proposal','f_support','i_scope'], '提议/支持不证明已经制作或签署'),
        ('c_answer','evidence_limit',[],['i_execution'], '可识别提议人与内容，实际执行unknown；不裁定遗嘱有效性'),
    ],
    ('en_probate_283','q2'): [
        ('f_support','read_response',['m006','m008'],[], '绿色发言者支持群内提议'),
        ('f_claim','read_response',['m019'],[], '私人聊天绿色发言者请求executor给付'),
        ('i_identity','cross_conversation_identity',[],['f_support','f_claim'], '需确认两个绿色发言者是同一人及其身份；case.json中的viewer_id不是截图证据'),
        ('i_intent','intent_and_scope',[],['i_identity'], '同意安排与明确放弃所有遗产权利是不同意思表示'),
        ('c_limit','evidence_limit',[],['i_intent'], '不足证明全面弃权或最终继承权；缺实名锚点时分开描述两个会话'),
    ],
    ('en_probate_283','q3'): [
        ('f_proposal','read_proposal',['m006'],[], '群聊出现拟准备遗嘱的提议'),
        ('f_executor','read_role_reference',['m019'],[], '私人聊天提及executor'),
        ('i_scope','full_provided_record_scan',[],[], '检查整个提供记录的文书交付/阅览确认'),
        ('i_receipt','knowledge_vs_receipt',[],['f_proposal','f_executor','i_scope'], '知道executor或有拟立遗嘱讨论不等于收到遗嘱文书'),
        ('c_limit','evidence_limit',[],['i_receipt'], '无法从这些聊天确定首次收到/阅览遗嘱时间'),
    ],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value, lines=False):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        if lines:
            for row in value: f.write(json.dumps(row,ensure_ascii=False)+'\n')
        else:
            json.dump(value,f,ensure_ascii=False,indent=2)
            f.write('\n')


def covers(required, images):
    valid = []
    for n in range(1,len(images)+1):
        for indices in itertools.combinations(range(len(images)),n):
            seen = {m for i in indices for m in images[i]['message_ids']}
            if required <= seen and not any(set(v) <= set(indices) for v in valid):
                valid.append(list(indices))
    return [[images[i]['page'] for i in indices] for indices in valid]


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output).resolve();out.relative_to(ROOT)
    if out.exists():raise FileExistsError('Choose a new sidecar directory.')
    protected={}; rows=[]
    for name in CASES:
        folder=ROOT/'datasets/v2.0.0/round_002'/name
        loaded={}
        for file in ['case.json','questions.review.json','render.json','tasks.image_only.json']:
            q=folder/file;protected[str(q.relative_to(ROOT)).replace('\\','/')]=sha(q)
            loaded[file]=json.loads(q.read_text(encoding='utf-8'))
        case=loaded['case.json'];messages={m['id']:m for m in case['messages']};images=loaded['render.json']['images']
        for img in images:
            q=folder/img['path'];assert sha(q)==img['sha256']
            protected[str(q.relative_to(ROOT)).replace('\\','/')]=sha(q)
        for question in loaded['questions.review.json']:
            spec=GRAPHS[(case['id'],question['id'])];nodes=[]
            known=set()
            for nid,op,mids,deps,target in spec:
                assert set(deps)<=known;known.add(nid)
                refs=[]
                for mid in mids:
                    message=messages[mid]
                    for img in images:
                        for box in img['boxes']:
                            if box['message_id']!=mid:continue
                            x,y,w,h=box['bbox_pixels'];bounds=[x,y,x+w,y+h]
                            assert 0<=x<x+w<=img['width'] and 0<=y<y+h<=img['height']
                            refs.append({'message_id':mid,'image':str((folder/img['path']).relative_to(ROOT)).replace('\\','/'),
                                'image_sha256':img['sha256'],'render_page':img['page'],'evidence_page':None,
                                'conversation_id':message['conversation_id'],'bbox_xyxy':bounds,
                                'bbox_scope':'message_block_not_date_separator',
                                'text':message['text'],'attachment':message.get('attachment'),
                                'timestamp':message['timestamp'],'minute_basis':message.get('minute_basis'),
                                'origin_type':message['origin_type'],'source_refs':message['source_refs']})
                nodes.append({'id':nid,'operation':op,'depends_on':deps,'message_ids':mids,
                    'target_judgment':target,'source_refs':refs,'review_status':'AI_development_draft',
                    'professional_signoff':False,'legal_score':None})
            required={m for _,_,mids,_,_ in spec for m in mids}
            missing=[]
            if case['id']=='en_probate_283' and question['id']=='q2':
                missing=['explicit_visible_shared_viewer_identity_anchor_or_authorized_case_identity_context']
            whole=any(n['operation']=='full_provided_record_scan' for n in nodes)
            rows.append({'task_id':case['id']+'_'+question['id'],'original_question':question['question'],
                'original_reference_answer':question['answer'],'reference_status':question['status'],
                'purpose':'development_dependency_annotation_not_new_gold',
                'nodes':nodes,'dimensions':sorted({n['operation'] for n in nodes}),
                'render_message_coverage_minimal_page_sets':covers(required,images),
                'coverage_is_not_evidence_sufficiency':True,'full_provided_record_scan_required':whole,
                'provided_record_pages':[i['page'] for i in images] if whole else None,
                'missing_evidence':missing,'minimal_sufficient_sets':[],
                'minimal_sufficiency_status':'not_certified', 'multihop_difficulty_status':'not_certified',
                'scores':{'fact_extraction':None,'identity_alignment':None,'time_condition':None,
                    'legal_conclusion':None,'citation_grounding':None,'missing_evidence_detection':None}})
    out.mkdir(parents=True,exist_ok=False)
    dump(out/'reasoning_graphs.review.jsonl',rows,lines=True)
    after={q:sha(ROOT/q) for q in protected};assert protected==after
    dump(out/'source_integrity.json',{'before':protected,'after':after,'unchanged':True})
    summary={'questions_annotated':len(rows),'rendered_images_bound':9,'original_files_checked':len(protected),
        'original_files_unchanged':True,'legal_scores_published':False,'certified_multihop_questions':0,
        'identity_anchor_review_needed':['en_probate_283_q2'],
        'new_api_calls':0,'schema':'observable_dependency_graph_v1'}
    dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
