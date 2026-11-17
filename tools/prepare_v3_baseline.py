"""Freeze an explicit, local V3 preparation batch; no inference or certification.

Run from the repository root. Each output directory is append-only: use a new
name for the next batch. check verifies the frozen copy; --check-sources also
detects changes, additions and removals in the selected working-tree inputs.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = 'configs/v3/baseline_inputs.json'
FIELDS = ('source_id', 'version', 'origin_type', 'author_status', 'review_status', 'permitted_use')
SKIP_DIRS = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
BLOCKED_DIRS = {'.git', '.codex', '.agents', '.aws', 'node_modules', '.runtime'}
CONTROL_FILES = {'input_spec.snapshot.json', 'gap_ledger.snapshot.json',
                 'source_manifest.jsonl', 'readiness.json', 'inherited_gaps.md'}


def local_path(base, relative):
    """Reject ambiguous paths, traversal and links before reading or writing."""
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Expected a POSIX relative path: ' + str(relative))
    parts = PurePosixPath(relative).parts
    if relative.startswith('/') or any(p in {'.', '..'} for p in relative.split('/')):
        raise ValueError('Unsafe relative path: ' + relative)
    base = base.resolve()
    target = base.joinpath(*parts)
    for ancestor in [target, *target.parents]:
        if ancestor == base:
            break
        if ancestor.is_symlink() or getattr(ancestor, 'is_junction', lambda: False)():
            raise ValueError('Links are not snapshot inputs: ' + relative)
    if not target.resolve().is_relative_to(base):
        raise ValueError('Path escapes root: ' + relative)
    return target


def permitted_path(relative):
    p = PurePosixPath(relative)
    if any(part in BLOCKED_DIRS or part.startswith(('.venv', '.conda')) for part in p.parts):
        raise ValueError('Runtime/private directory is excluded: ' + relative)
    name = p.name.lower()
    if (name == '.env' or name.startswith('.env.') or name.endswith(('.local.yaml', '.local.yml', '.local.env', '.pem', '.key'))
            or re.search(r'\.(sqlite3?|db)(-|$)', name)):
        raise ValueError('Local credentials/databases are excluded: ' + relative)


def digest(file):
    h = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(file):
    return json.loads(file.read_text(encoding='utf-8-sig'))


def write_json(file, value):
    with file.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def collect(root, spec):
    selected = {}
    group_ids = set()
    if spec.get('schema_version') != 1 or not spec.get('groups') or not spec.get('scope'):
        raise ValueError('Expected schema_version=1, scope and nonempty groups')
    for group in spec['groups']:
        gid = group['id']
        if not isinstance(gid, str) or not gid or gid in group_ids:
            raise ValueError('Empty/duplicate group ID: ' + str(gid))
        group_ids.add(gid)
        if any(not isinstance(group.get(k), str) or not group[k].strip() for k in FIELDS):
            raise ValueError('Missing source/review/use metadata: ' + gid)
        if group['permitted_use'] != 'internal_preparation_only':
            raise ValueError('This tool only creates internal preparation batches')
        if not group.get('paths'):
            raise ValueError('Empty input group: ' + gid)
        for relative in group['paths']:
            source = local_path(root, relative)
            permitted_path(relative)
            if not source.exists():
                raise ValueError('Missing input: ' + relative)
            files = []
            if source.is_dir():
                for folder, dirs, names in os.walk(source, followlinks=False):
                    dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                    for name in dirs + sorted(names):
                        rel = (Path(folder) / name).relative_to(root).as_posix()
                        local_path(root, rel)
                        permitted_path(rel)
                    files.extend(Path(folder) / name for name in sorted(names))
            else:
                files = [source]
            if not files:
                raise ValueError('Input path contains no files: ' + relative)
            for file in files:
                rel = file.relative_to(root).as_posix()
                if not file.is_file():
                    raise ValueError('Not a regular file: ' + rel)
                if rel in selected:
                    raise ValueError('Input selected more than once: ' + rel)
                selected[rel] = group
    return dict(sorted(selected.items()))


def output_path(root, relative):
    out = local_path(root, relative)
    if not relative.startswith('datasets/v3.0.0/') or len(PurePosixPath(relative).parts) != 3:
        raise ValueError('Output must be datasets/v3.0.0/<new-batch-name>')
    return out


def freeze(root, spec_path, output):
    root = root.resolve()
    out = output_path(root, output)
    if out.exists():
        raise ValueError('Output already exists; use a new batch name: ' + output)
    spec_file = local_path(root, spec_path)
    spec_bytes = spec_file.read_bytes()
    spec = json.loads(spec_bytes)
    selected = collect(root, spec)
    if not isinstance(spec.get('limitations'), list) or not spec['limitations'] or not spec.get('software_baseline'):
        raise ValueError('Declare limitations and software baseline before freezing')
    if any(local_path(root, p).is_relative_to(out) for p in selected):
        raise ValueError('Output must not be an input')
    ledger_file = local_path(root, spec['gap_ledger'])
    ledger_bytes = ledger_file.read_bytes()
    ledger = json.loads(ledger_bytes)
    gaps = []
    for gap in ledger['gaps']:
        if gap['status'] not in {'open', 'deferred', 'partial'}:
            continue
        owners = spec['gap_owners'].get(gap['id'])
        if not owners or not gap.get('stage') or not gap.get('acceptance'):
            raise ValueError('Unassigned gap: ' + gap['id'])
        gaps.append({**gap, 'owners': owners})
    # Validate everything above before allocating a new output. On an I/O
    # failure retain .incomplete for diagnosis, never overwrite/reuse the batch.
    out.mkdir(parents=True)
    marker = out / '.incomplete'
    marker.write_text('Freeze in progress; no usable baseline until check passes.\n', encoding='utf-8')
    (out / 'input_spec.snapshot.json').write_bytes(spec_bytes)
    (out / 'gap_ledger.snapshot.json').write_bytes(ledger_bytes)
    rows = []
    for relative, group in selected.items():
        source = local_path(root, relative)
        before = digest(source)
        snapshot = 'snapshot/' + relative
        dest = local_path(out, snapshot)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        if digest(dest) != before or digest(source) != before:
            raise ValueError('Input changed during freeze: ' + relative)
        rows.append(dict(asset_id='sha256-path-' + hashlib.sha256(relative.encode('utf-8')).hexdigest(),
                         path=relative, snapshot_path=snapshot, sha256=before,
                         bytes=dest.stat().st_size, group_id=group['id'],
                         **{key: group[key] for key in FIELDS}))
    with (out / 'source_manifest.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    write_json(out / 'readiness.json', dict(schema_version=1, status='preparation_batch_frozen',
               asset_count=len(rows), s0_accepted=False, can_prepare_s1=True,
               can_run_formal_evaluation=False, release_ready=False, new_api_calls=0,
               limitations=spec['limitations'], remaining_gaps=gaps))
    lines = ['# 本批继承缺口', '', '只冻结内部准备输入；责任人为角色，未表示已安排实际复核人员。', '',
             '| ID | 影响阶段 | 责任角色 | 状态 | 验收/下一步 |', '|---|---|---|---|---|']
    for gap in gaps:
        cells = [gap['id'], gap['stage'], ', '.join(gap['owners']), gap['status'], gap['acceptance']]
        lines.append('| ' + ' | '.join(str(c).replace('|', '/').replace('\n', ' ') for c in cells) + ' |')
    (out / 'inherited_gaps.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    write_json(out / 'baseline_snapshot.json', dict(schema_version=1, complete=True,
               created_at=datetime.now(timezone.utc).isoformat(), scope=spec['scope'],
               software_baseline=spec['software_baseline'], asset_count=len(rows),
               total_bytes=sum(row['bytes'] for row in rows),
               groups=dict(sorted(Counter(row['group_id'] for row in rows).items())),
               capture_environment=dict(python=sys.version, platform=platform.platform()),
               artifacts={name: digest(out / name) for name in sorted(CONTROL_FILES)}))
    marker.unlink()
    return check(root, output, check_sources=True)


def check(root, output, check_sources=False):
    root = root.resolve()
    out = output_path(root, output)
    errors = []
    try:
        if (out / '.incomplete').exists():
            raise ValueError('Incomplete freeze: ' + output)
        baseline = read_json(local_path(out, 'baseline_snapshot.json'))
        if baseline.get('schema_version') != 1 or baseline.get('complete') is not True:
            raise ValueError('Unsupported or incomplete baseline')
        if set(baseline['artifacts']) != CONTROL_FILES:
            raise ValueError('Missing/unexpected control files')
        for name, expected in baseline['artifacts'].items():
            if digest(local_path(out, name)) != expected:
                raise ValueError('Control file hash mismatch: ' + name)
        spec = read_json(out / 'input_spec.snapshot.json')
        rows = [json.loads(line) for line in (out / 'source_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
        paths = set()
        ids = set()
        for row in rows:
            rel = row['path']
            local_path(out / 'snapshot', rel)
            permitted_path(rel)
            if rel in paths or row['asset_id'] in ids:
                raise ValueError('Duplicate manifest asset: ' + rel)
            paths.add(rel)
            ids.add(row['asset_id'])
            expected_id = 'sha256-path-' + hashlib.sha256(rel.encode('utf-8')).hexdigest()
            if (row['asset_id'] != expected_id or row['snapshot_path'] != 'snapshot/' + rel
                    or not re.fullmatch('[0-9a-f]{64}', row['sha256'])
                    or any(not row.get(k) for k in FIELDS)
                    or row['permitted_use'] != 'internal_preparation_only'):
                raise ValueError('Invalid manifest contract: ' + rel)
            frozen = local_path(out, row['snapshot_path'])
            if digest(frozen) != row['sha256'] or frozen.stat().st_size != row['bytes']:
                errors.append('Snapshot hash/size mismatch: ' + rel)
            if check_sources:
                current = local_path(root, rel)
                if not current.is_file() or digest(current) != row['sha256']:
                    errors.append('Working-tree input changed/missing: ' + rel)
        actual = {p.relative_to(out / 'snapshot').as_posix() for p in (out / 'snapshot').rglob('*') if p.is_file()}
        if actual != paths:
            errors.append('Snapshot file set differs from manifest')
        if (not rows or len(rows) != baseline['asset_count']
                or sum(row['bytes'] for row in rows) != baseline['total_bytes']
                or dict(Counter(row['group_id'] for row in rows)) != baseline['groups']):
            errors.append('Manifest count/size/group mismatch')
        if check_sources and set(collect(root, spec)) != paths:
            errors.append('Working-tree input set changed')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return dict(status='failed' if errors else 'passed', output=output,
                check_sources=check_sources, errors=errors,
                asset_count=baseline.get('asset_count') if 'baseline' in locals() else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'check'])
    parser.add_argument('--spec', default=DEFAULT_SPEC, help='Repository-relative input specification')
    parser.add_argument('--output', required=True, help='datasets/v3.0.0/<new-batch-name>')
    parser.add_argument('--check-sources', action='store_true')
    args = parser.parse_args()
    try:
        result = freeze(ROOT, args.spec, args.output) if args.action == 'freeze' else check(ROOT, args.output, args.check_sources)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = dict(status='failed', errors=[str(exc)])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
