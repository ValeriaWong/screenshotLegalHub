"""Export corrected native project separately; verify its AST matches tested working code."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
run=ROOT/'paper/author_reproductions/results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native'
feedback=run.parent/'cf51096b1f9b1a17__native_feedback'
original=json.loads((run/'e22_metagpt.output.json').read_text(encoding='utf-8'))
review=json.loads((feedback/'e22_metagpt.output.json').read_text(encoding='utf-8'))
probe=max(run.glob('e22_metagpt.native_functional_after_feedback*.json'),key=lambda p:p.stat().st_mtime_ns)
checks=json.loads(probe.read_text(encoding='utf-8'))
assert checks['all_passed'] and review['harness_triggered_feedback']
files=dict(original['output']['files']);files['snake_game/snake_game/snake.py']=review['output']
ast_equal={}
for name,text in files.items():
    if name.endswith('.py'):
        tested=(run/'.runtime/utf8_project'/name).read_text(encoding='utf-8')
        ast_equal[name]=ast.dump(ast.parse(tested),include_attributes=False)==ast.dump(ast.parse(text),include_attributes=False)
        assert ast_equal[name]
    destination=run/'native_project_after_author_review'/name
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists() and destination.read_bytes()!=text.encode('utf-8'):raise ValueError('Existing export changed; preserve it')
    destination.write_bytes(text.encode('utf-8'))
result=dict(input_idea='Write a cli snake game',files=files,ast_equal_to_tested=ast_equal,functional_checks=checks,
    original_native_requests=18,extra_author_code_review_requests=1,manual_feedback_selection=True,
    original_autonomous_qa_pipeline_completed=False,interactive_terminal_tested=False,
    original_native_output='e22_metagpt.output.json',native_feedback_directory=str(feedback.relative_to(ROOT)),
    first_generated_result_preserved=True,local_model_inference=False,original_complete_benchmark=False)
(run/'e22_metagpt.native_followup_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(exported_files=len(files),python_ast_matches=len(ast_equal),supplier_requests=0,autonomous_qa_completed=False)))
