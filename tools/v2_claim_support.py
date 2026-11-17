"""Offline, versioned claim-support cohort: inventory, build, render, verify, bundle.

Agent prose is archived input, not deterministic regeneration. No model API calls.
Existing V1/V2 rounds are read-only. All CLI writes stay in the specified cohort.
"""
from __future__ import annotations
import argparse, copy, hashlib, html, importlib.metadata, json, os, platform, re, shutil, subprocess, sys
from functools import lru_cache
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.v2_cause_batch import read, save, normalize, case_review
PREVIOUS = ROOT / 'datasets/v2.0.0/round_003'
DEFAULT = ROOT / 'datasets/v2.0.0/round_004'
LABELS = {'supported', 'contradicted', 'insufficient'}
ESC = lambda x: html.escape(str(x))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def sources():
    paths = list((PREVIOUS/'zh').glob('*/source.json'))
    paths += list((PREVIOUS/'zh').glob('*/alternatives/*/source.json'))
    result = {}
    for path in sorted(paths):
        s = read(path)
        result.setdefault(s['source_index'], (path, s))
    return result


def inventory(out):
    rendered = {}
    for path in (PREVIOUS/'zh').glob('*/status.json'):
        if read(path).get('phase') == 'rendered':
            s = read(path.parent/'source.json')
            rendered[s['source_index']] = path.parent.name
    records = []
    signals = r'不足以|不能证明|无法证明|不予采信|不予认可|真实性|原始载体|证明目的'
    for index, (path, s) in sorted(sources().items()):
        evidence = []
        for paragraph in s['paragraphs']:
            text = paragraph['text']
            if re.search(r'微信|聊天|截图|语音', text) and re.search(signals, text):
                evidence.append({'source_id': paragraph['id'], 'quote': text,
                                 'char_start': paragraph['char_start'], 'char_end': paragraph['char_end']})
        records.append({'source_index': index, 'cause': s['cause'],
                        'judgment_text_sha256': s['judgment_text_sha256'],
                        'source_path': path.relative_to(ROOT).as_posix(),
                        'previous_rendered_id': rendered.get(index),
                        'keyword_screen_candidate': bool(evidence),
                        'screen_refs': evidence, 'full_read_completed_this_round': False,
                        'court_rejection_is_image_label': False})
    save(out/'source_inventory.json', {'records': records, 'source_count': len(records),
        'keyword_candidates': sum(x['keyword_screen_candidate'] for x in records),
        'screening_is_semantic_annotation': False})
    gap = read(PREVIOUS/'source_gaps.json')
    unresolved = [r for r in gap['records'] if not r['rendered_alternative_ids']]
    save(out/'previous_gaps.json', {'records': unresolved,
        'meaning': 'Missing reconstructable communication anchors; not a negative proof label.',
        'missing_dialogue_may_be_used_as_explicit_context_task': True,
        'unseen_dialogue_may_not_be_fabricated_as_judgment_quote': True})
    # Frozen snapshots make accidental previous-round mutations detectable.
    if not (out/'previous_round_lock.json').exists():
        lock = {}
        for path in sorted(PREVIOUS.rglob('*')):
            if path.is_file() and path.suffix in {'.json', '.png', '.txt', '.md', '.html', '.jsonl'}:
                lock[path.relative_to(ROOT).as_posix()] = digest(path)
        save(out/'previous_round_lock.json', lock)
    print(json.dumps({'sources': len(records), 'keyword_candidates': sum(x['keyword_screen_candidate'] for x in records),
                      'previous_unresolved_labels': len(unresolved)}, ensure_ascii=False))


def validate_claims(raw, case, source):
    claims = copy.deepcopy(raw['claims'])
    assert len(claims) >= 3, 'Need supported control and non-support probes'
    ids = {m['id']: m for m in case['messages']}
    seen = set()
    # Reuse the literal-span validator rather than introducing a second resolver.
    probe = copy.deepcopy(case)
    probe['facts'] = [{'id': 'claim_'+q['id'], 'source_refs': q['source_refs']} for q in claims]
    normalized, errors = normalize(probe, source)
    assert not errors, errors
    for q, fact in zip(claims, normalized['facts']):
        assert q['id'] not in seen, 'Duplicate claim ID'
        seen.add(q['id'])
        assert q['label'] in LABELS
        assert q['task_mode'] in {'image_only', 'case_context'}
        assert q['claim'] and q['answer'] and q['reasoning']
        citations = q['evidence_message_ids']
        assert citations and set(citations) <= set(ids), 'Invalid message citation'
        assert any(ids[i]['origin_type'] != 'synthetic_completion' for i in citations)
        if q['label'] == 'insufficient':
            assert q['missing_evidence'], 'State what is missing'
        if q['task_mode'] == 'case_context':
            assert q.get('context'), 'Context must be explicitly supplied to the model'
        q['source_refs'] = fact['source_refs']
        q['annotation_status'] = 'agent_authored_root_reviewed_candidate_not_professional_gold'
    assert 'supported' in {q['label'] for q in claims}
    assert 'insufficient' in {q['label'] for q in claims}
    return claims


