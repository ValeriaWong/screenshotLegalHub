"""Re-render frozen V3 inputs in an isolated output; never write into snapshots."""
import argparse, hashlib, importlib.metadata, importlib.util, json, platform, shutil, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name, p):
    spec = importlib.util.spec_from_file_location(name, p)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', default='datasets/v3.0.0/baseline_20261023_001')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    baseline = (ROOT / args.baseline).resolve()
    out = (ROOT / args.output).resolve()
    if not baseline.is_relative_to(ROOT / 'datasets/v3.0.0') or not out.is_relative_to(ROOT / 'reports/v3.0.0'):
        raise ValueError('Use bounded V3 baseline and report paths')
    out.mkdir(parents=True, exist_ok=False)
    marker = out / '.incomplete'; marker.write_text('rendering', encoding='utf-8')
    snapshot = baseline / 'snapshot'
    renderer = load('frozen_renderer', snapshot / 'tools/render_v2_round2.py')
    renderer.ROOT = out / 'work'  # Browser profile must never live inside the frozen source.
    cases = ['zh/zh_sales_146', 'en/en_probate_283']
    results = []
    with renderer.Browser('reproduction') as browser:
        browser.call('Network.enable')
        browser.call('Network.setBlockedURLs', {'urls': ['http://*', 'https://*']})
        version = browser.call('Browser.getVersion')
        for run in ['first', 'repeat']:
            target = out / run
            shutil.copytree(snapshot / 'datasets/v2.0.0/round_002/assets', target / 'assets')
            for relative in cases:
                source = snapshot / 'datasets/v2.0.0/round_002' / relative
                dest = target / relative; dest.mkdir(parents=True)
                shutil.copyfile(source / 'case.json', dest / 'case.json')
                renderer.render_case(browser, dest)
                rendered = json.loads((dest / 'render.json').read_text(encoding='utf-8'))
                case = json.loads((dest / 'case.json').read_text(encoding='utf-8'))
                seen = set(); pages = []
                for entry in rendered['images']:
                    p = dest / entry['path']
                    with Image.open(p) as im: size = list(im.size)
                    assert size == [860, 1864]
                    for box in entry['boxes']:
                        x, y, w, h = box['bbox_pixels']
                        assert 0 <= x < x+w <= size[0] and 0 <= y < y+h <= size[1]
                    seen.update(entry['message_ids'])
                    old = source / entry['path']
                    pages.append(dict(path=p.relative_to(out).as_posix(), sha256=sha(p), size=size,
                                      historical_pixel_match=old.is_file() and sha(old)==sha(p)))
                assert seen == {m['id'] for m in case['messages']}
                browser.call('DOM.enable'); browser.call('CSS.enable')
                document = browser.call('DOM.getDocument')['root']['nodeId']
                nodes = browser.call('DOM.querySelectorAll', {'nodeId':document,'selector':'.bubble, .stamp, .sender'})['nodeIds']
                fonts = [font for node in nodes for font in browser.call('CSS.getPlatformFontsForNode', {'nodeId':node})['fonts']]
                assert fonts, 'Actual rendered font evidence is empty'
                results.append(dict(run=run, case_id=case['id'], pages=pages, messages=len(seen), actual_fonts=fonts))
    for case_id in {r['case_id'] for r in results}:
        first, repeat = [r for r in results if r['case_id']==case_id]
        assert [p['sha256'] for p in first['pages']] == [p['sha256'] for p in repeat['pages']], 'Repeat pixels differ'
    font_files = []
    for pattern in ['msyh*.ttc','segoeui*.ttf','arial*.ttf']:
        for p in sorted(Path('C:/Windows/Fonts').glob(pattern)):
            font_files.append(dict(file=p.name,sha256=sha(p),bytes=p.stat().st_size))
    packages = {}
    for name in ['Pillow','websocket-client','PyYAML','openpyxl','requests']:
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name] = None
    report = dict(status='passed', baseline=args.baseline, python=sys.version, platform=platform.platform(),
                  dependencies=packages, browser=version, browser_sha256=sha(renderer.CHROME),
                  renderer_sha256=sha(snapshot/'tools/render_v2_round2.py'), viewport=[430,932], scale=2,
                  font_files=font_files, runs=results, repeated_pixels_identical=True, network_pages_blocked=True,
                  limitations=['Installed environment reused; no clean-machine dependency installation.',
                               'Historical images compared separately; repeat determinism does not imply historical pixel equality.',
                               'No independent semantic or legal certification.'],new_model_calls=0)
    (out/'reproduction.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    marker.unlink()
    print(json.dumps(dict(status='passed',cases=2,pages=sum(len(r['pages']) for r in results),output=args.output)))
if __name__ == '__main__': main()
