"""Audit V3 preparation inputs against archived workbooks and original images.

Uses the existing openpyxl dependency; no network, inference, workbook edits or
formula recalculation. Output is a new local batch; errors never become gold.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_v3_baseline import digest, local_path, output_path, read_json, write_json


def normalized(value):
    # Match the historical extractor's JSON conversion, including Excel dates.
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def zip_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode('cp437').decode('utf-8')
    except UnicodeError:
        return info.filename


def put_lines(file, rows):
    with file.open('x', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')


def score_audit(root, files, out):
    """Compare the entire nonempty row and its header, not just selected cells."""
    groups = defaultdict(list)
    for file in files:
        for index, record in enumerate(read_json(local_path(root, file))):
            groups[(record['archive'], record['workbook'])].append((file, index, record))
    manifests, checks = [], []
    archive_hashes = {}
    for (archive_path, workbook_name), records in sorted(groups.items()):
        archive = local_path(root, archive_path)
        archive_hashes.setdefault(archive_path, digest(archive))
        with zipfile.ZipFile(archive) as zipped:
            matches = [i for i in zipped.infolist() if zip_name(i) == workbook_name]
            if len(matches) != 1:
                raise ValueError('Missing/ambiguous ZIP member: ' + workbook_name)
            info = matches[0]
            raw = zipped.read(info)
        sha = sha_bytes(raw)
        relative = 'workbooks/' + sha + '.xlsx'
        dest = out / relative
        dest.parent.mkdir(exist_ok=True)
        if not dest.exists():
            dest.write_bytes(raw)
        manifest = dict(archive=archive_path, archive_sha256=archive_hashes[archive_path],
                        workbook=workbook_name, zip_stored_name=info.filename,
                        path=dest.relative_to(root).as_posix(), sha256=sha, bytes=len(raw))
        manifests.append(manifest)
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        try:
            by_sheet = defaultdict(list)
            for record in records:
                by_sheet[record[2]['sheet']].append(record)
            for sheet_name, sheet_records in sorted(by_sheet.items()):
                wanted = {r['excel_row'] for _, _, r in sheet_records}
                if any(type(n) is not int or n < 2 for n in wanted):
                    raise ValueError('Invalid Excel row locator')
                values, header = {}, []
                if sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    sheet.reset_dimensions()  # Historical Feishu exports may claim A1:A1.
                    for number, row in enumerate(sheet.iter_rows(values_only=True), 1):
                        if number == 1:
                            header = list(row)
                        if number in wanted:
                            values[number] = list(row)
                        if number >= max(wanted):
                            break
                for file, index, record in sheet_records:
                    errors = []
                    row_no = record['excel_row']
                    actual = [dict(column=openpyxl.utils.get_column_letter(i+1),
                                   label=header[i] if i < len(header) else None, value=value)
                              for i, value in enumerate(values.get(row_no, [])) if value is not None]
                    if record['workbook_sha256'] != sha:
                        errors.append('workbook_hash_mismatch')
                    if row_no not in values:
                        errors.append('sheet_or_row_missing')
                    if normalized(actual) != record['cells']:
                        errors.append('row_cells_or_headers_mismatch')
                    identity = sha + '/' + sheet_name + '/' + str(row_no)
                    checks.append(dict(reference_file=file, record_index=index,
                        row_id=sha_bytes(identity.encode('utf-8')), workbook_path=manifest['path'],
                        workbook_sha256=sha, sheet=sheet_name, excel_row=row_no,
                        cell_coordinates=[c['column'] + str(row_no) for c in record['cells']],
                        cells_checked=len(actual), content_status='nonempty' if actual else 'empty',
                        usable_for_mapping=bool(actual) and not errors, actual_cells_sha256=sha_bytes(
                            json.dumps(normalized(actual), ensure_ascii=False, sort_keys=True).encode('utf-8')),
                        status='failed' if errors else 'passed', errors=errors))
        finally:
            wb.close()
    return manifests, checks


def image_audit(root, task_file):
    tasks = [json.loads(line) for line in local_path(root, task_file).read_text(encoding='utf-8').splitlines()]
    if not tasks or len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError('Empty task file or duplicate task IDs')
    rows, image_paths, cache = [], set(), {}
    for task in tasks:
        if not task['images'] or len(task['images']) != len(task['image_hashes']):
            raise ValueError('Image/hash cardinality mismatch: ' + task['id'])
        for index, (relative, expected) in enumerate(zip(task['images'], task['image_hashes'])):
            image = local_path(root, relative)
            if relative not in cache:
                cache[relative] = digest(image) if image.is_file() else None
            actual = cache[relative]
            image_paths.add(relative)
            rows.append(dict(task_id=task['id'], split=task['split'], image_position=index,
                path=relative, expected_sha256=expected, actual_sha256=actual,
                status='passed' if actual == expected and actual is not None else 'failed'))
    return tasks, rows, sorted(image_paths)


def upstream_rows(root, relative, indices):
    """Use the same zero-based source index as legalhub.synthesis.prepare."""
    file = local_path(root, relative)
    rows = {}
    if file.suffix == '.xlsx':
        # A read-only iterator may retain a ZIP stream after an early break.
        # Read bytes first so Windows never retains a lock on the source workbook.
        wb = openpyxl.load_workbook(io.BytesIO(file.read_bytes()), read_only=True, data_only=True)
        try:
            sheet = wb.active
            sheet.reset_dimensions()
            iterator = sheet.iter_rows(values_only=True)
            header = next(iterator)
            for index, values in enumerate(iterator):
                if index in indices:
                    rows[index] = (dict(zip(header, values)), dict(sheet=sheet.title, excel_row=index+2))
                if index >= max(indices):
                    break
        finally:
            wb.close()
    elif file.suffix == '.jsonl':
        with file.open(encoding='utf-8') as stream:
            for index, line in enumerate(stream):
                if index in indices:
                    rows[index] = (json.loads(line), dict(jsonl_line=index+1))
                if index >= max(indices):
                    break
    else:
        raise ValueError('Unsupported upstream source: ' + relative)
    return rows


def candidate_audit(root, candidates, language_targets):
    sources = [(c, read_json(local_path(root, c['directory'] + '/source.json'))) for c in candidates]
    if dict(Counter(s['language'] for _, s in sources)) != language_targets:
        raise ValueError('Calibration language targets not met')
    for key in ['id', 'case_no', 'judgment_text_sha256']:
        if len({s[key] for _, s in sources}) != len(sources):
            raise ValueError('Repeated calibration source: ' + key)
    grouped = defaultdict(set)
    for _, source in sources:
        index = source['source_index']
        if type(index) is not int or index < 0:
            raise ValueError('Invalid upstream source index')
        grouped[source['source_file']].add(index)
    upstream = {p: (digest(local_path(root, p)), upstream_rows(root, p, indices)) for p, indices in grouped.items()}
    checks = []
    for candidate, source in sources:
        errors = []
        source_hash, rows = upstream[source['source_file']]
        original, locator = rows.get(source['source_index'], ({}, {}))
        zh = source['language'] == 'zh'
        if source_hash != source['source_sha256']:
            errors.append('upstream_file_hash_mismatch')
        if original.get('content' if zh else 'judgment_text') != source['text']:
            errors.append('upstream_text_mismatch')
        if original.get('case_no' if zh else 'neutral_citation') != source['case_no']:
            errors.append('upstream_case_number_mismatch')
        if sha_bytes(source['text'].encode('utf-8')) != source['judgment_text_sha256']:
            errors.append('judgment_text_hash_mismatch')
        paragraphs = source['paragraphs']
        if not paragraphs or len({p['id'] for p in paragraphs}) != len(paragraphs):
            errors.append('empty_or_duplicate_paragraphs')
        for p in paragraphs:
            start, end = p['char_start'], p['char_end']
            if not (0 <= start < end <= len(source['text'])) or source['text'][start:end] != p['text']:
                errors.append('paragraph_offset_mismatch:' + p['id'])
        draft = read_json(local_path(root, candidate['directory'] + '/' + candidate['candidate_file']))
        if not draft.get('messages'):
            errors.append('candidate_messages_missing')
        checks.append(dict(case_id=source['id'], language=source['language'], jurisdiction=source['jurisdiction'],
            case_no=source['case_no'], directory=candidate['directory'], candidate_file=candidate['candidate_file'],
            source_file=source['source_file'], source_sha256=source_hash, source_index=source['source_index'],
            upstream_locator=locator, judgment_text_sha256=source['judgment_text_sha256'],
            paragraph_count=len(paragraphs), messages=len(draft.get('messages', [])),
            scope_proposal=candidate['scope_proposal'], evidence_boundary='screenshots_only_for_future_tasks; judgments_reviewer_only',
            identity_time_policy='Use explicit source statements only; unknown remains unknown; assertions are not established facts.',
            split='development', review_status='source_bytes_checked_not_independently_certified',
            permitted_use='internal_preparation_only', status='failed' if errors else 'passed', errors=errors))
    return checks, sorted(upstream)


def audit(root, config_path, output):
    root = root.resolve()
    out = output_path(root, output)
    if out.exists():
        raise ValueError('Output already exists; use a new batch name')
    config = read_json(local_path(root, config_path))
    out.mkdir(parents=True)
    marker = out / '.incomplete'
    marker.write_text('Source audit in progress\n', encoding='utf-8')
    workbooks, scores = score_audit(root, config['reference_files'], out)
    tasks, image_checks, image_paths = image_audit(root, config['task_file'])
    pool, source_files = candidate_audit(root, config['candidates'], config['language_targets'])
    errors = [dict(kind=kind, index=i, details=row) for kind, rows in
              [('score', scores), ('image', image_checks), ('candidate', pool)]
              for i, row in enumerate(rows) if row['status'] != 'passed']
    put_lines(out / 'workbook_manifest.jsonl', workbooks)
    put_lines(out / 'legacy_score_checks.jsonl', scores)
    put_lines(out / 'task_image_checks.jsonl', image_checks)
    write_json(out / 'calibration_source_pool.json', dict(status='development_source_pool_only',
               certified=False, calibration_scenarios_completed=0, cases=pool))
    write_json(out / 'closure_inputs.json', dict(image_paths=image_paths, source_containers=source_files))
    write_json(out / 'input_spec.snapshot.json', config)
    summary = dict(status='failed' if errors else 'passed', checked_at=datetime.now(timezone.utc).isoformat(),
        workbooks=len(workbooks), score_records=len(scores), unique_score_rows=len({r['row_id'] for r in scores}),
        nonempty_score_records=sum(r['content_status']=='nonempty' for r in scores),
        empty_score_records=sum(r['content_status']=='empty' for r in scores),
        duplicate_score_records=len(scores)-len({r['row_id'] for r in scores}),
        cells_checked=sum(r['cells_checked'] for r in scores), tasks=len(tasks), image_references=len(image_checks),
        unique_images=len(image_paths), calibration_sources=len(pool), languages=dict(Counter(r['language'] for r in pool)),
        errors=errors, new_api_calls=0, values_mode='cached_excel_values_data_only; no_formula_recalculation',
        limits=['Mechanical provenance checks only; not legal review or new calibration scenarios.',
                'Image closure is for the selected P3 task file, not the entire v1 benchmark.',
                'Rubric-to-V3 semantic mapping remains S1 work; development sources must not become held-out test cases.',
                'Empty worksheet rows are preserved but excluded from mapping evidence; repeated row IDs are not independent scores.'])
    write_json(out / 'audit_summary.json', summary)
    marker.unlink()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', default='configs/v3/source_audit.json')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        result = audit(ROOT, args.spec, args.output)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        result = dict(status='failed', error=str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
