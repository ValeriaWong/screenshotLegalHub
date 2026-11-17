"""Snapshot paused V2 authoring state without launching, reviewing or rendering."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'datasets/v2.0.0/library_expansion_20261106'
FACT = ROOT / 'datasets/v2.0.0/fact_constrained_20261106'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshot():
    assert (LIB / 'STOP').exists(), 'Set STOP and confirm no campaign processes before snapshotting'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = LIB / 'pause.checkpoints' / stamp
    out.mkdir(parents=True, exist_ok=False)
    result = {'paused_at_utc': datetime.now(timezone.utc).isoformat(),
              'user_request': '暂停并做好断点续传', 'independent_review_enabled': False,
              'execution_mode': 'generation_only', 'tracks': {}}
    hashes = {}
    for track in (LIB, FACT):
        jobs = []
        for assignment in sorted((track / 'jobs').glob('*/assignment.json')):
            records = read(assignment)['records']
            items = []
            for row in records:
                ident = row.get('document_id') or row['id']
                folder = track / 'authoring' / assignment.parent.name / ident
                if (folder / 'decision.json').exists():
                    phase = read(folder / 'decision.json').get('decision', 'unknown')
                elif all((folder / n).exists() for n in (
                        'source.reading.json', 'direct.draft.json', 'direct.revised.json',
                        'claims.json', 'codex.review.json')):
                    phase = 'authored_pending_pipeline'
                else:
                    phase = 'partial' if folder.exists() else 'not_started'
                items.append({'id': ident, 'phase': phase, 'path': folder.relative_to(ROOT).as_posix()})
            jobs.append({'job': assignment.parent.name, 'assigned': len(records),
                         'completion_marker': (assignment.parent / 'last_message.txt').exists(),
                         'runtime_exists': (assignment.parent / 'runtime.json').exists(), 'items': items})
        # Pin all author inputs, model logs and current materialized artifacts. Copy
        # mutable JSON/checkpoint inputs; large images/logs remain in place and hashed.
        paths = list(track.glob('*.json')) + [p for p in track.glob('*.md')]
        for group in ('jobs', 'peer_jobs', 'authoring', 'cases', 'peer_reviews'):
            for p in (track / group).rglob('*'):
                if p.is_file() and not any(x in p.parts for x in (
                        'render.versions', 'peer.versions', 'recovery.inputs', '__pycache__')):
                    paths.append(p)
        for p in sorted(set(paths)):
            relative = p.relative_to(ROOT)
            hashes[relative.as_posix()] = sha(p)
            if p.suffix in ('.json', '.md') or p.name in ('last_message.txt', 'prompt.txt'):
                dest = out / 'files' / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dest)
                assert sha(dest) == hashes[relative.as_posix()]
        state_path = track / ('authoring_status.json' if track == LIB else 'state.json')
        state = read(state_path)
        result['tracks'][track.name] = {
            'jobs': jobs, 'assigned': sum(j['assigned'] for j in jobs),
            'author_jobs_with_completion_marker': sum(j['completion_marker'] for j in jobs),
            'author_jobs_without_completion_marker': [j['job'] for j in jobs if not j['completion_marker']],
            'author_phase_counts': dict(Counter(i['phase'] for j in jobs for i in j['items'])),
            'materialized_records': len(state['records']),
            'reported_summary': read(track / ('expansion_summary.json' if track == LIB else 'summary.json')),
        }
    assignments = [r['document_id'] for p in (LIB / 'jobs').glob('*/assignment.json') for r in read(p)['records']]
    assert len(assignments) == len(set(assignments)), 'Duplicate source assignment'
    queue = read(LIB / 'queue.json')
    remaining = [r['document_id'] for k in ('chinese', 'english') for r in queue[k]
                 if r['document_id'] not in set(assignments)]
    result['remaining_unassigned_source_ids'] = remaining
    result['remaining_unassigned'] = len(remaining)
    result['source_assignments_disjoint'] = True
    save(out / 'manifest.json', {'sha256': hashes, 'scope': 'Current authoring inputs, jobs, review backlog and cases; runtime browser profiles excluded'})
    save(out / 'checkpoint.json', result)
    # Re-read all live files to detect a writer racing this supposedly paused snapshot.
    assert all(sha(ROOT / p) == digest for p, digest in hashes.items()), 'Files changed during pause snapshot'
    save(LIB / 'pause.checkpoint.latest.json', {
        'path': (out / 'checkpoint.json').relative_to(ROOT).as_posix(),
        'sha256': sha(out / 'checkpoint.json'), 'manifest_sha256': sha(out / 'manifest.json'),
        'files_pinned': len(hashes), 'snapshot_stable': True, 'paused_at_utc': result['paused_at_utc']})
    print(json.dumps({'checkpoint': out.relative_to(ROOT).as_posix(), 'files_pinned': len(hashes),
                      'remaining_unassigned': len(remaining), 'tracks': {
                          k: {a: b for a, b in v.items() if a not in ('jobs', 'reported_summary')}
                          for k, v in result['tracks'].items()}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    snapshot()
