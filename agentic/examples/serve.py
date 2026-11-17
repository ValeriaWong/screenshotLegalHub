"""Local demo HTTP server. HARNESS_SERVICE_TOKEN is required (>=24 chars)."""
import argparse
import asyncio
import os
import tempfile
import uvicorn
from .report import create_runtime, demo_case
from ..adapters.http import TokenAuth, create_app

async def serve(port):
    token = os.environ.get('HARNESS_SERVICE_TOKEN','')
    if len(token)<24:
        raise SystemExit('Set HARNESS_SERVICE_TOKEN to a random secret of at least 24 characters')
    with tempfile.TemporaryDirectory(prefix='agentic-server-') as directory:
        runtime,principal = create_runtime(directory)
        app=create_app(runtime,TokenAuth({token:principal}),base_url=f'http://127.0.0.1:{port}')
        print('Use the CaseInput JSON in agentic/examples/case.json', flush=True)
        try:
            await uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False)).serve()
        finally:
            if not runtime.closed: await runtime.close()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=18440)
    args=parser.parse_args()
    if not 1024<=args.port<=65535: parser.error('port must be 1024..65535')
    asyncio.run(serve(args.port))

if __name__=='__main__': main()
