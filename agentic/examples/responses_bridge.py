"""A real local workflow called via a Responses function-call envelope."""
import asyncio
import json
import tempfile
from .report import create_runtime, demo_case
from ..adapters.responses import ResponsesAdapter

async def main():
    with tempfile.TemporaryDirectory(prefix='agentic-responses-') as directory:
        runtime, principal = create_runtime(directory)
        try:
            bridge = ResponsesAdapter(runtime, principal, scope_id='example-session')
            tool_call = dict(type='function_call',call_id='call_demo_1',name='harness_run_evidence_analysis',
                             arguments=json.dumps(demo_case(),ensure_ascii=False))
            outputs = await bridge.handle_response({'output':[tool_call]})
            result = json.loads(outputs[0]['output'])
            assert result['ok'] and result['data']['status']=='COMPLETED'
            print(json.dumps(dict(type=outputs[0]['type'],call_id=outputs[0]['call_id'],
                                  status=result['data']['status'],stages=len(result['data']['tasks']))))
        finally:
            await runtime.close()

if __name__=='__main__': asyncio.run(main())
