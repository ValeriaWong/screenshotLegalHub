"""Keep a coordinate-mode development trial separate from frozen label evaluation."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legalhub import benchmark as b

base=ROOT/'blocks/evidence/artifacts/extractor-normalized/sf_qwen38_thinking'
corpus=b.read(base/'corpus.json')
targets=b.read(ROOT/'blocks/evidence/artifacts/extractor-comparison/manifest.json')['targets']
messages=[x for x in corpus['records'] if x['kind']=='message'];checks=[]
for target in targets:
    candidates=[x for x in messages if x['image_id']==target['image_id'] and b.normalize(target['quote']) in b.normalize(x['text'])]
    x,y=target['point']
    covered=[m for m in candidates if any(r['bbox'][0]<=x<=r['bbox'][2] and r['bbox'][1]<=y<=r['bbox'][3] for r in m['source_refs'])]
    checks.append({**target,'quote_match':bool(candidates),'source_point_covered':bool(covered),
                   'source_refs':[r for m in candidates for r in m['source_refs']]})
rows=[json.loads(s) for s in (base/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
result={'coordinate_space':'normalized_1000','planned_images':2,'statuses':{r['image_id']:r['status'] for r in rows},
        'attempts':sum(len(r['attempts']) for r in rows),'elapsed_seconds':sum(r['elapsed_seconds'] for r in rows),
        'quote_hits':sum(x['quote_match'] for x in checks),'anchored_hits':sum(x['source_point_covered'] for x in checks),'checks':checks,
        'promoted_to_production':False,'limitation':'Two development screenshots, five previously inspected points, not independent or exhaustive gold.'}
b.write(base/'results.json',result)
lines=['# 显式归一化坐标开发实验','',
       'Qwen3.8 的两张开发截图重新请求，显式要求 x/y 均为 0–1000。软件校验原始框，再按原图尺寸转换一次，source_refs 同时保存 raw_bbox 和像素 bbox；不重新解释旧输出。', '',
       f"有效输出 {corpus['metadata']['ok_images']}/2；{result['attempts']} 次实际 HTTP 尝试（含重试），串行含重试总耗时 {result['elapsed_seconds']:.2f} 秒。五处检查原文匹配 {result['quote_hits']}/5，对应区域覆盖 {result['anchored_hits']}/5。", '',
       '| 原图 | 状态 |','|---|---|']
lines += [f"| {r['image_id']} | {r['status']} |" for r in rows]
lines += ['', '首张回答存在缺失冒号的 JSON 语法错误，作为 invalid_format 原样保留；没有修补回答再计为成功。该图锚点未得到可用结果，计入五项分母。',
          '该实验仅提示坐标协议值得显式适配，当前不足以替换生产默认模型；没有修改冻结留出评测输入。点覆盖不是完整框 IoU，锚点也不是独立金标。', '',
          '[Qwen 官方仓库讨论](https://github.com/QwenLM/Qwen3-VL/issues/1512)说明 Qwen3-VL 使用相对坐标。对 Qwen3.8 的效果为本库单独实验，不把不同模型的行为直接等同。',
          '原始产物：`blocks/evidence/artifacts/extractor-normalized/sf_qwen38_thinking/`。']
(ROOT/'reports/v1.0.0_extractor_coordinate_trial.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','statuses')},ensure_ascii=True))