def claim_questions(claims):
    return [{'id':q['id'],'question':'仅据提供图片，判断主张：'+q['claim'],
             'answer':q['answer'],'message_ids':q['evidence_message_ids'],
             'source_refs':q['source_refs'],'type':'claim_support','label':q['label'],
             'task_mode':q['task_mode'],'whole_case_required':True} for q in claims]


def build(out):
    results = []
    failures = []
    for path in sorted((out/'authoring').glob('*/*/direct.revised.json')):
        folder = path.parent
        try:
            source = read(folder/'source.json')
            ident = source['id']
            input_digest = hashlib.sha256(''.join(digest(folder/name) for name in
                ['source.json','source.reading.json','direct.draft.json','direct.revised.json','codex.review.json','claims.json']).encode()).hexdigest()
            directory = out/'zh'/ident
            if (directory/'cohort.record.json').exists() and (directory/'status.json').exists():
                existing = read(directory/'cohort.record.json')
                if existing.get('authoring_digest')==input_digest and read(directory/'status.json')['phase']=='rendered':
                    results.append(existing); continue
            assert re.fullmatch(r'r4_(?:zh_\d{4}|web_\d{3})', ident)
            if source.get('source_kind') == 'official_web_judgment':
                assert (ROOT/source['source_file']).resolve().is_relative_to((ROOT/'datasets/v2.0.0').resolve())
                assert (ROOT/source['source_file']).read_bytes() == source['text'].encode('utf-8')
                assert digest(ROOT/source['snapshot_file']) == source['snapshot_sha256']
            else:
                original = sources()[source['source_index']][1]
                assert source['text'] == original['text']
            assert source['judgment_text_sha256'] == hashlib.sha256(source['text'].encode()).hexdigest()
            reading = read(folder/'source.reading.json')
            assert reading['source_chars'] == len(source['text'])
            assert reading['source_paragraphs'] == len(source['paragraphs'])
            review = read(folder/'codex.review.json')
            assert review.get('full_judgment_read'), 'Full reading required'
            case, errors = normalize(read(path), source)
            assert not errors, errors
            assert case.get('suitability', {}).get('decision') != 'defer'
            case.update(author=folder.parent.name+'; Codex direct writing; runtime model identifier not exposed',
                        status='claim_support_development_candidate', model_difficulty_certified=False)
            # Old parent IDs refer outside this cohort; preserve as provenance only.
            if case.get('parent_case_id'):
                case['previous_round_parent_id'] = case.pop('parent_case_id')
            if source.get('parent_case_id'):
                source['previous_round_parent_id'] = source.pop('parent_case_id')
            claims = validate_claims(read(folder/'claims.json'), case, source)
            case['questions'] = claim_questions(claims)
            # A rerun can rebuild unchanged candidates, never overwrite a reviewed correction.
            if (directory/'root.review.json').exists():
                results.append(read(directory/'cohort.record.json'))
                continue
            directory.mkdir(parents=True, exist_ok=True)
            for name in ['source.json', 'source.reading.json', 'direct.draft.json', 'direct.revised.json', 'codex.review.json']:
                shutil.copyfile(folder/name, directory/name)
            save(directory/'source.json', source)
            (directory/'judgment.txt').write_bytes(source['text'].encode('utf-8'))
            for old_path, old in sources().values():
                if old['source_index'] == source['source_index'] and (old_path.parent/'source.audit.json').exists():
                    audit = read(old_path.parent/'source.audit.json')
                    save(directory/'source.audit.json', audit)
                    if audit.get('case_no_from_text'):
                        case['case_no'] = audit['case_no_from_text']
                    break
            if not (directory/'source.audit.json').exists():
                found = re.search(r'[（(]\d{4}[）)][^\n]{1,45}?号', source['text'][:1600])
                if found:
                    save(directory/'source.audit.json', {'case_no_from_text':found[0],
                         'warnings':['显示案号从正文首部提取，原字段保留；尚待专业身份核查。'] if found[0]!=source['case_no'] else []})
                    case['case_no'] = found[0]
            save(directory/'case.json', case)
            save(directory/'claims.review.json', {'claims': claims})
            save(directory/'case.checks.json', {'errors': [], 'source_spans_exact': True, 'human_review': False})
            save(directory/'status.json', {'phase': 'reviewed'})
            record = {'id': ident, 'source_index': source['source_index'], 'cause': source['cause'],
                      'judgment_text_sha256': source['judgment_text_sha256'], 'author': folder.parent.name,
                      'claims': len(claims), 'authoring_input': folder.relative_to(ROOT).as_posix()}
            record['new_external_judgment'] = source.get('source_kind') == 'official_web_judgment'
            record['authoring_digest'] = input_digest
            save(directory/'cohort.record.json', record)
            results.append(record)
        except Exception as error:
            failures.append({'path': str(folder.relative_to(ROOT)), 'error': str(error)})
    assert len({r['id'] for r in results}) == len(results), 'Overlapping agent ownership'
    save(out/'build.verification.json', {'accepted': results, 'failures': failures})
    save(out/'manifest.json', {'round': out.name, 'split': 'development', 'records': results,
                              'count_is_new_judgments': False, 'professional_gold': False})
    print(json.dumps({'accepted': len(results), 'failures': failures}, ensure_ascii=False))


