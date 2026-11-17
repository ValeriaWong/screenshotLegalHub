"""B01 official key_answer/key_middle source branches; no BERTScore/model calls.
From CSHaitao/LegalAgentBench src/evaluation/eval.py at pinned sources.lock commit.
Input: filtered answer, summarized trajectory, official keys (evaluation side only).
Output: original substring success/progress rates; not semantic legal accuracy.
"""
import ast,contextlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'paper/author_reproductions'))
from author_runtime import source

def score(answer,summary,reference):
    folder,pin=source('legalagentbench');path=folder/'src/evaluation/eval.py'
    tree=ast.parse(path.read_text(encoding='utf-8-sig'));result={}
    for mode in ['key_answer','key_middle']:
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='mode' and any(isinstance(v,ast.Constant) and v.value==mode for v in n.test.comparators))
        env=dict(json=json,ground_truth=[reference],test_datas=[json.dumps(dict(res=answer,summary=summary))],start=0,end=1,average_score=0)
        with contextlib.redirect_stdout(io.StringIO()) as display:exec(compile(ast.Module(body=node.body,type_ignores=[]),str(path),'exec'),env)
        result[mode]=dict(score=env['average_score'],original_display=display.getvalue().strip(),source_line=node.lineno)
    return dict(metrics=result,source_commit=pin['commit'],method='original substring-scoring branches, unchanged AST bodies',local_model_inference=False)
