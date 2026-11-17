"""Isolated crash fixture, invoked only by test_benchmark_pipeline.py."""
import asyncio
import json
import sys
import time
from pathlib import Path
import httpx
from screenshotlegal.research.store import Store
from screenshotlegal.research.gateway import Gateway
from screenshotlegal.research.benchmark import Benchmark
from screenshotlegal.research.benchmark_pipeline import Pipeline
from screenshotlegal.research.worker import Worker

store=Store(sys.argv[1]);marker=Path(sys.argv[2]);mode=sys.argv[3]
gateway=Gateway(store,None)
async def remote(owner,model,messages,purpose,request_id):
    async with httpx.AsyncClient() as client:
        r=await client.post(model['endpoint'],json={'messages':messages})
        result=r.json()
    if mode=='before_gateway_commit':
        marker.write_text('request received, response not durable',encoding='utf8');time.sleep(60)
    return result
gateway._call=remote
original=gateway.call
async def saved(*args,**kw):
    response=await original(*args,**kw)
    marker.write_text('gateway response committed, attempt not projected',encoding='utf8');time.sleep(60)
    return response
if mode=='after_gateway_commit':gateway.call=saved
benchmark=Benchmark(store,gateway);pipeline=Pipeline(benchmark)
worker=Worker(store,None,gateway,None);worker.benchmark=benchmark;worker.pipeline=pipeline
asyncio.run(worker.execute(store.claim()))
