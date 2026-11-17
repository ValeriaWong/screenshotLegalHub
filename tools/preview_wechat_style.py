"""Render two review-only excerpts from existing V2 cases without changing datasets."""
import argparse
import copy
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from tools import render_v2_round2 as renderer
from tools.v2_peer_round import render_current_case

REFERENCE = 'https://github.com/gaopengbin/wechat-dialog-generator/blob/0e64ddb3b1a6843cc92218270bb539a0b2a6b352/src/components/PhonePreview.css'
SAMPLES = [
    ('01_text', '普通聊天', 'datasets/v2.0.0/round_006/zh/q6_0078', 'c1',
     ['m001', 'm002', 'm003', 'm004', 'm005', 'm006']),
    ('02_transfer', '转账与日期', 'datasets/v2.0.0/round_006/zh/q6_0047_5ed6e70b', 'c1',
     ['m001', 'm002', 'm003', 'm004', 'm005']),
]


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def save(file, value):
    file.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def check_layout(browser):
    layout = browser.evaluate('''(() => {
      const content = document.querySelector('.content').getBoundingClientRect();
      const rect = x => {const r=x.getBoundingClientRect(); return [r.x,r.y,r.width,r.height]};
      const overflows = x => {
        const b=x.getBoundingClientRect(), range=document.createRange();
        range.selectNodeContents(x);
        // A bubble's decorative tail legitimately extends its scrollWidth.
        return Array.from(range.getClientRects()).some(r=>r.width && (r.left<b.left-.5 || r.right>b.right+.5));
      };
      return {
        content: [content.x,content.y,content.width,content.height],
        title: rect(document.querySelector('.header .title')),
        avatar_count: document.querySelectorAll('.avatar svg').length,
        external_resources: performance.getEntriesByType('resource').filter(x=>/^https?:/.test(x.name)).length,
        rows: Array.from(document.querySelectorAll('.row'), row => ({
          id: row.dataset.id, bounds: rect(row),
          stamp: row.querySelector('.stamp')?.textContent || '',
          parts: Array.from(row.querySelectorAll('.bubble,.filename,.transfer-amount,.excerpt'), x => ({
            kind:x.className, bounds:rect(x), overflow:overflows(x)
          }))
        }))
      };
    })()''')
    cx, cy, cw, ch = layout['content']
    for row in layout['rows']:
        x, y, w, h = row['bounds']
        assert cx <= x < x+w <= cx+cw and cy <= y < y+h <= cy+ch, row
        for part in row['parts']:
            x, y, w, h = part['bounds']
            assert 0 <= x < x+w <= renderer.WIDTH, part
            assert not part['overflow'], part
    tx, _, tw, _ = layout['title']
    assert abs(tx+tw/2-renderer.WIDTH/2) < 1, 'Title is not centered'
    assert layout['avatar_count'] == len(layout['rows'])
    assert layout['external_resources'] == 0
    return layout


def build(output):
    output = output.resolve()
    if not output.is_relative_to((ROOT/'reports').resolve()):
        raise ValueError('Preview output must be under reports/')
    output.mkdir(parents=True, exist_ok=False)
    records = []
    with renderer.Browser('wechat-style-preview') as browser:
        browser.call('Network.enable')
        browser.call('Network.setBlockedURLs', {'urls': ['http://*', 'https://*']})
        version = browser.call('Browser.getVersion')
        for key, label, source_path, conversation, ids in SAMPLES:
            source = ROOT/source_path/'case.json'
            source_hash = sha(source)
            original = json.loads(source.read_text(encoding='utf-8'))
            case = copy.deepcopy(original)
            case['conversations'] = [c for c in case['conversations'] if c['id'] == conversation]
            case['messages'] = [m for m in case['messages'] if m['id'] in ids]
            assert [m['id'] for m in case['messages']] == ids
            assert all(m['conversation_id'] == conversation for m in case['messages'])
            case.pop('questions', None)  # Review excerpts do not carry old task/image references.
            case['status'] = 'style_preview_excerpt_only'
            directory = output/key
            directory.mkdir()
            save(directory/'case.json', case)
            render_current_case(browser, directory)
            manifest = json.loads((directory/'render.json').read_text(encoding='utf-8'))
            assert len(manifest['images']) == 1, 'Expected one screenshot per review sample'
            shot = manifest['images'][0]
            assert shot['message_ids'] == ids
            with Image.open(directory/shot['path']) as picture:
                assert picture.size == (860, 1864)
            browser.load(directory/(conversation+'.html'))
            layout = check_layout(browser)
            by_id = {m['id']: m for m in case['messages']}
            for row in layout['rows']:
                if by_id[row['id']].get('minute_basis') == 'not_visible':
                    assert ':' not in row['stamp'], row
            for box in shot['boxes']:
                x, y, w, h = box['bbox_pixels']
                assert 0 <= x < x+w <= 860 and 0 <= y < y+h <= 1864
            assert sha(source) == source_hash, 'Source case changed'
            record = dict(sample=key, label=label, source_case=source_path+'/case.json',
                          source_sha256=source_hash, message_ids=ids,
                          omitted_message_ids=[m['id'] for m in original['messages'] if m['id'] not in ids],
                          image=key+'/'+shot['path'], image_sha256=sha(directory/shot['path']),
                          message_text_unchanged=True, source_case_unchanged=True, layout=layout)
            save(directory/'provenance.json', record)
            records.append(record)
    report = dict(style_version=renderer.STYLE_VERSION, reference=REFERENCE,
                  renderer_sha256=sha(Path(renderer.__file__)), css_sha256=sha(renderer.WECHAT_STYLE),
                  browser=version, viewport=[430, 932], scale=2, samples=records,
                  new_model_calls=0, historical_images_overwritten=False)
    save(output/'verification.json', report)
    cards = ''.join(
        '<section><h2>'+html.escape(r['label'])+'</h2><a href="'+r['image']+'"><img src="'+r['image']+
        '" width="430" height="932" alt="'+html.escape(r['label'])+'样图"></a><p>'+str(len(r['message_ids']))+
        ' 条既有消息 · <a href="'+r['sample']+'/provenance.json">来源与范围</a></p></section>' for r in records)
    (output/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>微信截图样式预览</title>
<style>body{margin:32px auto;max-width:960px;padding:0 20px;background:#fafafa;color:#222;font:16px/1.65 "Microsoft YaHei",sans-serif}h1{font-size:26px}h2{font-size:18px}main{display:flex;gap:32px;flex-wrap:wrap}section{flex:1;min-width:280px}img{width:100%;max-width:430px;height:auto;display:block;border:1px solid #ddd}a{color:#17633b}p{color:#666}</style>
<h1>微信截图样式预览</h1><p>两段已有判决衍生对话的样式预览。头像为装饰图，消息与时间精度沿用原数据。</p>
<main>'''+cards+'</main><p><a href="'+REFERENCE+'">GitHub 样式参考</a> · <a href="verification.json">渲染核验记录</a></p></html>', encoding='utf-8')
    print(json.dumps(dict(output=str(output), images=[r['image'] for r in records], checks='passed'), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/wechat_style_preview_20261106')
    build(parser.parse_args().output)
