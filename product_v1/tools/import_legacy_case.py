"""Validate a legacy export, then atomically import into an isolated new case."""
import argparse
import asyncio
import hashlib
import json
from io import BytesIO
from PIL import Image
import re
import shutil
from pathlib import Path
from uuid import uuid4
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.application.services.workspace import Workspace
from screenshotlegal.domain.common.models import CaseCreate, CaseRecord, digest, now
from screenshotlegal.domain.evidence.models import EvidenceItem
from screenshotlegal.plugins.perception.adapters import normalize


def prepare(workspace, corpus, legacy_root, title):
    """Read and validate all bytes/references before writing any case or upload."""
    request = CaseCreate(title=title)
    case = CaseRecord(id=str(uuid4()), title=request.title,
                      description='Imported corpus; transcriptions and identities remain unreviewed', created_at=now())
    legacy_root = Path(legacy_root).resolve(strict=True)
    if not legacy_root.is_dir():
        raise ValueError('Legacy root must be a directory')
    legacy_cases = {row.get('case_id') for row in corpus['images']+corpus['records'] if row.get('case_id')}
    if len(legacy_cases) > 1:
        raise ValueError('Import one legacy case at a time; mixed case IDs are unsafe')
    images = {}; uploads = {}; messages = []; refs = []; by_legacy = {}; events = []
    total = 0
    for image in corpus['images']:
        image_id = image['image_id']
        if not image_id or image_id in images:
            raise ValueError('Duplicate or empty legacy image ID')
        relative = Path(image['file'])
        source = (legacy_root / relative).resolve(strict=True)
        if relative.is_absolute() or not source.is_relative_to(legacy_root):
            raise ValueError('Legacy file escapes explicit legacy root')
        content = source.read_bytes(); total += len(content)
        if not content or len(content) > workspace.settings.max_upload_bytes:
            raise ValueError('Legacy image exceeds upload limit or is empty')
        expected = image.get('sha256', '')
        actual = hashlib.sha256(content).hexdigest()
        if not re.fullmatch(r'[0-9a-fA-F]{64}', expected) or expected.lower() != actual:
            raise ValueError('Legacy original SHA256 missing or mismatched')
        # Historical corpora may have .jpg names containing WebP bytes. Trust decoded format, never rename/re-encode originals.
        with Image.open(BytesIO(content)) as decoded:
            mime = Image.MIME.get(decoded.format)
        if not mime or not mime.startswith('image/'):
            raise ValueError('Legacy image has no supported decoded MIME')
        prepared = workspace.storage.registry.prepare(source.name, mime, content)
        if prepared.kind != 'image' or prepared.mime not in workspace.settings.allowed_mime_types:
            raise ValueError('Legacy images must be supported image files')
        item = EvidenceItem(id='ev.'+actual[:24], case_id=case.id, filename=source.name[:200],
                            mime_type=prepared.mime, sha256=actual,
                            storage_path=case.id+'/'+actual+'.'+prepared.extension, size_bytes=len(content),
                            width=prepared.width, height=prepared.height, kind=prepared.kind)
        images[image_id] = item
        uploads.setdefault(item.id, (item, content))
    if not images or len(images) > workspace.settings.max_batch_files or total > workspace.settings.max_batch_bytes:
        raise ValueError('Legacy image batch is empty or exceeds configured limits')
    rows = corpus['records']; row_ids = [r['id'] for r in rows]
    if any(not value for value in row_ids) or len(set(row_ids)) != len(row_ids):
        raise ValueError('Duplicate or empty legacy record ID')
    if any(r['kind'] in {'message', 'event'} and not isinstance(r.get('text'), str) for r in rows):
        raise ValueError('Legacy message/event text must be a string')
    if any(r['kind'] not in {'image', 'message', 'event', 'case_law', 'statute'} for r in rows):
        raise ValueError('Unsupported legacy record kind')
    for row in rows:
        if row['kind'] != 'message':
            continue
        if not row.get('source_refs'):
            raise ValueError('Legacy message lacks source refs')
        by_legacy[row['id']] = []
        for index, ref in enumerate(row['source_refs']):
            item = images.get(ref.get('image_id'))
            if item is None:
                raise ValueError('Legacy message image is unresolved')
            if ref.get('message_id') not in (None, row['id']):
                raise ValueError('Legacy message reference has a different ID')
            if ref.get('quote') and ref['quote'] not in row['text']:
                raise ValueError('Legacy quote differs from message text')
            page = ref.get('evidence_page')
            if page is not None and (isinstance(page, bool) or not isinstance(page, int) or page < 1):
                raise ValueError('Invalid legacy evidence page')
            result = normalize(item.model_dump(), [dict(text=row['text'], speaker=row.get('person') or 'unknown',
                timestamp=row.get('timestamp_normalized'), event_type=row.get('event_type') or 'other',
                bbox=ref.get('bbox'), coordinate_space=ref.get('coordinate_space', 'pixels'), page=page)])
            mid = 'msg.'+digest([row['id'], index, ref])[:24]; rid = 'ref.'+mid
            message = result.messages[0].model_copy(update={'id':mid, 'source_refs':[rid]}).model_dump()
            source_ref = result.source_refs[0].model_copy(update={'id':rid, 'message_id':mid}).model_dump()
            messages.append(message); refs.append(source_ref)
            by_legacy[row['id']].append((ref, source_ref))
    if not messages:
        raise ValueError('Legacy corpus contains no grounded messages')
    for row in rows:
        if row['kind'] != 'event':
            continue
        selected = []
        for ref in row.get('source_refs', []):
            matches = by_legacy.get(ref.get('message_id'), [])
            if ref.get('image_id') is not None:
                matches = [(old, new) for old, new in matches if old['image_id'] == ref['image_id']]
            if ref.get('bbox') is not None:
                matches = [(old, new) for old, new in matches if old.get('bbox') == ref['bbox']]
            if ref.get('evidence_page') is not None:
                matches = [(old, new) for old, new in matches if old.get('evidence_page') == ref['evidence_page']]
            if not matches or any(ref.get('quote') and ref['quote'] not in new['quote'] for _, new in matches):
                raise ValueError('Legacy event source message/location is unresolved')
            selected.extend(new['id'] for _, new in matches)
        if not selected:
            raise ValueError('Legacy event lacks grounded sources')
        events.append(dict(id='legacy.'+row['id'], kind='event', title=row['text'],
            source_refs=list(dict.fromkeys(selected)), review_status='unreviewed',
            details=dict(legacy_id=row['id'],event_type=row.get('event_type','other'),timestamp=row.get('timestamp_normalized'))))
    records = [('cases', case.id, case.model_dump(), case.id, '', True)]
    for table, values in [('evidence_items',[v[0].model_dump() for v in uploads.values()]),
                          ('messages',messages),('source_refs',refs),('events',events)]:
        records.extend((table,case.id+':'+v['id'],v,case.id,'',True) for v in values)
    for evidence_id in uploads:
        selection = dict(perception_id='legacy.'+case.id,message_ids=[m['id'] for m in messages if m['evidence_id']==evidence_id])
        records.append(('active_perceptions',case.id+':'+evidence_id,selection,case.id,'',False))
    return case, uploads, messages, records


