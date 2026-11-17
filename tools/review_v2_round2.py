"""Record the actual second writing pass and publish an inspectable review page."""
from pathlib import Path
from collections import Counter
import hashlib, html, json, sys
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'datasets/v2.0.0/round_002'
esc=lambda value:html.escape(str(value))


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def revise():
    changes={'zh_sales_146':{'m003':'收到，我晚点看','m017':'货这边你跟刘总对接吧'},
             'en_probate_283':{'m018':'Not like this. We need to talk properly'}}
    reasons={'m003':'去掉没根据的“在外面”场景信息，保留延迟阅读的日常回复。',
             'm017':'删去没有后续情节承接的“别漏东西”，避免为了自然感塞悬空冲突。',
             'm018':'把泛化的 going round in circles 改成更直接的家人沟通语气；仍明确是创作衔接。'}
    for directory in OUT.glob('*/*'):
        path=directory/'case.json'
        if not path.exists():continue
        draft=directory/'direct.draft.json'
        if not draft.exists():draft.write_bytes(path.read_bytes())
        case=json.loads(draft.read_text(encoding='utf-8'));log=[]
        for message in case['messages']:
            if message['id'] in changes[case['id']]:
                new=changes[case['id']][message['id']]
                log.append({'message_id':message['id'],'before':message['text'],'after':new,'reason':reasons[message['id']]})
                message['text']=new
            message['date_basis']='source_day_context; utterance may be synthetic'
        case['second_pass_edits']=log
        save(path,case)
        save(directory/'self_review.json',{'reviewer':'Codex (same author, not independent)',
            'new_rating':None,'second_pass_edits':log,'remaining_issues':[
                '聊天仍是少量摘取的场景，并不等于完整案情；头像和界面是模拟。',
                '衔接话语只能代表一种可能，不能拿来证明真实人物的行为。',
                '新增合成附件让部分事实可见，也引入图像与版式偏差，后续应做不同版式对照。',
                '尚未做难度校准；短期优先验证自然感和事实边界。']})
    print('Direct drafts retained; three actual wording edits recorded.')


