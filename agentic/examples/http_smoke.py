"""Exercise the actual loopback HTTP transport; never uses a production database."""
import asyncio
import json
import secrets
import socket
import tempfile
import httpx
import uvicorn
from .report import create_runtime, demo_case
from ..adapters.http import create_app, TokenAuth

async def main():
    with tempfile.TemporaryDirectory(prefix='agentic-http-') as directory:
        runtime,principal=create_runtime(directory)
        token=secrets.token_urlsafe(32)
        listener=socket.socket(); listener.bind(('127.0.0.1',0))
        port=listener.getsockname()[1]
        app=create_app(runtime,TokenAuth({token:principal}),base_url=f'http://127.0.0.1:{port}')
        server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False))
        running=asyncio.create_task(server.serve(sockets=[listener]))
        try:
            for _ in range(100):
                if server.started: break
                if running.done(): await running
                await asyncio.sleep(.02)
            if not server.started: raise RuntimeError('local server did not start')
            async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer '+token},timeout=10) as client:
                schema=await client.get('/adapters/responses/tools'); schema.raise_for_status()
                call={'type':'function_call','call_id':'call_socket','name':'harness_run_evidence_analysis',
                      'arguments':json.dumps(demo_case())}
                reply=await client.post('/adapters/responses/calls',json=call,headers={'X-Harness-Scope':'socket-session'})
                reply.raise_for_status(); final=json.loads(reply.json()['output'])['data']
                assert final['status']=='COMPLETED'
                events=await client.get('/runs/'+final['run_id']+'/events'); events.raise_for_status()
                assert 'event: run-completed' in events.text
                print(json.dumps({'transport':'loopback HTTP + SSE','status':final['status'],
                                  'stages':len(final['tasks']),'tools':len(schema.json())}))
        finally:
            server.should_exit=True
            await asyncio.wait_for(running,10)
            listener.close()
            if not runtime.closed: await runtime.close()

if __name__=='__main__': asyncio.run(main())
