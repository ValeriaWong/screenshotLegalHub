"""Development-only factual/source checks for software extraction candidates."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub import benchmark as b
from legalhub.evidence import extract, extraction_prompt
from legalhub.retrieval import merge, DEFAULT_DB

ART = ROOT/'blocks/evidence/artifacts/extractor-comparison'
ALIASES = ['sf_qwen38_thinking', 'sf_qwen3vl_thinking_native', 'kimi3_low']
TARGETS = [
    {'image_id':'58b7dff082ec3972eb9edeb4_image_1.jpg','quote':'你可以雇我帮你管理','point':[700,635]},
    {'image_id':'58b7dff082ec3972eb9edeb4_image_1.jpg','quote':'起码得先付个预付款','point':[700,1430]},
    {'image_id':'5ad6f87311be1056f7197a9f_image_6.jpg','quote':'给你转了2000','point':[310,155]},
    {'image_id':'5ad6f87311be1056f7197a9f_image_6.jpg','quote':'钱收到没，让手下转的','point':[350,505]},
    {'image_id':'5ad6f87311be1056f7197a9f_image_6.jpg','quote':'收到了','point':[545,746]},
]


def prepare():
    parent = b.read(ROOT/'blocks/evidence/artifacts/demo_manifest.json')
    images = [x for x in parent['images'] if x['image_id'] in {t['image_id'] for t in TARGETS}]
    spec = {'images': images, 'targets': TARGETS, 'scope':'development_only',
            'gold_origin':'Original-pixel regions visually inspected; minimal quote anchors, not exhaustive transcription or independent legal gold.'}
    if (ART/'manifest.json').exists() and b.read(ART/'manifest.json')!=spec:
        raise ValueError('Extractor comparison changed')
    b.write(ART/'manifest.json',spec)
    # Reuse K3's two individual requests only after verifying image and prompt hashes.
    original = ROOT/'blocks/evidence/artifacts/runs/p2-kimi3-development'
    source = original/'predictions.jsonl'
    rows = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]
    refs = {x['image_id']:x for x in images}
    reused=[]
    for row in rows:
        if row['image_id'] not in refs:continue
        image = refs[row['image_id']]
        if row['image_sha256']!=image['sha256'] or row['prompt_sha256']!=hashlib.sha256(extraction_prompt(image).encode()).hexdigest():
            raise ValueError('Extractor reuse input mismatch')
        reused.append(dict(row,carried_over_from={'path':source.relative_to(ROOT).as_posix(),'sha256':b.sha(source)}))
    out = ART/'kimi3_low'; out.mkdir(parents=True,exist_ok=True)
    if not (out/'predictions.jsonl').exists():
        (out/'predictions.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in reused),encoding='utf-8')


def run(alias):
    result = extract(ART/'manifest.json',alias,ART/alias,True,progress=lambda x:print(alias,json.dumps(x,ensure_ascii=True),flush=True))
    return result


def report():
    spec=b.read(ART/'manifest.json'); rows=[]
    for alias in ALIASES:
        folder=ART/alias
        if not (folder/'corpus.json').exists():continue
        corpus=b.read(folder/'corpus.json'); messages=[x for x in corpus['records'] if x['kind']=='message']
        checks=[]
        for target in spec['targets']:
            candidates=[x for x in messages if x['image_id']==target['image_id'] and b.normalize(target['quote']) in b.normalize(x['text'])]
            x,y=target['point']
            anchored=[m for m in candidates if any(ref['bbox'][0]<=x<=ref['bbox'][2] and ref['bbox'][1]<=y<=ref['bbox'][3] for ref in m['source_refs'])]
            checks.append({**target,'transcription_match':bool(candidates),'source_point_covered':bool(anchored),
                           'matched_record_ids':[m['id'] for m in candidates]})
        rows.append({'alias':alias,'planned_images':corpus['metadata']['planned_images'],'ok_images':corpus['metadata']['ok_images'],
                     'messages':len(messages),'events':sum(x['kind']=='event' for x in corpus['records']),
                     'rejected_messages':len(corpus['metadata']['rejected_messages']),'checks':checks,
                     'quote_hits':sum(x['transcription_match'] for x in checks),'anchored_hits':sum(x['source_point_covered'] for x in checks),
                     'limitations':'Five previously inspected development quote anchors. Not an exhaustive extraction precision/recall or generalization benchmark.'})
    b.write(ART/'results.json',{'spec':spec,'runs':rows})
    lines=['# 证据抽取开发集检查','','两张开发截图、五处人工检查过的原文锚点；不是完整转录金标、独立测试集或法律理解排名。K3沿用输入和提示摘要匹配的已有请求。','',
           '| 配置 | 图片成功 | 消息 | 事件候选 | 无效消息 | 原文锚点命中 | 对应区域覆盖 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f'| {r["alias"]} | {r["ok_images"]}/{r["planned_images"]} | {r["messages"]} | {r["events"]} | {r["rejected_messages"]} | {r["quote_hits"]}/5 | {r["anchored_hits"]}/5 |')
    lines+=['','框的区域锚点曾借助首个候选输出进行人工检查，因此不用于证明该候选的 bbox 优势。抽取数量较多也不直接代表质量更好。','所有事件解释、跨图身份和不完整时间均保留待核对状态。']
    (ROOT/'reports/v1.0.0_extractor_development_check.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','report']);args=parser.parse_args()
    if args.command=='prepare':prepare()
    elif args.command=='run':
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,ALIASES))
        report()
    else:report()
