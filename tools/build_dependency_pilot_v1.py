"""Create new fictional dependency cases, screenshots and finite-world checks.

The finite model is a declared development oracle, never a lawyer's gold.
Original evidence and historical runs remain read-only.
"""
import argparse
import copy
import hashlib
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from render_v2_round2 import Browser, render_case

ROLES = ['bridge', 'clause', 'ledger', 'dispatch']
FIELDS = {
    'bridge': ['payment_map', 'dispatch_map'],
    'clause': ['required'],
    'ledger': ['payment_ref', 'last_amount', 'last_day'],
    'dispatch': ['dispatch_ref', 'dispatch_day'],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value, lines=False):
    with path.open('x', encoding='utf-8', newline='\n') as file:
        if lines:
            for row in value: file.write(json.dumps(row, ensure_ascii=False)+'\n')
        else:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write('\n')


def domain(language):
    if language == 'zh':
        return {'payment_map':['TX82','TX93'], 'dispatch_map':['LK74','LK85'],
                'payment_ref':['TX82','TX93'], 'dispatch_ref':['LK74','LK85'],
                'required':[280000,144000,290000], 'last_amount':[136000,135000],
                'last_day':['2024-03-28','2024-03-31'],
                'dispatch_day':['2024-03-30','2024-03-27']}
    return {'payment_map':['PX63','PX74'], 'dispatch_map':['D18','D29'],
            'payment_ref':['PX63','PX74'], 'dispatch_ref':['D18','D29'],
            'required':[2500,1000,2600], 'last_amount':[1500,1490],
            'last_day':['2024-09-08','2024-09-10'],
            'dispatch_day':['2024-09-09','2024-09-07']}


def worlds(language):
    values = domain(language)
    return [dict(zip(values, row)) for row in itertools.product(*values.values())]


def evaluate(world, language):
    # Only judge the reported payment batch, not unseen funds or enforceability.
    first = 144000 if language == 'zh' else 1000
    first_day = '2023-10-27' if language == 'zh' else '2024-09-04'
    if world['payment_map'] != world['payment_ref']:
        return 'not_established'
    if first + world['last_amount'] < world['required']:
        return 'not_satisfied'
    if world['dispatch_map'] != world['dispatch_ref']:
        return 'not_established'
    paid_before = (first if first_day < world['dispatch_day'] else 0)
    if world['last_day'] < world['dispatch_day']:
        paid_before += world['last_amount']
    return 'satisfied' if paid_before >= world['required'] else 'not_satisfied'


def subset_check(actual, language, roles, universe):
    observed = {field:actual[field] for role in roles for field in FIELDS[role]}
    compatible = [w for w in universe if all(w[key] == value for key,value in observed.items())]
    outcomes = sorted({evaluate(w, language) for w in compatible})
    # Ambiguous evidence must not be scored against the full-record label.
    expected = outcomes[0] if len(outcomes) == 1 else 'not_established'
    return {'roles':list(roles), 'compatible_worlds':len(compatible),
            'possible_full_world_labels':outcomes, 'expected_subset_answer':expected,
            'determinate_under_declared_domain':len(outcomes)==1,
            'ambiguity_witnesses':[{**next(w for w in compatible if evaluate(w,language)==label),
                                    'label':label} for label in outcomes],
            'certification_status':'finite_model_checked_independent_review_pending'}


def question(language):
    if language == 'zh':
        return ('只根据所给截图，对订单R17判断：图示这组到账款项是否满足双方约定的付款前提？'
                '以消息报告的事实为条件，只判断这组款项，不推定截图外另有付款；'
                '不裁判真实证据真伪、合同效力或最终违约责任。')
    return ('Using only the screenshots, does the shown payment batch satisfy the agreed payment prerequisite '
            'for marking file E42 settled? Treat the reported events as conditional facts and assess this batch only; '
            'do not assume unseen payments. Do not decide authenticity, enforceability, or whether a release actually occurred.')


def prompt(language):
    base = question(language)
    if language == 'zh':
        return base + ('\n返回JSON：{"answer":"satisfied|not_satisfied|not_established",'
            '"identity_alignment":{"statement":"简短的身份/订单/流水关联判断","evidence_refs":[]},'
            '"time_condition":{"statement":"金额、消息中事件日期和付款条件判断","evidence_refs":[]},'
            '"legal_conclusion":{"statement":"仅限约定的付款前提","evidence_refs":[]},'
            '"missing_evidence":[]}。引用为{"image_id":"P0","quote":"可见原文"}，P0起按本次输入顺序编号。'
            '条件满足用satisfied；关联已建立而图示款项/时序不满足用not_satisfied；缺证用not_established。'
            '不要把手机状态栏当事件时间。只提交可核对判断，不输出内部思维过程。')
    return base + ('\nReturn JSON {"answer":"satisfied|not_satisfied|not_established",'
        '"identity_alignment":{"statement":"short identity/file/reference alignment judgment","evidence_refs":[]},'
        '"time_condition":{"statement":"amount, reported event dates and prerequisite judgment","evidence_refs":[]},'
        '"legal_conclusion":{"statement":"limited to the agreed payment prerequisite","evidence_refs":[]},'
        '"missing_evidence":[]}. Each evidence ref is {"image_id":"P0","quote":"visible text"}; '
        'number from P0 in the current input order. Use not_satisfied only when the relevant batch is linked '
        'but its amount/timing fails the condition; use not_established for missing evidence. '
        'The phone status bar is not an event timestamp. Submit short verifiable judgments, not private reasoning.')


