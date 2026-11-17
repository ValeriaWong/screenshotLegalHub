"""LawBench (EMNLP 2024), https://aclanthology.org/2024.emnlp-main.452/.
Author code: https://github.com/open-compass/LawBench @ e30981bb3ff54c41571f222e0b23e92d27375388.
Reproduction: original released dataset, original scorer functions AND main.py CLI;
19/20 tasks runnable without neural weights. Task 2-1 ChERRANT/LTP is deferred by
user instruction. This is a benchmark, not an invented agent or a trained model.
Innovation: 20 Chinese legal tasks across knowledge memorization, understanding,
and application, with task-specific metrics and zero/one-shot evaluation.
Original input: {instruction, question, answer} in data/{zero,one}_shot/<task>.json;
only instruction + question go to the model. answer is evaluator-only reference.
Original output: text prediction, then {origin_prompt,prediction,refr} for scoring;
main.py emits task/model_name/score/abstention_rate CSV. Scores stay in [0,1].
Native scope: first published row of each eligible task, both prompt regimes;
DeepSeek API replaces published tested models. No whole benchmark reproduction.
Product adaptation: frozen global classification labels map to A-D for official
1-2 accuracy (a domain adaptation, not the original legal-knowledge task).
Official 2-5 rc-F1 can compare visible text VQA answers and
geometry-matched KIE text fields. It cannot assess bounding boxes, speaker identity,
amount/currency semantics, open legal reasoning, or unmapped criminal NER labels.
Task 2-6's original entity taxonomy is NOT renamed into screenshot message fields.
No scorer/parser fixes: even original 'anstention_rate' spelling and CLI's default
abstention 0 are preserved, separately identified in returned raw and CSV outputs.
"""
import ast
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'paper/author_reproductions'))
from author_runtime import source,emit

DEFERRED={'2-1':'Official ChERRANT tokenizer imports ltp.LTP and torch; local model branch deferred by user.'}

def native_inputs():
    folder,entry=source('lawbench')
    samples=[]
    inventory=[]
    for regime in ('zero_shot','one_shot'):
        for path in sorted((folder/'data'/regime).glob('*.json')):
            rows=json.loads(path.read_text(encoding='utf-8'))
            task=path.stem
            inventory.append(dict(task=task,regime=regime,samples=len(rows),deferred=task in DEFERRED))
            if task in DEFERRED:continue
            row=rows[0]
            samples.append(dict(task=task,regime=regime,index=0,
                messages=[dict(role='user',content=row['instruction']+'\n'+row['question'])],
                origin_prompt=row['instruction']+'\n'+row['question'],reference=row['answer'],
                input_path=path.relative_to(ROOT).as_posix(),
                reference_sent_to_model=False))
    return dict(samples=samples,inventory=inventory,deferred=DEFERRED,source=entry['commit'])

def original_scorers(folder):
    """Load original main and its exact funct_dict AST; scorer bodies are unmodified."""
    sys.path.insert(0,str(folder/'evaluation'))
    path=folder/'evaluation/main.py'
    spec=importlib.util.spec_from_file_location('lawbench_original_main',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    assignment=next(n for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='funct_dict' for t in n.targets))
    namespace=dict(vars(module))
    exec(compile(ast.Module(body=[assignment],type_ignores=[]),str(path),'exec'),namespace)
    return module,namespace['funct_dict']

def evaluate(payload):
    folder,entry=source('lawbench')
    logs=io.StringIO()
    with contextlib.redirect_stdout(logs):
        main,functions=original_scorers(folder)
        tasks=payload['tasks']
        if not tasks or not set(tasks)<=set(functions)-set(DEFERRED):
            raise ValueError('Unknown, empty, or locally deferred LawBench task')
        raw={}
        for task,rows in tasks.items():
            if not rows:raise ValueError('Empty task cannot be scored')
            for row in rows:
                if set(row)!={'origin_prompt','prediction','refr'} or not all(isinstance(v,str) for v in row.values()):
                    raise ValueError('Original scorer input must contain three text fields only')
            raw[task]=functions[task](rows)
        with tempfile.TemporaryDirectory(prefix='lawbench-scoring-') as temporary:
            work=Path(temporary);inputs=work/'predictions'/'submitted_predictions';inputs.mkdir(parents=True)
            for task,rows in tasks.items():
                (inputs/(task+'.json')).write_text(json.dumps({str(i):r for i,r in enumerate(rows)},ensure_ascii=False),encoding='utf-8')
            out=work/'official_scores.csv'
            main.main(['-i',str(inputs.parent),'-o',str(out)])
            csv_text=out.read_text(encoding='utf-8')
            csv_rows=list(csv.DictReader(io.StringIO(csv_text)))
    return dict(event='result',method='b02_lawbench',source=entry['commit'],raw_scores=raw,
        official_cli=dict(entry='evaluation/main.py:main',csv=csv_text,rows=csv_rows,stdout=logs.getvalue()),
        deferred_tasks=DEFERRED,local_model_inference=False,model_requests=0,
        original_complete_benchmark=False,
        metric_caveats=['2-6 raw scorer spells anstention_rate; original CLI defaults missing abstention_rate to 0.',
            'Lexical overlap is not semantic correctness or legal accuracy.'])

if __name__=='__main__':
    payload=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=evaluate(payload)
    emit(result)
