"""Regenerate checked-in public schemas without a model, database or network."""
import asyncio
import json
from pathlib import Path
from ..builtin.workflow import components
from ..adapters.dify import DifyAdapter
from ..adapters.responses import ResponsesAdapter
from ..adapters.http import create_app, TokenAuth
from ..contracts import RunRequest, Run, TaskSpec, ReviewResult, Principal
from ..builtin.contracts import CaseInput, ReportData, Reasoning, AnalysisPlan, Ledger, Assessment, Gaps
from ..model import stage_prompt
from ..primitives import digest
from .. import __version__
from ..core import Runtime
from ..state import SQLiteStore

def main():
    root = Path(__file__).resolve().parents[1]
    runtime = Runtime(*components(None), SQLiteStore())
    principal = Principal(subject='schema-export',permissions=frozenset({'run:read'}))
    outputs = {
        'examples/responses-tools.json': ResponsesAdapter(runtime,principal,scope_id='schema-export').tools(),
        'examples/dify-openapi.json': DifyAdapter(runtime).openapi('http://127.0.0.1:18440'),
        'docs/contracts.schema.json': {cls.__name__: cls.model_json_schema() for cls in (RunRequest,Run,TaskSpec,ReviewResult,CaseInput,ReportData,Reasoning,AnalysisPlan,Ledger,Assessment,Gaps)},
        'docs/http-openapi.json': create_app(runtime,TokenAuth({'schema-export-placeholder-not-a-live-token':principal})).openapi(),
    }
    outputs['examples/harness-manifest.json'] = {
        'package':'screenshotlegal-agentic','version':__version__,
        'workflow':'evidence_analysis','stages':['planning','facts','assessment','gaps','synthesis'],
        'skills':runtime.skills.describe(),'tools':runtime.tools.describe(),
        'prompts':{s:{'content':stage_prompt(s),'sha256':digest(stage_prompt(s))} for s in ('planning','facts','assessment','gaps','synthesis')},
        'responses_tools':outputs['examples/responses-tools.json'],
        'binding':'Host must bind Responses function_call callbacks to ResponsesAdapter; stage model is configured separately.',
    }
    for name, payload in outputs.items():
        (root/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    asyncio.run(runtime.close())
    print('Exported',len(outputs),'contract artifacts')

if __name__=='__main__':
    main()
