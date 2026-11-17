"""One offline, escaped, interactive HTML view of reviewed Run data."""
import base64
import hashlib
import html
import json
import re
from importlib.resources import files
from .builtin.contracts import ReportData
from .contracts import HarnessError
from .model import stage_prompt

STAGE_NAMES = {'planning':'任务规划','facts':'事实整理','assessment':'争点与条件分析','gaps':'缺口补全评估','synthesis':'报告综合'}
STATUS_NAMES = {'completed':'已由代码完成','candidate':'候选 / 待验证','needs_evidence':'需要新证据','needs_review':'需要人工复核'}
METHOD_NAMES = {'code':'代码逻辑','model':'模型推理','prompt':'Prompt 约束','evidence':'外部证据','human':'专业复核'}
LABEL_NAMES = {'borrowing_statement':'借款 / 归还线索','payment_statement':'付款陈述','receipt_statement':'收款陈述',
               'investment_statement':'投资表述','future_or_conditional':'未来 / 条件词','negation':'否定词'}

def esc(value):
    return html.escape(str(value), quote=True)

def refs(ids):
    return ''.join('<button type="button" class="source-link" data-source="'+esc(i)+'">'+esc(i)+' ↗</button>' for i in dict.fromkeys(ids))

def badge(text, kind=''):
    return '<span class="badge '+kind+'">'+esc(text)+'</span>'

def script_json(value):
    text = json.dumps(value,ensure_ascii=False,allow_nan=False)
    for character, escaped in [('<','u003c'),('>','u003e'),('&','u0026'),(chr(8232),'u2028'),(chr(8233),'u2029')]:
        text = text.replace(character,chr(92)+escaped)
    return text

