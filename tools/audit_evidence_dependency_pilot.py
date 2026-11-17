"""Lossless request reconciliation and source integrity audit; no legal scoring."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def write_new(path, obj, lines=False):
    with path.open('x', encoding='utf-8', newline='\n') as file:
        if lines:
            for row in obj:
                file.write(json.dumps(row, ensure_ascii=False) + '\n')
        else:
            json.dump(obj, file, ensure_ascii=False, indent=2)
            file.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--design', required=True)
    args = parser.parse_args()
    run, design = (ROOT / args.run).resolve(), (ROOT / args.design).resolve()
    run.relative_to(ROOT)
    design.relative_to(ROOT)
    outputs = [run/'predictions.reconciled.jsonl', run/'verification.json']
    assert not any(path.exists() for path in outputs), 'Use new output files.'
    originals = {path: sha(path) for path in run.glob('*') if path.is_file()}
    requests = load_lines(run/'requests.jsonl')
    spec = json.loads((run/'run.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(json.dumps(requests, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == spec['request_sha256']
    key = lambda row: (row['task_id'], row['protocol'], row['condition'])
    lookup = {key(row): row for row in requests}
    assert len(lookup) == len(requests) == 19
    predictions = load_lines(run/'predictions.jsonl')
    seen, reconciled, repaired = set(), [], 0
    for row in predictions:
        request = lookup[key(row)]
        assert row['images'] == request['images']
        assert row['image_hashes'] == request['image_hashes']
        # The original runner did not persist prompt_sha256 on all rows.
        # Verify it if present; otherwise preserve the limitation in the audit.
        if row.get('prompt_sha256'):
            assert row['prompt_sha256'] == hashlib.sha256(request['prompt'].encode()).hexdigest()
        pair = (row['model_config'], request['request_id'])
        assert pair not in seen
        seen.add(pair)
        fixed = dict(row)
        if row['request_id'] != request['request_id']:
            assert row['status'] in ['ok', 'invalid_format']
            fixed['provider_request_id'] = row['request_id']
            repaired += 1
        fixed['request_id'] = request['request_id']
        fixed['original_log_request_id'] = row['request_id']
        fixed['reconciliation_basis'] = 'unique_task_protocol_condition_plus_exact_image_hashes'
        reconciled.append(fixed)
    assert len(predictions) == len(seen) == 38
    aliases = {row['model_config'] for row in predictions}
    assert len(aliases) == 2
    assert aliases == set(spec['models'])
    assert seen == {(alias, r['request_id']) for alias in aliases for r in requests}
    before = json.loads((run/'source_integrity.before.json').read_text(encoding='utf-8'))
    assert all(sha(ROOT / path) == digest for path, digest in before.items())
    graphs = load_lines(design/'reasoning_graphs.review.jsonl')
    assert len(graphs) == 6
    node_count = 0
    for graph in graphs:
        ids = set()
        assert graph['minimal_sufficient_sets'] == []
        assert all(value is None for value in graph['scores'].values())
        for node in graph['nodes']:
            assert node['id'] not in ids
            assert set(node['depends_on']) <= ids
            ids.add(node['id'])
            node_count += 1
            for ref in node['source_refs']:
                assert sha(ROOT / ref['image']) == ref['image_sha256']
    design_hashes = json.loads((design/'source_integrity.json').read_text(encoding='utf-8'))
    # Builder snapshots use before/after dictionaries.
    protected = design_hashes.get('before', design_hashes.get('hashes'))
    assert protected is not None
    assert all(sha(ROOT / path) == digest for path, digest in protected.items())
    write_new(outputs[0], reconciled, lines=True)
    assert all(sha(path) == digest for path, digest in originals.items())
    verification = {
        'original_run_files_unchanged': True,
        'protected_original_inputs_checked': len(before),
        'original_inputs_unchanged': True,
        'design_source_files_checked': len(protected),
        'design_source_files_unchanged': True,
        'requests_per_model': len(requests),
        'complete_unique_prediction_slots': len(seen),
        'provider_request_id_collisions_reconciled': repaired,
        'raw_log_sha256': sha(run/'predictions.jsonl'),
        'reconciled_log_sha256': sha(outputs[0]),
        'prompt_hashes_present_in_original_predictions': sum(bool(r.get('prompt_sha256')) for r in predictions),
        'prompt_provenance_limitation': 'Successful response prompt hashes were verified against the frozen manifest; failed rows have no prompt hash. The plan hash identifies all requested prompts.',
        'dependency_graphs': len(graphs), 'dependency_nodes': node_count,
        'graph_topological_order_valid': True,
        'numeric_legal_scores': None, 'professional_signoff': False,
        'additional_api_calls': 0,
    }
    write_new(outputs[1], verification)
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
