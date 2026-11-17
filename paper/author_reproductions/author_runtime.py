"""Shared I/O and pinned-source verification for isolated author adapters.

Only transport is shared. Algorithms stay in their paper-specific adapter and
execute the pinned author's classes/functions. No credentials or API retries here.
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PROTOCOL_OUT = sys.stdout

def source(name):
    lock = json.loads((Path(__file__).with_name('sources.lock.json')).read_text(encoding='utf-8'))
    entry = next(item for item in lock if item['name'] == name)
    folder = ROOT / entry['local_path']
    for relative, expected in entry['files'].items():
        if hashlib.sha256((folder / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Pinned author file changed: ' + name + '/' + relative)
    return folder, entry

def emit(event):
    print(json.dumps(event, ensure_ascii=False), file=_PROTOCOL_OUT, flush=True)

def exchange(event):
    emit(event)
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError('Author transport closed before a response')
    result = json.loads(line)
    if result.get('error'):
        raise RuntimeError(str(result['error']))
    return result

def call(stage, messages, parameters=None):
    return exchange(dict(event='request', stage=stage, messages=messages,
                         original_parameters=parameters or {}))['raw']

def tool(action, result):
    exchange(dict(event='tool', action=action, result=result))

def original_definitions(path, names, namespace):
    """Load exact named top-level definitions, avoiding hardcoded bulk scripts."""
    tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names]
    if {node.name for node in body} != set(names):
        raise ValueError('Author entry missing: ' + str(path))
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace
