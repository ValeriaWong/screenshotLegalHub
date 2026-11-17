"""Expose archived judgment text and message grounding for user review.

Does not change approved chat wording, images, or original source files.
"""
from pathlib import Path
import argparse, hashlib, html, json, sys
import openpyxl

ROOT=Path(__file__).resolve().parents[1]
ROUND=ROOT/'datasets/v2.0.0/round_002'
esc=lambda value:html.escape(str(value))


def verify_archive(source):
    path=ROOT/source['source_file']
    result={'source_file':source['source_file'],'source_sha256_expected':source['source_sha256'],
            'source_sha256_actual':hashlib.sha256(path.read_bytes()).hexdigest()}
    assert result['source_sha256_expected']==result['source_sha256_actual']
    if source['language']=='zh':
        book=openpyxl.load_workbook(path,read_only=True,data_only=True)
        sheet=book.active;sheet.reset_dimensions()
        header=next(sheet.iter_rows(min_row=1,max_row=1,values_only=True))
        row_no=source['source_index']+2
        row=next(sheet.iter_rows(min_row=row_no,max_row=row_no,values_only=True))
        values=dict(zip(header,row))
        assert values['content']==source['text']
        assert values['case_no']==source['case_no']
        result.update({'sheet':sheet.title,'excel_row':row_no,
                       'content_cell':openpyxl.utils.get_column_letter(header.index('content')+1)+str(row_no),
                       'case_no_cell':openpyxl.utils.get_column_letter(header.index('case_no')+1)+str(row_no),
                       'court':values.get('court'),'date':values.get('date'),'content_exact':True})
        book.close()
    result['judgment_text_sha256']=hashlib.sha256(source['text'].encode('utf-8')).hexdigest()
    assert result['judgment_text_sha256']==source['judgment_text_sha256']
    return result


CSS='''
*{box-sizing:border-box}body{margin:0;font:16px/1.85 "Microsoft YaHei","Segoe UI",sans-serif;color:#253a31;background:#f1f5f0}main{max-width:1280px;margin:auto;padding:25px}section,header{background:white;padding:28px;border-radius:12px;margin-bottom:22px}h1{font-size:26px;margin:0 0 14px}h2{font-size:22px}h3{font-size:17px}a{color:#13745e}p{white-space:pre-wrap}small,.muted{color:#65786d;font-size:13px}nav{display:flex;gap:18px;flex-wrap:wrap}.meta{display:grid;grid-template-columns:130px 1fr;gap:6px 16px}.meta dt{color:#65786d}.meta dd{margin:0;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #d8e3dc;text-align:left;vertical-align:top;padding:13px;overflow-wrap:anywhere}th{background:#f2f7f2}th:first-child{width:34%}.tag{display:inline-block;padding:2px 9px;border-radius:5px;background:#e6f1e8;color:#237551;font-size:12px}.synthetic{background:#f8f0df;color:#866223}.attachment{background:#e8eef7;color:#425c87}.text{white-space:pre-wrap;margin:6px 0}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.card{background:#f6f9f5;padding:18px;border-radius:8px}.card p{margin:7px 0}.quoted{font-family:"SimSun","Microsoft YaHei",serif;font-size:17px;line-height:2.1;background:#f8faf7;border-left:4px solid #9bbfa6;padding:18px;white-space:pre-wrap}.fulltext{font-family:"SimSun","Microsoft YaHei",serif;color:#222;font-size:18px;line-height:2.15;white-space:pre-wrap;overflow-wrap:anywhere;max-width:950px;margin:auto}.loc{display:none;color:#84998e;font:11px/1.5 Arial;margin-right:9px}.show-locations .loc{display:inline}span:target{background:#fff0b2}details{background:#f6f9f5;border-radius:7px;padding:10px 14px;margin:9px 0}summary{cursor:pointer}.screen{max-width:320px;display:block;margin:10px auto}.status{background:#e9f5ec;padding:12px;border-radius:7px}button{background:#e8f1e9;border:0;border-radius:6px;padding:9px 13px;cursor:pointer;font:14px "Microsoft YaHei"}code{font-size:12px;overflow-wrap:anywhere}.notice{border-left:3px solid #d9bb7c;padding-left:14px}footer{font-size:13px;color:#6b7e72}@media(max-width:720px){main{padding:10px}section,header{padding:17px}.cards{grid-template-columns:1fr}.meta{grid-template-columns:90px 1fr}table{font-size:13px}td,th{padding:8px}.fulltext{font-size:16px}}
'''


