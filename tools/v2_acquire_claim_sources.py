"""Archive official source snapshots and prepare a 200-case review queue.

Search results, fetches, full judgments and accepted dialogues are separate states.
Fetching reuses the seed URLs; no login, paid access or anti-bot bypass.
"""
import argparse, hashlib, html, json, re, sys
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from tools.v2_cause_batch import read, save
OUT = ROOT/'datasets/v2.0.0/round_004'
TYPES = ['identity_unverified', 'statement_not_performance', 'consent_not_shown',
    'scope_mismatch', 'time_uncertain', 'source_authenticity_unverified',
    'causal_link_missing', 'claimant_statement_only', 'object_link_missing', 'amount_scope_mismatch']


class Text(HTMLParser):
    def __init__(self): super().__init__(); self.skip = 0; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}: self.skip += 1
        elif tag in {'p','div','br','h1','h2','h3','li','tr'} and not self.skip: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in {'script','style','noscript'}: self.skip = max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def prepare():
    inventory = read(OUT/'source_inventory.json')['records']
    groups = defaultdict(list)
    for r in inventory:
        if r['keyword_screen_candidate']: groups[r['cause']].append(r)
    # Coverage first, then additional cases in each cause; remove exact text duplicates.
    queue = []; seen = set()
    for position in range(max((len(g) for g in groups.values()), default=0)):
        for cause in sorted(groups):
            group = sorted(groups[cause], key=lambda r:(bool(r['previous_rendered_id']),r['source_index']))
            if position >= len(group): continue
            r = group[position]
            if r['judgment_text_sha256'] in seen: continue
            seen.add(r['judgment_text_sha256']); queue.append(r)
    selected = queue[:200]
    save(OUT/'acquisition/local_review_queue.json', {'records': selected, 'requested_cases':200,
        'screened_candidates_available':len(queue), 'queued_count':len(selected),
        'cause_count':len({r['cause'] for r in selected}), 'semantic_negative_label_confirmed':False,
        'new_external_cases':False, 'full_read_and_dialogue_feasibility_review_required':True})
    historical = read(ROOT/'datasets/v2.0.0/round_003/manifest.json')['representatives']
    causes = sorted({c for r in historical for c in r['atomic_causes']})
    queries = []
    words = ['不足以证明','不能证明','不予采信','原始载体','仅能证明']
    for cause in causes:
        for word in words:
            queries.append({'cause':cause,'query':f'"{cause.split(">")[ -1 ]}" "微信" "{word}" 判决 法院',
                            'status':'not_executed','exclude_news_only_sources':True})
    save(OUT/'acquisition/search_plan.json',{'queries':queries,'cause_labels_are_historical':True,
        'requested_new_external_case_target':200,'plan_is_not_executed_search_results':True})
    save(OUT/'acquisition/balance_policy.json', {'axes':['cause','claim_label','insufficiency_type','language','evidence_complexity'],
        'insufficiency_types':TYPES,'supported_controls_required':True,
        'contradicted_not_required_when_no_opposite_evidence':True,
        'report_macro_by_cause_and_claim_label':True,'majority_baseline_required':True,
        'split_by_judgment_family_not_screenshot':True,'target_new_external_cases':200,
        'target_distinct_causes_is_not_200':True,'quota_strategy':'cover causes first, then balance failure modes; disclose infeasible cells',
        'missing_chat_body_is_not_synthetic_negative_ground_truth':True})
    report()


def fetch_one(seed):
    result = dict(seed); result['fetch_time_utc'] = datetime.now(timezone.utc).isoformat()
    d = OUT/'acquisition/web'/seed['id']; d.mkdir(parents=True,exist_ok=True)
    try:
        response = requests.get(seed['url'],timeout=(10,25),headers={'User-Agent':'LegalChatResearch/0.1 (source archival)'})
        result.update(http_status=response.status_code,final_url=response.url,content_type=response.headers.get('Content-Type',''))
        response.raise_for_status()
        assert 'html' in result['content_type'].lower() or response.content.lstrip().startswith(b'<')
        (d/'snapshot.html').write_bytes(response.content)
        result['snapshot_sha256'] = hashlib.sha256(response.content).hexdigest()
        encoding = response.encoding
        raw = response.content[:4000]
        meta = re.search(br'charset\s*=\s*["\x27]?([\w-]+)',raw,re.I)
        if meta: encoding = meta.group(1).decode('ascii')
        if not encoding or encoding.lower() == 'iso-8859-1': encoding = response.apparent_encoding
        document = response.content.decode(encoding or 'utf-8',errors='replace')
        parser=Text(); parser.feed(document)
        text = '\n'.join(x.strip() for x in ''.join(parser.parts).splitlines() if x.strip())
        (d/'extracted.txt').write_text(text,encoding='utf-8')
        title = re.search(r'<title[^>]*>(.*?)</title>',document,re.S|re.I)
        result.update(title=html.unescape(re.sub('<[^>]+>','',title.group(1))).strip() if title else '',
                      encoding=encoding,text_chars=len(text),text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                      has_chat_keyword=bool(re.search('微信|聊天|截图',text)),
                      extraction_is_article_body_verified=False,
                      full_judgment_confirmed=False,dialogue_feasibility_review_completed=False,
                      status='archived_pending_full_source_review' if len(text)>300 and re.search('微信|聊天|截图',text) else 'fetch_not_useful_pending_review')
    except Exception as e:
        result.update(status='fetch_failed',error=type(e).__name__+': '+str(e))
    save(d/'provenance.json',result)
    return result


