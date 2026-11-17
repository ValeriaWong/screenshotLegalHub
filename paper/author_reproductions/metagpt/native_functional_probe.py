"""Functional checks on real generated Snake code. Zero supplier/model calls.
Expected behavior comes from the native task/PRD: movement, growth, collisions,
restart/quit and food outside the body. Original locale files stay unchanged;
this harness makes an exact Unicode-equivalent UTF8 working copy.
"""
import argparse,hashlib,json,random,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
DIRECTORY=ROOT/'paper/author_reproductions/results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native'
parser=argparse.ArgumentParser();parser.add_argument('--project');parser.add_argument('--output');args=parser.parse_args()
if args.project:
    source=Path(args.project).resolve();source.relative_to(ROOT);working=source.parent
else:
    result=json.loads((DIRECTORY/'e22_metagpt.output.json').read_text(encoding='utf-8'))
    working=DIRECTORY/'.runtime/utf8_project'
    for name,content in result['output']['files'].items():
        target=working/name
        if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content.encode('utf-8'))
    source=working/'snake_game/snake_game'
sys.path.insert(0,str(source))
from snake import Snake,Direction,Position
from food import Food
from game import Game,GameState
checks={}
def check(name,operation):
    try:operation();checks[name]=dict(passed=True)
    except Exception as error:checks[name]=dict(passed=False,error=type(error).__name__+': '+str(error),traceback=traceback.format_exc())
def snake_movement():
    s=Snake(Position(4,4),3,Direction.RIGHT)
    assert s.move(False)==Position(4,5) and s.length()==3
    s.set_direction(Direction.LEFT);assert s.direction()==Direction.RIGHT
    assert s.move(True)==Position(4,6) and s.length()==4
def game_eating():
    g=Game(20,40,rng=random.Random(0));g._food=Food(Position(10,21))
    assert g.tick()==GameState.RUNNING and g.score()==1 and g.snake().length()==4
    assert not g.snake().occupies(g.food().position())
def wall_and_restart():
    g=Game(20,40,rng=random.Random(0));g._snake=Snake(Position(0,0),1,Direction.UP)
    assert g.tick()==GameState.GAME_OVER
    g.reset();assert g.state()==GameState.RUNNING and g.score()==0 and g.snake().length()==3
    g.quit();assert g.tick()==GameState.QUIT
def food_exclusion():
    f=Food(Position(0,0));free=Position(1,1)
    occupied={Position(0,0),Position(0,1),Position(1,0)}
    f.respawn(occupied,2,2,random.Random(0));assert f.position()==free
for name,operation in [('movement_growth_reverse',snake_movement),('eat_score_respawn',game_eating),('wall_restart_quit',wall_and_restart),('food_exclusion',food_exclusion)]:check(name,operation)
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')}
record=dict(checks=checks,all_passed=all(c['passed'] for c in checks.values()),new_supplier_requests=0,
    local_model_inference=False,interactive_terminal_tested=False,working_copy=str(working.relative_to(ROOT)),source_hashes=hashes)
name='e22_metagpt.native_functional_after_feedback.json' if (DIRECTORY/'e22_metagpt.native_functional_before_feedback.json').exists() else 'e22_metagpt.native_functional_before_feedback.json'
if (DIRECTORY/name).exists():
    index=2
    while (DIRECTORY/(name.removesuffix('.json')+'_attempt'+str(index)+'.json')).exists():index+=1
    name=name.removesuffix('.json')+'_attempt'+str(index)+'.json'
destination=Path(args.output).resolve() if args.output else DIRECTORY/name
if args.output and destination.exists():raise ValueError('Existing independent probe evidence is preserved')
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=str(destination.relative_to(ROOT)),**record)))
