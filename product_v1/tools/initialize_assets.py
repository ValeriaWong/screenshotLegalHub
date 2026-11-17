"""Generate distributable synthetic fixtures and data-only plugin manifests."""
from pathlib import Path
import json
import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]

def write_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding='utf-8')

def initialize():
    pack = ROOT / 'matterpacks/cn/civil/private_lending/1.0.0'
    capabilities = ['claim.identify','fact.instantiate','burden.assign','evidence.map','evidence.strength','evidence.gap','contradiction.detect','strategy.generate','strategy.verify','adversarial.analyze']
    write_yaml(pack/'manifest.yaml', dict(id='cn.civil.private_lending',name_zh='民间借贷',name_en='Private Lending',jurisdiction='CN',practice_area='civil',version='1.0.0',schema_version=1,status='draft',valid_from=None,valid_to=None,expert_review=dict(status='unreviewed',reviewed_by=None,reviewed_at=None),required_capabilities=capabilities))
    definitions = [
        ('agreement','借贷合意','双方是否形成借贷合意？',['借','归还'],['投资'],['聊天原始记录','借条'],'civil-code-679'),
        ('delivery','款项交付','款项是否实际到达借款人账户？',['收到','转账'],[],['银行流水','收款记录'],'lending-9'),
        ('maturity','还款期限','约定还款期限是否届满？',['月底','到期'],[],['完整约定','催告送达记录'],'civil-code-675'),
        ('outstanding','未清偿本金','目前尚未清偿的本金是多少？',['未还','欠款'],['还清'],['完整还款流水','对账记录'],'civil-code-675')]
    elements = []
    for id,title,question,positive,negative,expected,authority in definitions:
        elements.append(dict(id='el.'+id,title=title,facts=[dict(id='fq.'+id,question=question,burden='主张返还本金的出借人（争议抗辩需分别审查）',expected_evidence=expected,signals=positive,negative_signals=negative,authority_ids=[authority])]))
    write_yaml(pack/'claims.yaml',[dict(id='principal',title='返还借款本金',remedy='请求返还经核实的未清偿本金',elements=elements,defenses=[dict(id='investment',title='投资关系抗辩',signals=['投资']),dict(id='repaid',title='已清偿抗辩',signals=['还清'])])])
    write_yaml(pack/'patterns.yaml',[dict(id='transfer_plus_acknowledgment',kind='practice_pattern',signals=['转账','收到'],usually_supports=['agreement','delivery'],risks=['investment_defense'],legal_rule=False)])
    authorities=[]
    for id,title,article,url in [('civil-code-675','中华人民共和国民法典','第675条','https://www.court.gov.cn/zixun/xiangqing/233181.html'),('civil-code-679','中华人民共和国民法典','第679条','https://www.court.gov.cn/zixun/xiangqing/233181.html'),('lending-9','最高人民法院关于审理民间借贷案件适用法律若干问题的规定（2020年第二次修正）','第9条','https://cicc.court.gov.cn/html/1/218/62/84/12844.html')]:
        authorities.append(dict(id=id,type='statute' if id.startswith('civil') else 'judicial_interpretation',title=title,article=article,jurisdiction='CN',valid_from='2021-01-01',valid_to=None,source_url=url,source_digest=None,verification_status='unverified'))
    write_yaml(pack/'authorities.yaml',authorities)
    write_yaml(pack/'tests.yaml',dict(expected_claims=1,expected_facts=4,expert_validation='unreviewed'))
    write_yaml(ROOT/'matterpacks/_template/manifest.yaml',dict(instructions='Copy a version directory; define claims/elements/fact questions, burden, signals, defenses and unverified authorities. Never add executor code to a Matter Pack.'))
    specs = [
        ('evidence.perceive',1,[],['evidence','messages','source_refs'],['perception']),
        ('timeline.build',2,['evidence.perceive'],['messages'],['event']),
        ('matter.route',3,['timeline.build'],['messages','matter'],['matter_candidate']),
        ('claim.identify',3,['matter.route'],['matter'],['claim','element']),
        ('fact.instantiate',4,['claim.identify'],['matter','claims','elements','case'],['fact']),
        ('burden.assign',4,['fact.instantiate'],['matter','facts'],['burden']),
        ('evidence.map',5,['burden.assign'],['matter','facts','messages','source_refs','evidence'],['evidence_link']),
        ('evidence.strength',5,['evidence.map'],['evidence_links','facts'],['strength']),
        ('evidence.gap',6,['evidence.strength'],['matter','facts','evidence_links'],['gap']),
        ('contradiction.detect',6,['evidence.strength'],['facts','evidence_links','messages'],['contradiction']),
        ('strategy.generate',7,['evidence.gap','contradiction.detect'],['proof_graph'],['strategy']),
        ('adversarial.analyze',7,['evidence.gap','contradiction.detect'],['proof_graph','matter'],['defense']),
        ('strategy.verify',8,['strategy.generate','adversarial.analyze'],['proof_graph'],['verification'])]
    for cap,stage,deps,needs,outputs in specs:
        write_yaml(ROOT/'backend/src/screenshotlegal/plugins/skills/manifests'/f'{cap}.yaml',dict(id=cap+'.generic.v1',capability=cap,version='1.0.0',schema_version=1,executor_type='python',applies_to=dict(jurisdictions=['*'],matters=['*'],practice_areas=['*']),input_schema=needs,output_schema=outputs,grounding=dict(require_source_refs=cap in ['timeline.build','evidence.map','contradiction.detect','strategy.generate']),dependencies=deps,side_effects=False,trust=dict(level='builtin'),permissions=dict(network=False,filesystem_read=False,filesystem_write=False,model=False,retrieval=True,authority_search=False),stage=stage))
    write_yaml(ROOT/'profiles/cn_civil_default.yaml',dict(id='cn_civil_default',capabilities={}))
    fixture = ROOT/'fixtures/demo_private_lending'
    fixture.mkdir(parents=True,exist_ok=True)
    font_path=Path('C:/Windows/Fonts/msyh.ttc')
    font=ImageFont.truetype(str(font_path),24) if font_path.exists() else ImageFont.load_default(size=24)
    rows=[('2024-01-05','李四','向你借50000元，月底归还。','agreement'),('2024-01-05','张三','已转账50000元，请查收。','payment'),('2024-01-05','李四','收到50000元，月底归还。','acknowledgment'),('2024-02-01','李四','这笔是投资款，不是借款。','dispute')]
    messages=[]
    for page in (1,2):
        img=Image.new('RGB',(720,640),'#f4f4f1');draw=ImageDraw.Draw(img)
        draw.text((32,25),'合成演示 / 非真实微信记录',fill='#333333',font=font)
        for i,(date,speaker,text,event_type) in enumerate(rows[(page-1)*2:page*2]):
            y=130+i*210
            draw.text((34,y-45),date+'  '+speaker,fill='#555555',font=font)
            draw.rounded_rectangle((30,y,690,y+90),radius=10,fill='white',outline='#cccccc')
            draw.text((45,y+25),text,fill='#222222',font=font)
            messages.append(dict(index=len(messages),page=page,text=text,speaker=speaker,timestamp=date,event_type=event_type,bbox=[30,y,690,y+90]))
        img.save(fixture/f'chat-{page}.png')
    (fixture/'fixture.json').write_text(json.dumps(dict(synthetic=True,messages=messages),ensure_ascii=False,indent=2),encoding='utf-8')

if __name__ == '__main__':
    initialize()
