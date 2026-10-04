"""Durable human annotations over source-bound review content.

This module neither extracts evidence nor changes model output. Content is supplied
by review_content; SQLite stores separate annotations and an append-only audit.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import threading


DEFAULT_DB = Path(__file__).resolve().parents[1] / 'blocks/reviewer/artifacts/reviews.sqlite3'
STATUSES = ('pending', 'confirmed', 'amended', 'rejected', 'deferred', 'stale')
KINDS = ('legal_event', 'contract_term', 'meaning', 'fact', 'qa_claim', 'transcription_gap')
DECISIONS = ('confirmed', 'amended', 'rejected', 'deferred', 'reopen')


class ReviewValidation(ValueError):
    """The request or supplied review content is invalid (HTTP 400)."""


class ReviewConflict(ValueError):
    """The submitted revision no longer matches (HTTP 409)."""


class ReviewNotFound(LookupError):
    """The requested item does not belong to the requested case (HTTP 404)."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class ReviewStore:
    def __init__(self, registry, chatwork=None, db_path=None, item_builder=None):
        self.registry = registry
        self.chatwork = chatwork
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB
        self.item_builder = item_builder
        self.lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ReviewValidation('Unsupported review database schema')
            db.execute('''CREATE TABLE IF NOT EXISTS review_items (
                case_id TEXT NOT NULL, item_id TEXT NOT NULL, body TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL, content_digest TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','confirmed','amended','rejected','deferred','stale')),
                revision INTEGER NOT NULL, edited_text TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL, available INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(case_id,item_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS review_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
                item_id TEXT NOT NULL, revision INTEGER NOT NULL, event TEXT NOT NULL,
                occurred_at TEXT NOT NULL, reviewer TEXT NOT NULL, payload TEXT NOT NULL,
                FOREIGN KEY(case_id,item_id) REFERENCES review_items(case_id,item_id),
                UNIQUE(case_id,item_id,revision))''')
            db.execute('CREATE INDEX IF NOT EXISTS review_queue ON review_items(case_id,status,available)')
            db.execute('''CREATE TRIGGER IF NOT EXISTS review_events_no_update
                BEFORE UPDATE ON review_events BEGIN SELECT RAISE(ABORT,'Audit events are append-only'); END''')
            db.execute('''CREATE TRIGGER IF NOT EXISTS review_events_no_delete
                BEFORE DELETE ON review_events BEGIN SELECT RAISE(ABORT,'Audit events are append-only'); END''')
            db.execute('PRAGMA user_version=1')

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self):
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def _cases(self, case_id=None):
        # The real registry can filter before reading per-case vision metadata.
        # Retain the older interface for lightweight integrations and fixtures.
        provider = getattr(self.registry, 'review_cases', None)
        cases = provider(case_id) if callable(provider) else self.registry.list()
        if case_id is not None:
            selected = [case for case in cases if case['case_id'] == case_id]
            if not selected:
                raise ReviewNotFound('Unknown review case')
            return selected
        return [case for case in cases if case.get('status') == 'analyzed']

    @staticmethod
    def _review(row):
        return {key: row[key] for key in ('status', 'revision', 'edited_text', 'note',
                'reviewer', 'updated_at', 'source_fingerprint')} | {'available': bool(row['available'])}

    def _item(self, row, db=None, history=False):
        item = json.loads(row['body'])
        item['review'] = self._review(row)
        if history:
            item['history'] = [dict(event_id=e['event_id'], revision=e['revision'],
                event=e['event'], occurred_at=e['occurred_at'], reviewer=e['reviewer'],
                **json.loads(e['payload'])) for e in db.execute(
                    'SELECT * FROM review_events WHERE case_id=? AND item_id=? ORDER BY event_id',
                    (row['case_id'], row['item_id']))]
        return item

    def _event(self, db, row, event, before=None):
        db.execute('''INSERT INTO review_events
            (case_id,item_id,revision,event,occurred_at,reviewer,payload) VALUES (?,?,?,?,?,?,?)''',
            (row['case_id'], row['item_id'], row['revision'], event, row['updated_at'],
             row['reviewer'], _json({'before': before, 'after': self._item(row)})))

    def _refresh(self, cases):
        # The builder alone owns evidence/claim interpretation. All validation here
        # is structural or protects case boundaries.
        builder = self.item_builder
        if builder is None:
            from legalhub.review_content import build_review_items
            builder = build_review_items
        content = {}
        for case in cases:
            case_id = case['case_id']
            workspace = self.registry.get(case_id)
            chats = self.chatwork.history(case_id) if self.chatwork is not None else None
            items = builder(workspace, chat_rows=chats)
            seen = set()
            for item in items:
                if not isinstance(item, dict) or item.get('case_id') != case_id:
                    raise ReviewValidation('Review content crosses case boundaries')
                if not isinstance(item.get('id'), str) or not item['id'] or item['id'] in seen:
                    raise ReviewValidation('Review item IDs must be unique nonempty strings')
                if item.get('kind') not in KINDS:
                    raise ReviewValidation('Unknown review item kind')
                if not isinstance(item.get('source_fingerprint'), str) or not item['source_fingerprint']:
                    raise ReviewValidation('Review content requires a source fingerprint')
                seen.add(item['id'])
            content[case_id] = copy.deepcopy(items)
        with self._transaction() as db:
            for case_id, items in content.items():
                previous = {row['item_id']: row for row in db.execute(
                    'SELECT * FROM review_items WHERE case_id=?', (case_id,))}
                for item in items:
                    # Never accept annotations embedded in the source provider.
                    item.pop('review', None)
                    item.pop('history', None)
                    body = _json(item)
                    digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
                    old = previous.pop(item['id'], None)
                    stamp = _now()
                    if old is None:
                        db.execute('''INSERT INTO review_items
                            (case_id,item_id,body,source_fingerprint,content_digest,status,revision,updated_at)
                            VALUES (?,?,?,?,?,'pending',0,?)''',
                            (case_id, item['id'], body, item['source_fingerprint'], digest, stamp))
                        event, before = 'registered', None
                    elif (old['source_fingerprint'] != item['source_fingerprint'] or
                          old['content_digest'] != digest or not old['available']):
                        before = self._item(old)
                        db.execute('''UPDATE review_items SET body=?, source_fingerprint=?,
                            content_digest=?,status='stale',revision=revision+1,updated_at=?,
                            reviewer='system',available=1 WHERE case_id=? AND item_id=?''',
                            (body, item['source_fingerprint'], digest, stamp, case_id, item['id']))
                        event = 'source_changed'
                    else:
                        continue
                    row = db.execute('SELECT * FROM review_items WHERE case_id=? AND item_id=?',
                        (case_id, item['id'])).fetchone()
                    self._event(db, row, event, before)
                for old in previous.values():
                    if not old['available']:
                        continue
                    db.execute('''UPDATE review_items SET status='stale',revision=revision+1,
                        available=0,updated_at=?,reviewer='system' WHERE case_id=? AND item_id=?''',
                        (_now(), case_id, old['item_id']))
                    row = db.execute('SELECT * FROM review_items WHERE case_id=? AND item_id=?',
                        (case_id, old['item_id'])).fetchone()
                    self._event(db, row, 'source_removed', self._item(old))

    def queue(self, case_id=None, status='pending', kind=None, offset=0, limit=50):
        if status not in (*STATUSES, 'all'):
            raise ReviewValidation('Unknown review status')
        if kind is not None and kind not in KINDS:
            raise ReviewValidation('Unknown review kind')
        if (type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200):
            raise ReviewValidation('offset must be nonnegative; limit must be between 1 and 200')
        with self.lock:
            cases = self._cases(case_id)
            self._refresh(cases)
            counts = dict.fromkeys(STATUSES, 0)
            rows = []
            with self._connection() as db:
                if cases:
                    ids = [case['case_id'] for case in cases]
                    rows = db.execute('SELECT * FROM review_items WHERE case_id IN (' +
                        ','.join('?' for _ in ids) + ')', ids).fetchall()
            items = [self._item(row) for row in rows]
            if kind:
                items = [item for item in items if item['kind'] == kind]
            for item in items:
                counts[item['review']['status']] += 1
            counts['total'] = len(items)
            if status != 'all':
                items = [item for item in items if item['review']['status'] == status]
            rank = {'high': 0, 'medium': 1, 'low': 2}
            items.sort(key=lambda item: (rank.get(item.get('priority'), 3), item['case_id'], item['id']))
            return {'items': items[offset:offset + limit], 'total': len(items),
                    'counts': counts, 'cases': cases, 'offset': offset, 'limit': limit}

    get_queue = queue

    def get_item(self, case_id, item_id):
        with self.lock:
            self._refresh(self._cases(case_id))
            with self._connection() as db:
                row = db.execute('SELECT * FROM review_items WHERE case_id=? AND item_id=?',
                    (case_id, item_id)).fetchone()
                if row is None:
                    raise ReviewNotFound('Unknown review item in this case')
                return self._item(row, db, history=True)

    def save(self, case_id, item_id, decision, edited_text='', note='', expected_revision=None, reviewer='user'):
        if decision not in DECISIONS:
            raise ReviewValidation('Unknown review decision')
        if type(expected_revision) is not int or expected_revision < 0:
            raise ReviewValidation('expected_revision is required and must be a nonnegative integer')
        if not isinstance(edited_text, str) or len(edited_text) > 50000:
            raise ReviewValidation('edited_text must be a string of at most 50000 characters')
        if not isinstance(note, str) or len(note) > 12000:
            raise ReviewValidation('note must be a string of at most 12000 characters')
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
            raise ReviewValidation('reviewer must be a nonempty string of at most 120 characters')
        if decision == 'amended' and not edited_text.strip():
            raise ReviewValidation('An amended decision requires nonempty edited_text')
        status = 'pending' if decision == 'reopen' else decision
        # Non-amendment decisions clear obsolete replacement content; old content
        # remains preserved in audit snapshots.
        edited_text = edited_text if decision == 'amended' else ''
        with self.lock:
            self._refresh(self._cases(case_id))
            with self._transaction() as db:
                row = db.execute('SELECT * FROM review_items WHERE case_id=? AND item_id=?',
                    (case_id, item_id)).fetchone()
                if row is None:
                    raise ReviewNotFound('Unknown review item in this case')
                if row['revision'] != expected_revision:
                    raise ReviewConflict('Review changed; reload the item before saving')
                if not row['available']:
                    raise ReviewConflict('The source item was removed and cannot be reviewed')
                if (row['status'], row['edited_text'], row['note'], row['reviewer']) == (status, edited_text, note, reviewer):
                    return self._item(row, db, history=True)
                before = self._item(row)
                db.execute('''UPDATE review_items SET status=?,revision=revision+1,
                    edited_text=?,note=?,reviewer=?,updated_at=? WHERE case_id=? AND item_id=?''',
                    (status, edited_text, note, reviewer, _now(), case_id, item_id))
                row = db.execute('SELECT * FROM review_items WHERE case_id=? AND item_id=?',
                    (case_id, item_id)).fetchone()
                self._event(db, row, decision, before)
                return self._item(row, db, history=True)

    def export_review(self, case_id):
        with self.lock:
            self._refresh(self._cases(case_id))
            with self._connection() as db:
                items = [self._item(row, db, history=True) for row in db.execute(
                    'SELECT * FROM review_items WHERE case_id=? ORDER BY item_id', (case_id,))]
            for item in items:
                status = item['review']['status']
                item['reviewed_text'] = (item['review']['edited_text'] if status == 'amended' else
                    item.get('proposed_text') if status == 'confirmed' else None)
                item['reviewed_text_origin'] = ('user_amendment' if status == 'amended' else
                    'user_confirmed_proposal' if status == 'confirmed' else None)
            return {'case_id': case_id, 'items': items, 'exported_at': _now(),
                    'annotation_policy': 'Human annotations are separate from original evidence and model output.'}