async def import_case(workspace, corpus, legacy_root, title):
    case, uploads, messages, records = prepare(workspace, corpus, legacy_root, title)
    directory = workspace.storage.path(case.id)
    if directory.exists():
        raise ValueError('New import directory already exists')
    try:
        for item, content in uploads.values():
            workspace.storage.save(case.id, item.filename, item.mime_type, content)
        with workspace.repo.engine.begin() as connection:
            workspace.repo.batch(records, connection=connection)
            workspace.retriever.index(case.id, messages, connection=connection)
    except BaseException:
        # Only this newly allocated UUID directory is removed; originals and existing cases are untouched.
        if directory.exists():
            if directory.resolve().parent != workspace.storage.root or directory.is_symlink():
                raise RuntimeError('Unsafe import cleanup path')
            shutil.rmtree(directory)
        raise
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', type=Path)
    parser.add_argument('--legacy-root', required=True, type=Path)
    parser.add_argument('--title', default='Imported legacy case')
    args = parser.parse_args()
    settings = Settings(); workspace = Workspace(settings, Repository(settings.database_url))
    try:
        case = asyncio.run(import_case(workspace, json.loads(args.corpus.read_text(encoding='utf-8')), args.legacy_root, args.title))
        print(case.model_dump_json())
    finally:
        workspace.repo.engine.dispose()


if __name__ == '__main__': main()
