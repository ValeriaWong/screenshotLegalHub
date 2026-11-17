"""Sync the manually reviewed ledger; check counts and evidence without network calls."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / 'docs/ai_docs_center'
SKIP = {'.git','.venv','.conda','.tools','.runtime','__pycache__','node_modules','vendor','ai_docs_center','.pytest_cache','.cache'}
LABEL = {'completed':'已完成（限定范围）','partial':'部分完成','planned':'待交付','resolved':'已修复/归档','open':'未关闭','deferred':'后续扩展'}
def link(p):
    return '['+p+'](../../'+p.replace(' ','%20')+')'
def refs(x):
    return '<br>'.join(link(p) for p in x['evidence'])
def table(headers,rows):
    def cell(c): return str(c).replace('|',chr(92)+'|').replace(chr(10),' ')
    return chr(10).join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(cell(c) for c in row)+' |' for row in rows])+chr(10)
def inventory():
    found=set(ROOT.glob('*.md'))
    for name in ['docs','reports','blocks','skills','paper','datasets','product_v1','evidence_workbench_v1']:
        for folder,dirs,names in os.walk(ROOT/name):
            dirs[:]=sorted(d for d in dirs if d not in SKIP and not d.startswith(('.venv', '.conda')) and not Path(folder,d).is_symlink())
            if Path(folder).relative_to(ROOT).as_posix().startswith('datasets/v3.0.0/'):
                dirs[:] = [d for d in dirs if d != 'snapshot']  # byte copies are indexed by their source manifest
            found.update(Path(folder,n) for n in names if n.lower().endswith('.md'))
    for child in (ROOT/'projects').iterdir():
        if child.is_dir() and not child.is_symlink():
            found.update(p for p in child.iterdir() if p.is_file() and p.name.lower().startswith('readme') and p.suffix.lower()=='.md')
    docs=[]
    for p in sorted(found):
        rel=p.relative_to(ROOT).as_posix();data=p.read_bytes();text=data.decode('utf-8-sig',errors='replace')
        title=next((line.lstrip('# ').strip() for line in text.splitlines() if line.startswith('# ')),p.stem)
        if rel.startswith('projects/') or '/archive_text/' in rel: category='历史来源/上游项目'
        elif rel.startswith('reports/v3.0.0/'): category='V3执行检查'
        elif rel.startswith(('evidence_workbench_v1/','reports/')) or '/artifacts/' in rel or rel in ['README.before_startup_update.md','docs/RESTART_ARCHITECTURE.md']: category='历史快照/验收证据'
        elif rel.startswith('datasets/v3.0.0/'): category='V3准备快照'
        elif rel.startswith('datasets/'): category='版本化开发候选'
        elif rel=='V3.0.0_PLAN.md' or rel.startswith('docs/v3.0.0/'): category='V3计划与交接'
        elif rel.startswith('skills/'): category='工作流Skill'
        elif rel.startswith('paper/'): category='论文工作稿'
        elif rel.startswith('docs/agency-agents/'): category='外部角色参考'
        else: category='现行入口/技术参考'
        docs.append(dict(path=rel,title=title,category=category,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
    return docs

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    s=json.loads((CENTER/'status.json').read_text(encoding='utf-8-sig'));errors=[];generated={}
    stamp='评估日期：'+s['assessed_on']+'（Asia/Singapore）。依据 '+link(s['basis'])+'。数据源：[status.json](status.json)。由 '+link('tools/sync_ai_docs_center.py')+' 生成；状态须人工核查，脚本不授予认证。'+chr(10)*2
    for key in ['features','issues','gaps']:
        if dict(Counter(x['status'] for x in s[key]))!=s['summary'][key]: errors.append('count mismatch: '+key)
        if len({x['id'] for x in s[key]})!=len(s[key]): errors.append('duplicate ID: '+key)
    for row in s['features']+s['issues']+s['gaps']+s['stages']:
        for p in row['evidence']:
            if not (ROOT/p).is_file(): errors.append('missing evidence: '+p)
    if len(s['stages'])!=s['v3_stage_acceptance']['total']: errors.append('stage count mismatch')
    for p in s['missing_v3_roots']:
        if (ROOT/p).exists(): errors.append('V3 root now exists; reassess manually: '+p)
    for key,title,headers,rows in [
        ('features','Feature统计',['ID','功能','状态/阶段','完成范围与限制','证据'],[(x['id'],x['title'],LABEL[x['status']]+' / '+x['stage'],x['scope'],refs(x)) for x in s['features']]),
        ('issues','Issues统计与归档',['ID','问题','状态/严重度','发现','处置或关闭条件','证据'],[(x['id'],x['title'],LABEL[x['status']]+' / '+x['severity'],x['finding'],x['resolution'],refs(x)) for x in s['issues']]),
        ('gaps','Gap清单与交接',['ID','缺口','阶段/优先级','状态','完成标准','证据'],[(x['id'],x['title'],x['stage']+' / '+x['priority'],LABEL[x['status']],x['acceptance'],refs(x)) for x in s['gaps']])]:
        summary='；'.join(LABEL[k]+' '+str(v) for k,v in s['summary'][key].items())
        generated[key.upper()+'.md']='# '+title+chr(10)*2+stamp+'共'+str(len(s[key]))+'项：'+summary+'。'+chr(10)*2+'Feature按限定能力计数；issue为有证据的问题；gap为交付差距，三者不相加为任务总数。已完成feature不代表V3阶段验收。P0为下一阶段前置，P1为后续必需交付，P2为另行验收扩展。'+chr(10)*2+table(headers,rows)
    wp=json.loads((ROOT/'docs/v3.0.0/work_packages.json').read_text(encoding='utf-8-sig'))
    if wp['progress_snapshot']['accepted_stages']!=s['v3_stage_acceptance']['completed']: errors.append('V3 work packages summary out of sync')
    checked=len(re.findall(r'^- \[x\]',(ROOT/'docs/v3.0.0/READINESS.md').read_text(encoding='utf-8'),flags=re.M))
    unchecked=len(re.findall(r'^- \[ \]',(ROOT/'docs/v3.0.0/READINESS.md').read_text(encoding='utf-8'),flags=re.M))
    if (checked,checked+unchecked)!=(s['readiness_checklist']['all_checked'],s['readiness_checklist']['all_total']): errors.append('readiness checkbox count mismatch')
    accepted=sum(row['status']=='accepted' for row in s['stages'])
    if accepted!=s['v3_stage_acceptance']['completed']: errors.append('accepted stage count mismatch')
    gap_ids={g['id'] for g in s['gaps']}
    for row in s['stages']:
        if not set(row['gaps'])<=gap_ids: errors.append('unknown gap reference: '+row['id'])
    archived=CENTER/'archive/2026-10-22/manifest.json'
    if archived.exists():
        for snap in json.loads(archived.read_text(encoding='utf-8'))['original_snapshots']:
            if hashlib.sha256((ROOT/snap['snapshot']).read_bytes()).hexdigest()!=snap['sha256']: errors.append('archive snapshot changed: '+snap['snapshot'])
    docs=inventory()
    generated['documents_inventory.json']=json.dumps(dict(assessed_on=s['assessed_on'],scope='first-party Markdown plus project root READMEs; excludes docs center, dependencies and V3 snapshot byte copies',count=len(docs),documents=docs),ensure_ascii=False,indent=2)+chr(10)
    generated['DOCUMENTS_INDEX.md']='# 第一方Markdown完整索引'+chr(10)*2+stamp+'清点'+str(len(docs))+'份。排除本文档中心（防止统计自身）、环境、依赖、vendor、临时目录及V3 snapshot字节副本（由source manifest单列）；projects仅收子项目顶层README。这里只清点和分类，不逐篇认证法律/研究事实。JSON/源码/图片另按证据校验。'+chr(10)*2+table(['分类','份数'],sorted(Counter(x['category'] for x in docs).items()))+chr(10)+table(['分类','文档','标题'],[(x['category'],link(x['path']),x['title']) for x in docs])
    for name,content in generated.items():
        dest=CENTER/name
        if args.check:
            if not dest.exists() or dest.read_text(encoding='utf-8')!=content: errors.append('out of sync: '+name)
        else:
            with dest.open('w',encoding='utf-8',newline='\n') as stream: stream.write(content)
    pages=[ROOT/p for p in ['README.md','docs/README.md','reports/README.md','V3.0.0_PLAN.md','docs/v3.0.0/READINESS.md','docs/v3.0.0/S0_BASELINE.md','docs/v3.0.0/SOURCE_CLOSURE.md','docs/architecture.md','docs/data-contracts.md','docs/skill-map.md','docs/RESTART_ARCHITECTURE.md','product_v1/README.md','product_v1/docs/REQUIREMENTS.md','product_v1/docs/ACCEPTANCE.md','evidence_workbench_v1/README.md']]+list(CENTER.glob('*.md'))+[CENTER/'archive/2026-10-22/README.md',CENTER/'archive/2026-10-22/COMPLETED.md']
    pages += [ROOT/b['report'] for b in s.get('preparation_batches',[])]
    pages += [ROOT/p for p in s.get('completed_updates',[])]
    pages += [ROOT/p for p in s.get('execution_docs',[])]
    for page in pages:
        if not page.exists(): continue
        for raw in re.findall(r'\]\(([^\n]+?)\)',page.read_text(encoding='utf-8-sig')):
            url=raw.strip().split(' "')[0].strip('<>')
            if urlsplit(url).scheme or url.startswith(('#','//')): continue
            target=unquote(url.split('#',1)[0].split('?',1)[0])
            if target and not (page.parent/target).exists(): errors.append('broken link: '+str(page.relative_to(ROOT))+' -> '+target)
    print(json.dumps(dict(status='passed' if not errors else 'failed',mode='check' if args.check else 'sync',date=s['assessed_on'],errors=sorted(set(errors)),features=len(s['features']),issues=len(s['issues']),gaps=len(s['gaps']),stages=len(s['stages']),markdown_documents=len(docs)),ensure_ascii=False,indent=2))
    return 1 if errors else 0
if __name__=='__main__': sys.exit(main())
