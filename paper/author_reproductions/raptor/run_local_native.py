"""Run author's Cinderella example with real local CPU inference, zero hosted calls.

Paper https://arxiv.org/abs/2401.18059. This validates original task execution
with explicitly substituted SBERT/FLAN-T5 models; it does not reproduce the
paper's GPT-4/ada-002 benchmark numbers. Every input and response is retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name',default='2026-10-29-native-cinderella-cpu-v1')
    args=parser.parse_args()
    base=Path(__file__).parent/'runs'
    output=(base/args.run_name).resolve()
    output.relative_to(base.resolve())
    output.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        (output/('raptor.'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lock=json.loads((ROOT/'paper/author_reproductions/local_models.lock.json').read_text(encoding='utf-8'))
    request=dict(mode='native',documents=[dict(id='author:demo/sample.txt',text=(ROOT/'paper/upstream_sources/raptor/demo/sample.txt').read_text(encoding='utf-8'))],
                 question='How did Cinderella reach her happy ending?',chunk_tokens=80,num_layers=5,reduction_dimension=2)
    save('input',request)
    record=dict(status='starting',method='raptor',verification='native_example_real_cpu_model_substitution',
                provider_requests=0,model=lock['native_generator'],embedding=lock['embedding'],
                input_sha256=hashlib.sha256(json.dumps(request,ensure_ascii=False).encode()).hexdigest(),
                original_benchmark=False,model_requests=[])
    save('record',record)
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    from transformers import AutoTokenizer,AutoModelForSeq2SeqLM
    torch.set_num_threads(2)
    model_path=ROOT/lock['native_generator']['path']
    tokenizer=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
    model=AutoModelForSeq2SeqLM.from_pretrained(model_path,local_files_only=True,use_safetensors=True).eval()
    env={k:v for k,v in os.environ.items() if k not in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY']}
    env.update(OPENAI_API_KEY='unused-local-transport',PYTHONIOENCODING='utf-8',NUMBA_NUM_THREADS='1')
    traces=[];tools=[];result=None
    with (output/'raptor.native.log').open('w',encoding='utf-8') as error_log:
        child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__).with_name('product_adapter.py'))],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error_log,encoding='utf-8',env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        def send(value):child.stdin.write(json.dumps(value,ensure_ascii=False)+'\n');child.stdin.flush()
        try:
            send(request)
            for line in child.stdout:
                event=json.loads(line)
                if event['event']=='request':
                    prompt='\n'.join(message['content'] for message in event['messages'])
                    encoded=tokenizer(prompt,return_tensors='pt',truncation=True,max_length=2048)
                    original_tokens=len(tokenizer.encode(prompt))
                    step=dict(stage=event['stage'],messages=event['messages'],original_parameters=event['original_parameters'],
                              effective_parameters=dict(max_input_tokens=2048,max_new_tokens=128,do_sample=False,device='cpu'),
                              encoded_input_tokens=encoded['input_ids'][0].tolist(),input_token_count=original_tokens,
                              truncated=original_tokens>2048,status='running')
                    traces.append(step);save('model_responses',traces)
                    print('CPU '+event['stage'],flush=True)
                    start=time.monotonic()
                    with torch.inference_mode():generated=model.generate(**encoded,max_new_tokens=128,do_sample=False)
                    answer=tokenizer.decode(generated[0],skip_special_tokens=True)
                    step.update(status='completed',raw=answer,output_tokens=generated[0].tolist(),latency_ms=round((time.monotonic()-start)*1000))
                    save('model_responses',traces);send(dict(raw=answer))
                elif event['event']=='tool':tools.append(event);save('tools',tools);send(dict(ok=True))
                elif event['event']=='result':result=event;break
            child.wait(timeout=30)
            if child.returncode or result is None:raise RuntimeError('Author process failed; see raptor.native.log')
            checks=dict(nonempty_answer=isinstance(result['output'],str) and bool(result['output'].strip()),
                        author_tree_has_summary_layer=len(result['tree']['layers'])>1,
                        real_local_generations=len(traces),all_generations_completed=all(t['status']=='completed' for t in traces),
                        retrieved_original_sources=bool(result['tree']['original_leaf_evidence']))
            record.update(status='completed' if all(checks[k] for k in ['nonempty_answer','author_tree_has_summary_layer','all_generations_completed','retrieved_original_sources']) else 'failed_checks',model_requests=traces)
            save('output',result);save('test_results',dict(checks=checks,scope='execution/provenance only; not answer accuracy or original benchmark score'))
            save('prompts',[dict(stage=t['stage'],messages=t['messages']) for t in traces])
            save('provenance',dict(author_commit=result['source_commit'],author_entry=result['author_entry'],source_files=result['source_files'],
                  adapter_sha256=hashlib.sha256(Path(__file__).with_name('product_adapter.py').read_bytes()).hexdigest(),runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
        except Exception as error:
            record.update(status='failed',error=type(error).__name__+': '+str(error),model_requests=traces)
            raise
        finally:
            if child.poll() is None:child.kill();child.wait()
            save('record',record)
    print(json.dumps(dict(status=record['status'],calls=len(traces),provider_requests=0,output=str(output)),ensure_ascii=False))

if __name__=='__main__':main()
