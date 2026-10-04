"""Local lexical retrieval. No provider, embedding, or model dependency."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import re
import sqlite3
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'blocks/retriever/artifacts/index.sqlite3'
KINDS = {'image', 'message', 'event', 'case_law', 'statute'}
SYNONYMS = [('借款', '借钱', '借贷'), ('还款', '还钱', '归还'), ('工资', '薪资', '薪酬'),
            ('转账', '打款', '汇款'), ('退款', '退钱'), ('合同', '协议'),
            ('收款确认','受领确认','收到了'), ('意思表示','要约','承诺','磋商')]


def normalized(text):
    return unicodedata.normalize('NFKC', str(text)).casefold()


def tokens(text):
    text = normalized(text)
    parts = re.findall(r'[a-z0-9_]+|[\u3400-\u9fff]+', text)
    out = []
    for part in parts:
        if re.fullmatch(r'[\u3400-\u9fff]+', part):
            out.extend(part)
            out.extend(part[i:i+2] for i in range(len(part)-1))
        else:
            out.append(part)
    return out


def workspace_file(path):
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError('Source path outside workspace')
    return p


def time_value(value):
    """Only accept explicit ISO calendar dates. Never infer a date from 12:10."""
    if value is None or value == '' or value == 'unknown':
        return None
    from datetime import datetime
    if not isinstance(value, str) or not re.match(r'^\d{4}-\d{2}-\d{2}(?:$|T| )', value):
        raise ValueError('Filterable timestamps require an explicit ISO calendar date')
    datetime.fromisoformat(value.replace('Z', '+00:00'))
    # Corpus uses local displayed dates/times; no timezone is invented.
    return value[:19].replace(' ', 'T')


def validate_image(image):
    from PIL import Image
    p = workspace_file(image['file'])
    if hashlib.sha256(p.read_bytes()).hexdigest() != image['sha256']:
        raise ValueError('Image digest mismatch')
    with p.open('rb') as image_file:
        with Image.open(image_file) as im:
            actual = list(im.size)
    if image['size'] != actual:
        raise ValueError('Image dimensions mismatch')
    if p.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise ValueError('Unsupported evidence image')


def validate_bbox(bbox, size):
    if (not isinstance(bbox, list) or len(bbox) != 4
            or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in bbox)):
        raise ValueError('Invalid original-pixel bbox')
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1]):
        raise ValueError('BBox outside original image')


def validate_corpus(corpus):
    images = {x['image_id']: x for x in corpus['images']}
    if len(images) != len(corpus['images']):
        raise ValueError('Duplicate image ID')
    for image in images.values():
        validate_image(image)
    records = {x['id']: x for x in corpus['records']}
    if len(records) != len(corpus['records']):
        raise ValueError('Duplicate record ID')
    for row in records.values():
        if row['kind'] not in KINDS or not isinstance(row['text'], str):
            raise ValueError('Invalid record')
        if row['kind'] in ('image', 'message', 'event') and not row.get('case_id'):
            raise ValueError('Evidence requires case ID')
        time_value(row.get('timestamp_normalized'))
        if row['kind'] in ('message', 'event') and not row.get('source_refs'):
            raise ValueError('Evidence record must have citations')
        for ref in row.get('source_refs', []):
            if ref.get('image_id'):
                image = images.get(ref['image_id'])
                if image is None or image['case_id'] != row['case_id']:
                    raise ValueError('Citation outside case')
                if row['kind'] in ('message', 'event') and ref.get('bbox') is None:
                    raise ValueError('Message/event citation needs original-pixel bbox')
                if row['kind'] == 'event' and not ref.get('message_id'):
                    raise ValueError('Event citation needs a supporting message')
                if ref.get('bbox') is not None:
                    validate_bbox(ref['bbox'], image['size'])
                if ref.get('evidence_page') != image.get('evidence_page'):
                    raise ValueError('Evidence page differs from manifest')
                if ref.get('message_id'):
                    msg = records.get(ref['message_id'])
                    if msg is None or msg['kind'] != 'message' or msg['case_id'] != row['case_id']:
                        raise ValueError('Unresolved source message')
                    quote = ref.get('quote', '')
                    if quote and quote not in msg['text']:
                        raise ValueError('Quote is not in the cited transcription')
                    if not any(r.get('image_id') == ref['image_id'] and r.get('bbox') == ref.get('bbox') for r in msg['source_refs']):
                        raise ValueError('Event source does not match message location')
            elif row['kind'] in ('message', 'event'):
                raise ValueError('Evidence citation needs image')
    return images, records


def build(corpus, db=DEFAULT_DB):
    images, records = validate_corpus(corpus)
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    # Transactionally replace tables: a failed rebuild leaves the previous usable index.
    with sqlite3.connect(db) as connection:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA synchronous=NORMAL')
        connection.executescript('''
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,kind TEXT,case_id TEXT,
          title TEXT,text TEXT,person TEXT,event_type TEXT,timestamp TEXT,body TEXT);
        CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY,body TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(id UNINDEXED, terms);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
        ''')
        connection.execute('BEGIN')
        for table in ('records', 'images', 'search_index', 'metadata'):
            connection.execute('DELETE FROM ' + table)
        for image in images.values():
            connection.execute('INSERT INTO images VALUES (?,?)', (image['image_id'], json.dumps(image, ensure_ascii=False)))
        for row in records.values():
            title = row.get('title') or ''
            # Index label/name metadata too; weighting and exact matching happen in retrieval.
            text = ' '.join([title, row['text'], row.get('person') or '', row.get('event_type') or ''])
            connection.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?)',
                               (row['id'], row['kind'], row.get('case_id'), title, row['text'], row.get('person', ''),
                                row.get('event_type') or '', time_value(row.get('timestamp_normalized')), json.dumps(row, ensure_ascii=False)))
            connection.execute('INSERT INTO search_index VALUES (?,?)', (row['id'], ' '.join(tokens(text))))
        digest = hashlib.sha256(json.dumps(corpus, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        for key, value in {'corpus_sha256': digest, 'schema_version': '1', 'model_requests_per_query': 0,
                           'counts': dict(Counter(x['kind'] for x in records.values())), 'run_metadata': corpus.get('metadata', {})}.items():
            connection.execute('INSERT INTO metadata VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))
    return {'db': str(db), 'records': len(records), 'images': len(images), 'corpus_sha256': digest,
            'counts': dict(Counter(x['kind'] for x in records.values()))}


def merge(corpus, db=DEFAULT_DB):
    """Validate the complete citation graph, then update only incoming index rows."""
    retriever = Retriever(db)
    with retriever.connect() as c:
        images = {x['image_id']: x for x in [json.loads(r['body']) for r in c.execute('SELECT body FROM images')]}
        records = {x['id']: x for x in [json.loads(r['body']) for r in c.execute('SELECT body FROM records')]}
    previous_records = dict(records)
    for image in corpus.get('images', []):
        prior = images.get(image['image_id'])
        if prior and (prior['sha256'] != image['sha256'] or prior['case_id'] != image['case_id']):
            raise ValueError('Conflicting image registration')
        images[image['image_id']] = image
    for row in corpus['records']:
        prior = records.get(row['id'])
        if prior and (prior['kind'] != row['kind'] or prior.get('case_id') != row.get('case_id')
                      or (prior.get('source_artifact') and row.get('source_artifact') and prior['source_artifact'] != row['source_artifact'])):
            raise ValueError('Conflicting record ID; extraction versions need distinct IDs')
        records[row['id']] = row
    metadata = retriever.metadata().get('run_metadata', {})
    metadata['latest_import'] = corpus.get('metadata', {})
    complete = {'images': list(images.values()), 'records': list(records.values()), 'metadata': metadata}
    validate_corpus(complete)
    digest = hashlib.sha256(json.dumps(complete, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    with sqlite3.connect(db) as c:
        c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=NORMAL')
        for image in corpus.get('images', []):
            c.execute('INSERT OR REPLACE INTO images VALUES (?,?)', (image['image_id'], json.dumps(image, ensure_ascii=False)))
        for row in corpus['records']:
            if previous_records.get(row['id']) == row:
                continue
            title = row.get('title') or ''; person = row.get('person') or ''; event = row.get('event_type') or ''
            c.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?,?,?,?,?,?)',
                      (row['id'], row['kind'], row.get('case_id'), title, row['text'], person, event,
                       time_value(row.get('timestamp_normalized')), json.dumps(row, ensure_ascii=False)))
            if row['id'] in previous_records:
                c.execute('DELETE FROM search_index WHERE id=?', (row['id'],))
            c.execute('INSERT INTO search_index VALUES (?,?)', (row['id'], ' '.join(tokens(' '.join([title, row['text'], person, event])))))
        counts = dict(Counter(x['kind'] for x in records.values()))
        for k, v in {'corpus_sha256': digest, 'counts': counts, 'run_metadata': metadata}.items():
            c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', (k, json.dumps(v, ensure_ascii=False)))
    return {'images': len(images), 'records': len(records), 'counts': counts, 'corpus_sha256': digest}


class Retriever:
    def __init__(self, db=DEFAULT_DB):
        self.db = Path(db)
        if not self.db.exists():
            raise FileNotFoundError('Build the index before querying')

    def connect(self):
        connection = sqlite3.connect('file:' + self.db.resolve().as_posix() + '?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def metadata(self):
        with self.connect() as c:
            return {r['key']: json.loads(r['value']) for r in c.execute('SELECT * FROM metadata')}

    def cases(self):
        with self.connect() as c:
            return [dict(x) for x in c.execute('SELECT case_id,count(*) AS records FROM records WHERE kind IN (\'message\',\'event\',\'image\') GROUP BY case_id ORDER BY case_id')]

    def image(self, id):
        with self.connect() as c:
            row = c.execute('SELECT body FROM images WHERE id=?', (id,)).fetchone()
            if row is None: raise KeyError('Unknown image')
            return json.loads(row['body'])

    def record(self, id):
        with self.connect() as c:
            row = c.execute('SELECT body FROM records WHERE id=?', (id,)).fetchone()
            if row is None: raise KeyError('Unknown record')
            return json.loads(row['body'])

    def search(self, query='', case_id=None, scope='evidence', person='', event_type='', after='', before='', limit=20, expand=True, kind=None):
        if scope not in ('evidence', 'case_law', 'statute'):
            raise ValueError('Invalid scope')
        if scope == 'evidence' and not case_id:
            raise ValueError('Select a case before retrieving its evidence')
        limit = int(limit)
        if not 1 <= limit <= 100 or len(query) > 500:
            raise ValueError('Query or limit out of range')
        kinds = ['image', 'message', 'event'] if scope == 'evidence' else [scope]
        if kind:
            if kind not in kinds: raise ValueError('Record kind differs from scope')
            kinds = [kind]
        where = ['r.kind IN (' + ','.join('?' for _ in kinds) + ')']; params = list(kinds)
        if scope == 'evidence': where.append('r.case_id=?'); params.append(case_id)
        if person: where.append('r.person=?'); params.append(person)
        if event_type: where.append('r.event_type=?'); params.append(event_type)
        if after: where.append('r.timestamp>=?'); params.append(time_value(after))
        if before:
            where.append('r.timestamp<=?'); end = time_value(before)
            params.append(end + 'T23:59:59' if len(end) == 10 else end)
        if after and before and time_value(after) > time_value(before): raise ValueError('Date range reversed')
        terms = list(dict.fromkeys(tokens(query)))
        # Multi-character Chinese queries use bigrams, avoiding matches on ubiquitous single characters.
        if len(normalized(query).strip()) > 1:
            terms = [t for t in terms if len(t) > 1 or not re.fullmatch(r'[\u3400-\u9fff]', t)]
        expanded = []
        if expand:
            for group in SYNONYMS:
                if any(x in normalized(query) for x in group):
                    expanded.extend(x for x in group if x not in normalized(query))
            terms = list(dict.fromkeys(terms + [t for x in expanded for t in tokens(x) if len(t)>1]))
        with self.connect() as c:
            if terms:
                # Only generated tokens reach MATCH. User text never becomes FTS syntax.
                match = ' OR '.join('"' + t.replace('"', '""') + '"' for t in terms)
                rows = c.execute('SELECT r.body,bm25(search_index) AS rank FROM search_index JOIN records r ON r.id=search_index.id WHERE search_index MATCH ? AND '
                                 + ' AND '.join(where) + ' ORDER BY rank,r.id LIMIT 1000', [match] + params).fetchall()
            else:
                rows = c.execute('SELECT r.body,0 AS rank FROM records r WHERE ' + ' AND '.join(where) + ' ORDER BY r.timestamp IS NULL,r.timestamp,r.id LIMIT ?', params + [limit]).fetchall()
        results = []
        for row in rows:
            item = json.loads(row['body'])
            searchable = normalized(' '.join([item.get('title') or '', item['text'], item.get('person') or '', item.get('event_type') or '']))
            literal = bool(query.strip() and normalized(query.strip()) in searchable)
            # Literal full-query matches precede partial lexical hits; BM25 orders each tier.
            item['retrieval'] = {'bm25_score': -row['rank'], 'exact_query_match': literal,
                                 'matched_terms': [t for t in terms if t in searchable], 'expanded_phrases': expanded}
            results.append(item)
        results.sort(key=lambda r: (not r['retrieval']['exact_query_match'], -r['retrieval']['bm25_score'], r['id']))
        if scope == 'case_law':
            distinct = []; seen = set()
            for row in results:
                key = row['source_refs'][0].get('content_sha256') or row['id']
                if key not in seen: distinct.append(row); seen.add(key)
            results = distinct
        return {'query': query, 'scope': scope, 'case_id': case_id, 'results': results[:limit],
                'model_requests': 0, 'algorithm': 'SQLite FTS5 BM25 + literal match + explicit synonym dictionary',
                'unknown_times_excluded_by_date_filter': bool(after or before)}

    def context(self, message_id, window=2):
        row = self.record(message_id)
        if row['kind'] != 'message': raise ValueError('Context target must be a message')
        with self.connect() as c:
            all_rows = [json.loads(x['body']) for x in c.execute('SELECT body FROM records WHERE case_id=? AND kind=\'message\'', (row['case_id'],))]
        same = [x for x in all_rows if x.get('conversation_id') == row.get('conversation_id') and x.get('image_id') == row.get('image_id')]
        # A context window must not interleave competing transcriptions of one image.
        same = [x for x in same if x.get('origin_type') == row.get('origin_type')
                and x.get('extraction_origin', {}).get('run_id') == row.get('extraction_origin', {}).get('run_id')]
        same.sort(key=lambda x: x.get('order', 0)); index = next(i for i, x in enumerate(same) if x['id'] == message_id)
        return same[max(0, index-window):index+window+1]

    def timeline(self, case_id):
        if not case_id: raise ValueError('Select a case')
        with self.connect() as c:
            records = [json.loads(x['body']) for x in c.execute('SELECT body FROM records WHERE case_id=? AND kind=\'event\'', (case_id,))]
        known = [x for x in records if x.get('timestamp_normalized')]
        unknown = [x for x in records if not x.get('timestamp_normalized')]
        known.sort(key=lambda x: (x['timestamp_normalized'], x['id']))
        unknown.sort(key=lambda x: x['id'])
        return {'case_id': case_id, 'known_dates': known, 'unresolved_dates': unknown, 'model_requests': 0,
                'note': '日期未知项需要核对，列表次序仅为展示次序。'}


def export_rows(results):
    """JSON/CSV/Excel consumers share all citations, not just the first page."""
    return [{'record_id': x['id'], 'case_id': x.get('case_id'), 'kind': x['kind'], 'time_raw': x.get('timestamp_raw'),
             'time_normalized': x.get('timestamp_normalized'), 'person': x.get('person'), 'event_type': x.get('event_type'),
             'text': x['text'], 'evidence_pages': sorted({str(r['evidence_page']) for r in x.get('source_refs', []) if r.get('evidence_page') is not None}),
             'source_refs': x.get('source_refs', []), 'origin_type': x.get('origin_type'), 'review_status': x.get('review_status')} for x in results]
