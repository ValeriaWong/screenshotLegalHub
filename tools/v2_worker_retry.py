"""Bounded retries for dead authors with explicit transient failures and no outputs."""
import json
import shutil
import time
from pathlib import Path

from tools.v2_library_expansion import read, save, sha

MAX_RETRIES = 3
BACKOFF_SECONDS = (30, 60, 120)


def terminal_failure(job):
    path = job / 'events.jsonl'
    if not path.exists():
        return None
    # Ignore a potentially truncated first line of this bounded tail.
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 65536))
        lines = stream.read().decode('utf-8', errors='replace').splitlines()
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'turn.completed':
            return None
        if event.get('type') == 'turn.failed':
            error = event.get('error', {})
            return error.get('message', '') if isinstance(error, dict) else str(error)
    return None


def transient(message):
    text = message.lower()
    # Invalid requests, authentication, validation and authoring errors are not
    # retried by this transport recovery path.
    if any(x in text for x in ('invalid_request_error', 'bad request', 'unauthorized', 'authentication')):
        return False
    return any(x in text for x in ('502', '503', '504', 'workspace routing discovery failed',
                                  'stream disconnected', 'connection reset', 'timed out'))


def recover_dead_authors(campaigns, active, finished, now_epoch=None):
    now_epoch = time.time() if now_epoch is None else now_epoch
    active = set(active)
    result = {'queued': [], 'waiting': [], 'refused': []}
    for campaign in campaigns:
        for assignment in sorted((campaign / 'jobs').glob('*/assignment.json')):
            job = assignment.parent
            if job in active or finished(job) or not (job / 'runtime.json').exists():
                continue
            message = terminal_failure(job)
            if not message or not transient(message):
                continue
            output = campaign / 'authoring' / job.name
            # Never overwrite partial or completed authored content automatically.
            if output.exists() and any(p.is_file() for p in output.rglob('*')):
                result['refused'].append({'job': str(job), 'reason': 'partial_author_outputs_require_reconciliation'})
                continue
            state_path = job / 'retry.state.json'
            state = read(state_path) if state_path.exists() else {'attempts': 0}
            archived_counts = [int(p.name.rsplit('_', 1)[-1]) for p in (job / 'attempts').glob('transport_retry_*')
                               if p.is_dir() and p.name.rsplit('_', 1)[-1].isdigit()]
            count = max([state['attempts'], *archived_counts])
            if count >= MAX_RETRIES:
                result['refused'].append({'job': str(job), 'reason': 'retry_limit_reached'})
                continue
            ready = (job / 'events.jsonl').stat().st_mtime + BACKOFF_SECONDS[count]
            if now_epoch < ready:
                result['waiting'].append({'job': str(job), 'ready_at_epoch': ready})
                continue
            archive = job / 'attempts' / f'transport_retry_{count + 1:03d}'
            archive.mkdir(parents=True, exist_ok=False)
            hashes = {}
            for p in sorted(job.iterdir()):
                if p.is_file():
                    shutil.copyfile(p, archive / p.name)
                    hashes[p.name] = sha(p)
                    assert sha(archive / p.name) == hashes[p.name]
            auto = campaign / 'automation.json'
            if auto.exists():
                shutil.copyfile(auto, archive / 'campaign.automation.before.json')
            save(archive / 'manifest.json', {'sha256': hashes, 'terminal_failure': message,
                                           'author_outputs_absent': True, 'retry_number': count + 1})
            # The archived attempt must exist before making the assignment runnable.
            for name in ('runtime.json', 'events.jsonl', 'stderr.log', 'last_message.txt'):
                p = job / name
                if p.exists():
                    assert sha(p) == hashes[name]
                    p.unlink()
            save(state_path, {'attempts': count + 1, 'queued_at_epoch': now_epoch,
                              'previous_failure': message, 'archive': str(archive),
                              'maximum_retries': MAX_RETRIES})
            if auto.exists():
                progress = read(auto)
                if progress.get('phase') == 'needs_attention':
                    progress.update(phase='transport_retry_queued', previous_error=progress.get('error'))
                    for key in ('error', 'traceback'):
                        progress.pop(key, None)
                    save(auto, progress)
            result['queued'].append({'job': str(job), 'retry_number': count + 1})
    return result
