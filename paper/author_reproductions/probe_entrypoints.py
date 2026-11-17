"""No-network author entrypoint diagnostics in the existing product environment.

A missing dependency here is an environment diagnostic, never a paper reproduction
result. Model inference, training and external requests are disabled for this probe.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
CASES=[
    ('legal_r1','infer_pipeline.py'),
    ('verdict','legal-task/run.py'),
    ('crag','scripts/CRAG_Inference.py'),
    ('solar','stage_two.py'),
    ('agentscourt','AgentsCourt/judge_final_once.py'),
]
results=[]
for name,entry in CASES:
    directory=ROOT/'paper/upstream_sources'/name
    code="\n".join([
        "import os,socket,runpy,sys",
        "for k in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY']:os.environ[k]=''",
        "def disabled(*args,**kwargs):raise RuntimeError('Network disabled: dependency preflight only')",
        "socket.socket.connect=disabled",
        "sys.path.insert(0,"+repr(str(directory))+")",
        "sys.argv=["+repr(entry)+",'--help']",
        "runpy.run_path("+repr(entry)+",run_name='__main__')",
    ])
    try:
        p=subprocess.run([sys.executable,'-B','-c',code],cwd=directory,text=True,capture_output=True,timeout=15,encoding='utf-8',errors='replace')
        record=dict(repository=name,entrypoint=entry,status='entrypoint_preflight_only',exit_code=p.returncode,
                    stdout=p.stdout,stderr=p.stderr,model_requests=0,original_benchmark_reproduced=False)
    except subprocess.TimeoutExpired:
        record=dict(repository=name,entrypoint=entry,status='preflight_timeout',model_requests=0,original_benchmark_reproduced=False)
    results.append(record)
destination=Path(__file__).parent/'entrypoint_preflight.json'
destination.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([dict(repository=r['repository'],status=r['status'],exit_code=r.get('exit_code'),
    diagnostic=(r.get('stderr') or '').splitlines()[-1:] ) for r in results],ensure_ascii=False))