def publish_tasks(directory):
    rendering = read(directory/'render.json')
    claims = read(directory/'claims.review.json')['claims']
    pages = {}
    for image in rendering['images']:
        for mid in image['message_ids']:
            pages.setdefault(mid, []).append(image['page'])
    tasks = []
    for claim in claims:
        claim['evidence_pages'] = sorted({p for mid in claim['evidence_message_ids'] for p in pages[mid]})
        claim['minimal_evidence_pages_certified'] = False
        task = {key: claim[key] for key in ['id', 'claim', 'task_mode']}
        task['instruction'] = '仅依据提供的材料，判断主张为 supported、contradicted 或 insufficient，并指出截图页码和具体语句。不能把未显示的事实当作已知事实。'
        task['images'] = [i['path'] for i in rendering['images']]
        if claim['task_mode'] == 'case_context': task['context'] = claim['context']
        tasks.append(task)
    save(directory/'claims.review.json', {'claims': claims})
    save(directory/'tasks.claim_support.json', {'case_id': directory.name, 'tasks': tasks})
    cards = []
    names = {'supported': '支持', 'contradicted': '反驳', 'insufficient': '证据不足'}
    for q in claims:
        refs = ''.join(f'<li>{ESC(r["source_id"])}：{ESC(r["quote"])}</li>' for r in q['source_refs'])
        cards.append(f'<article><h3>{ESC(q["id"])} · {ESC(q["claim"])}</h3><p><b>{names[q["label"]]}</b> · {ESC(q["task_mode"])}</p><p>{ESC(q["answer"])}</p><p>{ESC(q["reasoning"])}</p><p>证据页：{ESC(q["evidence_pages"])}；消息：{ESC(q["evidence_message_ids"])}</p><p>仍缺：{ESC(q["missing_evidence"])}</p><details><summary>判决依据（不提供给纯图任务）</summary><ul>{refs}</ul></details></article>')
    shots = ''.join(f'<figure><figcaption>第 {i["page"]} 页</figcaption><a href="{i["path"]}"><img src="{i["path"]}" loading="lazy"></a></figure>' for i in rendering['images'])
    page = '<!doctype html><meta charset="utf-8"><title>证据与主张评测预览</title><style>body{background:#f2f5f3;font:16px/1.8 Microsoft YaHei,sans-serif;margin:30px;color:#253d34}main{max-width:1200px;margin:auto}article,header{background:white;padding:22px;margin-bottom:16px;border-radius:10px}.images{display:flex;flex-wrap:wrap}figure{margin:10px}img{width:330px;max-width:90vw}a{color:#15745e}</style><main><header><h1>'+ESC(directory.name)+'</h1><p>合成研究样本；候选答案未经过专业律师独立认证。证据不足不等于主张为假。</p><p><a href="JUDGMENT.html">判决全文与逐句来源</a> · <a href="review.html">聊天记录预览</a> · <a href="tasks.claim_support.json">模型输入（无答案）</a></p></header><div class="images">'+shots+'</div>'+''.join(cards)+'</main>'
    (directory/'claims.html').write_text(page, encoding='utf-8')


