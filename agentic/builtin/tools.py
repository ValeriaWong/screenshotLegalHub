"""Deterministic atomic operations owned by this package, not an older pipeline."""
import re
from decimal import Decimal
from ..contracts import HarnessError
from ..primitives import digest
from ..tools import Tool, ToolRegistry
from .contracts import (CaseInput, AnalysisPlan, Ledger, Fact, AssessmentInput, Assessment,
                        Check, GapsInput, Gaps, Gap, ReportInput, ReportData)

STAGES = ['planning', 'facts', 'assessment', 'gaps', 'synthesis']
_AMOUNT = re.compile(r'(?<![\d.,+−-])([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\s*(万|千)?\s*元')
_LABELS = {
    'borrowing_statement': ('借款', '借给', '借我', '向你借', '归还'),
    'payment_statement': ('已转账', '已支付', '已付款', '转账成功'),
    'receipt_statement': ('收到', '收到了', '已到账'),
    'investment_statement': ('投资', '入股', '股权'),
    'future_or_conditional': ('下周', '月底', '以后', '计划', '如果', '准备'),
    'negation': ('不是', '没有', '未收到', '不认可'),
}

def plan_case(value, ctx, key):
    joined = value.question + ' '.join(s.text for s in value.sources)
    focus = ['identity', 'source_quality', 'chronology']
    if _AMOUNT.search(joined):
        focus.append('amounts')
    if any(x in joined for x in ('争议', '投资', '不是', '矛盾', '解释')):
        focus.append('alternatives')
    return AnalysisPlan(objective=value.question, focus=focus, stages=STAGES,
                        acceptance=['所有输入来源入账且原文不变', '缺证保持未知',
                                    '推断附引用和不确定性', '五阶段均通过确定性 Review'])

def extract_records(value, ctx, key):
    facts = []
    for source in value.sources:
        amounts = []
        for match in _AMOUNT.finditer(source.text):
            amount = Decimal(match[1].replace(',', '')) * {'万':10000, '千':1000, None:1}[match[2]]
            amounts.append(format(amount, '.2f'))
        facts.append(Fact(source_id=source.source_id, quote=source.text, speaker=source.speaker,
                          time=source.time, time_precision=source.time_precision, source_kind=source.kind,
                          labels=[k for k, words in _LABELS.items() if any(w in source.text for w in words)],
                          amounts=amounts, source_digest=digest(source.model_dump(mode='json'))))
    return Ledger(facts=facts, undated_sources=[f.source_id for f in facts if f.time is None],
                  note='金额是文本提及，不累加为实际流水；标签是词面线索，需结合否定、条件和上下文。原文与时间均为调用方提供，尚未核验真实性。')

def assess_evidence(value, ctx, key):
    facts = value.ledger.facts
    ids = [f.source_id for f in facts]
    checks = [Check(check_id='source_quality', title='材料可追溯性', status='observed',
                    detail=f'已逐条保留 {len(facts)} 条输入文本及其摘要；摘要不证明原件真实性。', source_ids=ids),
              Check(check_id='identity', title='主体与材料真实性', status='unknown',
                    detail='发言人标签来自输入，未完成身份、授权、材料完整性与真实性核验。', source_ids=ids)]
    focus = set(value.plan.focus)
    if 'chronology' in focus:
        uncertain = [f.source_id for f in facts if f.time_precision != 'day']
        checks.append(Check(check_id='chronology', title='时间顺序与精度',
                            status='unknown' if uncertain else 'observed',
                            detail=(f'{len(uncertain)} 条材料没有日级时间；不补造日期，也不把输入顺序当事件顺序。' if uncertain
                                    else '可按调用方提供的日期展示；同日先后顺序和时区仍不能由此确定。'),
                            source_ids=uncertain or ids))
    if 'amounts' in focus:
        amounts = sorted({a for f in facts for a in f.amounts}, key=Decimal)
        mentions = [f.source_id for f in facts if f.amounts]
        checks.append(Check(check_id='amounts', title='金额提及与资金流', status='candidate',
                            detail='材料提及金额：'+('、'.join(amounts) if amounts else '未识别到明确数字金额')+' 元。重复提及不累加；聊天付款/收款陈述不等于已核验银行流水。', source_ids=mentions or ids))
    if 'alternatives' in focus:
        borrowing = [f.source_id for f in facts if 'borrowing_statement' in f.labels]
        investment = [f.source_id for f in facts if 'investment_statement' in f.labels]
        checks.append(Check(check_id='alternatives', title='竞争性解释',
                            status='candidate' if borrowing and investment else 'unknown',
                            detail=('同时出现借款/归还与投资表述，需要核对是否涉及同一交易、完整上下文与反向材料；不能仅凭关键词决定交易性质。'
                                    if borrowing and investment else '目前词面规则不足以建立完整替代解释；缺少反向材料不等于不存在反向解释。'),
                            source_ids=list(dict.fromkeys(borrowing+investment)) or ids))
    future = [f.source_id for f in facts if 'future_or_conditional' in f.labels]
    if future:
        checks.append(Check(check_id='future', title='未来或附条件表述', status='candidate',
                            detail='存在未来或条件词，应按原文核验各子句；不得把尚未履行的承诺计入已完成付款。', source_ids=future))
    return Assessment(checks=checks, conclusion=f'已整理 {len(facts)} 条材料及 {len(checks)} 项检查。可展示文本中的交易线索，但主体、原件真实性、资金流及完整背景仍待核验，当前不足以形成确定法律结论。')