def build(directory,verified_source=None):
    source=json.loads((directory/'source.json').read_text(encoding='utf-8'))
    case=json.loads((directory/'case.json').read_text(encoding='utf-8'))
    render=json.loads((directory/'render.json').read_text(encoding='utf-8'))
    check=verified_source or verify_archive(source)
    people={p['id']:p['name'] for p in case['participants']}
    page_map={}
    for image in render['images']:
        for message in image['message_ids']:page_map.setdefault(message,[]).append(image)
    labels={'verbatim_quote':'判决引用原话','judgment_paraphrase':'事实转写 · 说法合成',
            'judgment_attachment_reconstruction':'重建附件 · 原件未取得','synthetic_completion':'创作衔接'}
    counts={k:sum(m['origin_type']==k for m in case['messages']) for k in labels}
    time_labels={'source_minute':'分钟来自判决记载','source_approximate_minute':'判决仅记载约数',
                 'synthetic_layout_only':'分钟为合成排版','not_visible':'来源日期不详，图内不生成时间'}
    rows=[];mdrows=[];exact=[]
    for message in case['messages']:
        tag=labels[message['origin_type']]
        klass='synthetic' if message['origin_type']=='synthetic_completion' else ('attachment' if 'attachment' in message['origin_type'] else '')
        body=message['text']
        if message.get('attachment'):
            a=message['attachment'];body+='\n'+a['title']+'\n'+'\n'.join(k+'：'+v for k,v in a['rows'])
        source_parts=[]
        for ref in message['source_refs']:
            assert source['text'][ref['char_start']:ref['char_end']]==ref['quote']
            links=' / '.join(f'<a href="#{pid}">{pid}</a>' for pid in ref['paragraph_ids'])
            source_parts.append(f'<p class="text">{esc(ref["quote"])}</p><small>全文位置：{links}；字符 {ref["char_start"]}–{ref["char_end"]}</small>')
        if not source_parts:source_parts=['<p>这句话没有判决原话依据，是为交流节奏创作的衔接。不能将其当成真实人物原话。</p>']
        if message.get('attachment'):source_parts.append('<p class="notice">'+esc(message['attachment']['reconstruction_notice'])+'</p>')
        minute_note=time_labels.get(message.get('minute_basis'),'时间依据见结构化记录')
        if message.get('date_basis')=='source_month':minute_note='来源仅载月份，未生成具体日和分钟'
        source_parts.append('<p class="muted">'+minute_note+'</p>')
        links=' · '.join(f'<a href="{image["path"]}">截图第{image["page"]}页</a>' for image in page_map[message['id']])
        display_time=message.get('timestamp') or message.get('time_label') or '日期未载'
        rows.append(f'<tr id="{message["id"]}"><td><small>{message["id"]} · {esc(display_time)}<br>{esc(people[message["sender_id"]])}</small><p class="text">{esc(body)}</p>{links}</td><td><span class="tag {klass}">{tag}</span>{"".join(source_parts)}</td></tr>')
        mdrows.extend([f'### {message["id"]} · {people[message["sender_id"]]} · {message["timestamp"]}',
                       '',f'属性：{tag}。{minute_note}。','',body,'',
                       '判决依据：'+('；'.join(ref['quote'] for ref in message['source_refs']) or '无，属于创作衔接。'),''])
        if message['origin_type']=='verbatim_quote':
            exact_ref=next(ref for ref in message['source_refs'] if message['text']==ref['quote'])
            quote_anchor=exact_ref['paragraph_ids'][0]
            exact.append(f'<div class="card"><small>{message["id"]} · {esc(people[message["sender_id"]])}</small><p>{esc(message["text"])}</p><a href="#{quote_anchor}">查看判决中的原文位置</a></div>')
    # Keep the exact text, including whitespace between chunks; pXXXX are local locator IDs.
    body=[];end=0
    for paragraph in source['paragraphs']:
        start=paragraph['char_start']
        body.append(esc(source['text'][end:start]))
        body.append(f'<span id="{paragraph["id"]}"><span class="loc">{paragraph["id"]}</span>{esc(paragraph["text"])}</span>')
        end=paragraph['char_end']
    body.append(esc(source['text'][end:]))
    exact_from_spans=''.join(source['text'][p['char_start']:p['char_end']] for p in source['paragraphs'])
    assert all(source['text'][p['char_start']:p['char_end']]==p['text'] for p in source['paragraphs'])
    meta=[('案号',source['case_no']),('法院',check.get('court','见全文')),('裁判日期',check.get('date','见全文')),
          ('案由',source['cause']),('归档工作表/原文单元格',f'{check.get("sheet","")}!{check.get("content_cell","")}'),
          ('源文件',source['source_file'])]
    if case.get('case_no')!=source['case_no']:
        meta[0]=('正文案号候选',case['case_no']);meta.insert(1,('归档案号原字段',source['case_no']))
    if case.get('source_metadata_warnings'):
        meta.append(('来源待核事项','；'.join(case['source_metadata_warnings'])))
    audit_path=directory/'source.audit.json'
    if audit_path.exists():
        audit=json.loads(audit_path.read_text(encoding='utf-8'));effective=audit.get('recovered_fields',{})
        if effective:
            meta[0]=('正文案号',effective['case_no'])
            meta=[(k,effective['court'] if k=='法院' else effective['date'] if k=='裁判日期' else v) for k,v in meta]
            meta.extend([('原归档三字段',f'案号={source["case_no"]}；日期={check.get("date")}；法院={check.get("court")}'),
                         ('元数据核对','三字段循环错位，派生值与正文案号、法院及落款日期一致；原字段未修改。')])
    details=''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k,v in meta)
    special=''
    if source['id']=='zh_sales_146':
        facts=next(p['text'] for p in source['paragraphs'] if p['id']=='p0021')
        special=f'''<section id="facts"><h2>与这组聊天有关的判决内容</h2><p>法院确认的事实集中在下方这一段：合同及改数量、单方发送新参数、三笔付款、到货和3月31日的原话。完整段落保留如下。</p><div class="quoted">{esc(facts)}</div><p><a href="#p0021">在全文中查看</a></p></section>
        <section id="decision"><h2>争议与法院结论 · 仅供来源核对</h2><div class="cards">
        <div class="card"><h3>合同与实际供货</h3><p>合同水泵条目记载 N=45千瓦；收到的14台水泵为 N=37千瓦。参数条目和供货事实来自法院认定，而非我添加的新案情。</p><a href="#p0021">对应全文</a></div>
        <div class="card"><h3>是否同意变更</h3><p>供方称当面沟通过变更，需方否认。法院认定现有证据不足以证实双方对参数变更协商一致。9月19日单方发图不能直接写成买方同意。</p><a href="#p0013">供方上诉理由</a> · <a href="#p0017">需方答辩</a> · <a href="#p0028">二审分析</a></div>
        <div class="card"><h3>裁判结果</h3><p>二审驳回上诉、维持原判。维持解除水泵部分买卖合同，退还水泵货款189,000元，工程公司退还14台37千瓦水泵。</p><a href="#p0029">二审分析及维持内容</a> · <a href="#p0032">裁判结果原文</a></div>
        <div class="card"><h3>本次没有生成的内容</h3><p>法院结论不进入聊天截图；4月6日律师函及后续诉讼也未纳入本组场景。判决中合同列举金额未构成完整价目表，未自行补出缺少的项目。</p><a href="REVIEW.md">聊天版本说明</a></div></div>
        <p class="muted">这里只概括这份已归档判决的内容，不把判决结论作为图片评测输入。全文中的“pXXXX”是本库定位编号，不是法院的正式段落编号。</p></section>'''
    if not special and case.get('facts'):
        statuses={'judicial_finding':'作者归类：法院记载事实','party_allegation':'作者归类：当事人主张',
                  'unresolved':'待查明','disputed':'存在争议'}
        cards=[]
        for fact in case['facts']:
            passages=[]
            for ref in fact.get('source_refs',[]):
                assert source['text'][ref['char_start']:ref['char_end']]==ref['quote']
                anchor=ref['paragraph_ids'][0]
                passages.append(f'<p class="quoted">{esc(ref["quote"])}</p><a href="#{anchor}">查看上下文</a>')
            cards.append(f'<div class="card"><small>{esc(statuses.get(fact.get("status"),"作者整理，性质待核对"))}</small><h3>{esc(fact["statement"])}</h3>'+''.join(passages)+'</div>')
        special='<section id="facts"><h2>本案相关判决信息与原文</h2><p>作者整理的来源台账供核对。部分条目是当事人主张；分类尚待人工复核，应结合原文上下文判断，不把主张当作法院认定。</p><div class="cards">'+''.join(cards)+'</div></section>'
    facts_link='<a href="#facts">相关事实原文</a>' if special else ''
    top=f'''<header><h1>判决原文与聊天来源对照</h1><p>{esc(source['title'])}</p><dl class="meta">{details}</dl><p class="status">已核对：源文件 SHA256 一致；归档原文单元格与本库全文逐字一致；{counts['verbatim_quote']}条聊天原话与原文一致。</p><nav>{facts_link}<a href="#quotes">{counts['verbatim_quote']}条原话</a><a href="#mapping">逐句来源</a><a href="#full">判决全文</a><a href="judgment.txt">纯文本原文</a><a href="../../index.html#{source['id']}">返回聊天预览</a></nav><p class="muted">这里展示的是历史来源表保存的判决文本，保持已有匿名化。原始聊天和附件并未取得；聊天及附件是按判决约束生成的可能场景。</p><details><summary>查看历史外部来源链接及文本校验值</summary><p><a href="{esc(source['url'])}" target="_blank" rel="noopener">历史来源：文书页面</a></p><p>本轮核验的是归档文本，并未把它冒充新下载的法院盖章PDF。外部页面的当前访问状态未核验。</p><p>判决文本 SHA256：<code>{check['judgment_text_sha256']}</code><br>原工作簿 SHA256：<code>{check['source_sha256_actual']}</code></p></details></header>'''
    counts_html=' · '.join(f'{labels[k]} {v} 条' for k,v in counts.items())
    page='<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(source['case_no'])+' · 判决与聊天对照</title><style>'+CSS+'</style><main>'+top+special+f'<section id="quotes"><h2>完整原话对照</h2><p>{counts["verbatim_quote"]}条原话逐字保留，不更改原有错字或添加表情。具体分钟为合成；这里的定位编号不是法院正式段落号。</p><div class="cards">'+''.join(exact)+'</div></section>'+f'<section id="mapping"><h2>每条聊天是从哪里来的</h2><p>{counts_html}</p><p>“创作衔接”没有原话依据；“事实转写”只保证参考事实有来源；“重建附件”不等于取得原件。</p><table><thead><tr><th>聊天消息及截图页</th><th>属性与判决依据</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></section>'+'<section id="full"><h2>判决全文 · 归档文本</h2><p><a href="judgment.txt">打开纯文本原文</a> · <a href="JUDGMENT.md">打开 Markdown 说明及全文</a> · <button onclick="document.body.classList.toggle(\'show-locations\')">显示/隐藏本库定位编号</button></p><div class="fulltext">'+''.join(body)+'</div></section><footer>原文与数据来源只读；本页新增展示，没有修改已审阅的聊天和截图。</footer></main></html>'
    page=page.replace('具体分钟为合成；这里的定位编号不是法院正式段落号。',
                      '时间依据见逐条记录；未载明的分钟为合成。本库定位编号不是法院正式段落号。')
    (directory/'JUDGMENT.html').write_text(page,encoding='utf-8')
    (directory/'judgment.txt').write_bytes(source['text'].encode('utf-8'))
    assert (directory/'judgment.txt').read_bytes()==source['text'].encode('utf-8')
    md=['# 判决原文与聊天依据','',source['title'],'']+[f'- {k}：{v}' for k,v in meta]+[
        '',f'历史来源：[威科先行文书页面]({source["url"]})。本轮核验本地归档文本，外部访问状态未核验。',
        '',f'原文 SHA256：{check["judgment_text_sha256"]}。原工作簿匹配，单元格正文逐字一致。',
        '',f'本组 {len(case["messages"])} 条聊天中，{counts["verbatim_quote"]} 条完整原话；时间依据分别标注，未载明的分钟为合成。',
        '', '## 逐句依据','']+mdrows+['## 判决全文（归档文本）','',source['text']]
    (directory/'JUDGMENT.md').write_text('\n'.join(md),encoding='utf-8')
    (directory/'source.verification.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'case_id':source['id'],'content_exact':True,'origin_counts':counts,'source_page':str(directory/'JUDGMENT.html')},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('--case',default='zh_sales_146');args=parser.parse_args()
    directory=next(p.parent for p in ROUND.glob('*/*/case.json') if p.parent.name==args.case)
    build(directory)
