"""python -m agentic.examples.report --output agentic/report.html [--model]"""
import argparse
import asyncio
import json
from importlib.resources import files
from pathlib import Path
import tempfile
from ..builtin.contracts import CaseInput
from ..builtin.workflow import components, runtime_limits
from ..contracts import Principal
from ..core import Runtime
from ..state import SQLiteStore
from ..report import render_report
from ..model import ModelConfig, ResponsesReasoner

def demo_case():
    return json.loads(files('agentic').joinpath('examples/case.json').read_text(encoding='utf-8'))

def create_runtime(directory, model=None):
    permissions = {'run:create','run:read','run:cancel','run:resume','run:review','evidence:analyze'}
    if model:
        permissions.add('model:invoke')
    principal = Principal(subject='local-operator',permissions=frozenset(permissions))
    runtime = Runtime(*components(model),SQLiteStore(Path(directory)/'harness.sqlite3'),limits=runtime_limits(model))
    return runtime,principal

async def example(directory, case=None, model=None):
    value = CaseInput.model_validate(demo_case() if case is None else case)
    runtime,principal = create_runtime(directory,model)
    try:
        created = runtime.create_run(dict(workflow='evidence_analysis',input=value.model_dump(mode='json'),
            idempotency_key='local-report',limits=runtime.limits.model_dump()),principal)
        result = await runtime.wait(created['run_id'],principal)
        events = [e async for e in runtime.stream_events(created['run_id'],principal)]
        if result['status']!='COMPLETED':
            raise RuntimeError('Pipeline failed: '+json.dumps(result['error']))
        return {'result':result,'events':events},render_report(result,events)
    finally:
        await runtime.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,help='CaseInput JSON; defaults to the packaged synthetic example')
    parser.add_argument('--output',type=Path,default=Path('report.html'))
    parser.add_argument('--model',action='store_true',help='enable explicitly configured Responses service')
    args = parser.parse_args()
    case = json.loads(args.input.read_text(encoding='utf-8')) if args.input else None
    model = ResponsesReasoner(ModelConfig.from_env()) if args.model else None
    with tempfile.TemporaryDirectory(prefix='agentic-report-') as directory:
        result,html = asyncio.run(example(directory,case,model))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(html,encoding='utf-8')
    args.output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    result = result['result']
    print(json.dumps({'status':result['status'],'stages':len(result['tasks']),'tool_calls':result['usage']['tool_calls'],
                      'model_calls':result['usage']['model_calls'],'report':str(args.output)},ensure_ascii=False))

if __name__=='__main__':
    main()