def publish():
    reports=[];sections=[];checks=[]
    feedback=json.loads((OUT/'references/same_case_feedback.json').read_text(encoding='utf-8'))
    for directory in sorted(OUT.glob('*/*')):
        if not (directory/'case.json').exists():continue
        c=json.loads((directory/'case.json').read_text(encoding='utf-8'));s=json.loads((directory/'source.json').read_text(encoding='utf-8'))
        r=json.loads((directory/'render.json').read_text(encoding='utf-8'));people={p['id']:p['name'] for p in c['participants']}
        relative=directory.relative_to(OUT).as_posix();byid={m['id']:m for m in c['messages']}
        covered=set();page_map={};quote_count=0;chrome_regions={}
        for image in r['images']:
            with Image.open(directory/image['path']) as png:
                assert png.size==(860,1864),(image['path'],png.size)
                fixed=(png.crop((0,0,860,176)).tobytes(),png.crop((0,1738,860,1864)).tobytes())
                cid=image['conversation_id']
                if cid in chrome_regions:assert fixed==chrome_regions[cid],'Screenshot header/footer shifted'
                else:chrome_regions[cid]=fixed
            image['sha256']=hashlib.sha256((directory/image['path']).read_bytes()).hexdigest()
            for ident in image['message_ids']:
                covered.add(ident);page_map.setdefault(ident,[]).append(image['page'])
            for box in image['boxes']:
                x,y,w,h=box['bbox_pixels'];assert x>=0 and y>=176 and x+w<=860 and y+h<=1738
        assert covered==set(byid),'Missing screenshot messages'
        for m in c['messages']:
            assert m['sender_id'] in people
            for ref in m['source_refs']:assert s['text'][ref['char_start']:ref['char_end']]==ref['quote']
            if m['origin_type']=='verbatim_quote':
                assert m['text']==m['source_refs'][0]['quote'];quote_count+=1
        for conv in c['conversations']:
            times=[m['timestamp'] for m in c['messages'] if m['conversation_id']==conv['id']]
            assert times==sorted(times)
        assert s['text']==json.loads((ROOT/'datasets/v2.0.0/round_001'/relative/'source.json').read_text(encoding='utf-8'))['text']
        checks.append({'case_id':c['id'],'messages':len(byid),'screenshots':len(r['images']),'exact_quote_messages':quote_count,
                       'source_spans_exact':True,'all_messages_visible':True,'image_size':[860,1864],'fixed_header_footer_verified':True,
                       'difficulty_certified':False,'naturalness_human_approved':False})
        save(directory/'render.json',r)
        for q in c['questions']:
            if c['id']=='zh_sales_146' and q['id']=='q1':
                q['question']='最初合同条目与后来样本对同一型号分别显示什么功率？来自哪两组会话？请使用截图中的称呼。'
                q['answer']='陈会计与李某某会话的合同条目 SLW200-400GB 为45千瓦；刘总与李某某会话的参数节选为37kW。不能从单字头像补出未显示的全名。'
            q['candidate_pages']=sorted({p for ident in q['message_ids'] for p in page_map[ident]})
            q['page_scope']='whole_case' if q.get('whole_case_required') else 'cited_messages_candidate'
            q['status']='author_draft_not_certified_gold'
        save(directory/'questions.review.json',c['questions'])
        tasks=[{'id':c['id']+'_'+q['id'],'language':c['language'],'question':q['question'],
                'images':[image['path'] for image in r['images']],'reference_status':'author_draft'} for q in c['questions']]
        save(directory/'tasks.image_only.json',tasks)
        save(directory/'case.json',c)
        title='中文 · 买卖合同 / 水泵参数' if c['language']=='zh' else 'English · Probate / family WhatsApp'
        md=[f'# {title}', '', f'判决：{c["case_no"]}。作者直接写作及自审；不是新人工评分。', '',
            '本次主动收窄场景，先处理自然感、原话和事实边界。不能据此声称覆盖整份判决，也没有新增批量 API 调用。','',
            '## 与上一轮相比改在哪里','']
        change_html=[]
        for change in c['changes']:
            md.extend([f'- 原来：{change["before"]}',f'  现在：{change["after"]}',f'  理由：{change["reason"]}',f'  依据：{change["feedback"]}',''])
            change_html.append(f'<div class="change"><div><b>上一轮</b><p>{esc(change["before"])}</p></div><div><b>这一轮</b><p>{esc(change["after"])}</p></div><p class="why">{esc(change["reason"])}<br><small>依据：{esc(change["feedback"])}</small></p></div>')
        md+=['## 本轮第二遍实际文字修订','']
        for edit in c['second_pass_edits']:md+=[f'- {edit["message_id"]}：“{edit["before"]}” → “{edit["after"]}”；{edit["reason"]}']
        md+=['','## 事实约束','']+[f'- {v}' for v in c['constraints']]
        md+=['','## 全部聊天和出处','']
        transcript=[]
        labels={'verbatim_quote':'判决引用原话','judgment_paraphrase':'事实转写（具体说法合成）','synthetic_completion':'创作衔接','judgment_attachment_reconstruction':'重建附件（原件未取得）'}
        for conv in c['conversations']:
            md+=['',f'### {conv["title"]} — 查看人 {people[conv["viewer_id"]]}','']
            transcript.append(f'<h3>{esc(conv["title"])} · 查看人 {esc(people[conv["viewer_id"]])}</h3>')
            for m in c['messages']:
                if m['conversation_id']!=conv['id']:continue
                body=m['text']
                if m.get('attachment'):body+='\n'+json.dumps(m['attachment']['rows'],ensure_ascii=False)
                refs='；'.join(f'{"/".join(ref["paragraph_ids"])}，字符 {ref["char_start"]}–{ref["char_end"]}：{ref["quote"]}' for ref in m['source_refs'])
                label=labels[m['origin_type']];pages='/'.join(map(str,page_map[m['id']]))
                md+=[f'**{m["id"]} | {m["timestamp"]} | {people[m["sender_id"]]} | 页 {pages} | {label}**','',body,'',f'来源：{refs or "无原话；作者创作的衔接。"}；分钟均合成。','']
                transcript.append(f'<div class="entry"><span class="meta">{m["id"]} · {esc(m["timestamp"])} · {esc(people[m["sender_id"]])} · 页 {pages} · {label}</span><p>{esc(body)}</p><details><summary>查看来源与时间依据</summary><p>{esc(refs or "无原话；作者创作衔接。")}</p><p>日期使用判决事件所在日，具体消息和分钟可能合成；不是原件恢复。</p></details></div>')
        md+=['## 候选题（未认证金标）','']
        for q in c['questions']:md+=[f'- {q["id"]}：{q["question"]}',f'  参考回答：{q["answer"]}',f'  消息：{", ".join(q["message_ids"])}；候选页：{q["candidate_pages"]}；范围：{q["page_scope"]}。','']
        md+=['## 仍需改进','']+[f'- {v}' for v in c['limitations']]
        (directory/'REVIEW.md').write_text('\n'.join(md),encoding='utf-8')
        # Honest paired visual comparisons: matching scenes, not arbitrary images.
        comparisons=[('round_001 m006–m008：把合同念成三条消息','../round_001/'+relative+'/screenshots/page_002.png',
                      'round_002：文件与重建合同条目图',relative+'/screenshots/accounts_02.png')] if c['language']=='zh' else [(
                      'round_001：Srimila 原话被拆成多条','../round_001/'+relative+'/screenshots/page_004.png',
                      'round_002：保留完整单条原话',relative+'/screenshots/siblings_02.png')]
        compare=''.join(f'<div class="pair"><figure><figcaption>{esc(a)}</figcaption><a href="{b}"><img src="{b}"></a></figure><figure><figcaption>{esc(d)}</figcaption><a href="{e}"><img src="{e}"></a></figure></div>' for a,b,d,e in comparisons)
        gallery=''.join(f'<figure><figcaption>页 {im["page"]} · {esc(im["conversation_id"])} · {", ".join(im["message_ids"])}</figcaption><a href="{relative}/{im["path"]}"><img src="{relative}/{im["path"]}" loading="lazy"></a></figure>' for im in r['images'])
        qs=''.join(f'<details><summary>{esc(q["question"])}</summary><p>{esc(q["answer"])}</p><small>候选页 {q["candidate_pages"]}；{q["page_scope"]}；未经独立评测。</small></details>' for q in c['questions'])
        judgment_link=f'<a href="{relative}/JUDGMENT.html">判决原文与聊天逐句对照</a> · ' if (directory/'JUDGMENT.html').exists() else ''
        sections.append(f'<section id="{c["id"]}"><h2>{title}</h2><p>{esc(c["case_no"])} · {len(byid)} 条消息 · {len(r["images"])} 张图</p><p>{judgment_link}<a href="{relative}/REVIEW.md">逐句来源与修订说明</a> · <a href="{relative}/source.json">判决全文 JSON</a> · <a href="{relative}/case.json">结构化聊天</a></p><h3>先看同一场景的图片变化</h3>{compare}<h3>实际修改与依据</h3>{"".join(change_html)}<h3>全部新截图</h3><div class="gallery">{gallery}</div><details><summary>展开全部聊天、来源和消息编号</summary>{"".join(transcript)}</details><h3>检查题目是否从图片可答</h3>{qs}<p class="note">这轮内容较短、覆盖面收窄；没有凭截图张数和消息数量宣布它更难。需要后续盲评自然感和实跑难度。</p></section>')
        reports.append({'id':c['id'],'title':title,'messages':len(byid),'images':len(r['images'])})
    assert sum(x['exact_quote_messages'] for x in checks)==9
    save(OUT/'verification.json',{'checks':checks,'scope':'provenance, visible coverage, dimensions and chronology only; not a naturalness or difficulty score'})
    style='body{font:16px/1.75 "Microsoft YaHei","Segoe UI",sans-serif;background:#f3f5f2;color:#26332e;margin:0}main{max-width:1260px;margin:auto;padding:28px}h1{font-size:28px}h2{font-size:24px}section,.intro{padding:25px;background:white;border-radius:12px;margin:24px 0}a{color:#14725c}p{white-space:pre-wrap}.pair,.gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.gallery{grid-template-columns:repeat(3,minmax(0,1fr))}figure{margin:0;padding:15px;background:#f6f7f5;border-radius:9px}figure img{display:block;width:100%;height:auto;margin-top:10px}figcaption{font-size:13px;color:#627269}.change{display:grid;grid-template-columns:1fr 1fr;border:1px solid #dce5df;border-radius:9px;padding:16px;gap:18px;margin:15px 0}.why{grid-column:1/-1;margin:0;border-top:1px solid #e5ebe7;padding-top:10px}.meta{font-size:12px;color:#67786f}.entry{border-left:3px solid #d2e4d9;padding:12px 16px;margin:13px 0;background:#fafcf9}details{padding:13px;margin:10px 0;background:#f7f9f6;border-radius:7px}summary{cursor:pointer}.note{font-size:14px;color:#6c776d}@media(max-width:760px){main{padding:10px}.gallery,.pair,.change{grid-template-columns:1fr}.why{grid-column:1}}'
    intro='''<div class="intro"><h1>第二轮：直接重写，再看图</h1><p>之前那版没有达到自然聊天的要求。这轮从归档表的评分与修正意见出发，回到判决正文，先做好中英文各一案。作者为 Codex，自审不冒充独立人工评审；没有新调用生成模型 API。</p><p>保留判决原话；事实写进附件或对应人物的实际沟通；其余衔接明确是创作。分钟为合成。文件与参数图属于按判决重建，原件未取得；页底有合成样本标识。</p><p><a href="#zh_sales_146">中文买卖合同案</a> · <a href="#en_probate_283">English probate case</a> · <a href="REPORT.md">完整迭代说明</a> · <a href="references/same_case_feedback.json">旧表记录（附单元格坐标）</a></p><p>旧表“prompt_v3——v9”148 行的四位人工分数为 4 / 3 / 4 / 5；历史扣分列指出日期错误、表达书面化。“多版本汇总表”的“5分完美剧本”只是列名，其作者与批准状态未确认，不能把整列视为人工金标。</p></div>'''
    (OUT/'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V2 第二轮 · 直接重写与图片对照</title><style>'+style+'</style><main>'+intro+''.join(sections)+'</main></html>',encoding='utf-8')
    report='''# V2 第二轮：先把两案写好

上一轮图片是排版原型，聊天中仍有案件摘要、旁白和扩写后的证人陈述。校验流程完成不等于聊天自然，也不等于数据集有难度。这轮由 Codex 直接依据判决写作，再做一次实际文字修订和图片复审；没有新增模型 API 调用。

## 从哪里找到旧反馈

只读原始 `归档.zip`，其中《大模型剧本prompt案由泛化性测试.xlsx》：

- `prompt_v3——v9!K148/M148/O148/Q148`：同一买卖合同案，四位具名人工评分 4/3/4/5。并无理由说明谁为什么打这几分。
- `prompt_v5!L148`：历史扣分理由为日期错误及表达书面化。该列未明确标注评论者，不将其宣称为新的人工反馈。
- `多版本汇总表!K148:L148`：修正版本与修改要点，强调原话、原有口语和不编造同意。修正版仍含“未回复”旁白和强加 emoji，本轮据其原则修正，没有照抄。
- `prompt_v0!N148`：历史建议加入查验、铭牌拍照、拒收通知。本轮没有取得原始图片，不用“建议”作为制造原始照片的依据。

提取记录见 `references/same_case_feedback.json`（18 条）、`human_corrected_examples.json`（229 条历史修正列记录）、`rubric_experiments.json`（265 条实验记录）。后两者来源列名不意味着人工审核完成；没有给本轮新评分。

## 可见的迭代步骤

1. 对照同案旧文本、具名单元格评分及扣分/修正意见。
2. 直接读判决，把日期、原话、附件、单方主张和不能补造的关键事实列为约束。
3. 我直接写两个场景组：中文合同/付款与现场争议，英文家庭群与后来的兄妹私聊。保存为 `direct.draft.json`。
4. 第二遍自审，实际修改三条衔接，记录在 `self_review.json` 和 `case.json` 的 `second_pass_edits`。逐字原话不改。
5. 新建本地 HTML/CSS 手机界面，以 Chromium 渲染，做消息覆盖和坐标核验；亲自看输出图后修正顶部裁切、英文字体和气泡尾部。没有使用私有浏览器会话。
6. 对照页保留上一轮同场景图片、这一轮图片，以及每处的旧写法、新写法和依据。文字通读页给出每句话的来源与合成属性。

这次不是把“换模型 → 自动高分”称为迭代。上一轮保持原样；本次只落在 `datasets/v2.0.0/round_002/`，与 v1 独立。

## 内容及难度

中文：28 条，2 个私聊，5 张图；英文：21 条，家庭群加私聊，4 张图。合计 49 条、9 张 860×1864 图、6 道候选题；9 条完整原话。没有新独立人工评审。

中文参数分散在会计收到的合同条目与项目经理收到的样本图，需要关联同一供方和型号。付款不直接宣布总额，需要跨日加总。争议消息保留原话，单方发图不能代替对方承诺。英文的群内赞成与后来的私人请求需要区分提议、执行、权益主张和文书知悉，不能直接推定放弃或送达。

这些是难度设计理由，不是已测出的多跳难度。新英文场景删去了不可靠的知悉链扩写，也主动减少了病程、授权书和债务等覆盖；不能声称整案还原更完整。先盲看自然感、逐题核对来源，再遮挡候选必要图片并实跑模型，才能定难度。

## 复现和下一轮入口

```powershell
.venv/Scripts/python.exe tools/extract_v2_human_reference.py
.venv/Scripts/python.exe tools/write_v2_round2.py
.venv/Scripts/python.exe tools/review_v2_round2.py revise
.venv/Scripts/python.exe tools/render_v2_round2.py
.venv/Scripts/python.exe tools/review_v2_round2.py publish
```

新渲染器使用本机已有 Chromium 和 websocket-client，只渲染本库 HTML。WhatsApp 背景复用本地 MIT 前端资源，许可与说明在 `assets/`。这是本轮可审阅的两案产物，尚未替换全部合成流水线的默认渲染器。

接下来把用户认定不自然的具体消息和图片记录成带消息 ID 的反馈，先修这两案，再把真正有效的规则回写生成和批评 prompt。不要用“必须 emoji”“必须冲突”“越长越难”作为自动达标规则；不要以同一个模型自评高分作为放行依据。
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8')
    save(OUT/'summary.json',{'cases':reports,'total_messages':49,'total_images':9,'exact_quotes':9,'candidate_questions':6,'independent_review':False})
    print(json.dumps({'cases':len(checks),'images':sum(c['screenshots'] for c in checks),'quotes':sum(c['exact_quote_messages'] for c in checks),'review_page':str(OUT/'index.html')},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv)>1 and sys.argv[1]=='revise':revise()
    else:publish()
