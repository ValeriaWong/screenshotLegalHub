"""Single-worker SQLite checkpoints with atomic event append and process lock."""
import json
import os
import sqlite3
from pathlib import Path
from .contracts import Run, Event, Status, HarnessError, digest, now
from .observability import log_event

class SQLiteStore:
    def __init__(self, filename=':memory:'):
        self._lock = None
        self.closed = False
        if str(filename) != ':memory:':
            p = Path(filename).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            self._lock = open(str(p) + '.lock', 'a+b')
            self._lock.seek(0, 2)
            if self._lock.tell() == 0:
                self._lock.write(b'0'); self._lock.flush()
            self._lock.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self._lock.close(); self._lock = None
                raise HarnessError('STORE_BUSY', 'one runtime worker per store') from None
        try:
            self.db = sqlite3.connect(str(filename), isolation_level=None)
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise HarnessError('STORE_VERSION_CONFLICT')
            self.db.execute('PRAGMA user_version=1')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, idem TEXT NOT NULL,
                    request_digest TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
                    UNIQUE(owner, idem));
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL, sequence INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(run_id, sequence));
                CREATE TABLE IF NOT EXISTS calls (
                    key TEXT PRIMARY KEY, run_id TEXT NOT NULL, status TEXT NOT NULL,
                    result TEXT);
            ''')
        except BaseException:
            self.close()
            raise

    def create(self, run):
        key = digest([run.request.model_dump(mode='json'), run.principal.model_dump(mode='json')])
        old = self.db.execute('SELECT request_digest, body FROM runs WHERE owner=? AND idem=?',
                              (run.principal.subject, run.request.idempotency_key)).fetchone()
        if old:
            if old[0] != key:
                raise HarnessError('IDEMPOTENCY_CONFLICT')
            return Run.model_validate_json(old[1]), False
        self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',
                        (run.run_id, run.principal.subject, run.request.idempotency_key, key, 0, run.model_dump_json()))
        return run, True

    def get(self, run_id):
        row = self.db.execute('SELECT body FROM runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise HarnessError('NOT_FOUND')
        return Run.model_validate_json(row[0])

    def save(self, run, event_type, task_id=None, **data):
        revision = run.revision
        run.updated_at = now()
        run.revision += 1
        event = Event(run_id=run.run_id, trace_id=run.trace_id, sequence=run.revision,
                      type=event_type, task_id=task_id, data=data)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            changed = self.db.execute('UPDATE runs SET revision=?,body=? WHERE id=? AND revision=?',
                                     (run.revision, run.model_dump_json(), run.run_id, revision)).rowcount
            if changed != 1:
                raise HarnessError('CHECKPOINT_CONFLICT')
            self.db.execute('INSERT INTO events VALUES(?,?,?)', (run.run_id, run.revision, event.model_dump_json()))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); run.revision = revision
            raise
        log_event(event.model_dump(mode='json'))

    def events(self, run_id, after=0):
        return [Event.model_validate_json(r[0]) for r in self.db.execute(
            'SELECT body FROM events WHERE run_id=? AND sequence>? ORDER BY sequence', (run_id, after))]

    def recover(self):
        for row in self.db.execute('SELECT body FROM runs').fetchall():
            run = Run.model_validate_json(row[0])
            if run.status == Status.RUNNING:
                run.status = Status.INTERRUPTED
                run.approvals = []
                for task in run.tasks.values():
                    if task.status == Status.RUNNING:
                        task.status = Status.PENDING
                self.save(run, 'run-interrupted', reason='process-restart')

    def call_get(self, key):
        row = self.db.execute('SELECT status,result FROM calls WHERE key=?', (key,)).fetchone()
        return None if not row else (row[0], json.loads(row[1]) if row[1] else None)

    def call_start(self, key, run_id):
        self.db.execute('INSERT OR IGNORE INTO calls VALUES(?,?,?,NULL)', (key, run_id, 'STARTED'))

    def call_finish(self, key, value):
        self.db.execute('UPDATE calls SET status=?,result=? WHERE key=?',
                        ('COMPLETED', json.dumps(value, ensure_ascii=False, allow_nan=False), key))

    def close(self):
        if self.closed:
            return
        if hasattr(self, 'db'):
            self.db.close()
        if self._lock:
            if os.name == 'nt':
                import msvcrt
                self._lock.seek(0); msvcrt.locking(self._lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_UN)
            self._lock.close()
        self.closed = True