def render(out):
    from tools.render_v2_round2 import Browser, render_case
    from tools.build_v2_judgment_review import build as source_page, verify_archive
    renderer_hash = digest(ROOT/'tools/render_v2_round2.py')
    with Browser('chrome-'+out.name) as browser:
        for record in read(out/'manifest.json')['records']:
            directory = out/'zh'/record['id']
            state = read(directory/'status.json')
            c = read(directory/'case.json')
            input_hash = hashlib.sha256(json.dumps({k:c[k] for k in ['messages','conversations','participants','language','platform']},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            if state['phase'] != 'rendered' or state.get('renderer_sha256') != renderer_hash or state.get('render_input_sha256') != input_hash:
                if (directory/'render.json').exists() and state.get('renderer_sha256') != renderer_hash:
                    version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
                    archive = directory/'render.versions'/version;archive.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(directory/'render.json',archive/'render.json')
                    for shot in read(directory/'render.json')['images']:
                        src=(directory/shot['path']).resolve();assert src.is_relative_to(directory.resolve())
                        target=archive/shot['path'];target.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(src,target)
                render_case(browser, directory)
                case = read(directory/'case.json')
                source = read(directory/'source.json')
                if source.get('source_kind') == 'official_web_judgment':
                    web_source_page(directory)
                else:
                    source_page(directory, verify_archive(source))
                case_review(directory, case, read(directory/'render.json'))
                save(directory/'status.json', {'phase': 'rendered', 'renderer_sha256':renderer_hash,'render_input_sha256':input_hash})
            # Refresh root-corrected questions even if the same screenshots are reused.
            case=read(directory/'case.json');case['questions']=claim_questions(read(directory/'claims.review.json')['claims'])
            save(directory/'case.json',case)
            case_review(directory,case,read(directory/'render.json'))
            publish_tasks(directory)
            current={i['path'] for i in read(directory/'render.json')['images']}
            orphaned=[]
            for path in (directory/'screenshots').glob('*.png'):
                if path.relative_to(directory).as_posix() in current:continue
                assert path.resolve().parent==(directory/'screenshots').resolve() and path.resolve().is_relative_to(out.resolve())
                archive=directory/'render.versions'/('orphaned_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
                archive.mkdir(parents=True,exist_ok=False);target=archive/path.name
                shutil.copyfile(path,target);assert digest(path)==digest(target)
                orphaned.append({'previous_path':path.relative_to(directory).as_posix(),
                                 'archive':target.relative_to(directory).as_posix(),'sha256':digest(target)})
                path.unlink()
            if orphaned:save(directory/'stale_image_archive.json',{'archived':orphaned,'removed_without_archive':False})
            print(record['id']+' rendered', flush=True)
    report(out)


def web_source_page(directory):
    source = read(directory/'source.json'); case = read(directory/'case.json')
    assert digest(ROOT/source['source_file']) == source['source_sha256']
    assert digest(ROOT/source['snapshot_file']) == source['snapshot_sha256']
    paragraphs = ''.join(f'<p id="{p["id"]}"><small>{p["id"]}</small> {ESC(p["text"])}</p>' for p in source['paragraphs'])
    mapping = ''.join(f'<tr><td>{ESC(m["id"])} · {ESC(m["text"])}</td><td>{ESC(m["origin_type"])}<ul>'+''.join(f'<li><a href="#{r["source_id"]}">{r["source_id"]}</a> {ESC(r["quote"])}</li>' for r in m['source_refs'])+'</ul></td></tr>' for m in case['messages'])
    page = '<!doctype html><meta charset="utf-8"><title>联网判决与逐句依据</title><style>body{max-width:1100px;margin:35px auto;font:16px/1.9 Microsoft YaHei,sans-serif;color:#253d34;padding:20px}td{border:1px solid #ccc;padding:15px}small{color:#888}a{color:#15745e}</style><h1>'+ESC(source['case_no'])+'</h1><p><a href="'+ESC(source['url'])+'">法院原始网页</a> · <a href="claims.html">主张评测</a> · <a href="judgment.txt">归档判决正文</a></p><p>正文从页面法院名称至落款日期逐字提取，移除页头页尾；完整HTML和提取文本另行保留。段落编号是本库定位，不是法院官方段号。只有合成研究截图，不冒充原件。</p><p>正文 SHA256：'+ESC(source['judgment_text_sha256'])+'</p><table>'+mapping+'</table><h2>判决全文</h2>'+paragraphs
    (directory/'JUDGMENT.html').write_text(page,encoding='utf-8')
    (directory/'JUDGMENT.md').write_text('# 联网判决原文\n\n'+source['url']+'\n\n'+source['text'],encoding='utf-8')
    save(directory/'source.verification.json', {'content_exact':True,'source_kind':source['source_kind'],
        'judgment_text_sha256':source['judgment_text_sha256'],'snapshot_sha256':source['snapshot_sha256'],
        'body_extraction':source['body_extraction'],'web_source_full_read':True})


def report(out):
    if not (out/'REPRODUCIBILITY.md').exists():
        link = Path(os.path.relpath(ROOT/'skills/judgment-chat-dataset/references/reproduction.md',out)).as_posix()
        (out/'REPRODUCIBILITY.md').write_text('# Archived-input replay\n\n'+
            f'[Reproduction protocol]({link}). This cohort rebuilds archived authoring inputs; it does not rerun a language model. Sources referenced in original archives remain read-only.\n',encoding='utf-8')
    if not (out/'acquisition/REPORT.md').exists():
        (out/'acquisition').mkdir(parents=True,exist_ok=True)
        (out/'acquisition/REPORT.md').write_text('# Source state\n\nThis replay did not perform new web acquisition. Refer to each archived source record and its snapshot hash.\n',encoding='utf-8')
    records = read(out/'manifest.json')['records']
    labels = Counter(); reasons = Counter(); rows = []; images = messages = 0
    prior = read(out/'source_inventory.json')['records']
    prior_indices = {r['source_index'] for r in prior if r['previous_rendered_id']}
    rendered = 0
    for r in records:
        d = out/'zh'/r['id']
        if read(d/'status.json')['phase'] != 'rendered': continue
        rendered += 1
        claims = read(d/'claims.review.json')['claims']
        labels.update(q['label'] for q in claims)
        reasons.update(q.get('insufficiency_type') or 'unspecified' for q in claims if q['label']=='insufficient')
        images += len(read(d/'render.json')['images'])
        messages += len(read(d/'case.json')['messages'])
        rows.append(f'<tr id="{r["id"]}"><td>{ESC(r["cause"].split(">")[-1])}</td><td><a href="zh/{r["id"]}/claims.html">{ESC(r["id"])}</a></td><td>{len(claims)}</td><td>'+('联网新增判决' if r.get('new_external_judgment') else '既有案件的新题与修订聊天' if r['source_index'] in prior_indices else '此前未生成的判决')+'</td></tr>')
    summary = {'cases': len(records), 'rendered_cases': rendered, 'images': images, 'messages': messages,
               'claim_labels': dict(labels), 'claims': sum(labels.values()),
               'insufficiency_types': dict(reasons),
               'causes': len({r['cause'] for r in records}),
               'previously_unrendered_local_sources': sum(r['source_index'] not in prior_indices and not r.get('new_external_judgment') for r in records),
               'new_internet_judgments_in_rendered_cohort': sum(r.get('new_external_judgment',False) for r in records),
               'target_additional_insufficient_cases': 200, 'target_completed': False,
               'split': 'development', 'professional_gold': False}
    save(out/'summary.json', summary)
    headline=f'{rendered} 案 · {summary["causes"]} 个历史案由标签 · {images} 张截图 · {sum(labels.values())} 道主张题'
    distribution=f'支持 {labels["supported"]} · 反驳 {labels["contradicted"]} · 证据不足 {labels["insufficient"]}'
    page = '<!doctype html><meta charset="utf-8"><title>第四轮：证据能否支持主张</title><style>body{font:16px/1.8 Microsoft YaHei,sans-serif;max-width:1200px;margin:35px auto;padding:15px;background:#f2f5f3;color:#253d34}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #cdded4;padding:12px;text-align:left}a{color:#15745e}.kpi{background:white;padding:22px;border-radius:10px;font-size:23px;font-weight:bold}</style><h1>第四轮：证据能否支持主张</h1><p>对同一份证据提出不同范围的主张：支持、反驳、证据不足。法院未采信与缺少聊天正文分别处理。</p><div class="kpi">'+ESC(headline)+'<br><small>'+ESC(distribution)+'</small></div><p>开发候选，保留判决全文及实际修改。未认证专业金标或困难程度；200案扩充目标仍在来源复核阶段。</p><p><a href="REPORT.md">本轮说明</a> · <a href="REPRODUCIBILITY.md">复现说明</a> · <a href="acquisition/REPORT.md">新增来源检索</a> · <a href="../round_003/SOURCE_GAPS.md">旧缺口原记录</a></p><table><tr><th>历史来源案由</th><th>截图、主张和依据</th><th>主张题数</th><th>来源状态</th></tr>'+''.join(rows)+'</table>'
    (out/'index.html').write_text(page, encoding='utf-8')
    md = '# 第四轮：证据能否支持主张\n\n'+f'完成 {rendered} 案、{images} 张860×1864截图、{messages} 条消息、{sum(labels.values())} 道主张题，覆盖 {summary["causes"]} 个历史来源标签。其中 {summary["previously_unrendered_local_sources"]} 案来自此前未生成的本地候补，{summary["new_internet_judgments_in_rendered_cohort"]} 案来自本轮新获取的官方判决，其余为既有案件的新题与聊天修订。\n\n'
    md+='|主张标签|数量|含义|\n|---|---:|---|\n'+f'|支持|{labels["supported"]}|限定主张得到所供材料支持|\n|反驳|{labels["contradicted"]}|存在明确相反内容|\n|证据不足|{labels["insufficient"]}|不能充分支持，也不能直接断定主张为假|\n\n'
    md+='[打开截图与题目](index.html)。同案包含 supported 控制题和 insufficient 核心题；contradicted 只用于有明确相反证据的主张。问题仅检验给定图片或明确 context 内的支持范围，不把法院最终结果直接作纯图答案。\n\n'
    md += '此前未渲染来源是本地350份归档中的新增合成案件；复用第三轮聊天的新主张题另计。联网检索候选不是已入组截图。200 是扩充目标，本轮没有宣称获得200份新的完整判决。全部是 development，未划为论文封闭测试集。\n\n'
    md += '[可复现性](REPRODUCIBILITY.md) · [来源检索状态](acquisition/REPORT.md) · [离线验证](verification.json)。旧30个来源缺口保留，不因本轮改变评测任务而虚报已补齐。\n'
    md+='\n## 实际修订与独立模型复核\n\n三位作者交叉复核了另外作者的26个案件，我写的两份官方判决由另一位作者复核。报告：[writer_1](peer.writer_1.review.json)、[writer_3](peer.writer_3.review.json)、[writer_2及联网新案](peer.writer_2_and_web.review.json)。这是模型复核，尚无律师金标。\n\n'
    md+='根修订计划均可检查：root.review_plan.json、peer_corrections.review_plan.json、peer_final.review_plan.json、minute_visibility.review_plan.json、answer_scope.review_plan.json、driver_scope.review_plan.json、recipient_clarity.review_plan.json。逐案 root.versions 保留修改前记录，render.versions 保留旧图。实际删除过无通信发送锚点的银行附件、纠正未知发言者归属、同步图外本人姓名题答、修正语音转文字和未披露分钟，不伪造修改历史。\n\n'
    md+='[修订落实清单](peer.resolution.json) 可核对每份计划与逐案已应用的哈希；交叉复核原报告保持原样。[独立 skill 前向验证](skill.forwardtest.json) 保留从单案原始输入重新构建的结果与初次失败；工具随后修复缺失说明文件、索引锚点和缓存图片与消息/渲染器指纹不一致的问题。当前全组 [布局检查](layout.verification.json) 与来源/图片/模型输入检查分别保留。详细机器计数见 [summary.json](summary.json)。\n'
    (out/'REPORT.md').write_text(md, encoding='utf-8')


def verify(out):
    from PIL import Image
    from tools.check_v2_round3 import Links
    records = read(out/'manifest.json')['records']; images = claims_n = links_n = 0
    failures = []
    for record in records:
        d = out/'zh'/record['id']; s = read(d/'source.json'); c = read(d/'case.json')
        assert not normalize(c, s)[1]
        assert s['judgment_text_sha256'] == hashlib.sha256(s['text'].encode()).hexdigest()
        assert (d/'judgment.txt').read_bytes() == s['text'].encode()
        qs = validate_claims(read(d/'claims.review.json'), c, s); claims_n += len(qs)
        assert read(d/'status.json')['phase'] == 'rendered'
        assert read(d/'status.json').get('renderer_sha256')==digest(ROOT/'tools/render_v2_round2.py')
        expected_input=hashlib.sha256(json.dumps({k:c[k] for k in ['messages','conversations','participants','language','platform']},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        assert read(d/'status.json').get('render_input_sha256')==expected_input,'Screenshots predate the current messages'
        r = read(d/'render.json'); covered = set()
        assert {p.relative_to(d).as_posix() for p in (d/'screenshots').glob('*.png')}=={i['path'] for i in r['images']},'Orphan active screenshot'
        chrome={}; fragments={}
        for shot in r['images']:
            with Image.open(d/shot['path']) as png:
                assert png.size == (860, 1864)
                fixed=(png.crop((0,0,860,176)).tobytes(),png.crop((0,1738,860,1864)).tobytes())
                if shot['conversation_id'] in chrome:assert fixed==chrome[shot['conversation_id']]
                else:chrome[shot['conversation_id']]=fixed
            for box in shot['boxes']:
                x,y,w,h=box['bbox_pixels'];assert 0<=x and x+w<=860 and 176<=y and y+h<=1738 and h>0,box
            if shot.get('scroll_fragment'):
                segment=shot['scroll_fragment'];fragments.setdefault(segment['message_id'],[]).append(segment)
            covered.update(shot['message_ids']); images += 1
        assert covered == {m['id'] for m in c['messages']}
        for mid,segments in fragments.items():
            segments.sort(key=lambda x:x['offset_css']);assert segments[0]['offset_css']==0
            end=0
            for segment in segments:
                assert segment['offset_css']<=end+.5
                end=max(end,segment['offset_css']+segment['visible_height_css'])
            assert end+.5>=segments[0]['full_height_css']
        tasks = read(d/'tasks.claim_support.json')['tasks']
        for task in tasks:
            assert not set(task) & {'answer', 'label', 'reasoning', 'source_refs', 'missing_evidence', 'evidence_message_ids'}
            if task['task_mode'] == 'image_only': assert 'context' not in task
        # Full source HTML/JSON intentionally remains outside model task payloads.
    for path in sorted(out.rglob('*.html')):
        # Raw website snapshots are provenance, not generated local review pages.
        if path.name=='snapshot.html' and 'acquisition' in path.relative_to(out).parts:continue
        parser = Links(); parser.feed(path.read_text(encoding='utf-8'))
        for link in parser.links:
            from urllib.parse import urlsplit, unquote
            part = urlsplit(link)
            if part.scheme or part.netloc: continue
            target = (path.parent/unquote(part.path)).resolve() if part.path else path.resolve()
            assert target.exists(), (path, link)
            if part.fragment and target.suffix == '.html':
                target_parser = Links(); target_parser.feed(target.read_text(encoding='utf-8'))
                assert unquote(part.fragment) in target_parser.ids, (path, link)
            links_n += 1
    lock = read(out/'previous_round_lock.json')
    for name, expected in lock.items(): assert digest(ROOT/name) == expected, 'Previous round changed: '+name
    # Observable rejection checks: answer leakage and missing evidence citations.
    if records:
        d = out/'zh'/records[0]['id']; q = read(d/'claims.review.json'); c = read(d/'case.json'); s = read(d/'source.json')
        broken = copy.deepcopy(q); broken['claims'][0]['evidence_message_ids'] = ['absent']
        try: validate_claims(broken, c, s)
        except AssertionError: pass
        else: raise AssertionError('Bad citation accepted')
        broken = copy.deepcopy(q); broken['claims'][0]['source_refs'][0]['char_start'] = -1
        try: validate_claims(broken, c, s)
        except AssertionError: pass
        else: raise AssertionError('Bad source coordinate accepted')
    save(out/'verification.json', {'passed': True, 'cases': len(records), 'images': images,
         'rendered_case_ids':[r['id'] for r in records],
         'claims': claims_n, 'local_links': links_n, 'previous_round_files_unchanged': len(lock),
         'bad_citation_rejected': True, 'bad_source_coordinate_rejected': True,
         'model_payload_answer_fields_absent': True, 'semantic_legal_gold_certified': False})
    print(json.dumps(read(out/'verification.json'), ensure_ascii=False))


def bundle(out):
    code_paths = [ROOT/'tools'/name for name in ['v2_claim_support.py', 'v2_cause_batch.py',
        'render_v2_round2.py', 'build_v2_judgment_review.py', 'check_v2_round3.py',
        'v2_apply_claim_review.py','v2_acquire_claim_sources.py','write_v2_web_claim_cases.py','check_v2_chat_layout.py']]
    code_paths += list((ROOT/'skills/judgment-chat-dataset').rglob('*'))
    code_paths += [ROOT/'legalhub/synthesis.py',ROOT/'legalhub/providers.py']
    environment = {'python': sys.version, 'platform': platform.platform(),
       'packages': {x: importlib.metadata.version(x) for x in ['Pillow', 'openpyxl', 'websocket-client', 'requests']},
       'model_identifier': 'not_exposed_by_runtime', 'authoring_mode': 'Codex agent direct writing',
       'exact_generation_replay_guaranteed': False, 'archived_artifact_replay_supported': True}
    try:
        head=subprocess.run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture_output=True,text=True,timeout=10)
        environment['git_base_head']=head.stdout.strip() if head.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):environment['git_base_head']=None
    environment['git_head_is_complete_artifact_version']=False
    for package in ['PyYAML','certifi','charset-normalizer','idna','urllib3','et_xmlfile']:
        try:environment['packages'][package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:environment['packages'][package]='not_installed'
    (out/'requirements.replay.lock.txt').write_text('\n'.join(f'{name}=={version}' for name,version in sorted(environment['packages'].items()) if version!='not_installed')+'\n',encoding='utf-8')
    from tools.render_v2_round2 import CHROME
    environment['browser_binary'] = str(CHROME)
    environment['browser_sha256'] = digest(CHROME) if CHROME.exists() else None
    save(out/'environment.json', environment)
    hashes = {}
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name not in {'artifact_manifest.json', 'artifact_manifest.sha256'} and '.tmp' not in path.name:
            hashes[path.relative_to(ROOT).as_posix()] = digest(path)
    for path in code_paths:
        if path.is_file(): hashes[path.relative_to(ROOT).as_posix()] = digest(path)
    save(out/'artifact_manifest.json', {'sha256': hashes, 'algorithm': 'sha256',
         'contains_secrets': False, 'archive_generation_inputs_outputs': True})
    (out/'artifact_manifest.sha256').write_text(digest(out/'artifact_manifest.json')+'\n', encoding='ascii')
    print(json.dumps({'hashed_files': len(hashes)}, ensure_ascii=False))


def freeze(out):
    records=[]
    for record in read(out/'manifest.json')['records']:
        d=out/'zh'/record['id'];assert read(d/'status.json')['phase']=='rendered'
        original=ROOT/record['authoring_input']
        target=out/'frozen_authoring'/record['author']/record['id'];target.mkdir(parents=True,exist_ok=True)
        for name in ['source.json','source.reading.json','direct.draft.json','codex.review.json']:
            shutil.copyfile(d/name,target/name)
        shutil.copyfile(d/'case.json',target/'direct.revised.json')
        shutil.copyfile(d/'claims.review.json',target/'claims.json')
        if (d/'root.review.json').exists():shutil.copyfile(d/'root.review.json',target/'root.review.json')
        records.append({'id':record['id'],'author':record['author'],
            'path':target.relative_to(ROOT).as_posix(),
            'original_authoring_path':original.relative_to(ROOT).as_posix(),
            'files':{p.name:digest(p) for p in target.iterdir() if p.is_file()}})
    save(out/'frozen_authoring_manifest.json',{'records':records,
        'meaning':'Final root-reviewed inputs for offline replay; original drafts and author revisions remain archived separately.',
        'new_language_model_calls':False})
    print(json.dumps({'frozen_cases':len(records)},ensure_ascii=False))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=['inventory', 'build', 'render', 'report', 'verify', 'freeze', 'bundle'])
    parser.add_argument('--out', type=Path, default=DEFAULT); args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to((ROOT/'datasets/v2.0.0').resolve()) and out not in {PREVIOUS.resolve(), (ROOT/'datasets/v2.0.0/round_002').resolve()}
    out.mkdir(parents=True, exist_ok=True)
    globals()[args.command](out)


if __name__ == '__main__': main()