def make_case(ident, language, w):
    zh = language == 'zh'
    people = [{'id':'viewer','name':'林岚' if zh else 'Alex Reed'},
              {'id':'coordinator','name':'顾经理' if zh else 'Morgan Lee'},
              {'id':'counterparty','name':'杨经理' if zh else 'Taylor West'},
              {'id':'finance','name':'周宁' if zh else 'N North'},
              {'id':'warehouse','name':'仓库小何' if zh else 'Jamie Cole'}]
    if zh:
        blocks = {
          'bridge': [('coordinator',f'林岚，青禾公司的R17订单由你对接。周宁处理的付款流水编号是{w["payment_map"]}，仓库交接单编号是{w["dispatch_map"]}。'),
                     ('viewer','收到，我按这些编号核对这个订单。')],
          'clause': [('counterparty',f'R17付款条件：出库前累计到账不少于{w["required"]:,}元。只有达到这一金额才满足本次出库的付款前提，其他款项不在本次判断内。'),
                     ('viewer','同意，按这条付款条件核对。')],
          'ledger': [('finance',f'我是周宁。对账流水{w["payment_ref"]}：2023年9月14日到账84,000元；2023年10月27日到账60,000元；{w["last_day"]}到账{w["last_amount"]:,}元。这组就是上述三笔到账。'),
                     ('viewer','我收到了这组三笔的对账消息。')],
          'dispatch': [('warehouse',f'交接单{w["dispatch_ref"]}：货物于{w["dispatch_day"]}交承运人并出库。这是出库日期，不是到货日期。'),
                       ('viewer','收到出库记录。')],
        }
    else:
        blocks = {
          'bridge': [('coordinator',f'Alex, for file E42 the Accounts contact is Nora North, who uses N North here. Her payment batch reference is {w["payment_map"]}; the envelope tracking reference is {w["dispatch_map"]}.'),
                     ('viewer','Thanks. I will use those references to check this file.')],
          'clause': [('counterparty',f'For E42, the payment prerequisite for marking this claim settled is at least GBP {w["required"]:,} received before the envelope is handed to the courier. This is the prerequisite we are assessing, not confirmation that a release was issued.'),
                     ('viewer','Agreed. That is the payment prerequisite for this file.')],
          'ledger': [('finance',f'Nora North here. Batch {w["payment_ref"]}: GBP 1,000 received on 2024-09-04; GBP {w["last_amount"]:,} received on {w["last_day"]}. Those are the two receipts in this batch.'),
                     ('viewer','Received your account of the two receipts.')],
          'dispatch': [('warehouse',f'Tracking {w["dispatch_ref"]}: the envelope was handed to the courier on {w["dispatch_day"]}. This is handover, not delivery to the addressee.'),
                       ('viewer','Thank you for the handover record.')],
        }
    conversations, messages = [], []
    interlocutors = dict(zip(ROLES,['coordinator','counterparty','finance','warehouse']))
    for role in ROLES:
        other = interlocutors[role]
        person = next(p for p in people if p['id']==other)
        conversations.append({'id':role, 'title':person['name'], 'viewer_id':'viewer',
                              'participant_ids':['viewer',other], 'is_group':False})
        for number, (sender,text) in enumerate(blocks[role],1):
            messages.append({'id':role+str(number), 'conversation_id':role,'sender_id':sender,
                'timestamp':'2024-04-05 10:0'+str(number) if zh else '2024-09-12 10:0'+str(number),
                'minute_basis':'synthetic_layout_only','date_basis':'fictional_message_date_not_reported_event_date',
                'kind':'text','text':text,'origin_type':'fictional_dependency_experiment','source_refs':[]})
    return {'id':ident,'language':language,'platform':'WeChat' if zh else 'WhatsApp',
            'source_mode':'fully_fictional_dependency_stress_test','not_judgment_reconstruction':True,
            'original_judgment_refs':[], 'participants':people,'conversations':conversations,'messages':messages,
            'status':'author_draft_independent_review_pending',
            'limitations':['No original evidence or real judgment quotation.',
                          'Self-identification is a conditional premise, not verified legal identity.',
                          'Event dates are in message bodies; message timestamps are simulated.',
                          'Only assess the reported batch and the stated prerequisite.']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output).resolve();out.relative_to(ROOT)
    if out.exists():raise FileExistsError('A new directory is required.')
    sources=[ROOT/'tools/render_v2_round2.py', ROOT/'tools/build_dependency_pilot_v1.py',
             ROOT/'datasets/v2.0.0/round_002/zh/zh_sales_146/case.json',
             ROOT/'datasets/v2.0.0/round_002/en/en_probate_283/case.json']
    protected={str(path.relative_to(ROOT)).replace('\\','/'):sha(path) for path in sources}
    out.mkdir(parents=True,exist_ok=False)
    prepared=[]
    for language in ['zh','en']:
        d=domain(language);base={key:values[0] for key,values in d.items()}
        variations=[('base',None,{}),('payment_reference_cf','base',{'payment_map':d['payment_map'][1]}),
                    ('payment_date_cf','base',{'last_day':d['last_day'][1]}),
                    ('amount_cf','base',{'last_amount':d['last_amount'][1]}),
                    ('prerequisite_cf','payment_date_cf',{'required':d['required'][1]}),
                    ('handover_date_cf','base',{'dispatch_day':d['dispatch_day'][1]})]
        scenario_worlds={};universe=worlds(language)
        for variant,parent,changes in variations:
            w=copy.deepcopy(base if parent is None else scenario_worlds[parent]);w.update(changes)
            scenario_worlds[variant]=w
            ident=f'{language}_dep_{variant}';directory=out/language/ident;directory.mkdir(parents=True)
            case=make_case(ident,language,w);put(directory/'case.json',case)
            subsets=[subset_check(w,language,subset,universe) for n in range(5) for subset in itertools.combinations(ROLES,n)]
            label=evaluate(w,language)
            sufficient=[s['roles'] for s in subsets if s['possible_full_world_labels']==[label]]
            minimum=[roles for roles in sufficient if not any(set(other)<set(roles) for other in sufficient)]
            facts={role:{key:w[key] for key in FIELDS[role]} for role in ROLES}
            review={'id':ident,'language':language,'family_id':language+'_dependency_family_001',
                'variant':variant,'counterfactual_parent':f'{language}_dep_{parent}' if parent else None,
                'changed_world_fields':list(changes),'author_reference_answer':label,'world':w,
                'observations_by_role':facts,'subset_checks':subsets,
                'inclusion_minimal_role_sets_under_declared_model':minimum,
                'minimum_cardinality_under_declared_model':min(map(len,minimum)),
                'compatible_world_domain_size':len(universe), 'all_16_role_subsets_checked':True,
                'formal_status':'checked_within_declared_finite_model',
                'semantic_sufficiency_status':'independent_review_pending',
                'professional_legal_status':'not_certified','difficulty_status':'not_empirically_certified',
                'provider_receives_review_data':False,'numeric_legal_score':None}
            if parent:
                differences=[key for key in w if w[key]!=scenario_worlds[parent][key]]
                assert differences==list(changes) and len(differences)==1
            assert label in ['satisfied','not_satisfied','not_established']
            if variant=='base':assert minimum==[ROLES] and label=='satisfied'
            put(directory/'question.review.json',{'question':question(language),'review':review})
            prepared.append((directory,case,review))
    tasks=[];bindings=[]
    with Browser(profile_name='dependency-pilot-001-render') as browser:
        for directory,case,review in prepared:
            render_case(browser,directory)
            render=json.loads((directory/'render.json').read_text(encoding='utf-8'))
            assert len(render['images'])==4 and [img['conversation_id'] for img in render['images']]==ROLES
            paths=[];hashes=[]
            for img in render['images']:
                path=directory/img['path'];paths.append(str(path.relative_to(ROOT)).replace('\\','/'));hashes.append(sha(path))
                bindings.append({'task_id':case['id'],'role':img['conversation_id'],'input_page':img['page'],
                    'image':paths[-1],'sha256':hashes[-1],'width':img['width'],'height':img['height'],
                    'message_boxes':img['boxes'],'court_evidence_page':None})
            tasks.append({'id':case['id'],'family_id':review['family_id'],'language':case['language'],
                'prompt':prompt(case['language']),'images':paths,'image_hashes':hashes,
                'roles':ROLES,'protocol':'conditional_payment_prerequisite_v1',
                'source_mode':'fully_fictional_dependency_stress_test'})
            # Review documents are stored separately, never embedded in provider tasks.
            review['image_role_bindings']=dict(zip(ROLES,paths))
    put(out/'tasks.image_only.jsonl',tasks,lines=True)
    put(out/'reviewer_only.certification_candidates.jsonl',[r for _,_,r in prepared],lines=True)
    put(out/'image_bindings.jsonl',bindings,lines=True)
    after={path:sha(ROOT/path) for path in protected};assert protected==after
    put(out/'source_integrity.json',{'before':protected,'after':after,'unchanged':True,
                                   'previous_cases_used_only_for_research_motifs':True})
    put(out/'manifest.json',{'schema':'dependency_pilot_001','development_only':True,
        'languages':['zh','en'],'families':2,'scenarios':12,'screenshots':48,
        'screenshot_size':[860,1864],'counterfactual_edges':10,'exhaustive_subset_checks':192,
        'original_files_unchanged':True,'human_certification':False,'new_api_calls':0,
        'provider_task_file':'tasks.image_only.jsonl','reviewer_only_file':'reviewer_only.certification_candidates.jsonl',
        'not_judgment_reconstruction':True,'finite_model_does_not_prove_real_world_completeness':True})
    print(json.dumps({'output':str(out),'scenarios':12,'screenshots':48,'subsets_checked':192},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
