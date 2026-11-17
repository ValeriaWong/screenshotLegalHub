"""Import audited source locations and historical predictions into a local index."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub import benchmark as b
from legalhub.retrieval import build, validate_bbox, DEFAULT_DB

DEST = ROOT / 'blocks/retriever/artifacts'


def image_inventory():
    return [{'image_id': x['name'], 'case_id': x['case_id'], 'file': x['path'], 'sha256': x['sha256'], 'size': x['size'],
             'evidence_page': None, 'conversation_id': 'unconfirmed:' + x['name'], 'submitted_by': 'unknown'}
            for x in b.read(ROOT / 'reports/restart/images_manifest.json')]


def historical(images):
    image_map = {x['image_id']: x for x in images}
    p = ROOT / 'projects/ScreenshotLegalBench_v2/process_local_evaluator/image_structured_info.json'
    digest = b.sha(p); records = []; issues = []
    for index, row in enumerate(b.read(p)):
        id = b.image_name(row.get('image_url', ''))
        if id not in image_map:
            issues.append({'source_index': index, 'reason': 'missing_image'}); continue
        image = image_map[id]
        try:
            info = row['structured_info']
            if isinstance(info, str):
                info = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', info.strip()))
            if not isinstance(info, dict) or not isinstance(info.get('conversation'), list):
                raise ValueError('invalid_structure')
        except (ValueError, TypeError, KeyError):
            issues.append({'source_index': index, 'reason': 'malformed_historical_json'}); continue
        for order, message in enumerate(info['conversation']):
            try:
                bb = message['message_bbox']; box = [bb['min_x'], bb['min_y'], bb['max_x'], bb['max_y']]
                validate_bbox(box, image['size'])
                text = message.get('content', '')
                if not isinstance(text, str) or not text.strip():
                    raise ValueError('empty_transcription')
            except (ValueError, TypeError, KeyError):
                issues.append({'source_index': index, 'message_index': order, 'reason': 'invalid_message_or_bbox'}); continue
            mid = f'historical:{id}:{index}:{order}'
            # Do not normalize partial clocks, merge avatar IDs across images, or treat predictions as gold.
            ref = {'image_id': id, 'evidence_page': None, 'bbox': box, 'message_id': mid, 'quote': text}
            records.append({'id': mid, 'kind': 'message', 'case_id': image['case_id'], 'image_id': id,
                            'conversation_id': image['conversation_id'], 'order': order, 'title': info.get('dialog_name', ''),
                            'text': text, 'speaker_local_id': message.get('speaker', 'unknown'),
                            'person': id + ':' + str(message.get('speaker', 'unknown')), 'speaker_party_id': None,
                            'timestamp_raw': str(message.get('timestamp', 'unknown')), 'timestamp_normalized': None,
                            'time_precision': 'unresolved', 'source_refs': [ref], 'origin_type': 'historical_model_prediction',
                            'review_status': 'unreviewed', 'source_artifact': str(p.relative_to(ROOT)).replace('\\', '/'),
                            'source_sha256': digest, 'source_index': index})
    return records, issues


def judgments():
    p = ROOT / 'projects/ScreenshotLegalBench_v2/generate_chat/output_full/wkinfo_parsed.jsonl'
    digest = b.sha(p); records = []; seen = set()
    for index, line in enumerate(p.open(encoding='utf-8')):
        if not line.strip(): continue
        row = json.loads(line); text = row.get('content', '')
        h = hashlib.sha256(text.encode()).hexdigest()
        if not text or h in seen: continue
        seen.add(h)
        # Fixed spans with overlap preserve character offsets in the original content field.
        for start in range(0, len(text), 1000):
            chunk = text[start:start+1200]
            records.append({'id': f'case-law:{h[:20]}:{start}', 'kind': 'case_law', 'title': row.get('title') or '',
                            'text': chunk, 'person': '', 'event_type': row.get('case_cause') or '',
                            'case_no': row.get('case_no'), 'court': row.get('court'), 'decision_date': row.get('date'),
                            'origin_type': 'imported_judgment_text', 'review_status': 'source_not_reverified',
                            'source_refs': [{'source_file': str(p.relative_to(ROOT)).replace('\\', '/'), 'source_sha256': digest,
                                             'source_index': index, 'content_sha256': h, 'char_start': start, 'char_end': start+len(chunk),
                                             'url': row.get('url'), 'quote': chunk}]})
    return records


def make(args):
    images = image_inventory()
    records = [{'id': 'image:' + x['image_id'], 'kind': 'image', 'case_id': x['case_id'], 'title': x['image_id'],
                'text': x['image_id'], 'origin_type': 'original_image_manifest', 'review_status': 'image_hash_checked',
                'source_refs': [{'image_id': x['image_id'], 'evidence_page': None, 'bbox': None, 'quote': ''}]} for x in images]
    issues = []
    if not args.no_historical:
        imported, issues = historical(images); records.extend(imported)
    if not args.no_judgments:
        records.extend(judgments())
    for source in args.corpus:
        corpus = b.read(source)
        updated = {x['image_id']: x for x in images}; updated.update({x['image_id']: x for x in corpus.get('images', [])})
        images = list(updated.values())
        records.extend(corpus['records'])
        # Existing image-only refs inherit an explicit submitted manifest page if provided.
        for r in records:
            if r['kind'] == 'image':
                for ref in r['source_refs']:
                    ref['evidence_page'] = updated[ref['image_id']].get('evidence_page')
    corpus = {'images': images, 'records': records,
              'metadata': {'historical_import_enabled': not args.no_historical, 'judgments_import_enabled': not args.no_judgments,
                           'fresh_corpora': args.corpus, 'retrieval_calls_models': False,
                           'case_id_note': 'Filename prefixes are provisional groups, not verified judicial case numbers.'}}
    result = build(corpus, args.db)
    DEST.mkdir(parents=True, exist_ok=True)
    b.write(DEST / 'build.json', result)
    b.write(DEST / 'historical_import_issues.json', issues)
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--corpus', action='append', default=[])
    parser.add_argument('--no-historical', action='store_true')
    parser.add_argument('--no-judgments', action='store_true')
    make(parser.parse_args())