def render_report(run_view, events=()):
    if run_view['status']!='COMPLETED' or any(t['review_status']!='PASS' for t in run_view['tasks'].values()):
        raise HarnessError('REPORT_NOT_REVIEWED')
    if not run_view.get('result') or 'synthesis' not in run_view['result']:
        raise HarnessError('REPORT_UNAVAILABLE')
    report = ReportData.model_validate(run_view['result']['synthesis'])
    case, ledger = report.case, report.ledger
    if len(report.stages)!=5:
        raise HarnessError('REPORT_NOT_REVIEWED')
    package = files('agentic')
    css = package.joinpath('templates/report.css').read_text(encoding='utf-8')
    js = package.joinpath('templates/report.js').read_text(encoding='utf-8')
    capability = json.loads(package.joinpath('builtin/capability-gaps.json').read_text(encoding='utf-8'))
    model_calls = run_view['usage']['model_calls']
    evidence_gaps = sum(g.status=='needs_evidence' for g in report.gaps.items)
    metrics = '<div class="metrics">'+''.join('<div class="metric"><strong>'+str(n)+'</strong><span>'+label+'</span></div>' for n,label in [
        (len(case.sources),'条输入材料'),(len(ledger.undated_sources),'条日期未知'),(evidence_gaps,'项待补证缺口'),(model_calls,'次模型调用')])+'</div>'
    checks = ''.join('<article class="card"><h3>'+esc(c.title)+'</h3><p>'+esc(c.detail)+'</p>'+refs(c.source_ids)+'</article>' for c in report.assessment.checks)
    timeline = ''
    for fact in sorted(ledger.facts,key=lambda f:(f.time is None, f.time or '', f.source_id)):
        timeline += '<article><div class="time">'+esc(fact.time or '日期未知 · 保留原始位置线索')+'</div><strong>'+esc(fact.speaker)+'</strong><blockquote>'+esc(fact.quote)+'</blockquote>'+refs([fact.source_id])+'</article>'
    overview = metrics+'<div class="callout"><h3>当前判断边界</h3><p>'+esc(report.conclusion)+'</p></div>'
    overview += '<div class="columns"><div class="stack"><h2>从材料出发的检查</h2>'+checks+'</div><div class="card"><h2>材料时间轴</h2><p class="muted">日期来自输入；同日排序不代表事件先后。未知日期单列。</p><div class="timeline">'+timeline+'</div></div></div>'
    overview += '<p class="result-note">Review PASS 表示结构、逐字引用与阶段约束通过软件检查。材料真实性、推断的实质支持关系与法律判断仍须核实。</p>'
    model_insights = ''.join('<article class="card"><h3>模型候选判断 · '+STAGE_NAMES[stage.stage]+'</h3><p>'+esc(finding.text)+'</p><small>'+esc(finding.uncertainty)+'</small><div>'+refs(c.source_id for c in finding.citations)+'</div></article>' for stage in report.stages if stage.mode=='model' and stage.stage in {'assessment','synthesis'} for finding in stage.reasoning.findings)
    if model_insights:
        overview += '<div class="section-head"><h2>阶段推理摘要</h2></div><div class="stack">'+model_insights+'</div>'
    rows = ''
    for fact in ledger.facts:
        rows += '<tr data-fact><td>'+refs([fact.source_id])+'<p>'+esc(fact.speaker)+'</p></td><td>'+esc(fact.time or '未知')+'<p class="muted">'+esc(fact.time_precision)+'</p></td><td><p>'+esc(fact.quote)+'</p>'+''.join(badge(LABEL_NAMES.get(k,k),'gray') for k in fact.labels)+'</td><td>'+esc('、'.join(fact.amounts) or '未识别')+'</td></tr>'
    ledger_html = '<h2>事实与来源账本</h2><p class="muted">'+esc(ledger.note)+'</p><label for="source-search">检索原文、来源、发言人或日期</label><br><input class="search" id="source-search" placeholder="例如：投资 / M003 / 2024-01"><p id="search-count" class="count-note" aria-live="polite">显示 '+str(len(ledger.facts))+' 条材料</p><div class="table-wrap"><table><thead><tr><th>来源 / 发言人</th><th>时间 / 精度</th><th>原文与词面线索</th><th>金额提及（元）</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
    filters = '<div class="filters" role="group" aria-label="筛选缺口">'+''.join('<button type="button" data-filter="'+k+'" aria-pressed="'+('true' if k=='all' else 'false')+'">'+v+'</button>' for k,v in [('all','全部'),*STATUS_NAMES.items()])+'</div>'
    gap_cards = ''
    for g in report.gaps.items:
        gap_cards += '<article class="card gap-card" data-gap data-status="'+g.status+'">'+badge(STATUS_NAMES[g.status], 'warn' if g.status in {'needs_evidence','needs_review'} else 'gray')+badge(METHOD_NAMES[g.method])+'<h3>'+esc(g.title)+'</h3><p>'+esc(g.rationale)+'</p><p><strong>下一步：</strong>'+esc(g.action)+'</p>'+refs(g.source_ids)+'</article>'
    capability_rows = ''.join('<tr><td>'+esc(c['name'])+'</td><td>'+esc(c['mechanism'])+'</td><td>'+esc(c['implemented'])+'</td><td>'+esc(c['remaining'])+'</td></tr>' for c in capability)
    gaps_html = '<h2>哪些可以补全，哪些必须保留未知</h2><p class="muted">模型 / Prompt 可补充解释与问题分解；补证和专业复核项不会被模型推断自动关闭。</p>'+filters+'<div class="gap-grid">'+gap_cards+'</div><div class="capability"><h2>程序包能力与项目缺口</h2><p class="muted">实现边界独立于当前材料补证清单。V3 研究认证缺口未因此自动关闭。</p><div class="table-wrap"><table><thead><tr><th>能力</th><th>补全机制</th><th>本包实现</th><th>保留边界</th></tr></thead><tbody>'+capability_rows+'</tbody></table></div></div>'
    stage_cards = ''
    for index, stage in enumerate(report.stages,1):
        task = run_view['tasks'][stage.stage]
        insights = ''
        for finding in stage.reasoning.findings:
            insights += '<div><p>'+badge('候选推断' if finding.kind=='inference' else '原文观察','gray')+esc(finding.text)+'</p><small>'+esc(finding.uncertainty)+'</small><div>'+refs(c.source_id for c in finding.citations)+'</div></div>'
        for proposal in stage.reasoning.gap_proposals:
            insights += '<p>'+badge('待验证缺口建议','warn')+esc(proposal.title)+'：'+esc(proposal.action)+'</p>'+refs(c.source_id for c in proposal.citations)
        if not insights:
            insights = '<p class="muted">本阶段没有新增判断。</p>'
        if stage.reasoning.questions:
            insights += '<p><strong>待验证问题</strong></p><ul>'+''.join('<li>'+esc(q)+'</li>' for q in stage.reasoning.questions)+'</ul>'
        receipt = stage.model_receipt
        execution = ('模型 '+receipt.model+' · 输入 '+str(receipt.input_tokens)+' / 输出 '+str(receipt.output_tokens)+' tokens' if receipt else '代码规则执行 · 模型未调用')
        stage_cards += '<article class="card step"><div class="step-number">'+str(index)+'</div><div><h3>'+STAGE_NAMES[stage.stage]+'</h3>'+badge(task['review_status'])+badge(execution,'gray')+'<p class="muted">尝试 '+str(task['attempts'])+' 次 · 修复 '+str(task['repairs'])+' 次</p>'+insights+'<details><summary>阶段 Prompt 与校验记录</summary><p><small>Prompt SHA-256</small><br><code>'+esc(stage.prompt_digest)+'</code></p><pre>'+esc(stage_prompt(stage.stage))+'</pre><pre>'+esc(json.dumps(task['reviews'],ensure_ascii=False,indent=2))+'</pre></details></div></article>'
    usage = run_view['usage']
    accounting_note = ('含 '+str(usage.get('unsettled_model_calls',0))+' 次未结算调用的保守预留' if usage.get('unsettled_model_calls') else ('已按模型服务 usage 结算' if model_calls else '未发起模型调用'))
    execution_html = '<h2>分阶段执行与 Review</h2><p class="muted">五个 Skills 消费显式依赖，调用包内 Tools；每阶段经过 Schema 和规则校验。</p><div class="callout"><p>实际 Tool 调用 '+str(usage['tool_calls'])+' 次 · 模型调用 '+str(model_calls)+' 次 · Token '+str(usage['tokens'])+' · 配置费率累计 USD '+format(usage['cost'],'.6f')+' · '+accounting_note+'</p></div><div class="stack">'+stage_cards+'</div><details><summary>执行事件与 Trace</summary><pre>'+esc(json.dumps(list(events),ensure_ascii=False,indent=2))+'</pre></details>'
    data = {'report':report.model_dump(mode='json'),'run':run_view,'events':list(events),'capability_gaps':capability}
    values = {
        'TITLE':esc(case.title),'QUESTION':esc(case.question),
        'BADGES':badge('合成演示材料' if case.synthetic else '调用方材料','gray')+badge('5 阶段 Review PASS')+badge('代码推理 · 未调用模型' if not model_calls else '模型候选推理 · 待实质复核','warn'),
        'OVERVIEW':overview,'LEDGER':ledger_html,'GAPS':gaps_html,'EXECUTION':execution_html,
        'FOOTER':'Agentic 0.2 · 本地自包含报告<br>Run '+esc(run_view['run_id'])+'<br>Trace '+esc(run_view['trace_id']),
        'DATA':script_json(data),'SCRIPT':js,'STYLE':css,
        'SCRIPT_HASH':base64.b64encode(hashlib.sha256(js.encode()).digest()).decode(),
        'STYLE_HASH':base64.b64encode(hashlib.sha256(css.encode()).digest()).decode(),
    }
    template = package.joinpath('templates/report.html').read_text(encoding='utf-8')
    return re.sub(r'@@([A-Z_]+)@@',lambda match:values[match[1]],template)
