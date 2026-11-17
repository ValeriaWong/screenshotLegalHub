"""PaddleOCR-VL v1 original pretrained element recognition (D02).

Paper: Cui et al., PaddleOCR-VL: Boosting Multilingual Document Parsing via a
0.9B Ultra-Compact Vision-Language Model, arXiv:2510.14528.
Source: https://huggingface.co/PaddlePaddle/PaddleOCR-VL (model.lock.json pins revision).
Innovation: NaViT-style dynamic-resolution vision encoder + ERNIE-4.5-0.3B;
multilingual text/table/formula/chart recognition. Benchmark: OmniDocBench v1.5,
OmniDocBench v1.0 and authors' element-level datasets. Full scores not reproduced.
Original input: an element image with OCR:/Table Recognition:/Formula Recognition:/Chart Recognition:.
Original output: recognized text/structured element content; NO message boxes or legal answers.
Fidelity: author transformer implementation and original checkpoint; explicit keyword-only
compatibility shim inputs_embeds -> input_embeds for the Transformers mask API (compat.py).
No mask/model algorithm or checkpoint is rewritten. CPU float32/SDPA
instead of example bfloat16. This validates the recognition core only. PP-DocLayoutV2
and full-page assembly are not executed; do not claim the complete PaddleOCR-VL pipeline.
Product fit: OCR text can feed a separate downstream global-VQA reader. KIE message
boxes require layout detection and message grouping; inventing boxes is prohibited.
State: environment/checkpoint preparation; real execution status is in the named run folder.
"""
import argparse,hashlib,json,os,time,traceback,sys
from compat import install_causal_mask_alias
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
os.environ.setdefault('HF_MODULES_CACHE',str(ROOT/'paper/.cache/hf_modules'))
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
MODEL=ROOT/'paper/.models/paddleocr_vl'
PROMPTS={'ocr':'OCR:','table':'Table Recognition:','formula':'Formula Recognition:','chart':'Chart Recognition:'}
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main(args):
    import torch
    from PIL import Image
    from transformers import AutoModelForCausalLM,AutoProcessor
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/'paddleocr_vl.original_task.py').write_bytes(Path(__file__).read_bytes())
    (out/'paddleocr_vl.compat.py').write_bytes(Path(__file__).with_name('compat.py').read_bytes())
    lock=json.loads(Path(__file__).with_name('model.lock.json').read_text(encoding='utf-8'))
    for name,value in lock['files'].items():
        if hashlib.sha256((MODEL/name).read_bytes()).hexdigest()!=value['sha256']:raise ValueError('Pinned model file changed: '+name)
    if not any(n.endswith('.safetensors') and '/' not in n for n in lock['files']):raise FileNotFoundError('Original weights not downloaded')
    image_path=Path(args.image).resolve();image=Image.open(image_path).convert('RGB')
    input_=dict(image=str(image_path),image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),size=list(image.size),task=args.task,prompt=PROMPTS[args.task])
    save(out/'paddleocr_vl.input.json',input_)
    save(out/'paddleocr_vl.provenance.json',dict(model=lock,device='cpu',dtype='float32',attention=args.attention,max_new_tokens=args.max_new_tokens,full_page_pipeline=False,complete_benchmark=False))
    torch.set_num_threads(4)
    start=time.monotonic()
    model=AutoModelForCausalLM.from_pretrained(str(MODEL),local_files_only=True,trust_remote_code=True,torch_dtype=torch.float32,attn_implementation=args.attention).to('cpu').eval()
    compatibility=install_causal_mask_alias(sys.modules[type(model).__module__])
    provenance=json.loads((out/'paddleocr_vl.provenance.json').read_text(encoding='utf-8'));provenance['runtime_compatibility']=compatibility;save(out/'paddleocr_vl.provenance.json',provenance)
    processor=AutoProcessor.from_pretrained(str(MODEL),local_files_only=True,trust_remote_code=True)
    messages=[dict(role='user',content=[dict(type='image',image=image),dict(type='text',text=PROMPTS[args.task])])]
    inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt').to('cpu')
    save(out/'paddleocr_vl.prompts.json',dict(messages=[dict(role='user',content=[dict(type='image',image=input_['image'],sha256=input_['image_sha256']),dict(type='text',text=PROMPTS[args.task])])],input_ids=inputs['input_ids'].tolist()))
    with torch.inference_mode():output=model.generate(**inputs,max_new_tokens=args.max_new_tokens,do_sample=False,use_cache=True)
    raw=processor.batch_decode(output,skip_special_tokens=True)[0]
    text=processor.batch_decode(output[:,inputs['input_ids'].shape[-1]:],skip_special_tokens=True)[0]
    result=dict(raw_decoded=raw,generated_text=text,generated_token_ids=output[:,inputs['input_ids'].shape[-1]:].tolist(),elapsed_seconds=time.monotonic()-start)
    save(out/'paddleocr_vl.model_responses.json',result);save(out/'paddleocr_vl.output.json',dict(text=text))
    save(out/'paddleocr_vl.test_results.json',dict(status='completed',nonempty_output=bool(text.strip()),supplier_requests=0,local_generations=1,hit_generation_limit=output.shape[-1]-inputs['input_ids'].shape[-1]>=args.max_new_tokens,complete_benchmark=False,full_page_pipeline=False,accuracy=None))
    print(json.dumps(dict(status='completed',characters=len(text),elapsed_seconds=result['elapsed_seconds'],output=str(out))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--out',required=True);p.add_argument('--task',choices=PROMPTS,default='ocr');p.add_argument('--attention',choices=['sdpa','eager'],default='sdpa');p.add_argument('--max-new-tokens',type=int,default=1024);args=p.parse_args()
    try:main(args)
    except Exception as e:
        out=Path(args.out);out.mkdir(parents=True,exist_ok=True);save(out/'paddleocr_vl.test_results.json',dict(status='failed',error_type=type(e).__name__,error=str(e),supplier_requests=0,accuracy=None));traceback.print_exc();raise SystemExit(1)