def fetch():
    seeds=read(OUT/'acquisition/seed_urls.json')['records']
    with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(fetch_one,seeds))
    save(OUT/'acquisition/web_registry.json',{'records':results,'accepted_into_screenshot_cohort':0,
         'http_success_is_full_judgment':False})
    report()
    print(json.dumps({'states':dict(Counter(r['status'] for r in results))},ensure_ascii=False))


def report():
    path=OUT/'acquisition'; path.mkdir(parents=True,exist_ok=True)
    local=read(path/'local_review_queue.json') if (path/'local_review_queue.json').exists() else {}
    online=read(path/'web_registry.json')['records'] if (path/'web_registry.json').exists() else []
    for n,r in enumerate(online):
        provenance=path/'web'/r['id']/'provenance.json'
        if provenance.exists():online[n]=read(provenance)
    cohort=read(OUT/'manifest.json')['records'] if (OUT/'manifest.json').exists() else []
    accepted=sum(bool(r.get('new_external_judgment')) and
        (OUT/'zh'/r['id']/'status.json').exists() and read(OUT/'zh'/r['id']/'status.json')['phase']=='rendered' for r in cohort)
    rendered_external = {r['source_index']:r['id'] for r in cohort if r.get('new_external_judgment') and
        (OUT/'zh'/r['id']/'status.json').exists() and read(OUT/'zh'/r['id']/'status.json')['phase']=='rendered'}
    for r in online:
        if r['id'] in rendered_external:
            assert r.get('full_judgment_confirmed') and r.get('dialogue_feasibility_review_completed')
            r.update(status='rendered_candidate_pending_professional_review',cohort_case_id=rendered_external[r['id']])
            save(path/'web'/r['id']/'provenance.json',r)
    rendered_local={r['source_index']:r['id'] for r in cohort if not r.get('new_external_judgment') and
        (OUT/'zh'/r['id']/'status.json').exists() and read(OUT/'zh'/r['id']/'status.json')['phase']=='rendered'}
    for r in local.get('records',[]):
        if r['source_index'] in rendered_local:
            r.update(full_read_completed_this_round=True,cohort_case_id=rendered_local[r['source_index']],
                     review_status='rendered_candidate_pending_professional_review')
    if local:save(path/'local_review_queue.json',local)
    if online:save(path/'web_registry.json',{'records':online,'accepted_into_screenshot_cohort':accepted,
                                          'http_success_is_full_judgment':False})
    md='# 证据不足案件扩充：来源获取状态\n\n'
    md+=f'目标新增200个外部案件，不将“200案”写成“200种案由”。当前本地350份来源中，250份命中粗筛；去重后的可排队候选为 {local.get("screened_candidates_available",0)} 份；按案由优先排入 {local.get("queued_count",0)} 份，覆盖 {local.get("cause_count",0)} 个历史原始标签。关键词粗筛可能命中诉辩、法律套话或已经有支持证据的案，不是200个已确认负样本。\n\n'
    md+='[本地200案全文复核队列](local_review_queue.json) · [历史案由检索计划](search_plan.json) · [多维平衡策略](balance_policy.json)。检索计划的未执行查询不能算作检索成果。本轮实际新截图见上级 REPORT.md，与来源候选分开计数。队列中进入本轮截图组的来源已更新全文复核与案件映射；其他条目仍是待复核候选。\n\n'
    md+=f'本轮新增互联网检索种子15个；实际网页获取状态：{dict(Counter(r["status"] for r in online))}。法院案例解读不是完整判决；网页获取成功也不表示其中有可还原聊天。网页快照、文本与哈希保留；本轮有 {accepted} 份联网完整判决经全文阅读和通信锚点审查进入截图组，其余按状态保留。无原件、身份未核验可以作为评测限制，缺少正文不能补造成判决原话。\n\n'
    md+='|来源|主题|文书类型候选|获取状态|\n|---|---|---|---|\n'
    for r in online:
        md+=f'|[{r["id"]}]({r["url"]})|{r["topic"]}|{r["source_type"]}|{r["status"]}|\n'
    (path/'REPORT.md').write_text(md,encoding='utf-8')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','fetch','report']);a=p.parse_args();globals()[a.command]()
