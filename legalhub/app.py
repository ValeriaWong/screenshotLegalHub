"""Loopback evidence workbench and CLI. Queries never invoke a model."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timezone
import argparse
import base64
import csv
import hashlib
import io
import json
import mimetypes
import re
import threading
import uuid

from legalhub import benchmark as b
from legalhub.retrieval import Retriever, DEFAULT_DB, merge, export_rows, workspace_file

STATIC = b.ROOT / 'blocks/retriever/web'
JOBS = {}
LOCK = threading.Lock()


def update_progress(job, value):
    """A successful image is progress, not completion of the import/indexing job."""
    progress = dict(value)
    image_status = progress.pop('status', None)
    job.update(progress)
    if image_status is not None: job['last_image_status'] = image_status


def merge_corpus(retriever, incoming):
    return merge(incoming, retriever.db)


def serve(db=DEFAULT_DB, port=18420, model='kimi3_low', review_db=None):
    retriever = Retriever(db)
    from legalhub.casework import DEFAULT_CASE
    from legalhub.case_registry import CaseRegistry
    from legalhub.case_chat import CaseChat, PROFILES
    from legalhub.legal_review import ReviewStore, ReviewConflict, ReviewNotFound, ReviewValidation
    registry=CaseRegistry(retriever);chatwork=CaseChat(registry)
    reviewstore=ReviewStore(registry,chatwork,db_path=review_db)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Paths may contain query text. Log status only.
            pass

        def send(self, body, status=200, mime='application/json; charset=utf-8', headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            elif isinstance(body, str): body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', (headers or {}).get('Cache-Control','no-store'))
            for k, v in (headers or {}).items():
                if k != 'Cache-Control':self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)

        def local_request(self):
            host = self.headers.get('Host', '').split(':')[0]
            if host not in ('127.0.0.1', 'localhost'):
                raise ValueError('Local host required')
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc not in (f'127.0.0.1:{port}', f'localhost:{port}'):
                raise ValueError('Origin differs from local app')
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise ValueError('Cross-site access rejected')

        def search(self, q):
            return retriever.search(query=q.get('q', [''])[0], case_id=q.get('case_id', [None])[0],
                                    scope=q.get('scope', ['evidence'])[0], person=q.get('person', [''])[0],
                                    event_type=q.get('event_type', [''])[0], after=q.get('after', [''])[0],
                                    before=q.get('before', [''])[0], limit=int(q.get('limit', ['20'])[0]), kind=q.get('kind', [None])[0])

        def do_GET(self):
            try:
                self.local_request()
                parsed = urlsplit(self.path); q = parse_qs(parsed.query, keep_blank_values=True)
                path = parsed.path
                if path.startswith('/api/case/'):
                    case_id=q.get('case_id',[DEFAULT_CASE])[0];casework=registry.get(case_id)
                if path == '/api/review/queue':
                    self.send(reviewstore.queue(case_id=q.get('case_id',[None])[0] or None,status=q.get('status',['pending'])[0],kind=q.get('kind',[None])[0] or None,offset=int(q.get('offset',['0'])[0]),limit=int(q.get('limit',['50'])[0])))
                elif path == '/api/review/item':self.send(reviewstore.get_item(q['case_id'][0],q['item_id'][0]))
                elif path == '/api/review/export':self.send(reviewstore.export_review(q['case_id'][0]),headers={'Content-Disposition':'attachment; filename="legal-review.json"'})
                elif path == '/api/workspace/cases':self.send({'cases':registry.list(),'models':PROFILES})
                elif path == '/api/workspace/image':
                    case_id=q['case_id'][0];id=q['id'][0]
                    image=next((x for x in registry.images.get(case_id,[]) if x['image_id']==id),None)
                    if not image:raise KeyError('Unknown image in this case')
                    p=workspace_file(image['file'])
                    if b.sha(p)!=image['sha256']:raise ValueError('Image changed after registration')
                    self.send(p.read_bytes(),mime=mimetypes.guess_type(p)[0] or 'image/jpeg',headers={'Cache-Control':'private, max-age=300'})
                elif path == '/api/case/current': self.send(registry.state(case_id))
                elif path == '/api/case/timeline':
                    self.send(casework.timeline())
                elif path == '/api/case/search': self.send(casework.search(q.get('q',[''])[0],q.get('kind',['all'])[0]))
                elif path == '/api/case/jobs': self.send(registry.state(case_id)['job'])
                elif path == '/api/case/chat':self.send({'messages':chatwork.history(case_id),'models':PROFILES})
                elif path == '/api/case/record': self.send(casework.retriever().record(q['id'][0]))
                elif path == '/api/case/context': self.send(casework.retriever().context(q['id'][0]))
                elif path == '/api/case/image':
                    image=casework.retriever().image(q['id'][0]);p=workspace_file(image['file'])
                    version=q.get('sha',[None])[0]
                    if version is not None and version!=image['sha256']:raise ValueError('Image version differs from registered original')
                    if b.sha(p)!=image['sha256']:raise ValueError('Image changed after indexing')
                    self.send(p.read_bytes(),mime=mimetypes.guess_type(p)[0] or 'image/jpeg',
                              headers={'Cache-Control':'private, max-age=86400, immutable'} if version else None)
                elif path == '/api/case/export':
                    analysis=casework.state()['analysis']
                    exported=dict(analysis,case_id=case_id,case_name=casework.material['metadata'].get('case_name',''),images=casework.material['images'],messages=casework.material['records'],presentation_timeline=casework.timeline()) if analysis else {'case_id':case_id,'images':casework.material['images'],'messages':casework.material['records'],'analysis':None,'presentation_timeline':casework.timeline()}
                    self.send(exported,headers={'Content-Disposition':'attachment; filename="case-analysis.json"'})
                elif path == '/health':
                    self.send({'status': 'ok', 'retrieval_model_requests': 0, **retriever.metadata()})
                elif path == '/api/cases': self.send(retriever.cases())
                elif path == '/api/search': self.send(self.search(q))
                elif path == '/api/persons':
                    case = q['case_id'][0]
                    with retriever.connect() as c:
                        rows = c.execute('SELECT body FROM records WHERE case_id=? AND kind=\'message\'', (case,)).fetchall()
                    persons = {}
                    for x in rows:
                        r = json.loads(x['body']); person = r.get('person', '')
                        side = {'left': '左侧', 'right': '右侧', 'system': '系统', 'unknown': '未知'}.get(r.get('speaker_local_id'), r.get('speaker_local_id', '未知'))
                        name = r.get('speaker_name', '')
                        persons[person] = {'id': person, 'label': (name if name and name != 'unknown' else side) + ' · ' + str(r.get('image_id', ''))}
                    self.send(list(persons.values()))
                elif path == '/api/context': self.send(retriever.context(q['id'][0]))
                elif path == '/api/timeline': self.send(retriever.timeline(q['case_id'][0]))
                elif path == '/api/record': self.send(retriever.record(q['id'][0]))
                elif path == '/api/jobs':
                    with LOCK: self.send(dict(JOBS))
                elif path == '/api/image':
                    image = retriever.image(q['id'][0]); p = workspace_file(image['file'])
                    if b.sha(p) != image['sha256']: raise ValueError('Image changed after indexing')
                    self.send(p.read_bytes(), mime=mimetypes.guess_type(p)[0] or 'image/jpeg')
                elif path == '/api/export':
                    if q.get('timeline', [''])[0] == '1':
                        timeline = retriever.timeline(q['case_id'][0])
                        rows = export_rows(timeline['known_dates'] + timeline['unresolved_dates'])
                    else:
                        rows = export_rows(self.search(q)['results'])
                    if q.get('format', ['json'])[0] == 'csv':
                        stream = io.StringIO(newline=''); fields = list(rows[0]) if rows else ['record_id', 'text', 'source_refs']
                        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
                        for row in rows:
                            row = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()}
                            # Spreadsheet import must not execute a chat message as a formula.
                            row = {k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v for k, v in row.items()}
                            writer.writerow(row)
                        self.send(b'\xef\xbb\xbf' + stream.getvalue().encode('utf-8'), mime='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="evidence.csv"'})
                    else: self.send(rows, headers={'Content-Disposition': 'attachment; filename="evidence.json"'})
                elif path in ('/', '/index.html', '/app.js', '/style.css','/case','/case.html','/case.js','/case.css','/case-i18n.js','/case-chat.js','/hub.js','/hub.css','/library','/review','/review.html','/review.js','/review.css','/workbench-theme.css'):
                    name = 'hub.html' if path=='/' else 'case.html' if path in ('/case','/case.html') else 'review.html' if path in ('/review','/review.html') else 'index.html' if path == '/library' else path[1:]
                    self.send((STATIC / name).read_bytes(), mime={'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8'}[name.rsplit('.', 1)[-1]])
                else: self.send({'error': 'Not found'}, 404)
            except ReviewConflict as error:self.send({'error':str(error),'code':'review_conflict'},409)
            except ReviewNotFound as error:self.send({'error':str(error),'code':'review_not_found'},404)
            except KeyError: self.send({'error': '记录或参数不存在'}, 404)
            except (ValueError, TypeError) as error: self.send({'error': str(error)}, 400)
            except Exception: self.send({'error': '请求未完成，请检查本地运行记录'}, 500)

        def do_POST(self):
            try:
                self.local_request()
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 80 * 1024 * 1024: raise ValueError('Upload size out of range')
                data = json.loads(self.rfile.read(length))
                path=urlsplit(self.path).path
                if path=='/api/review/decision':
                    self.send(reviewstore.save(data['case_id'],data['item_id'],data['decision'],data.get('edited_text',''),data.get('note',''),data.get('expected_revision'),reviewer='user'));return
                if path=='/api/workspace/create':
                    self.send(registry.create(data['files'],data.get('name',''),data.get('context','')),202);return
                if path=='/api/case/chat':
                    self.send(chatwork.start(data.get('case_id',DEFAULT_CASE),data['question'],data.get('profile','fast'),data.get('locale','zh')),202);return
                if urlsplit(self.path).path == '/api/case/analyze':
                    self.send(registry.start(data.get('case_id',DEFAULT_CASE)),202);return
                if urlsplit(self.path).path != '/api/import': self.send({'error': 'Not found'}, 404); return
                case = data['case_id']
                if not re.fullmatch(r'[a-zA-Z0-9_\-\u3400-\u9fff]{1,80}', case): raise ValueError('案件名称可使用中文、字母、数字、下划线或横线')
                files = data['files']
                if not isinstance(files, list) or not 1 <= len(files) <= 30: raise ValueError('一次导入1至30张截图')
                from PIL import Image
                incoming = {'images': [], 'records': [], 'metadata': {'origin_type': 'user_uploaded_originals'}}
                dest = b.ROOT / 'blocks/evidence/artifacts/uploads'; dest.mkdir(parents=True, exist_ok=True)
                job = uuid.uuid4().hex[:16]; images = []
                seen = set()
                for index, item in enumerate(files):
                    blob = base64.b64decode(item['base64'], validate=True)
                    if len(blob) > 15 * 1024 * 1024: raise ValueError('单张图片超过15MB')
                    with Image.open(io.BytesIO(blob)) as im:
                        size = list(im.size); format = im.format
                        if format not in ('JPEG', 'PNG', 'WEBP'): raise ValueError('仅支持JPEG、PNG和WebP截图')
                        im.verify()
                    digest = hashlib.sha256(blob).hexdigest()
                    # Content + case yields stable IDs; exact duplicate uploads are collapsed explicitly.
                    id = 'upload-' + hashlib.sha256((case + digest).encode()).hexdigest()[:24]
                    if id in seen: continue
                    seen.add(id)
                    file = dest / (digest + {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}[format])
                    if not file.exists(): file.write_bytes(blob)
                    image = {'image_id': id, 'case_id': case, 'file': file.relative_to(b.ROOT).as_posix(), 'sha256': digest, 'size': size,
                             'evidence_page': index + 1, 'conversation_id': 'unconfirmed:' + id, 'submitted_by': 'unknown',
                             'original_filename': str(item.get('name', ''))[:200], 'page_basis': 'user_selected_upload_order'}
                    try:
                        prior = retriever.image(id)
                        image = prior  # Reimport preserves previously registered evidence pages.
                    except KeyError: pass
                    images.append(image)
                    incoming['records'].append({'id': 'image:' + id, 'kind': 'image', 'case_id': case,
                                                'title': image['original_filename'], 'text': image['original_filename'],
                                                'origin_type': 'user_uploaded_original', 'review_status': 'unreviewed',
                                                'source_refs': [{'image_id': id, 'evidence_page': image['evidence_page'], 'bbox': None, 'quote': ''}]})
                incoming['images'] = images
                manifest = b.ROOT / 'blocks/evidence/artifacts/uploads' / (job + '-manifest.json'); b.write(manifest, {'images': images})
                with LOCK:
                    if any(x['status'] == 'running' for x in JOBS.values()): raise ValueError('已有导入任务正在运行，请稍后再试')
                    JOBS[job] = {'status': 'running', 'case_id': case, 'completed': 0, 'planned': len(images)}
                def process():
                    try:
                        merge_corpus(retriever, incoming)
                        if data.get('extract'):
                            from legalhub.evidence import extract
                            def progress(value):
                                with LOCK: update_progress(JOBS[job], value)
                            result = extract(manifest, model, b.ROOT / 'blocks/evidence/artifacts/runs' / job, True, progress)
                            merge_corpus(retriever, b.read(result['corpus']))
                            final = 'completed' if result['ok_images'] == result['planned_images'] and not result['rejected_messages'] else 'needs_review'
                            with LOCK: JOBS[job].update(status=final, result=result)
                        else:
                            with LOCK: JOBS[job].update(status='completed', completed=len(images))
                    except Exception as error:
                        with LOCK: JOBS[job].update(status='error', error_type=type(error).__name__)
                threading.Thread(target=process, daemon=True).start()
                self.send({'job_id': job, 'case_id': case, 'images': len(images)}, 202)
            except ReviewConflict as error:self.send({'error':str(error),'code':'review_conflict'},409)
            except ReviewNotFound as error:self.send({'error':str(error),'code':'review_not_found'},404)
            except ReviewValidation as error:self.send({'error':str(error),'code':'review_validation'},400)
            except (ValueError, TypeError, KeyError): self.send({'error': '请求未完成，请核对输入和任务状态'}, 400)
            except Exception: self.send({'error': '导入未完成，请检查本地运行记录'}, 500)
    class WorkbenchServer(ThreadingHTTPServer):
        # Timeline views request several originals together; allow that local burst.
        request_queue_size=64
        daemon_threads=True
    server = WorkbenchServer(('127.0.0.1', port), Handler)
    print(json.dumps({'url': f'http://127.0.0.1:{port}', 'retrieval_model_requests': 0, 'extraction_model': model}), flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['serve', 'query', 'check'])
    parser.add_argument('--db', default=str(DEFAULT_DB)); parser.add_argument('--port', type=int, default=18420)
    parser.add_argument('--model', default='kimi3_low'); parser.add_argument('--query', default='')
    parser.add_argument('--review-db', default=None, help='Optional isolated annotation database for local verification')
    parser.add_argument('--case'); parser.add_argument('--scope', default='evidence'); parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    if args.command == 'serve': serve(args.db, args.port, args.model,args.review_db)
    elif args.command == 'check': print(json.dumps(Retriever(args.db).metadata(), ensure_ascii=False))
    else: print(json.dumps(Retriever(args.db).search(args.query, args.case, args.scope, limit=args.limit), ensure_ascii=False))


if __name__ == '__main__': main()
