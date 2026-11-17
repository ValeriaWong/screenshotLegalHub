"""Read-only source audit. Outputs only under reports/restart; no model calls."""
from pathlib import Path
import collections, hashlib, io, json, os, re, zipfile
import openpyxl
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/restart'
SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.next', '.pnpm-store'}

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def zip_name(info):
    if info.flag_bits & 0x800: return info.filename
    try: return info.filename.encode('cp437').decode('utf-8')
    except (UnicodeError, LookupError): return info.filename

def workbook_summary(data):
    wb = openpyxl.load_workbook(data, read_only=True, data_only=False)
    result = []
    for s in wb:
        # Feishu exports may declare A1:A1 even when sheet XML contains many rows.
        s.reset_dimensions()
        preview = []
        rows = columns = 0
        for row in s.iter_rows(values_only=True):
            rows += 1; columns = max(columns, len(row))
            if rows <= 4: preview.append([str(v)[:180] if v is not None else None for v in row])
        result.append({'sheet': s.title, 'rows': rows, 'columns': columns, 'header_preview': preview})
    wb.close()
    return result

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    images = ROOT/'projects/ScreenshotLegalBench_v2/process_local_evaluator/images'
    primary_files = sorted(images.glob('*'))
    selected = {p.name: p for p in primary_files if p.is_file()}
    aliases = collections.defaultdict(list)
    # Human-answering assets also contain all 82 screenshots absent from KIE.
    # Ignore thumbnails and use a canonical name without moving originals.
    for p in sorted((ROOT/'projects/quiz-collector/images').glob('*')):
        match = re.search(r'([0-9a-f]{24}_(?:image_\d+|cover)\.(?:jpg|png|jpeg))$', p.name, re.I)
        if not p.is_file() or not match: continue
        name = match.group(1)
        if name in selected and digest(selected[name]) != digest(p):
            raise ValueError(f'Conflicting original image bytes for {name}')
        aliases[name].append(str(p.relative_to(ROOT)).replace('\\', '/'))
        # Prefer an unprefixed filename within the supplemental source.
        if name not in selected or (selected[name].parent != images and p.name == name):
            selected[name] = p
    manifest = []
    for name, p in sorted(selected.items()):
        if not p.is_file(): continue
        item = {'path': str(p.relative_to(ROOT)).replace('\\','/'), 'name': name, 'bytes': p.stat().st_size, 'sha256': digest(p), 'case_id': name.split('_image_')[0], 'aliases': aliases[name]}
        try:
            with Image.open(p) as im:
                item['size'] = list(im.size); im.verify()
        except Exception as e: item['error'] = str(e)
        manifest.append(item)
    (OUT/'images_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    counts = collections.Counter(x['case_id'] for x in manifest)
    archive = []
    for p in ROOT.glob('*.zip'):
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                name = zip_name(info)
                if name.startswith('__MACOSX/') or info.is_dir(): continue
                item = {'archive': p.name, 'name': name, 'bytes': info.file_size}
                raw = z.read(info); item['sha256'] = hashlib.sha256(raw).hexdigest()
                if name.endswith('.xlsx'):
                    try: item['workbook'] = workbook_summary(io.BytesIO(raw))
                    except Exception as e: item['error'] = str(e)
                if name.endswith('.md'):
                    text = raw.decode('utf-8-sig', errors='replace')
                    item['headings'] = [x for x in text.splitlines() if x.startswith('#')][:35]
                    dest = OUT/'archive_text'/Path(name).name
                    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(text, encoding='utf-8')
                if name.endswith('.zip'):
                    try:
                        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
                            item['members'] = [{'name': zip_name(e), 'bytes': e.file_size} for e in inner.infolist() if not e.filename.startswith('__MACOSX/')]
                            for e in inner.infolist():
                                n=zip_name(e)
                                if n.endswith('.md') and not n.startswith('__MACOSX/'):
                                    dest=OUT/'archive_text'/Path(n).name
                                    dest.parent.mkdir(parents=True,exist_ok=True)
                                    dest.write_text(inner.read(e).decode('utf-8-sig',errors='replace'),encoding='utf-8')
                    except Exception as e: item['error'] = str(e)
                archive.append(item)
    (OUT/'archive_inventory.json').write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding='utf-8')
    parent = ROOT.parent
    candidates = [p for p in parent.iterdir() if p.is_dir() and re.search(r'legal|law|vqa|quiz|evaluator|evluator|whatsapp|wechat|label|batch|rag', p.name, re.I)]
    # User requested upper levels; inventory their immediate directories, then relevant projects.
    scope = {'workspace': str(parent), 'upper': str(parent.parent), 'workspace_directories': [p.name for p in parent.iterdir() if p.is_dir()], 'upper_directories': [p.name for p in parent.parent.iterdir() if p.is_dir()]}
    projects = []
    for p in candidates:
        if p == ROOT: continue
        files=[]
        for base, dirs, names in os.walk(p):
            dirs[:] = [d for d in dirs if d not in SKIP]
            for n in names:
                f=Path(base)/n
                if f.suffix.lower() in {'.md','.py','.yaml','.yml','.json','.xlsx','.csv','.pdf'}:
                    files.append({'path': str(f.relative_to(p)).replace('\\','/'), 'bytes': f.stat().st_size})
        projects.append({'path': str(p), 'files': files})
    scope['relevant_projects']=projects
    thesis = parent.parent / '\u6bd5\u4e1a\u6587\u6863'
    scope['thesis_files'] = [{'path':str(p),'bytes':p.stat().st_size} for p in thesis.rglob('*') if p.is_file()] if thesis.exists() else []
    vqa_xlsx = thesis/'vqa_statictics.xlsx'
    if vqa_xlsx.exists(): scope['historical_vqa_workbook'] = workbook_summary(vqa_xlsx)
    (OUT/'local_inventory.json').write_text(json.dumps(scope, ensure_ascii=False, indent=2),encoding='utf-8')
    hashes=collections.Counter(x['sha256'] for x in manifest)
    summary={'images':len(manifest), 'primary_images':len([p for p in primary_files if p.is_file()]), 'supplemental_images':len(manifest)-len([p for p in primary_files if p.is_file()]), 'image_bytes':sum(x['bytes'] for x in manifest), 'filename_case_groups':len(counts), 'multi_image_groups':sum(n>1 for n in counts.values()), 'duplicate_image_hash_groups':sum(n>1 for n in hashes.values()), 'corrupt_images':sum('error' in x for x in manifest), 'archive_files':len(archive), 'local_projects':len(projects)}
    (OUT/'inventory_summary.json').write_text(json.dumps(summary, indent=2),encoding='utf-8')
    print(json.dumps(summary))

if __name__ == '__main__': main()