def map_gaps(value, ctx, key):
    facts = value.ledger.facts
    ids = [f.source_id for f in facts]
    items = [
        Gap(gap_id='traceability', title='输入文本与来源绑定', method='code', status='completed',
            rationale='已建立逐条原文、来源 ID 和内容哈希；完成范围仅为输入文本可追溯。', action='补充原始材料后再次核验完整性。', source_ids=ids),
        Gap(gap_id='authenticity', title='主体身份与原始材料真实性', method='evidence', status='needs_evidence',
            rationale='名称/昵称与文本哈希不能证明真实身份、授权或未篡改。', action='提供原始载体、完整会话、身份或授权材料。', source_ids=ids),
        Gap(gap_id='semantic', title='语义、条件与反向解释', method='model', status='candidate',
            rationale='模型和阶段 Prompt 可提出带引用的解释；代码只能识别有限词面线索。', action='配置模型后逐阶段分析，保留候选状态并经独立复核。', source_ids=ids),
        Gap(gap_id='professional', title='法律适用与证据充分性', method='human', status='needs_review',
            rationale='适用法域、完整证据及专业判断不由本地软件测试或模型置信度替代。', action='由合适专业人员核实适用规则、反证和必要前提。', source_ids=ids),
    ]
    uncertain = [f.source_id for f in facts if f.time_precision != 'day']
    if uncertain:
        items.append(Gap(gap_id='time_precision', title='事件日期与顺序', method='evidence', status='needs_evidence',
                         rationale='部分日期未知或仅精确到月；Prompt 不能补出可靠日级日期。', action='补充时间戳、相邻上下文或其他时间证据。', source_ids=uncertain))
    if any(f.amounts for f in facts):
        bank = [f for f in facts if f.source_kind == 'bank_record']
        items.append(Gap(gap_id='money_flow', title='实际资金流与重复金额', method='evidence', status='needs_evidence',
                         rationale=('已提供标注为银行记录的文本，但仍需核验原件、双方账户及交易对应关系。' if bank else '当前材料的金额提及不能代替真实资金流水。'),
                         action='核对交易号、出入账主体、时间与金额，分别核实付款、收款和还款。', source_ids=[f.source_id for f in facts if f.amounts]))
    return Gaps(items=items)

def compose_report(value, ctx, key):
    return ReportData(case=value.case, plan=value.planning.plan, ledger=value.facts.ledger,
                      assessment=value.assessment.assessment, gaps=value.gaps.gaps,
                      stages=[v.meta for v in (value.planning,value.facts,value.assessment,value.gaps)],
                      conclusion=value.assessment.assessment.conclusion)

def register_tools():
    registry = ToolRegistry()
    for name, input_type, output_type, handler, description in [
        ('plan_case', CaseInput, AnalysisPlan, plan_case, '依据问题与文本线索规划分析重点'),
        ('extract_records', CaseInput, Ledger, extract_records, '原文账本、时间精度、金额提及与来源哈希'),
        ('assess_evidence', AssessmentInput, Assessment, assess_evidence, '检查金额、时间、条件与竞争解释'),
        ('map_gaps', GapsInput, Gaps, map_gaps, '区分代码、模型、证据与人工可补全的缺口'),
        ('compose_report', ReportInput, ReportData, compose_report, '聚合已复核阶段为报告数据'),
    ]:
        registry.register(Tool(name, '0.2', input_type, output_type, handler,
                               permissions=frozenset({'evidence:analyze'}), description=description))
    return registry
